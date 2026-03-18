"""Read-only decision discovery entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.discovery_context import build_discovery_context
from lib.discovery_signals import detect_signals, sort_candidates


def discover_decisions(
    project_root: Path | None,
    *,
    summary: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """Discover candidate knowledge items from current changes."""
    root = project_root or Path.cwd()
    context = build_discovery_context(root, summary=summary)
    candidates = _dedupe(sort_candidates(detect_signals(context)))[:limit]
    return {
        "candidate_count": len(candidates),
        "changed_files": context.changed_files,
        "summary_used": bool(context.summary),
        "items": candidates,
    }


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str | None, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        marker = (
            item.get("target_ref"),
            str(item.get("signal_kind")),
            str(item.get("title")),
        )
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(item)
    return deduped
