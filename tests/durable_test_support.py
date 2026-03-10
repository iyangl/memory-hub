"""Shared helpers for durable memory tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.durable_db import connect, ensure_schema, hash_text, transaction, utc_now


def bootstrap_project(project_root: Path) -> Path:
    """Initialize the durable memory database for a test project."""
    ensure_schema(project_root)
    return project_root


def seed_approved_memory(
    project_root: Path,
    *,
    uri: str,
    memory_type: str,
    title: str,
    content: str,
    recall_when: str = "",
    why_not_in_code: str = "seed why",
    source_reason: str = "seed source",
    actor: str = "seed",
    created_via: str = "approve",
) -> int:
    """Insert a version row and point approved_memories at it."""
    with transaction(project_root) as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS version_number FROM memory_versions WHERE uri = ?",
            (uri,),
        ).fetchone()
        version_number = int(row["version_number"]) + 1
        previous = conn.execute(
            "SELECT current_version_id, created_at FROM approved_memories WHERE uri = ?",
            (uri,),
        ).fetchone()
        supersedes = previous["current_version_id"] if previous is not None else None
        version_id = conn.execute(
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
                memory_type,
                title,
                content,
                hash_text(content),
                recall_when,
                why_not_in_code,
                source_reason,
                supersedes,
                utc_now(),
                actor,
                created_via,
            ),
        ).lastrowid
        if previous is None:
            conn.execute(
                """
                INSERT INTO approved_memories(
                    uri, type, title, content, content_hash, recall_when, why_not_in_code,
                    source_reason, current_version_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uri,
                    memory_type,
                    title,
                    content,
                    hash_text(content),
                    recall_when,
                    why_not_in_code,
                    source_reason,
                    version_id,
                    utc_now(),
                    utc_now(),
                ),
            )
        else:
            conn.execute(
                """
                UPDATE approved_memories
                SET content = ?, content_hash = ?, recall_when = ?, why_not_in_code = ?,
                    source_reason = ?, current_version_id = ?, updated_at = ?
                WHERE uri = ?
                """,
                (
                    content,
                    hash_text(content),
                    recall_when,
                    why_not_in_code,
                    source_reason,
                    version_id,
                    utc_now(),
                    uri,
                ),
            )
    return version_id


def fetch_one(project_root: Path, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    """Fetch one row as dict."""
    with connect(project_root) as conn:
        row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def fetch_all(project_root: Path, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Fetch all rows as dicts."""
    with connect(project_root) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def count_rows(project_root: Path, table_name: str) -> int:
    """Count rows in a table."""
    with connect(project_root) as conn:
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"])
