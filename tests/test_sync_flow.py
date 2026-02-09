import tempfile
import unittest
from pathlib import Path

from memory_hub.store import MemoryStore
from memory_hub.sync import (
    session_sync_pull,
    session_sync_push,
    session_sync_resolve_conflict,
)


class SyncFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = MemoryStore(root_dir=self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_push_then_pull_round_trip(self) -> None:
        push = session_sync_push(
            self.store,
            {
                "project_id": "proj_a",
                "client_id": "codex",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "Initialized project goals",
                "role_deltas": [
                    {
                        "role": "pm",
                        "memory_key": "project_goal",
                        "value": "Build role-isolated memory sync",
                        "confidence": 0.95,
                    }
                ],
                "decisions_delta": [
                    {
                        "title": "Use SQLite",
                        "rationale": "Local-first requirement",
                        "status": "active",
                    }
                ],
                "open_loops_new": [
                    {"title": "Define conflict UX", "priority": 1, "owner_role": "architect"}
                ],
                "open_loops_closed": [],
                "files_touched": ["memory_hub/sync.py"],
            },
        )
        self.assertEqual(push["status"], "ok")
        self.assertEqual(push["memory_version"], 1)

        pull = session_sync_pull(
            self.store,
            {
                "project_id": "proj_a",
                "client_id": "codex",
                "session_id": "s2",
                "task_prompt": "please create roadmap for next milestone",
                "task_type": "auto",
                "max_tokens": 1200,
            },
        )
        self.assertEqual(pull["trace"]["resolved_task_type"], "planning")
        self.assertEqual(pull["context_stamp"], "v1")
        self.assertTrue(any(block["role"] == "pm" for block in pull["role_payloads"]))
        self.assertTrue(pull["open_loops_top"])

    def test_conflict_and_merge_note_resolution(self) -> None:
        first = session_sync_push(
            self.store,
            {
                "project_id": "proj_conflict",
                "client_id": "client_a",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "seed",
                "role_deltas": [
                    {
                        "role": "architect",
                        "memory_key": "constraint.runtime",
                        "value": "python",
                    }
                ],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": [],
            },
        )
        self.assertEqual(first["memory_version"], 1)

        second = session_sync_push(
            self.store,
            {
                "project_id": "proj_conflict",
                "client_id": "client_a",
                "session_id": "s2",
                "context_stamp": "v1",
                "session_summary": "a change",
                "role_deltas": [
                    {
                        "role": "architect",
                        "memory_key": "constraint.runtime",
                        "value": "python3.12",
                    }
                ],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": [],
            },
        )
        self.assertEqual(second["status"], "ok")
        self.assertEqual(second["memory_version"], 2)

        stale = session_sync_push(
            self.store,
            {
                "project_id": "proj_conflict",
                "client_id": "client_b",
                "session_id": "s3",
                "context_stamp": "v1",
                "session_summary": "stale update",
                "role_deltas": [
                    {
                        "role": "architect",
                        "memory_key": "constraint.runtime",
                        "value": "cpython",
                    }
                ],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": [],
            },
        )
        self.assertEqual(stale["status"], "needs_resolution")
        self.assertTrue(stale["conflicts"])

        resolved = session_sync_resolve_conflict(
            self.store,
            {
                "project_id": "proj_conflict",
                "client_id": "client_b",
                "session_id": "s3",
                "strategy": "merge_note",
                "session_summary": "resolve conflict",
                "role_deltas": [
                    {
                        "role": "architect",
                        "memory_key": "constraint.runtime",
                        "value": "cpython",
                    }
                ],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": [],
            },
        )
        self.assertEqual(resolved["status"], "ok")
        self.assertGreaterEqual(resolved["memory_version"], 3)

    def test_project_isolation(self) -> None:
        session_sync_push(
            self.store,
            {
                "project_id": "proj_one",
                "client_id": "codex",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "one",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "A"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": [],
            },
        )

        session_sync_push(
            self.store,
            {
                "project_id": "proj_two",
                "client_id": "codex",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "two",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "B"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": [],
            },
        )

        pull_one = session_sync_pull(
            self.store,
            {
                "project_id": "proj_one",
                "client_id": "codex",
                "session_id": "s2",
                "task_prompt": "plan next step",
                "task_type": "planning",
            },
        )
        pull_two = session_sync_pull(
            self.store,
            {
                "project_id": "proj_two",
                "client_id": "codex",
                "session_id": "s2",
                "task_prompt": "plan next step",
                "task_type": "planning",
            },
        )

        values_one = [
            item["value"]
            for block in pull_one["role_payloads"]
            for item in block["items"]
            if item["memory_key"] == "goal"
        ]
        values_two = [
            item["value"]
            for block in pull_two["role_payloads"]
            for item in block["items"]
            if item["memory_key"] == "goal"
        ]

        self.assertEqual(values_one, ["A"])
        self.assertEqual(values_two, ["B"])


if __name__ == "__main__":
    unittest.main()
