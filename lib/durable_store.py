"""Shared SQLite helpers for durable memory repository and services."""

from __future__ import annotations

import sqlite3
from typing import Any

from lib.durable_db import hash_text, row_to_dict, utc_now
from lib.durable_errors import DurableMemoryError


def require_text(value: str | None, code: str, message: str) -> str:
    """Validate that text input is non-empty after trimming."""
    text = str(value or "").strip()
    if not text:
        raise DurableMemoryError(code, message)
    return text


def get_proposal(
    conn: sqlite3.Connection,
    proposal_id: int,
    *,
    pending_only: bool = False,
) -> dict[str, Any]:
    """Fetch a proposal row or raise a structured error."""
    proposal = row_to_dict(
        conn.execute(
            "SELECT * FROM memory_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
    )
    if proposal is None:
        raise DurableMemoryError("PROPOSAL_NOT_FOUND", f"Proposal not found: {proposal_id}")
    if pending_only and proposal["status"] != "pending":
        raise DurableMemoryError("PROPOSAL_NOT_PENDING", f"Proposal is not pending: {proposal_id}")
    return proposal


def get_approved(
    conn: sqlite3.Connection,
    uri: str,
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    """Fetch an approved memory row."""
    approved = row_to_dict(
        conn.execute("SELECT * FROM approved_memories WHERE uri = ?", (uri,)).fetchone()
    )
    if approved is None and required:
        raise DurableMemoryError("MEMORY_NOT_FOUND", f"Approved memory not found: {uri}")
    return approved


def get_version(conn: sqlite3.Connection, version_id: int) -> dict[str, Any]:
    """Fetch a version row or raise a structured error."""
    version = row_to_dict(
        conn.execute(
            "SELECT * FROM memory_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()
    )
    if version is None:
        raise DurableMemoryError("VERSION_NOT_FOUND", f"Version not found: {version_id}")
    return version


def next_version_number(conn: sqlite3.Connection, uri: str) -> int:
    """Return the next version number for a URI."""
    row = conn.execute(
        "SELECT COALESCE(MAX(version_number), 0) AS version_number FROM memory_versions WHERE uri = ?",
        (uri,),
    ).fetchone()
    return int(row["version_number"]) + 1


def reserved_create_uris(conn: sqlite3.Connection) -> set[str]:
    """Return URIs reserved by approved memories and pending create proposals."""
    approved = conn.execute("SELECT uri FROM approved_memories").fetchall()
    pending = conn.execute(
        """
        SELECT target_uri FROM memory_proposals
        WHERE proposal_kind = 'create' AND status = 'pending'
        """
    ).fetchall()
    return {row[0] for row in approved + pending}


def insert_version(
    conn: sqlite3.Connection,
    *,
    uri: str,
    version_number: int,
    type: str,
    title: str,
    content: str,
    recall_when: str,
    why_not_in_code: str,
    source_reason: str,
    supersedes_version_id: int | None,
    created_by: str,
    created_via: str,
) -> int:
    """Insert a durable memory version row."""
    return conn.execute(
        """
        INSERT INTO memory_versions(
            uri, version_number, type, title, content, content_hash, recall_when,
            why_not_in_code, source_reason, supersedes_version_id, created_at,
            created_by, created_via
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uri,
            version_number,
            type,
            title,
            content,
            hash_text(content),
            recall_when,
            why_not_in_code,
            source_reason,
            supersedes_version_id,
            utc_now(),
            created_by or "",
            created_via,
        ),
    ).lastrowid


def upsert_approved(
    conn: sqlite3.Connection,
    *,
    uri: str,
    data: dict[str, Any],
    version_id: int,
) -> None:
    """Insert or update the approved memory pointer."""
    existing = get_approved(conn, uri, required=False)
    now = utc_now()
    if existing is None:
        conn.execute(
            """
            INSERT INTO approved_memories(
                uri, type, title, content, content_hash, recall_when, why_not_in_code,
                source_reason, current_version_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uri,
                data["type"],
                data["title"],
                data["content"],
                hash_text(data["content"]),
                data["recall_when"],
                data["why_not_in_code"],
                data["source_reason"],
                version_id,
                now,
                now,
            ),
        )
        return
    conn.execute(
        """
        UPDATE approved_memories
        SET type = ?, title = ?, content = ?, content_hash = ?, recall_when = ?,
            why_not_in_code = ?, source_reason = ?, current_version_id = ?, updated_at = ?
        WHERE uri = ?
        """,
        (
            data["type"],
            data["title"],
            data["content"],
            hash_text(data["content"]),
            data["recall_when"],
            data["why_not_in_code"],
            data["source_reason"],
            version_id,
            now,
            uri,
        ),
    )
