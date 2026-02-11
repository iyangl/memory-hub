"""Tests for code review fixes: crash-recovery, lock contention, old schema compat."""
from __future__ import annotations

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_hub.catalog_worker import _begin_immediate_with_retry, process_catalog_jobs
from memory_hub.errors import BusinessError
from memory_hub.store import (
    MemoryStore,
    _future_utc,
    claim_next_catalog_job,
    enqueue_catalog_job,
    init_db,
    insert_sync_audit,
    now_utc,
    resolve_project_workspace,
)
from memory_hub.sync import session_sync_push


class CrashRecoveryTest(unittest.TestCase):
    """Verify that running jobs with expired lease are reclaimed."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_expired_running_job_is_reclaimed(self) -> None:
        project_id = "proj_crash"
        conn = self.store.connect(project_id)
        try:
            job_id = enqueue_catalog_job(
                conn,
                project_id=project_id,
                job_type="incremental_refresh",
                payload={"files_touched": ["src/main.py"]},
            )
            conn.commit()

            # Simulate a crash: set status to running with an already-expired lease.
            past = "2020-01-01T00:00:00+00:00"
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE catalog_jobs SET status = 'running', attempts = 1, lease_expires_at = ? WHERE job_id = ?",
                (past, job_id),
            )
            conn.commit()

            # Verify a normal pending-only claim would NOT find it.
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT job_id FROM catalog_jobs WHERE project_id = ? AND status = 'pending'",
                (project_id,),
            ).fetchone()
            conn.rollback()
            self.assertIsNone(row, "Stale job should not appear as pending")

            # claim_next_catalog_job should reclaim the expired running job.
            conn.execute("BEGIN IMMEDIATE")
            claimed = claim_next_catalog_job(conn, project_id=project_id)
            conn.commit()
            self.assertIsNotNone(claimed)
            assert claimed is not None
            self.assertEqual(claimed["job_id"], job_id)
            self.assertEqual(claimed["attempts"], 2)  # incremented from 1
        finally:
            conn.close()

    def test_non_expired_running_job_is_not_reclaimed(self) -> None:
        project_id = "proj_no_reclaim"
        conn = self.store.connect(project_id)
        try:
            job_id = enqueue_catalog_job(
                conn,
                project_id=project_id,
                job_type="incremental_refresh",
                payload={"files_touched": ["src/main.py"]},
            )
            conn.commit()

            # Set status to running with a future lease (not expired).
            future = _future_utc(3600)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE catalog_jobs SET status = 'running', attempts = 1, lease_expires_at = ? WHERE job_id = ?",
                (future, job_id),
            )
            conn.commit()

            # claim should NOT reclaim it.
            conn.execute("BEGIN IMMEDIATE")
            claimed = claim_next_catalog_job(conn, project_id=project_id)
            conn.commit()
            self.assertIsNone(claimed, "Active lease should not be reclaimed")
        finally:
            conn.close()

    def test_worker_processes_reclaimed_job(self) -> None:
        project_id = "proj_worker_reclaim"
        conn = self.store.connect(project_id)
        try:
            job_id = enqueue_catalog_job(
                conn,
                project_id=project_id,
                job_type="incremental_refresh",
                payload={"files_touched": ["src/main.py"]},
            )
            conn.commit()
            past = "2020-01-01T00:00:00+00:00"
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE catalog_jobs SET status = 'running', attempts = 1, lease_expires_at = ? WHERE job_id = ?",
                (past, job_id),
            )
            conn.commit()
        finally:
            conn.close()

        result = process_catalog_jobs(self.store, project_id)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)

        conn = self.store.connect(project_id)
        try:
            row = conn.execute(
                "SELECT status FROM catalog_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["status"], "done")
        finally:
            conn.close()


class LockContentionRetryTest(unittest.TestCase):
    """Verify that lock contention triggers retry, not a crash."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_begin_immediate_retries_on_transient_lock(self) -> None:
        """_begin_immediate_with_retry retries internally and succeeds after lock releases."""
        import threading

        project_id = "proj_lock"
        db_path = self.store.db_path(project_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn_main = self.store.connect(project_id)
        # Set a very short busy_timeout so the BEGIN IMMEDIATE fails fast.
        conn_main.execute("PRAGMA busy_timeout = 10;")

        # Blocker connection holds the write lock.
        conn_blocker = sqlite3.connect(db_path, check_same_thread=False)
        conn_blocker.execute("PRAGMA journal_mode = WAL;")
        conn_blocker.execute("BEGIN IMMEDIATE")

        # Schedule the lock release after a brief delay.
        def delayed_release():
            time.sleep(0.08)
            conn_blocker.rollback()
            conn_blocker.close()

        t = threading.Thread(target=delayed_release, daemon=True)
        t.start()

        try:
            # base_delay=0.05 -> attempt 0 fails, sleep 0.05s, attempt 1 fails,
            # sleep 0.1s (total ~0.15s) -> by then blocker released at 0.08s.
            with patch("memory_hub.catalog_worker._LOCK_RETRY_BASE_DELAY", 0.05):
                _begin_immediate_with_retry(conn_main)
            # If we reach here, the retry succeeded.
            conn_main.rollback()
        finally:
            t.join(timeout=2)
            conn_main.close()

    def test_exhausted_retries_returns_partial_stats(self) -> None:
        project_id = "proj_lock_exhaust"
        conn = self.store.connect(project_id)
        try:
            enqueue_catalog_job(
                conn,
                project_id=project_id,
                job_type="incremental_refresh",
                payload={"files_touched": ["src/main.py"]},
            )
            conn.commit()
        finally:
            conn.close()

        def always_locked(c: sqlite3.Connection) -> None:
            raise sqlite3.OperationalError("database is locked")

        with patch("memory_hub.catalog_worker._begin_immediate_with_retry", side_effect=always_locked):
            result = process_catalog_jobs(self.store, project_id)

        # Should return stats without raising.
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["lock_failures"], 1)


class OldSchemaCompatTest(unittest.TestCase):
    """Verify that migration 006 allows catalog-direction audit inserts."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_old_check_constraint_is_relaxed_after_migration(self) -> None:
        db_path = self.root / "projects" / "proj_compat" / "memory.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create an "old" sync_audit with a restrictive CHECK on direction.
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                memory_version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_audit (
                sync_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                direction TEXT NOT NULL CHECK (direction IN ('pull', 'push', 'resolve_conflict')),
                client_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                error_code TEXT,
                latency_ms INTEGER,
                created_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations (version, applied_at) VALUES ('000', '2025-01-01T00:00:00');
            INSERT INTO schema_migrations (version, applied_at) VALUES ('001', '2025-01-01T00:00:00');
            INSERT INTO schema_migrations (version, applied_at) VALUES ('002', '2025-01-01T00:00:00');
            INSERT INTO schema_migrations (version, applied_at) VALUES ('003', '2025-01-01T00:00:00');
            INSERT INTO schema_migrations (version, applied_at) VALUES ('004', '2025-01-01T00:00:00');
            INSERT INTO schema_migrations (version, applied_at) VALUES ('005', '2025-01-01T00:00:00');
            CREATE TABLE IF NOT EXISTS catalog_jobs (
                job_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                payload_json TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                last_error TEXT,
                next_retry_at TEXT,
                lease_expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Verify the old CHECK blocks catalog_brief.
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sync_audit (sync_id, project_id, direction, client_id, session_id, "
                "request_json, response_json, error_code, latency_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("err_test", "proj_compat", "catalog_brief", "c", "s", "{}", "{}", "X", 0, "2025-01-01"),
            )
        conn.rollback()
        conn.close()

        # Now open via MemoryStore.connect which runs init_db -> applies migration 006.
        store = MemoryStore(root_dir=self.root, workspace_root=self.root)
        conn = store.connect("proj_compat")
        try:
            # After migration 006, catalog_brief should be accepted.
            insert_sync_audit(
                conn,
                sync_id="err_post_migration",
                project_id="proj_compat",
                direction="catalog_brief",
                client_id="codex",
                session_id="s1",
                request_payload={"tool": "catalog.brief.generate"},
                response_payload={"status": "error"},
                error_code="MISSING_REQUIRED_FIELDS",
                latency_ms=5,
            )
            conn.commit()

            row = conn.execute(
                "SELECT direction FROM sync_audit WHERE sync_id = 'err_post_migration'"
            ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["direction"], "catalog_brief")
        finally:
            conn.close()


class NullLeaseReclaimTest(unittest.TestCase):
    """Verify that running jobs with lease_expires_at=NULL are reclaimable (upgrade compat)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_running_null_lease_is_reclaimed(self) -> None:
        project_id = "proj_null_lease"
        conn = self.store.connect(project_id)
        try:
            job_id = enqueue_catalog_job(
                conn,
                project_id=project_id,
                job_type="incremental_refresh",
                payload={"files_touched": ["src/main.py"]},
            )
            conn.commit()

            # Simulate pre-upgrade state: running with no lease.
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE catalog_jobs SET status = 'running', attempts = 1, lease_expires_at = NULL WHERE job_id = ?",
                (job_id,),
            )
            conn.commit()

            conn.execute("BEGIN IMMEDIATE")
            claimed = claim_next_catalog_job(conn, project_id=project_id)
            conn.commit()
            self.assertIsNotNone(claimed, "Running job with NULL lease must be reclaimable")
            assert claimed is not None
            self.assertEqual(claimed["job_id"], job_id)
            # After reclaim, lease_expires_at should be set.
            row = conn.execute(
                "SELECT lease_expires_at FROM catalog_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            self.assertIsNotNone(row["lease_expires_at"])
        finally:
            conn.close()


class DriftScoreClampTest(unittest.TestCase):
    """Verify drift_score is always in [0, 1.0]."""

    def test_git_mode_drift_score_clamped(self) -> None:
        from memory_hub.drift import detect_drift

        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            # 1 known hash, but git mode returns 3 changed files -> raw score=3.0
            known_hashes = {"old.py": "abc123"}

            many_changed = ["a.py", "b.py", "c.py"]
            fake_git_result = {
                "method": "git_diff",
                "changed_files": many_changed,
                "drift_score": 0.0,
            }

            with patch("memory_hub.drift._detect_with_git_diff", return_value=fake_git_result):
                result = detect_drift(root, known_hashes)

            self.assertEqual(result["method"], "git_diff")
            self.assertLessEqual(float(result["drift_score"]), 1.0)
            self.assertGreaterEqual(float(result["drift_score"]), 0.0)
        finally:
            tmp.cleanup()

    def test_hash_mode_drift_score_bounded(self) -> None:
        """Hash mode uses union of known+current as denominator, so score is naturally <= 1.0."""
        from memory_hub.drift import detect_drift

        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            # Create 3 files, only 1 known -> 2 new + 1 changed = 3 changed out of 3 total = 1.0
            for name in ("a.py", "b.py", "c.py"):
                (root / name).write_text(f"# {name}\n", encoding="utf-8")
            known_hashes = {"a.py": "wrong_hash"}

            # Force hash fallback by making git fail.
            with patch("memory_hub.drift._detect_with_git_diff", side_effect=RuntimeError("no git")):
                result = detect_drift(root, known_hashes)

            self.assertEqual(result["method"], "hash_compare")
            self.assertLessEqual(float(result["drift_score"]), 1.0)
        finally:
            tmp.cleanup()

class HalfMigratedHealingTest(unittest.TestCase):
    """Verify that init_db auto-repairs a 006 half-migrated state."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_half_migrated_006_self_heals(self) -> None:
        db_path = self.root / "projects" / "proj_heal" / "memory.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Simulate the half-migrated state: sync_audit_new exists, sync_audit was dropped.
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                memory_version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalog_jobs (
                job_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                payload_json TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                last_error TEXT,
                next_retry_at TEXT,
                lease_expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_audit_new (
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
            INSERT INTO schema_migrations (version, applied_at)
                VALUES ('000','x'),('001','x'),('002','x'),('003','x'),
                       ('004','x'),('005','x');
            INSERT INTO project_meta (id, memory_version, updated_at)
                VALUES (1, 0, 'x');
        """)
        conn.close()

        # init_db should heal: rename sync_audit_new -> sync_audit, then apply remaining.
        store = MemoryStore(root_dir=self.root, workspace_root=self.root)
        conn = store.connect("proj_heal")
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("sync_audit", tables)
            self.assertNotIn("sync_audit_new", tables)

            # Verify we can insert into the healed table.
            conn.execute(
                "INSERT INTO sync_audit (sync_id, project_id, direction, client_id, "
                "session_id, request_json, response_json, created_at) "
                "VALUES ('t','p','pull','c','s','{}','{}','2025-01-01')"
            )
            conn.rollback()
        finally:
            conn.close()


class WorkspaceIsolationTest(unittest.TestCase):
    """Verify per-project workspace binding."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ws_a = self.root / "workspace_a"
        self.ws_b = self.root / "workspace_b"
        for ws in (self.ws_a, self.ws_b):
            (ws / "src").mkdir(parents=True, exist_ok=True)
            (ws / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_workspace_binding_prevents_cross_project(self) -> None:
        store_a = MemoryStore(root_dir=self.root / "db", workspace_root=self.ws_a)
        conn_a = store_a.connect("proj_a")
        try:
            ws = resolve_project_workspace(conn_a, store_a.project_workspace("proj_a"))
            self.assertEqual(ws, self.ws_a.resolve())
            # Binding should persist.
            row = conn_a.execute(
                "SELECT workspace_root FROM project_meta WHERE id = 1"
            ).fetchone()
            self.assertEqual(row["workspace_root"], str(self.ws_a.resolve()))
        finally:
            conn_a.close()

        store_b = MemoryStore(root_dir=self.root / "db", workspace_root=self.ws_b)
        conn_b = store_b.connect("proj_b")
        try:
            ws = resolve_project_workspace(conn_b, store_b.project_workspace("proj_b"))
            self.assertEqual(ws, self.ws_b.resolve())
        finally:
            conn_b.close()

    def test_workspace_mismatch_raises(self) -> None:
        store = MemoryStore(root_dir=self.root / "db", workspace_root=self.ws_a)
        conn = store.connect("proj_mismatch")
        try:
            resolve_project_workspace(conn, self.ws_a)
        finally:
            conn.close()

        # Re-open with a *different* workspace -> should raise.
        store2 = MemoryStore(root_dir=self.root / "db", workspace_root=self.ws_b)
        conn2 = store2.connect("proj_mismatch")
        try:
            with self.assertRaises(BusinessError) as ctx:
                resolve_project_workspace(conn2, self.ws_b)
            self.assertEqual(ctx.exception.error_code, "WORKSPACE_MISMATCH")
        finally:
            conn2.close()

    def test_session_sync_push_rejects_workspace_mismatch(self) -> None:
        store_a = MemoryStore(root_dir=self.root / "db", workspace_root=self.ws_a)
        first = session_sync_push(
            store_a,
            {
                "project_id": "proj_shared",
                "client_id": "codex-a",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "seed from ws_a",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "A"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": ["src/main.py"],
            },
        )
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["memory_version"], 1)

        store_b = MemoryStore(root_dir=self.root / "db", workspace_root=self.ws_b)
        with self.assertRaises(BusinessError) as ctx:
            session_sync_push(
                store_b,
                {
                    "project_id": "proj_shared",
                    "client_id": "codex-b",
                    "session_id": "s2",
                    "context_stamp": first["consistency_stamp"],
                    "session_summary": "attempt from ws_b",
                    "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "B"}],
                    "decisions_delta": [],
                    "open_loops_new": [],
                    "open_loops_closed": [],
                    "files_touched": ["src/main.py"],
                },
            )
        self.assertEqual(ctx.exception.error_code, "WORKSPACE_MISMATCH")

        conn = store_a.connect("proj_shared")
        try:
            version_row = conn.execute("SELECT memory_version FROM project_meta WHERE id = 1").fetchone()
            self.assertIsNotNone(version_row)
            assert version_row is not None
            self.assertEqual(int(version_row["memory_version"]), 1)

            state_row = conn.execute(
                """
                SELECT value_json
                FROM role_state_current
                WHERE project_id = ? AND role = 'pm' AND memory_key = 'goal'
                """,
                ("proj_shared",),
            ).fetchone()
            self.assertIsNotNone(state_row)
            assert state_row is not None
            self.assertEqual(state_row["value_json"], '"A"')
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
