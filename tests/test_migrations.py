import sqlite3
import tempfile
import unittest
from pathlib import Path

from memory_hub.store import MemoryStore, init_db, _migration_files, _migration_version


class MigrationTests(unittest.TestCase):
    def test_migrations_applied_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(root_dir=root / "db", workspace_root=workspace)

            conn = store.connect("proj_migrations")
            versions = {
                row["version"]
                for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }
            expected_versions = {_migration_version(p) for p in _migration_files()}
            self.assertEqual(expected_versions, expected_versions & versions)

            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(sync_audit)").fetchall()
            }
            self.assertIn("error_code", columns)
            self.assertIn("latency_ms", columns)
            count_before = conn.execute("SELECT COUNT(1) AS cnt FROM schema_migrations").fetchone()["cnt"]
            conn.close()

            conn2 = store.connect("proj_migrations")
            count_after = conn2.execute("SELECT COUNT(1) AS cnt FROM schema_migrations").fetchone()["cnt"]
            conn2.close()

            self.assertEqual(count_before, count_after)

    def test_duplicate_column_migration_remains_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """
                CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE project_meta (id INTEGER PRIMARY KEY CHECK (id = 1), memory_version INTEGER NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE sync_audit (
                    sync_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    error_code TEXT,
                    latency_ms INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE catalog_jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 5,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO schema_migrations(version, applied_at) VALUES ('000','x'),('001','x'),('002','x');
                INSERT INTO project_meta(id, memory_version, updated_at) VALUES (1,0,'x');
                """
            )
            conn.commit()

            # Should not raise even though 003 migration tries to add existing columns.
            init_db(conn)
            versions = {
                row["version"]
                for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }
            self.assertIn("003", versions)
            self.assertIn("004", versions)
            conn.close()


if __name__ == "__main__":
    unittest.main()
