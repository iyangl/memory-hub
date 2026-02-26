"""memory.index — Register a knowledge file in topics.md index.

Usage: memory-hub index <bucket> <file> --topic <name> --summary <desc>
       [--anchor <anchor>]

The target file must already exist in .memory/<bucket>/<file>.
This command only updates the topics.md knowledge index.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope, paths
from lib.utils import atomic_write

TOPICS_KNOWLEDGE_HEADER = "## 知识文件"


def _update_topics_knowledge(topics_file: Path, topic: str, summary: str,
                             bucket: str, filename: str, anchor: str | None) -> None:
    """Update the knowledge file section of topics.md."""
    file_ref = f"{bucket}/{filename}"
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
        file_prefix = f"- {bucket}/{filename}"
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

    # Verify target file exists
    fp = paths.file_path(parsed.bucket, parsed.file, project_root)
    if not fp.exists():
        envelope.fail("FILE_NOT_FOUND", f"Target file does not exist: {parsed.bucket}/{parsed.file}. Write the file first, then call index.")

    # Update topics.md knowledge index
    topics_file = paths.topics_path(project_root)
    _update_topics_knowledge(topics_file, parsed.topic, parsed.summary,
                             parsed.bucket, parsed.file, parsed.anchor)

    envelope.ok({
        "bucket": parsed.bucket,
        "file": parsed.file,
        "topic": parsed.topic,
    })
