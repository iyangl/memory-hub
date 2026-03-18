"""SQLite storage for durable memory."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from lib import paths

SCHEMA_VERSION = "0003_phase2d"
SCHEMA_CHECKSUM = hashlib.sha256(SCHEMA_VERSION.encode("utf-8")).hexdigest()
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL,
    checksum TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    uri TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('identity','decision','constraint','preference')),
    storage_lane TEXT NOT NULL DEFAULT 'durable' CHECK (storage_lane IN ('durable','dual')),
    doc_ref TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    recall_when TEXT NOT NULL DEFAULT '',
    why_not_in_code TEXT NOT NULL,
    source_reason TEXT NOT NULL,
    supersedes_version_id INTEGER REFERENCES memory_versions(version_id),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_via TEXT NOT NULL CHECK (created_via IN ('approve','rollback')),
    UNIQUE(uri, version_number)
);
CREATE TABLE IF NOT EXISTS approved_memories (
    uri TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('identity','decision','constraint','preference')),
    storage_lane TEXT NOT NULL DEFAULT 'durable' CHECK (storage_lane IN ('durable','dual')),
    doc_ref TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    recall_when TEXT NOT NULL DEFAULT '',
    why_not_in_code TEXT NOT NULL,
    source_reason TEXT NOT NULL,
    current_version_id INTEGER NOT NULL UNIQUE REFERENCES memory_versions(version_id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_proposals (
    proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_kind TEXT NOT NULL CHECK (proposal_kind IN ('create','update')),
    status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected')),
    target_uri TEXT NOT NULL,
    base_version_id INTEGER REFERENCES memory_versions(version_id),
    type TEXT NOT NULL CHECK (type IN ('identity','decision','constraint','preference')),
    storage_lane TEXT NOT NULL DEFAULT 'durable' CHECK (storage_lane IN ('durable','dual')),
    doc_ref TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    recall_when TEXT NOT NULL DEFAULT '',
    why_not_in_code TEXT NOT NULL,
    source_reason TEXT NOT NULL,
    patch_old_string TEXT,
    patch_new_string TEXT,
    append_content TEXT,
    guard_decision TEXT NOT NULL CHECK (guard_decision='PENDING_REVIEW'),
    guard_reason TEXT NOT NULL,
    guard_target_uri TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    review_note TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_create_target_uri
    ON memory_proposals(target_uri)
    WHERE proposal_kind='create' AND status='pending';
CREATE INDEX IF NOT EXISTS idx_memory_proposals_status_created_at
    ON memory_proposals(status, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_memory_proposals_target_uri
    ON memory_proposals(target_uri);
CREATE INDEX IF NOT EXISTS idx_memory_proposals_base_version_id
    ON memory_proposals(base_version_id);
CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL CHECK (event_type IN ('approve','reject','rollback')),
    proposal_id INTEGER REFERENCES memory_proposals(proposal_id),
    uri TEXT NOT NULL,
    from_version_id INTEGER REFERENCES memory_versions(version_id),
    to_version_id INTEGER REFERENCES memory_versions(version_id),
    actor TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approved_memories_type
    ON approved_memories(type);
CREATE INDEX IF NOT EXISTS idx_approved_memories_updated_at
    ON approved_memories(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_versions_uri_created_at
    ON memory_versions(uri, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_uri_created_at
    ON audit_events(uri, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_proposal_id
    ON audit_events(proposal_id);
CREATE TABLE IF NOT EXISTS docs_change_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected')),
    doc_ref TEXT NOT NULL,
    title TEXT NOT NULL,
    before_content TEXT NOT NULL DEFAULT '',
    after_content TEXT NOT NULL,
    reason TEXT NOT NULL,
    linked_proposal_id INTEGER REFERENCES memory_proposals(proposal_id),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    review_note TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_docs_change_ref
    ON docs_change_reviews(doc_ref)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_docs_change_reviews_status_created_at
    ON docs_change_reviews(status, created_at ASC);
"""


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    if column_name in _table_columns(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {definition}")


def _ensure_phase2c_schema(conn: sqlite3.Connection) -> None:
    _ensure_column(
        conn,
        "memory_versions",
        "storage_lane",
        "storage_lane TEXT NOT NULL DEFAULT 'durable' CHECK (storage_lane IN ('durable','dual'))",
    )
    _ensure_column(conn, "memory_versions", "doc_ref", "doc_ref TEXT")
    _ensure_column(
        conn,
        "approved_memories",
        "storage_lane",
        "storage_lane TEXT NOT NULL DEFAULT 'durable' CHECK (storage_lane IN ('durable','dual'))",
    )
    _ensure_column(conn, "approved_memories", "doc_ref", "doc_ref TEXT")
    _ensure_column(
        conn,
        "memory_proposals",
        "storage_lane",
        "storage_lane TEXT NOT NULL DEFAULT 'durable' CHECK (storage_lane IN ('durable','dual'))",
    )
    _ensure_column(conn, "memory_proposals", "doc_ref", "doc_ref TEXT")
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_approved_memories_doc_ref
            ON approved_memories(doc_ref);
        CREATE INDEX IF NOT EXISTS idx_memory_proposals_doc_ref_status
            ON memory_proposals(doc_ref, status);
        """
    )


def _ensure_phase2d_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS docs_change_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected')),
            doc_ref TEXT NOT NULL,
            title TEXT NOT NULL,
            before_content TEXT NOT NULL DEFAULT '',
            after_content TEXT NOT NULL,
            reason TEXT NOT NULL,
            linked_proposal_id INTEGER REFERENCES memory_proposals(proposal_id),
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            reviewed_at TEXT,
            reviewed_by TEXT,
            review_note TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_docs_change_ref
            ON docs_change_reviews(doc_ref)
            WHERE status = 'pending';
        CREATE INDEX IF NOT EXISTS idx_docs_change_reviews_status_created_at
            ON docs_change_reviews(status, created_at ASC);
        """
    )


def utc_now() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_text(text: str) -> str:
    """Hash text with sha256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def connect(project_root: Path | None = None) -> sqlite3.Connection:
    """Open a durable memory SQLite connection."""
    db_path = paths.store_db_path(project_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(project_root: Path | None = None) -> Path:
    """Ensure database and schema exist."""
    db_path = paths.store_db_path(project_root)
    with connect(project_root) as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_phase2c_schema(conn)
        _ensure_phase2d_schema(conn)
        row = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at, checksum) VALUES (?, ?, ?)",
                (SCHEMA_VERSION, utc_now(), SCHEMA_CHECKSUM),
            )
    return db_path


@contextmanager
def transaction(project_root: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a write transaction."""
    conn = connect(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert sqlite row to plain dict."""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert sqlite rows to dicts."""
    return [row_to_dict(row) for row in rows if row is not None]
