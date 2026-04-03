"""inbox-clean — Remove files from .memory/inbox/.

Usage: memory-hub inbox-clean [--before <ISO>] [--project-root <path>]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from lib import envelope, paths


def clean_inbox(
    project_root: Path | None = None,
    before_iso: str | None = None,
) -> dict:
    """Delete .md files from inbox. Optionally only those modified before *before_iso*."""
    inbox = paths.inbox_root(project_root)
    if not inbox.is_dir():
        return {"removed": [], "kept": []}

    cutoff: datetime | None = None
    if before_iso is not None:
        cutoff = datetime.fromisoformat(before_iso)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)

    removed: list[str] = []
    kept: list[str] = []

    for f in sorted(inbox.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        if cutoff is not None:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime >= cutoff:
                kept.append(f.name)
                continue
        f.unlink()
        removed.append(f.name)

    return {"removed": removed, "kept": kept}


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub inbox-clean")
    parser.add_argument("--before", help="ISO timestamp cutoff (remove files modified before this)", default=None)
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    try:
        result = clean_inbox(project_root, before_iso=parsed.before)
    except ValueError:
        envelope.fail("INVALID_TIMESTAMP", f"Cannot parse ISO timestamp: {parsed.before}")
    envelope.ok(result)
