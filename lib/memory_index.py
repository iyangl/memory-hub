"""memory.index — Register a knowledge file in topics.md index.

Usage: memory-hub index <bucket> <file> --topic <name> --summary <desc>
       [--anchor <anchor>]

The target file must already exist in .memory/docs/<bucket>/<file>.
This command only updates the topics.md knowledge index.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from lib import envelope, paths
from lib.brief import _extract_best_section
from lib.utils import atomic_write

TOPICS_KNOWLEDGE_HEADER = "## 知识文件"


def _normalize_summary_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().lstrip("- ").strip()


def _normalize_summary_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_h1_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return _normalize_summary_line(stripped[2:])
    return ""


def _extract_h2_sections(content: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    for line in content.splitlines():
        if line.startswith("## "):
            if current:
                sections.append("\n".join(current).rstrip())
            current = [line.rstrip()]
            continue
        if current:
            current.append(line.rstrip())
    if current:
        sections.append("\n".join(current).rstrip())
    return sections


def summarize_markdown(bucket: str, content: str, fallback: str = "") -> str:
    best = _extract_best_section(content, bucket, max_lines=2).strip()
    lines = [_normalize_summary_line(line) for line in best.splitlines() if line.strip()]
    if not lines:
        return fallback or ""

    heading = ""
    body: list[str] = []
    if lines[0].startswith("## "):
        heading = lines[0][3:].strip()
        body = lines[1:]
    else:
        body = lines[:]

    if heading and body:
        lead = body[0]
        return f"{heading}：{lead}"
    if heading:
        return heading
    return body[0]


def summary_candidates_markdown(bucket: str, content: str, fallback: str = "") -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        normalized = _normalize_summary_text(value)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(summarize_markdown(bucket, content, fallback))

    title = _extract_h1_title(content)
    if title:
        add(title)

    for section in _extract_h2_sections(content):
        section_summary = summarize_markdown(bucket, section, fallback)
        add(section_summary)
        if title and section_summary:
            normalized_title = _normalize_summary_text(title)
            normalized_section = _normalize_summary_text(section_summary)
            if normalized_section != normalized_title and not normalized_section.startswith(f"{normalized_title}："):
                add(f"{title}：{section_summary}")

    return candidates


def summarize_doc(bucket: str, filename: str, project_root: Path | None = None) -> str:
    content = paths.file_path(bucket, filename, project_root).read_text(encoding="utf-8")
    return summarize_markdown(bucket, content, fallback=filename) or filename


def summary_candidates_doc(bucket: str, filename: str, project_root: Path | None = None) -> list[str]:
    content = paths.file_path(bucket, filename, project_root).read_text(encoding="utf-8")
    return summary_candidates_markdown(bucket, content, fallback=filename)


def refresh_doc_summary(bucket: str, filename: str, project_root: Path | None = None, summary: str | None = None) -> bool:
    topics_file = paths.topics_path(project_root)
    if not topics_file.exists():
        return False

    file_ref = paths.docs_file_ref(bucket, filename)
    content = topics_file.read_text(encoding="utf-8")
    entries = content.splitlines()
    prefix = f"- {file_ref}"
    topic: str | None = None
    anchor: str | None = None

    for line in entries:
        stripped = line.strip()
        if stripped.startswith("### "):
            topic = stripped[4:].strip()
            continue
        if not stripped.startswith(prefix):
            continue
        match = re.match(r"^-\s+\S+?(?:\s+#(\S+))?\s+—\s+.+$", stripped)
        if match:
            anchor = match.group(1)
        break
    else:
        return False

    if not topic:
        return False

    register_doc(
        bucket,
        filename,
        topic,
        summary or summarize_doc(bucket, filename, project_root),
        anchor,
        project_root,
    )
    return True


def register_doc(bucket: str, filename: str, topic: str, summary: str,
                 anchor: str | None = None, project_root: Path | None = None) -> None:
    err = paths.validate_bucket(bucket)
    if err:
        raise ValueError(f"Invalid bucket: {bucket}")

    fp = paths.file_path(bucket, filename, project_root)
    if not fp.exists():
        raise FileNotFoundError(
            f"Target file does not exist: docs/{bucket}/{filename}. Write the file first, then call index."
        )

    topics_file = paths.topics_path(project_root)
    _update_topics_knowledge(topics_file, topic, summary, bucket, filename, anchor)


def _update_topics_knowledge(topics_file: Path, topic: str, summary: str,
                             bucket: str, filename: str, anchor: str | None) -> None:
    """Update the knowledge file section of topics.md."""
    file_ref = paths.docs_file_ref(bucket, filename)
    if anchor:
        file_ref += f" #{anchor}"
    entry_line = f"- {file_ref} — {summary}"

    if not topics_file.exists():
        return

    content = topics_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Find knowledge section boundaries
    knowledge_start = None
    knowledge_end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == TOPICS_KNOWLEDGE_HEADER:
            knowledge_start = i
        elif knowledge_start is not None and line.startswith("## ") and i > knowledge_start:
            knowledge_end = i
            break

    if knowledge_start is None:
        lines.append("")
        lines.append(TOPICS_KNOWLEDGE_HEADER)
        knowledge_start = len(lines) - 1
        knowledge_end = len(lines)

    # Find or create topic subsection within knowledge section
    topic_header = f"### {topic}"
    topic_start = None
    topic_end = knowledge_end

    for i in range(knowledge_start + 1, knowledge_end):
        if lines[i].strip() == topic_header:
            topic_start = i
        elif topic_start is not None and lines[i].startswith("### "):
            topic_end = i
            break

    if topic_start is not None:
        file_prefix = f"- {paths.docs_file_ref(bucket, filename)}"
        replaced = False
        for i in range(topic_start + 1, topic_end):
            if lines[i].startswith(file_prefix):
                lines[i] = entry_line
                replaced = True
                break
        if not replaced:
            lines.insert(topic_end, entry_line)
    else:
        insert_lines = [topic_header, entry_line]
        for idx, new_line in enumerate(insert_lines):
            lines.insert(knowledge_end + idx, new_line)

    atomic_write(topics_file, "\n".join(lines) + "\n")


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub index")
    parser.add_argument("bucket", help="Bucket name (pm/architect/dev/qa)")
    parser.add_argument("file", help="Filename within the bucket")
    parser.add_argument("--topic", required=True, help="Topic name for topics.md index")
    parser.add_argument("--summary", required=True, help="One-line description for topics.md")
    parser.add_argument("--anchor", help="Anchor tag for topics.md reference")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None

    err = paths.validate_bucket(parsed.bucket)
    if err:
        envelope.fail("INVALID_BUCKET", f"Invalid bucket: {parsed.bucket}. Valid: {', '.join(paths.BUCKETS)}")

    try:
        register_doc(parsed.bucket, parsed.file, parsed.topic, parsed.summary, parsed.anchor, project_root)
    except FileNotFoundError:
        envelope.fail(
            "FILE_NOT_FOUND",
            f"Target file does not exist: docs/{parsed.bucket}/{parsed.file}. Write the file first, then call index.",
        )

    envelope.ok({
        "bucket": parsed.bucket,
        "file": parsed.file,
        "topic": parsed.topic,
    })
