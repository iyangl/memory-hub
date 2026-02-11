import tempfile
import unittest
from pathlib import Path

from memory_hub.store import MemoryStore
from memory_hub.sync import session_sync_pull, session_sync_push


class PullCacheStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "service.py").write_text(
            "from src.repo import fetch\n",
            encoding="utf-8",
        )
        (self.workspace / "src" / "repo.py").write_text(
            "def fetch():\n    return []\n",
            encoding="utf-8",
        )
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)

        session_sync_push(
            self.store,
            {
                "project_id": "proj_cache",
                "client_id": "codex",
                "session_id": "seed",
                "context_stamp": None,
                "session_summary": "seed",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "cache"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": ["src/service.py"],
            },
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_second_pull_hits_catalog_cache(self) -> None:
        first = session_sync_pull(
            self.store,
            {
                "project_id": "proj_cache",
                "client_id": "codex",
                "session_id": "s1",
                "task_prompt": "implement service fetch logic",
                "task_type": "implement",
                "max_tokens": 1200,
            },
        )
        second = session_sync_pull(
            self.store,
            {
                "project_id": "proj_cache",
                "client_id": "codex",
                "session_id": "s2",
                "task_prompt": "implement service fetch logic",
                "task_type": "implement",
                "max_tokens": 1200,
            },
        )

        self.assertIn("catalog", first["trace"])
        self.assertIn("catalog", second["trace"])
        self.assertFalse(bool(first["trace"]["catalog"]["cache_hit"]))
        self.assertTrue(bool(second["trace"]["catalog"]["cache_hit"]))


if __name__ == "__main__":
    unittest.main()
