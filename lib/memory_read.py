"""memory.read — Read a file from a knowledge bucket.

Usage: memory-hub read <bucket> <file> [--anchor <anchor>]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from lib import envelope, paths


def find_anchor(content: str, anchor: str) -> bool:
    """Check if a markdown heading matching the anchor exists."""
    # Anchor matches if any heading text, when slugified, equals the anchor
    # or if the raw heading text equals the anchor
    for line in content.splitlines():
        m = re.match(r"^#{1,6}\s+(.+)$", line)
        if m:
            heading = m.group(1).strip()
            if heading == anchor or _slugify(heading) == anchor:
                return True
    return False


def _slugify(text: str) -> str:
    """Simple slugify for heading anchors."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    return text


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub read")
    parser.add_argument("bucket", help="Bucket name (pm/architect/dev/qa)")
    parser.add_argument("file", help="Filename within the bucket")
    parser.add_argument("--anchor", help="Check if this anchor exists in the file")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None

    err = paths.validate_bucket(parsed.bucket)
    if err:
        envelope.fail("INVALID_BUCKET", f"Invalid bucket: {parsed.bucket}. Valid: {', '.join(paths.BUCKETS)}")

    fp = paths.file_path(parsed.bucket, parsed.file, project_root)
    if not fp.exists():
        envelope.fail("FILE_NOT_FOUND", f"File not found: {parsed.bucket}/{parsed.file}")

    content = fp.read_text(encoding="utf-8")

    data: dict = {"bucket": parsed.bucket, "file": parsed.file, "content": content}

    if parsed.anchor:
        anchor_valid = find_anchor(content, parsed.anchor)
        data["anchor"] = parsed.anchor
        data["anchor_valid"] = anchor_valid

        if not anchor_valid:
            # Trigger catalog.repair for invalid anchor
            from lib.catalog_repair import repair
            repair_result = repair(project_root)
            data["repair_triggered"] = True
            data["repair_result"] = repair_result
            envelope.ok(data,
                        ai_actions=repair_result.get("ai_actions", []),
                        manual_actions=repair_result.get("manual_actions", []))
            return  # envelope.ok calls sys.exit, but for clarity

    envelope.ok(data)
