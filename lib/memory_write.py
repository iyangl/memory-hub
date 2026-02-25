"""memory.write — Write knowledge to a bucket file and update topics.md.

Usage: memory-hub write <bucket> <file> --topic <name> --summary <desc>
       [--anchor <anchor>] [--mode append|overwrite]
Content is read from stdin.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from lib import envelope, paths

TOPICS_KNOWLEDGE_HEADER = "## 知识文件"
TOPICS_CODE_HEADER = "## 代码模块"


def _atomic_write(filepath: Path, content: str) -> None:
    """Write content atomically: write to .tmp then rename."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    # On Windows, need to remove target first if it exists
    if filepath.exists():
        filepath.unlink()
    tmp_path.rename(filepath)


def _update_topics_knowledge(topics_file: Path, topic: str, summary: str,
                             bucket: str, filename: str, anchor: str | None) -> None:
    """Update the knowledge file section of topics.md."""
    # Build the entry line
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
        # Append knowledge section at end
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
        # Check if this exact file ref already exists, update it
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
        # Insert new topic subsection before knowledge_end
        insert_lines = [topic_header, entry_line]
        for idx, new_line in enumerate(insert_lines):
            lines.insert(knowledge_end + idx, new_line)

    _atomic_write(topics_file, "\n".join(lines) + "\n")


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub write")
    parser.add_argument("bucket", help="Bucket name (pm/architect/dev/qa)")
    parser.add_argument("file", help="Filename within the bucket")
    parser.add_argument("--topic", required=True, help="Topic name for topics.md index")
    parser.add_argument("--summary", required=True, help="One-line description for topics.md")
    parser.add_argument("--anchor", help="Anchor tag for topics.md reference")
    parser.add_argument("--mode", choices=["append", "overwrite"], default="append",
                        help="Write mode: append (default) or overwrite")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None

    err = paths.validate_bucket(parsed.bucket)
    if err:
        envelope.fail("INVALID_BUCKET", f"Invalid bucket: {parsed.bucket}. Valid: {', '.join(paths.BUCKETS)}")

    # Read content from stdin
    if sys.stdin.isatty():
        envelope.fail("NO_INPUT", "Content must be provided via stdin.")
    content = sys.stdin.read()
    if not content.strip():
        envelope.fail("EMPTY_CONTENT", "Stdin content is empty.")

    fp = paths.file_path(parsed.bucket, parsed.file, project_root)

    # Write knowledge file
    if parsed.mode == "overwrite":
        _atomic_write(fp, content)
    else:
        # append
        fp.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if fp.exists():
            existing = fp.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        _atomic_write(fp, existing + content)

    # Update topics.md knowledge index
    topics_file = paths.topics_path(project_root)
    _update_topics_knowledge(topics_file, parsed.topic, parsed.summary,
                             parsed.bucket, parsed.file, parsed.anchor)

    envelope.ok({
        "bucket": parsed.bucket,
        "file": parsed.file,
        "topic": parsed.topic,
        "mode": parsed.mode,
        "bytes_written": len(content.encode("utf-8")),
    })
