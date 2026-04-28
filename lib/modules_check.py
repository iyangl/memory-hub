"""modules-check — deprecated legacy command.

Usage: memory-hub modules-check [--project-root <path>]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from lib import envelope, paths
from lib.scan_modules import MODULE_CARD_GENERATOR_VERSION, scan
from lib.utils import fail_legacy_command, find_module_name_collisions, sanitize_module_name

_HASH_RE = re.compile(r"<!--\s*structure_hash:\s*(\w+)\s*-->")
_VERSION_RE = re.compile(r"<!--\s*generator_version:\s*(\S+)\s*-->")


def _read_card_metadata(project_root: Path | None = None) -> dict[str, dict[str, str]]:
    """Read module card metadata from existing module card files.

    Returns {sanitized_module_name: {"structure_hash": "...", "generator_version": "..."}}.
    """
    modules_dir = paths.modules_path(project_root)
    if not modules_dir.is_dir():
        return {}

    result: dict[str, dict[str, str]] = {}
    for card in modules_dir.iterdir():
        if card.suffix != ".md":
            continue
        content = card.read_text(encoding="utf-8")
        hash_match = _HASH_RE.search(content)
        version_match = _VERSION_RE.search(content)
        result[card.stem] = {
            "structure_hash": hash_match.group(1) if hash_match else "",
            "generator_version": version_match.group(1) if version_match else "",
        }
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

    current_metadata: dict[str, dict[str, str]] = {}
    for mod in current_modules:
        key = sanitize_module_name(mod["name"])
        current_metadata[key] = {
            "structure_hash": mod.get("structure_hash", ""),
            "generator_version": mod.get("generator_version", MODULE_CARD_GENERATOR_VERSION),
        }

    card_metadata = _read_card_metadata(project_root)

    current_keys = set(current_metadata)
    card_keys = set(card_metadata)

    added = sorted(current_keys - card_keys)
    removed = sorted(card_keys - current_keys)

    stale = []
    up_to_date = []
    for key in sorted(current_keys & card_keys):
        current = current_metadata[key]
        stored = card_metadata[key]
        if (
            not stored.get("structure_hash")
            or stored.get("structure_hash") != current["structure_hash"]
            or stored.get("generator_version") != current["generator_version"]
        ):
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
    fail_legacy_command(
        "modules-check",
        [
            "memory-hub search <query>",
            "memory-hub read <bucket> <file>",
        ],
        reason="Module-card staleness checks are legacy compatibility and removed from default workflow.",
    )
