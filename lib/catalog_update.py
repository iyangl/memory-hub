"""catalog.update — Update code module index from AI-generated JSON.

Usage: memory-hub catalog-update [--project-root <path>]
Reads JSON from stdin with schema: {"modules": [{"name", "summary", "files": [{"path", "description"}]}]}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib import envelope, paths
from lib.utils import atomic_write, sanitize_module_name

TOPICS_CODE_HEADER = "## 代码模块"
TOPICS_KNOWLEDGE_HEADER = "## 知识文件"


def _generate_module_md(module: dict) -> str:
    """Generate markdown content for a module index file."""
    summary = module.get("summary", "")
    lines = [f"# {module['name']}"]
    if summary:
        lines += ["", f"> {summary}"]
    lines.append("")
    for f in module.get("files", []):
        desc = f.get("description", "")
        path = f.get("path", "")
        lines.append(f"- {path} — {desc}" if desc else f"- {path}")
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
        summary = m.get("summary", "")
        new_code_lines.append(f"- {m['name']} — {summary}" if summary else f"- {m['name']}")

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

    atomic_write(topics_file, "\n".join(lines) + "\n")


def _validate_module(m: dict) -> tuple[str | None, str | None]:
    """Validate a module entry. Returns (sanitized_name, error_reason).

    If error_reason is not None, the module should be skipped.
    """
    name = m.get("name", "")
    if not name or not isinstance(name, str):
        return None, "missing or empty 'name'"

    files = m.get("files")
    if files is not None and not isinstance(files, list):
        return None, f"'files' must be a list, got {type(files).__name__}"

    sanitized = sanitize_module_name(name)
    return sanitized, None


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub catalog-update")
    parser.add_argument("--file", required=True, help="Path to JSON file with module definitions")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None

    # Read JSON from file
    json_path = Path(parsed.file)
    if not json_path.exists():
        envelope.fail("FILE_NOT_FOUND", f"JSON file not found: {parsed.file}")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        envelope.fail("INVALID_JSON", f"Failed to parse JSON file: {e}")

    modules = data.get("modules", [])
    if not isinstance(modules, list):
        envelope.fail("INVALID_SCHEMA", "'modules' must be an array.")

    modules_dir = paths.modules_path(project_root)
    modules_dir.mkdir(parents=True, exist_ok=True)

    # Track which module files we create
    new_module_names = set()
    skipped = []
    valid_modules = []

    for m in modules:
        sanitized, error = _validate_module(m)
        if error:
            skipped.append({"name": m.get("name", ""), "reason": error})
            continue
        # Use sanitized name for file, keep original name for display
        m_copy = dict(m)
        m_copy["_sanitized"] = sanitized
        new_module_names.add(sanitized)
        md_content = _generate_module_md(m_copy)
        atomic_write(modules_dir / f"{sanitized}.md", md_content)
        valid_modules.append(m_copy)

    # Delete old module files not in new list
    deleted = []
    for existing in modules_dir.iterdir():
        if existing.suffix == ".md" and existing.stem not in new_module_names:
            deleted.append(existing.name)
            existing.unlink()

    # Update topics.md code modules section
    topics_file = paths.topics_path(project_root)
    _update_topics_code_section(topics_file, valid_modules)

    # Auto-trigger catalog.repair
    from lib.catalog_repair import repair
    repair_result = repair(project_root)

    ai_actions = list(repair_result.get("ai_actions", []))
    for s in skipped:
        ai_actions.append({
            "type": "invalid_module_skipped",
            "name": s["name"],
            "reason": s["reason"],
            "action": f"Module '{s['name']}' skipped: {s['reason']}. Fix and re-run.",
        })

    envelope.ok(
        {
            "modules_written": sorted(new_module_names),
            "modules_deleted": deleted,
            "modules_skipped": skipped,
            "repair_result": repair_result,
        },
        ai_actions=ai_actions,
        manual_actions=repair_result.get("manual_actions", []),
    )
