"""modules-check — Detect stale, added, or removed module cards.

Usage: memory-hub modules-check [--project-root <path>]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from lib import envelope, paths
from lib.scan_modules import scan
from lib.utils import find_module_name_collisions, sanitize_module_name

_HASH_RE = re.compile(r"<!--\s*structure_hash:\s*(\w+)\s*-->")


def _read_card_hashes(project_root: Path | None = None) -> dict[str, str]:
    """Read structure_hash from existing module card files.

    Returns {sanitized_module_name: hash}.
    """
    modules_dir = paths.modules_path(project_root)
    if not modules_dir.is_dir():
        return {}

    result: dict[str, str] = {}
    for card in modules_dir.iterdir():
        if card.suffix != ".md":
            continue
        content = card.read_text(encoding="utf-8")
        m = _HASH_RE.search(content)
        result[card.stem] = m.group(1) if m else ""
    return result


def check_modules(project_root: Path | None = None) -> dict:
    """Compare current project modules against stored module cards."""
    scan_result = scan(project_root, include_untracked=True)
    current_modules = scan_result.get("modules", [])

    collisions = find_module_name_collisions([mod["name"] for mod in current_modules])
    if collisions:
        envelope.fail(
            "MODULE_NAME_COLLISION",
            "Multiple module names map to the same catalog filename.",
            details={"collisions": collisions},
        )

    current_hashes: dict[str, str] = {}
    for mod in current_modules:
        key = sanitize_module_name(mod["name"])
        current_hashes[key] = mod.get("structure_hash", "")

    card_hashes = _read_card_hashes(project_root)

    current_keys = set(current_hashes)
    card_keys = set(card_hashes)

    added = sorted(current_keys - card_keys)
    removed = sorted(card_keys - current_keys)

    stale = []
    up_to_date = []
    for key in sorted(current_keys & card_keys):
        cur = current_hashes[key]
        stored = card_hashes[key]
        if not stored or cur != stored:
            stale.append(key)
        else:
            up_to_date.append(key)

    return {
        "stale": stale,
        "added": added,
        "removed": removed,
        "up_to_date": up_to_date,
    }


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub modules-check")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    result = check_modules(project_root)

    ai_actions = []
    if result["stale"] or result["added"] or result["removed"]:
        ai_actions.append({
            "type": "modules_outdated",
            "action": "Module cards are outdated. Re-run scan-modules + catalog-update to refresh.",
            "stale": result["stale"],
            "added": result["added"],
            "removed": result["removed"],
        })

    envelope.ok(result, ai_actions=ai_actions)
