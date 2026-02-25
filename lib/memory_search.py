"""memory.search — Full-text search across knowledge buckets.

Usage: memory-hub search <query> [--context N]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from lib import envelope, paths


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub search")
    parser.add_argument("query", help="Search query (substring or regex)")
    parser.add_argument("--context", type=int, default=1, help="Lines of context around match")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    root = paths.memory_root(project_root)

    if not root.exists():
        envelope.fail("NOT_INITIALIZED", ".memory/ directory not found. Run memory-hub init first.")

    try:
        pattern = re.compile(parsed.query, re.IGNORECASE)
    except re.error:
        # Fall back to literal substring
        pattern = re.compile(re.escape(parsed.query), re.IGNORECASE)

    results = []
    for bucket in paths.BUCKETS:
        bp = root / bucket
        if not bp.exists():
            continue
        for md_file in sorted(bp.rglob("*.md")):
            rel = f"{bucket}/{md_file.name}"
            try:
                lines = md_file.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines):
                if pattern.search(line):
                    start = max(0, i - parsed.context)
                    end = min(len(lines), i + parsed.context + 1)
                    results.append({
                        "file": rel,
                        "line_number": i + 1,
                        "line_content": line,
                        "context": lines[start:end],
                    })

    envelope.ok({"query": parsed.query, "matches": results, "total": len(results)})
