"""memory.list — List files in a knowledge bucket.

Usage: memory-hub list <bucket>
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope, paths


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub list")
    parser.add_argument("bucket", help="Bucket name (pm/architect/dev/qa)")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None

    err = paths.validate_bucket(parsed.bucket)
    if err:
        envelope.fail("INVALID_BUCKET", f"Invalid bucket: {parsed.bucket}. Valid: {', '.join(paths.BUCKETS)}")

    bp = paths.bucket_path(parsed.bucket, project_root)
    if not bp.exists():
        envelope.fail("BUCKET_NOT_FOUND", f"Bucket directory not found: {parsed.bucket}")

    files = sorted(f.name for f in bp.iterdir() if f.suffix == ".md")
    envelope.ok({"bucket": parsed.bucket, "files": files})
