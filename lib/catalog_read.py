"""catalog.read — Read catalog index files.

Usage: memory-hub catalog-read [topics|<module>]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope, paths


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub catalog-read")
    parser.add_argument("target", nargs="?", default="topics",
                        help="'topics' or a module name")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None

    if parsed.target == "topics":
        fp = paths.topics_path(project_root)
    else:
        fp = paths.module_file_path(parsed.target, project_root)

    if not fp.exists():
        envelope.fail("CATALOG_NOT_FOUND", f"Catalog file not found: {fp.name}")

    content = fp.read_text(encoding="utf-8")
    envelope.ok({"target": parsed.target, "content": content})
