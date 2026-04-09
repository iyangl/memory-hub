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
from lib.utils import (
    COMMON_FACET_KEYWORDS,
    COMMON_FACET_ORDER_BY_BUCKET,
    COMMON_GENERIC_SECTION_HEADINGS,
    atomic_write,
)

TOPICS_KNOWLEDGE_HEADER = "## 知识文件"
FACET_KEYWORDS = COMMON_FACET_KEYWORDS
FACET_ORDER_BY_BUCKET = COMMON_FACET_ORDER_BY_BUCKET
GENERIC_SECTION_HEADINGS = COMMON_GENERIC_SECTION_HEADINGS


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



def _parse_h2_sections(content: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_body
        if current_heading is None:
            return
        sections.append((current_heading, current_body))
        current_heading = None
        current_body = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            flush()
            current_heading = _normalize_summary_line(stripped[3:])
            continue
        if current_heading is None or not stripped:
            continue
        current_body.append(_normalize_summary_line(stripped))

    flush()
    return sections



def _summarize_lines(lines: list[str]) -> str:
    normalized = [_normalize_summary_line(line) for line in lines if line.strip()]
    if not normalized:
        return ""

    heading = ""
    body: list[str] = []
    if normalized[0].startswith("## "):
        heading = normalized[0][3:].strip()
        body = normalized[1:]
    else:
        body = normalized[:]

    if heading and body:
        return f"{heading}：{body[0]}"
    if heading:
        return heading
    return body[0]



def _legacy_summary(bucket: str, content: str, fallback: str = "") -> str:
    best = _extract_best_section(content, bucket, max_lines=2).strip()
    if not best:
        return fallback or ""
    return _summarize_lines(best.splitlines()) or (fallback or "")



def _facet_order(bucket: str) -> tuple[str, ...]:
    return FACET_ORDER_BY_BUCKET.get(bucket, ("decision", "constraint", "risk", "verification"))



def _facet_rank(bucket: str, facet: str) -> int:
    order = _facet_order(bucket)
    try:
        return order.index(facet)
    except ValueError:
        return len(order)



def _keyword_score(text: str, keywords: tuple[str, ...], *, base: int) -> int:
    score = 0
    for idx, keyword in enumerate(keywords):
        if keyword in text:
            score += base - idx * 5
    return score



def _heading_matches_facet(heading: str, facet: str) -> bool:
    return _keyword_score(heading, FACET_KEYWORDS.get(facet, ()), base=100) > 0



def _detect_facet(bucket: str, heading: str, body: list[str]) -> tuple[str | None, int]:
    body_text = " ".join(body[:2])
    scores: dict[str, int] = {}
    for facet, keywords in FACET_KEYWORDS.items():
        score = _keyword_score(heading, keywords, base=100)
        score += _keyword_score(body_text, keywords, base=20)
        scores[facet] = score

    facet, score = max(scores.items(), key=lambda item: (item[1], -_facet_rank(bucket, item[0])))
    if score <= 0:
        return None, 0
    return facet, score



def _is_generic_heading(heading: str, facet: str) -> bool:
    normalized = re.sub(r"[\s:：\-_/()（）]", "", heading)
    if heading in GENERIC_SECTION_HEADINGS:
        return True
    if len(normalized) > 4:
        return False
    return any(keyword in normalized for keyword in FACET_KEYWORDS.get(facet, ()))



def _section_summary(heading: str, body: list[str]) -> str:
    if heading and body:
        return f"{heading}：{body[0]}"
    if heading:
        return heading
    return body[0] if body else ""



def _section_candidates(bucket: str, content: str) -> list[dict]:
    candidates: list[dict] = []
    for index, (heading, body) in enumerate(_parse_h2_sections(content)):
        facet, facet_score = _detect_facet(bucket, heading, body)
        if not facet:
            continue
        summary = _section_summary(heading, body)
        if not summary:
            continue
        candidates.append({
            "summary": summary,
            "compatibility_summary": body[0] if body and _is_generic_heading(heading, facet) else summary,
            "facet": facet,
            "facet_score": facet_score,
            "is_generic_heading": _is_generic_heading(heading, facet),
            "specificity": len(heading),
            "body_size": len(body),
            "index": index,
        })
    return candidates



def _sorted_candidates(bucket: str, candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda item: (
            _facet_rank(bucket, item["facet"]),
            item.get("is_generic_heading", False),
            -item["facet_score"],
            -item["specificity"],
            -item["body_size"],
            item["index"],
        ),
    )



def _select_primary_summary(bucket: str, content: str, fallback: str = "") -> tuple[str, str | None]:
    candidates = _sorted_candidates(bucket, _section_candidates(bucket, content))
    if candidates:
        primary = candidates[0]
        return primary["summary"], primary["facet"]
    return _legacy_summary(bucket, content, fallback), None



def _select_secondary_summary(bucket: str, content: str, primary_summary: str, primary_facet: str | None) -> str:
    primary_normalized = _normalize_summary_text(primary_summary)
    for candidate in _sorted_candidates(bucket, _section_candidates(bucket, content)):
        summary = candidate["summary"]
        compatibility_summary = candidate.get("compatibility_summary", summary)
        normalized = _normalize_summary_text(summary)
        compatibility_normalized = _normalize_summary_text(compatibility_summary)
        if not normalized or normalized == primary_normalized:
            continue
        if primary_facet and candidate["facet"] == primary_facet:
            continue
        if normalized in primary_normalized or primary_normalized in normalized:
            continue
        if compatibility_normalized and (compatibility_normalized in primary_normalized or primary_normalized in compatibility_normalized):
            continue
        return summary
    return ""



def summarize_markdown(bucket: str, content: str, fallback: str = "") -> str:
    primary_summary, primary_facet = _select_primary_summary(bucket, content, fallback)
    if not primary_summary:
        return fallback or ""

    secondary_summary = _select_secondary_summary(bucket, content, primary_summary, primary_facet)
    if not secondary_summary:
        return primary_summary
    return f"{primary_summary}；{secondary_summary}"



def summary_candidates_markdown(bucket: str, content: str, fallback: str = "") -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        normalized = _normalize_summary_text(value)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    canonical_summary = summarize_markdown(bucket, content, fallback)
    legacy_summary = _legacy_summary(bucket, content, fallback)
    add(canonical_summary)
    add(legacy_summary)

    title = _extract_h1_title(content)
    primary_summary, primary_facet = _select_primary_summary(bucket, content, fallback)
    if title and canonical_summary and canonical_summary != title and not canonical_summary.startswith(f"{title}："):
        add(f"{title}：{canonical_summary}")
    elif title and primary_summary and primary_facet and not _heading_matches_facet(title, primary_facet):
        add(f"{title}：{primary_summary}")
    if title and legacy_summary and legacy_summary != title and not legacy_summary.startswith(f"{title}："):
        add(f"{title}：{legacy_summary}")

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
