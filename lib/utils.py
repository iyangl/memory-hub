"""Shared utility functions for memory-hub."""

from __future__ import annotations

import re
from pathlib import Path


def sanitize_module_name(name: str) -> str:
    """Sanitize a module name for use as a filename.

    Strips whitespace, removes parenthesized content and CJK characters,
    replaces non-alphanumeric chars with hyphens, collapses runs.
    Returns "unnamed" if result is empty.
    """
    s = name.strip().lower()
    s = re.sub(r"\s*\(.*?\)\s*", " ", s)
    s = re.sub(r"[\u4e00-\u9fff]+", "", s)
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    return s or "unnamed"


def find_module_name_collisions(names: list[str]) -> dict[str, list[str]]:
    """Return sanitized-name collisions as {sanitized: [original names...]}"""
    groups: dict[str, list[str]] = {}
    for name in names:
        sanitized = sanitize_module_name(name)
        groups.setdefault(sanitized, []).append(name)
    return {
        sanitized: originals
        for sanitized, originals in groups.items()
        if len(originals) > 1
    }


def atomic_write(filepath: Path, content: str) -> None:
    """Write content atomically: write to .tmp then rename."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    if filepath.exists():
        filepath.unlink()
    tmp_path.rename(filepath)
