"""memory.init — Initialize .memory/ directory structure.

Usage: memory-hub init [--project-root <path>]
Creates the directory skeleton with empty template files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope, paths
from lib.memory_write import _atomic_write

TOPICS_SKELETON = """\
# Memory Hub — Topics Index

## 代码模块

## 知识文件
"""


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub init")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    root = paths.memory_root(project_root)

    if root.exists():
        envelope.fail("ALREADY_INITIALIZED", f".memory/ already exists at {root}")

    # Create bucket directories and base files
    created_files = []
    for bucket, files in paths.BASE_FILES.items():
        bucket_dir = root / bucket
        bucket_dir.mkdir(parents=True, exist_ok=True)
        for filename in files:
            fp = bucket_dir / filename
            fp.write_text("", encoding="utf-8")
            created_files.append(f"{bucket}/{filename}")

    # Create catalog structure
    catalog_dir = paths.catalog_path(project_root)
    catalog_dir.mkdir(parents=True, exist_ok=True)

    modules_dir = paths.modules_path(project_root)
    modules_dir.mkdir(parents=True, exist_ok=True)

    topics_file = paths.topics_path(project_root)
    _atomic_write(topics_file, TOPICS_SKELETON)
    created_files.append("catalog/topics.md")

    # Auto-trigger catalog.repair
    from lib.catalog_repair import repair
    repair_result = repair(project_root)

    envelope.ok(
        {
            "created_files": created_files,
            "repair_result": repair_result,
        },
        ai_actions=repair_result.get("ai_actions", []),
        manual_actions=repair_result.get("manual_actions", []),
    )
