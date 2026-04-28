"""catalog.update — deprecated legacy command.

Usage: memory-hub catalog-update --file <path> [--project-root <path>]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib import envelope, paths
from lib.scan_modules import MODULE_CARD_GENERATOR_VERSION
from lib.utils import atomic_write, fail_legacy_command, find_module_name_collisions, sanitize_module_name

TOPICS_CODE_HEADER = "## 代码模块"
TOPICS_KNOWLEDGE_HEADER = "## 知识文件"


def _append_list_section(lines: list[str], heading: str, items: list[str]) -> None:
    if not items:
        return
    lines += ["", heading]
    for item in items:
        lines.append(f"- {item}")


def _append_files_section(lines: list[str], files: list[dict]) -> None:
    if not files:
        return
    lines += ["", "## 代表文件"]
    for f in files:
        desc = f.get("description", "")
        path = f.get("path", "")
        lines.append(f"- `{path}` — {desc}" if desc else f"- `{path}`")


def _generate_module_md(module: dict) -> str:
    lines = [f"# {module['name']}"]

    summary = module.get("summary", "")
    if summary:
        lines += ["", f"> {summary}"]

    read_when = module.get("read_when", "")
    if read_when:
        lines += ["", "## 何时阅读", "", read_when]

    entry_points = module.get("entry_points", [])
    _append_list_section(lines, "## 推荐入口", [f"`{item}`" for item in entry_points])

    read_order = module.get("read_order", [])
    _append_list_section(lines, "## 推荐阅读顺序", [f"`{item}`" for item in read_order])

    implicit_constraints = module.get("implicit_constraints", [])
    _append_list_section(lines, "## 隐含约束", implicit_constraints)

    known_risks = module.get("known_risks", [])
    _append_list_section(lines, "## 主要风险", known_risks)

    verification_focus = module.get("verification_focus", [])
    _append_list_section(lines, "## 验证重点", verification_focus)

    dir_tree = module.get("dir_tree", "")
    if dir_tree:
        lines += ["", "## 目录结构", "", "```", dir_tree, "```"]

    _append_files_section(lines, module.get("files", []))

    related_memory = module.get("related_memory", [])
    _append_list_section(lines, "## 关联记忆", [f"`{item}`" for item in related_memory])

    structure_hash = module.get("structure_hash", "")
    lines.append(f"\n<!-- generator_version: {MODULE_CARD_GENERATOR_VERSION} -->")
    if structure_hash:
        lines.append(f"<!-- structure_hash: {structure_hash} -->")

    lines.append("")
    return "\n".join(lines)


def _update_topics_code_section(topics_file: Path, modules: list[dict]) -> None:
    if not topics_file.exists():
        return

    content = topics_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    code_start = None
    code_end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == TOPICS_CODE_HEADER:
            code_start = i
        elif code_start is not None and line.startswith("## ") and i > code_start:
            code_end = i
            break

    new_code_lines = [TOPICS_CODE_HEADER]
    for m in modules:
        read_when = m.get("read_when", "")
        entry_points = m.get("entry_points", [])
        parts = [m["name"]]
        if read_when:
            parts.append(read_when)
        if entry_points:
            parts.append("入口: " + ", ".join(f"`{item}`" for item in entry_points[:2]))
        new_code_lines.append("- " + "；".join(parts))

    if code_start is not None:
        lines[code_start:code_end] = new_code_lines
    else:
        knowledge_idx = None
        for i, line in enumerate(lines):
            if line.strip() == TOPICS_KNOWLEDGE_HEADER:
                knowledge_idx = i
                break
        if knowledge_idx is not None:
            lines[knowledge_idx:knowledge_idx] = new_code_lines + [""]
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(new_code_lines)

    atomic_write(topics_file, "\n".join(lines) + "\n")


def _validate_module(m: dict) -> tuple[str | None, str | None]:
    name = m.get("name", "")
    if not name or not isinstance(name, str):
        return None, "missing or empty 'name'"

    files = m.get("files")
    if files is not None and not isinstance(files, list):
        return None, f"'files' must be a list, got {type(files).__name__}"

    return sanitize_module_name(name), None


def run(args: list[str]) -> None:
    fail_legacy_command(
        "catalog-update",
        [
            "memory-hub search <query>",
            "memory-hub read <bucket> <file>",
        ],
        reason="Catalog/module-card update is legacy compatibility and no longer part of explicit-memory default workflow.",
    )
