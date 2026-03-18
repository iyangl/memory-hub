"""Tests for durable memory schema bootstrap and read helpers."""

import sqlite3

from lib import paths
from lib.durable_repo import ensure_schema, get_boot_memories
from tests.durable_test_support import bootstrap_project, seed_approved_memory


def test_ensure_schema_creates_tables_and_is_idempotent(tmp_path):
    project_root = bootstrap_project(tmp_path)

    first_db_path = ensure_schema(project_root)
    second_db_path = ensure_schema(project_root)

    assert first_db_path == paths.store_db_path(project_root)
    assert second_db_path == first_db_path
    assert first_db_path.exists()

    conn = sqlite3.connect(first_db_path)
    try:
        rows = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type IN ('table', 'index')
            """
        ).fetchall()
        names = {row[0] for row in rows}
        assert "schema_migrations" in names
        assert "approved_memories" in names
        assert "memory_versions" in names
        assert "memory_proposals" in names
        assert "audit_events" in names
        assert "docs_change_reviews" in names
        proposal_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(memory_proposals)").fetchall()
        }
        approved_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(approved_memories)").fetchall()
        }
        assert "storage_lane" in proposal_columns
        assert "doc_ref" in proposal_columns
        assert "storage_lane" in approved_columns
        assert "doc_ref" in approved_columns
        versions = conn.execute("SELECT version FROM schema_migrations").fetchall()
        assert len(versions) == 1
    finally:
        conn.close()


def test_get_boot_memories_returns_only_identity_and_constraint_in_order(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="constraint://second",
        memory_type="constraint",
        title="Second Constraint",
        content="second",
    )
    seed_approved_memory(
        project_root,
        uri="decision://ignored",
        memory_type="decision",
        title="Ignored Decision",
        content="ignored",
    )
    seed_approved_memory(
        project_root,
        uri="identity://first",
        memory_type="identity",
        title="First Identity",
        content="first",
    )

    rows = get_boot_memories(project_root)

    assert [row["uri"] for row in rows] == [
        "identity://first",
        "constraint://second",
    ]
