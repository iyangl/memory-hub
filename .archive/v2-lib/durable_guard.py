"""Minimal write guard for durable memory proposals."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lib.durable_db import connect, rows_to_dicts
from lib.durable_errors import DurableMemoryError
from lib.durable_uri import validate_memory_type

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(_normalize(text)))


def _overlap_score(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return len(intersection) / len(union)


def evaluate_write_guard(
    project_root: Path | None,
    *,
    memory_type: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    """Evaluate whether a candidate should create a proposal."""
    validate_memory_type(memory_type)

    try:
        with connect(project_root) as conn:
            rows = conn.execute(
                """
                SELECT uri, title, content
                FROM approved_memories
                WHERE type = ?
                """,
                (memory_type,),
            ).fetchall()
    except Exception as exc:
        raise DurableMemoryError(
            "GUARD_UNAVAILABLE",
            "Write guard is unavailable.",
            {"reason": type(exc).__name__},
        ) from exc

    normalized_content = _normalize(content)
    candidate_text = f"{title} {content}"
    best_target = None
    best_score = 0.0

    for row in rows_to_dicts(rows):
        existing_content = _normalize(str(row["content"]))
        if existing_content == normalized_content:
            return {
                "action": "NOOP",
                "reason": "duplicate_content",
                "target_uri": row["uri"],
            }

        score = _overlap_score(candidate_text, f"{row['title']} {row['content']}")
        if score > best_score:
            best_score = score
            best_target = row["uri"]

    if best_target is not None and best_score >= 0.55:
        return {
            "action": "UPDATE_TARGET",
            "reason": "high_overlap_existing_memory",
            "target_uri": best_target,
        }

    return {
        "action": "PENDING_REVIEW",
        "reason": "new_high_value_memory",
        "target_uri": None,
    }
