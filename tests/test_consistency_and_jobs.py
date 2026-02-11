from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_hub.catalog import catalog_health_check
from memory_hub.catalog_worker import process_catalog_jobs
from memory_hub.store import MemoryStore, enqueue_catalog_job
from memory_hub.sync import session_sync_pull, session_sync_push


class ConsistencyAndJobsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "main.py").write_text(
            "from src.lib import go\n",
            encoding="utf-8",
        )
        (self.workspace / "src" / "lib.py").write_text("def go():\n    return 1\n", encoding="utf-8")
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_push_enqueues_job_and_worker_restores_consistency(self) -> None:
        push = session_sync_push(
            self.store,
            {
                "project_id": "proj_consistency",
                "client_id": "codex",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "seed",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "x"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": ["src/main.py"],
            },
        )

        self.assertEqual(push["status"], "ok")
        self.assertEqual(push["consistency_stamp"]["consistency"], "degraded")
        self.assertEqual(push["catalog_job"]["status"], "pending")

        worker_result = process_catalog_jobs(self.store, "proj_consistency")
        self.assertGreaterEqual(worker_result["processed"], 1)

        health = catalog_health_check(self.store, {"project_id": "proj_consistency"})
        self.assertIn(health["consistency_status"], {"ok", "degraded", "unknown"})
        self.assertIn("coverage", health)
        self.assertIn("coverage_pct", health)

        pull = session_sync_pull(
            self.store,
            {
                "project_id": "proj_consistency",
                "client_id": "codex",
                "session_id": "s2",
                "task_prompt": "implement new feature",
                "task_type": "implement",
            },
        )
        self.assertIsInstance(pull["consistency_stamp"], dict)
        self.assertIn("catalog_version", pull["consistency_stamp"])

    def test_catalog_job_failure_uses_backoff_window(self) -> None:
        session_sync_push(
            self.store,
            {
                "project_id": "proj_backoff",
                "client_id": "codex",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "seed",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "x"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": ["src/main.py"],
            },
        )

        with patch("memory_hub.catalog_worker.build_catalog_snapshot", side_effect=RuntimeError("boom")):
            first = process_catalog_jobs(self.store, "proj_backoff")
            self.assertEqual(first["processed"], 1)
            self.assertEqual(first["failed"], 1)

        # Retry should be deferred by next_retry_at; immediate run should not re-claim the same job.
        second = process_catalog_jobs(self.store, "proj_backoff")
        self.assertEqual(second["processed"], 0)

    def test_worker_does_not_hold_write_lock_during_indexing(self) -> None:
        session_sync_push(
            self.store,
            {
                "project_id": "proj_lock_window",
                "client_id": "codex",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "seed",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "x"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": ["src/main.py"],
            },
        )

        def fake_snapshot(*_args, **_kwargs):
            # Regression check: indexing phase should run outside write transaction.
            conn = self.store.connect("proj_lock_window")
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE project_meta SET updated_at = updated_at WHERE id = 1")
                conn.commit()
            finally:
                conn.close()
            return {
                "workspace_root": self.workspace.resolve(),
                "files": [],
                "edges": [],
                "full_rebuild": True,
            }

        with patch("memory_hub.catalog_worker.build_catalog_snapshot", side_effect=fake_snapshot):
            result = process_catalog_jobs(self.store, "proj_lock_window")

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], 0)

    def test_concurrent_workers_stress_no_duplicate_claim(self) -> None:
        project_id = "proj_stress"
        total_jobs = 60

        conn = self.store.connect(project_id)
        try:
            for i in range(total_jobs):
                enqueue_catalog_job(
                    conn,
                    project_id=project_id,
                    job_type="incremental_refresh",
                    payload={
                        "files_touched": ["src/main.py"],
                        "memory_version": 1,
                        "sync_id": f"stress_sync_{i}",
                    },
                )
            conn.commit()
        finally:
            conn.close()

        def fast_snapshot(*_args, **_kwargs):
            return {
                "workspace_root": self.workspace.resolve(),
                "files": [
                    {
                        "file_path": "src/main.py",
                        "file_hash": "h1",
                        "language": "python",
                        "import_count": 1,
                    }
                ],
                "edges": [],
                "full_rebuild": False,
            }

        with patch("memory_hub.catalog_worker.build_catalog_snapshot", side_effect=fast_snapshot):
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(lambda _i: process_catalog_jobs(self.store, project_id, limit=20), range(6)))

        self.assertEqual(sum(item["failed"] for item in results), 0)

        conn = self.store.connect(project_id)
        try:
            status_rows = conn.execute(
                """
                SELECT status, COUNT(1) AS cnt
                FROM catalog_jobs
                WHERE project_id = ?
                GROUP BY status
                """,
                (project_id,),
            ).fetchall()
            status_map = {str(row["status"]): int(row["cnt"]) for row in status_rows}
            self.assertEqual(status_map.get("done", 0), total_jobs)
            self.assertEqual(status_map.get("pending", 0), 0)
            self.assertEqual(status_map.get("running", 0), 0)
            self.assertEqual(status_map.get("failed", 0), 0)

            attempts_row = conn.execute(
                """
                SELECT MIN(attempts) AS min_attempts, MAX(attempts) AS max_attempts
                FROM catalog_jobs
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
            assert attempts_row is not None
            self.assertEqual(int(attempts_row["min_attempts"]), 1)
            self.assertEqual(int(attempts_row["max_attempts"]), 1)

            consistency_row = conn.execute(
                """
                SELECT COUNT(1) AS total, COUNT(DISTINCT sync_id) AS distinct_sync
                FROM consistency_links
                WHERE project_id = ? AND sync_id LIKE 'stress_sync_%'
                """,
                (project_id,),
            ).fetchone()
            assert consistency_row is not None
            self.assertEqual(int(consistency_row["total"]), total_jobs)
            self.assertEqual(int(consistency_row["distinct_sync"]), total_jobs)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
