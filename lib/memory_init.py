"""memory.init — Initialize .memory/ directory structure.

Usage: memory-hub init [--project-root <path>]
Creates the directory skeleton with empty template files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib import envelope, paths
from lib.utils import atomic_write

TOPICS_SKELETON = """\
# Memory Hub — Topics Index

## 代码模块

## 知识文件
"""

MANIFEST = {
    "layout_version": "4",
    "docs_root": "docs",
    "catalog_root": "catalog",
    "inbox_root": "inbox",
    "session_root": "session",
    "brief_file": "BRIEF.md",
    "project_scope": "project",
}


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub init")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    root = paths.memory_root(project_root)

    if root.exists():
        envelope.fail("ALREADY_INITIALIZED", f".memory/ already exists at {root}")

    created_files = []
    for bucket, files in paths.BASE_FILES.items():
        bucket_dir = paths.bucket_path(bucket, project_root)
        bucket_dir.mkdir(parents=True, exist_ok=True)
        for filename in files:
            fp = bucket_dir / filename
            fp.write_text("", encoding="utf-8")
            created_files.append(f"docs/{bucket}/{filename}")

    catalog_dir = paths.catalog_path(project_root)
    catalog_dir.mkdir(parents=True, exist_ok=True)
    paths.modules_path(project_root).mkdir(parents=True, exist_ok=True)

    topics_file = paths.topics_path(project_root)
    atomic_write(topics_file, TOPICS_SKELETON)
    created_files.append("catalog/topics.md")

    paths.inbox_root(project_root).mkdir(parents=True, exist_ok=True)
    paths.session_root(project_root).mkdir(parents=True, exist_ok=True)

    manifest_file = paths.manifest_path(project_root)
    atomic_write(manifest_file, json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n")
    created_files.append("manifest.json")

    from lib.catalog_repair import repair
    repair_result = repair(project_root)

    from lib.brief import generate_brief
    generate_brief(project_root)
    created_files.append("BRIEF.md")

    envelope.ok(
        {
            "created_files": created_files,
            "repair_result": repair_result,
        },
        ai_actions=repair_result.get("ai_actions", []),
        manual_actions=repair_result.get("manual_actions", []),
    )
