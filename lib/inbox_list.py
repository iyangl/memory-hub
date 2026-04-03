"""inbox-list — List files in .memory/inbox/.

Usage: memory-hub inbox-list [--project-root <path>]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from lib import envelope, paths


def list_inbox(project_root: Path | None = None) -> list[dict]:
    """Return inbox .md files sorted by modification time (oldest first)."""
    inbox = paths.inbox_root(project_root)
    if not inbox.is_dir():
        return []

    items = []
    for f in inbox.iterdir():
        if f.is_file() and f.suffix == ".md":
            stat = f.stat()
            items.append({
                "name": f.name,
                "size_bytes": stat.st_size,
                "modified_iso": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc,
                ).isoformat(),
            })

    items.sort(key=lambda x: x["modified_iso"])
    return items


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub inbox-list")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    items = list_inbox(project_root)
    envelope.ok({"files": items, "count": len(items)})
