"""Shared utility functions for memory-hub."""

from __future__ import annotations

import re
from pathlib import Path


COMMON_FACET_KEYWORDS = {
    "decision": ("决策", "结论", "规则", "口径", "原则", "范围", "需求"),
    "constraint": ("约束", "约定", "规范", "流程", "命名"),
    "risk": ("风险", "注意", "误区", "陷阱"),
    "verification": ("验证", "测试", "策略", "回归", "检查"),
}
COMMON_FACET_ORDER_BY_BUCKET = {
    "architect": ("decision", "constraint", "risk", "verification"),
    "pm": ("decision", "risk", "verification", "constraint"),
    "qa": ("verification", "risk", "decision", "constraint"),
    "dev": ("constraint", "decision", "risk", "verification"),
}
COMMON_GENERIC_SECTION_HEADINGS = frozenset({
    keyword for keywords in COMMON_FACET_KEYWORDS.values() for keyword in keywords
})


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
