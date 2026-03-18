"""Proposal-specific helpers for durable memory repository flows."""

from __future__ import annotations

from typing import Any

from lib.durable_db import hash_text, utc_now
from lib.durable_errors import DurableMemoryError

_INSERT_PROPOSAL_SQL = """
    INSERT INTO memory_proposals(
        proposal_kind, status, target_uri, base_version_id, type, storage_lane, doc_ref, title, content,
        content_hash, recall_when, why_not_in_code, source_reason, patch_old_string,
        patch_new_string, append_content, guard_decision, guard_reason,
        guard_target_uri, created_at, created_by
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def guard_result(guard: dict[str, Any]) -> dict[str, Any]:
    """Return a stable write-guard response payload."""
    return {
        "code": guard["action"],
        "guard_decision": guard["action"],
        "guard_reason": guard["reason"],
        "guard_target_uri": guard["target_uri"],
    }


def insert_proposal(
    conn: Any,
    *,
    proposal_kind: str,
    target_uri: str,
    base_version_id: int | None,
    memory_type: str,
    storage_lane: str = "durable",
    doc_ref: str | None = None,
    title: str,
    content: str,
    recall_when: str,
    why_not_in_code: str,
    source_reason: str,
    patch_old_string: str | None = None,
    patch_new_string: str | None = None,
    append_content: str | None = None,
    guard_reason: str,
    created_by: str,
) -> int:
    """Insert a pending proposal row."""
    return conn.execute(
        _INSERT_PROPOSAL_SQL,
        (
            proposal_kind,
            "pending",
            target_uri,
            base_version_id,
            memory_type,
            storage_lane,
            doc_ref,
            title,
            content,
            hash_text(content),
            recall_when,
            why_not_in_code,
            source_reason,
            patch_old_string,
            patch_new_string,
            append_content,
            "PENDING_REVIEW",
            guard_reason,
            None,
            utc_now(),
            created_by or "",
        ),
    ).lastrowid


def validate_update_mode(old_string: str | None, new_string: str | None, append: str | None) -> None:
    """Validate the mutually exclusive patch vs append update modes."""
    if old_string is not None and append is not None:
        raise DurableMemoryError("PATCH_MODE_CONFLICT", "Patch mode and append mode are mutually exclusive.")
    if old_string in (None, "") and new_string is not None:
        raise DurableMemoryError("MISSING_OLD_STRING", "old_string is required for patch mode.")
    if old_string not in (None, "") and new_string is None:
        raise DurableMemoryError("MISSING_NEW_STRING", "new_string is required for patch mode.")
    if append == "":
        raise DurableMemoryError("EMPTY_APPEND", "append must not be empty.")


def materialize_candidate_content(
    current_content: str,
    old_string: str | None,
    new_string: str | None,
    append: str | None,
) -> str:
    """Apply a validated patch/append operation in memory."""
    if old_string in (None, ""):
        return current_content if append is None else current_content + append
    if old_string == new_string:
        raise DurableMemoryError("IDENTICAL_PATCH", "old_string and new_string must differ.")
    if old_string == current_content:
        raise DurableMemoryError("FULL_REPLACE_FORBIDDEN", "Full replace is forbidden.")
    occurrences = current_content.count(old_string)
    if occurrences == 0:
        raise DurableMemoryError("OLD_STRING_NOT_FOUND", "old_string was not found in the approved content.")
    if occurrences > 1:
        raise DurableMemoryError("OLD_STRING_NOT_UNIQUE", "old_string must match exactly one location.")
    return current_content.replace(old_string, new_string or "", 1)
