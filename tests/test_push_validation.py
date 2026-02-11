import tempfile
import unittest
from pathlib import Path

from memory_hub.errors import BusinessError
from memory_hub.server import TOOLS
from memory_hub.store import MemoryStore
from memory_hub.sync import session_sync_push


class PushValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "main.py").write_text("print('ok')\n", encoding="utf-8")
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_invalid_role_deltas_type_raises_business_error(self) -> None:
        with self.assertRaises(BusinessError) as ctx:
            session_sync_push(
                self.store,
                {
                    "project_id": "proj",
                    "client_id": "codex",
                    "session_id": "s1",
                    "session_summary": "x",
                    "role_deltas": "bad-type",
                },
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_PUSH_PAYLOAD")

    def test_invalid_context_stamp_object_raises_business_error(self) -> None:
        with self.assertRaises(BusinessError) as ctx:
            session_sync_push(
                self.store,
                {
                    "project_id": "proj",
                    "client_id": "codex",
                    "session_id": "s1",
                    "context_stamp": {"memory_version": "bad"},
                    "session_summary": "x",
                    "role_deltas": [],
                    "files_touched": [],
                },
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_CONTEXT_STAMP")

    def test_context_stamp_schema_matches_runtime_legacy_support(self) -> None:
        push_tool = next(tool for tool in TOOLS if tool.name == "session.sync.push")
        stamp_types = push_tool.input_schema["properties"]["context_stamp"]["type"]
        self.assertIn("string", stamp_types)

        first = session_sync_push(
            self.store,
            {
                "project_id": "proj",
                "client_id": "codex",
                "session_id": "s1",
                "context_stamp": None,
                "session_summary": "seed",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "x"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": ["main.py"],
            },
        )
        self.assertEqual(first["status"], "ok")

        second = session_sync_push(
            self.store,
            {
                "project_id": "proj",
                "client_id": "codex",
                "session_id": "s2",
                "context_stamp": f"v{first['memory_version']}",
                "session_summary": "legacy stamp accepted",
                "role_deltas": [{"role": "pm", "memory_key": "goal", "value": "y"}],
                "decisions_delta": [],
                "open_loops_new": [],
                "open_loops_closed": [],
                "files_touched": ["main.py"],
            },
        )
        self.assertEqual(second["status"], "ok")


if __name__ == "__main__":
    unittest.main()
