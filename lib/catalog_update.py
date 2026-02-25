"""catalog.update — Update code module index from AI-generated JSON.

Usage: memory-hub catalog-update [--project-root <path>]
Reads JSON from stdin with schema: {"modules": [{"name", "summary", "files": [{"path", "description"}]}]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib import envelope, paths
from lib.memory_write import _atomic_write

TOPICS_CODE_HEADER = "## 代码模块"
TOPICS_KNOWLEDGE_HEADER = "## 知识文件"


def _generate_module_md(module: dict) -> str:
    """Generate markdown content for a module index file."""
    lines = [f"# {module['name']}", "", f"> {module['summary']}", ""]
    for f in module.get("files", []):
        lines.append(f"- {f['path']} — {f['description']}")
    lines.append("")
    return "\n".join(lines)


def _update_topics_code_section(topics_file: Path, modules: list[dict]) -> None:
    """Replace the code modules section in topics.md."""
    if not topics_file.exists():
        return

    content = topics_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Find code modules section boundaries
    code_start = None
    code_end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == TOPICS_CODE_HEADER:
            code_start = i
        elif code_start is not None and line.startswith("## ") and i > code_start:
            code_end = i
            break

    # Build new code section lines
    new_code_lines = [TOPICS_CODE_HEADER]
    for m in modules:
        new_code_lines.append(f"- {m['name']} — {m['summary']}")

    if code_start is not None:
        # Replace existing section
        lines[code_start:code_end] = new_code_lines
    else:
        # Insert at the beginning (before knowledge section if it exists)
        knowledge_idx = None
        for i, line in enumerate(lines):
            if line.strip() == TOPICS_KNOWLEDGE_HEADER:
                knowledge_idx = i
                break
        if knowledge_idx is not None:
            lines[knowledge_idx:knowledge_idx] = new_code_lines + [""]
        else:
            # Append after any existing content
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(new_code_lines)

    _atomic_write(topics_file, "\n".join(lines) + "\n")


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub catalog-update")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None

    # Read JSON from stdin
    if sys.stdin.isatty():
        envelope.fail("NO_INPUT", "Module index JSON must be provided via stdin.")
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        envelope.fail("INVALID_JSON", f"Failed to parse stdin JSON: {e}")

    modules = data.get("modules", [])
    if not isinstance(modules, list):
        envelope.fail("INVALID_SCHEMA", "'modules' must be an array.")

    modules_dir = paths.modules_path(project_root)
    modules_dir.mkdir(parents=True, exist_ok=True)

    # Track which module files we create
    new_module_names = set()

    for m in modules:
        name = m.get("name", "")
        if not name:
            continue
        new_module_names.add(name)
        md_content = _generate_module_md(m)
        _atomic_write(modules_dir / f"{name}.md", md_content)

    # Delete old module files not in new list
    deleted = []
    for existing in modules_dir.iterdir():
        if existing.suffix == ".md" and existing.stem not in new_module_names:
            deleted.append(existing.name)
            existing.unlink()

    # Update topics.md code modules section
    topics_file = paths.topics_path(project_root)
    _update_topics_code_section(topics_file, modules)

    # Auto-trigger catalog.repair
    from lib.catalog_repair import repair
    repair_result = repair(project_root)

    envelope.ok(
        {
            "modules_written": sorted(new_module_names),
            "modules_deleted": deleted,
            "repair_result": repair_result,
        },
        ai_actions=repair_result.get("ai_actions", []),
        manual_actions=repair_result.get("manual_actions", []),
    )
