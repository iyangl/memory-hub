import tempfile
import time
import unittest
from pathlib import Path

from memory_hub.server import MCPServer, TOOLS
from memory_hub.store import MemoryStore, insert_sync_audit


class SyncAuditListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)
        self.server = MCPServer(self.store)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed_audit(self, project_id: str, sync_id: str, direction: str) -> None:
        conn = self.store.connect(project_id)
        try:
            insert_sync_audit(
                conn,
                sync_id=sync_id,
                project_id=project_id,
                direction=direction,
                client_id="codex",
                session_id="s1",
                request_payload={"sync_id": sync_id},
                response_payload={"status": "ok"},
                latency_ms=1,
            )
            conn.commit()
        finally:
            conn.close()

    def test_tool_is_declared_with_expected_schema(self) -> None:
        tool = next(tool for tool in TOOLS if tool.name == "session.sync.audit.list")
        self.assertEqual(tool.input_schema["required"], ["project_id"])
        self.assertIn("limit", tool.input_schema["properties"])
        self.assertIn("direction", tool.input_schema["properties"])

    def test_list_returns_recent_entries_with_limit(self) -> None:
        self._seed_audit("proj_a", "sync_1", "push")
        time.sleep(0.001)
        self._seed_audit("proj_a", "sync_2", "pull")
        time.sleep(0.001)
        self._seed_audit("proj_a", "sync_3", "resolve_conflict")

        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "session.sync.audit.list",
                    "arguments": {"project_id": "proj_a", "limit": 2},
                },
            }
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertNotIn("error", response)
        content = response["result"]["content"]
        self.assertEqual(content["project_id"], "proj_a")
        self.assertEqual(content["limit"], 2)
        self.assertEqual(content["count"], 2)
        self.assertEqual([item["sync_id"] for item in content["items"]], ["sync_3", "sync_2"])

    def test_list_filters_by_project_and_direction(self) -> None:
        self._seed_audit("proj_a", "sync_a_push", "push")
        self._seed_audit("proj_a", "sync_a_pull", "pull")
        self._seed_audit("proj_b", "sync_b_pull", "pull")

        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "session.sync.audit.list",
                    "arguments": {
                        "project_id": "proj_a",
                        "direction": "pull",
                        "limit": 10,
                    },
                },
            }
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertNotIn("error", response)
        content = response["result"]["content"]
        self.assertEqual(content["count"], 1)
        self.assertEqual(content["items"][0]["sync_id"], "sync_a_pull")
        self.assertEqual(content["items"][0]["project_id"], "proj_a")
        self.assertEqual(content["items"][0]["direction"], "pull")

    def test_invalid_limit_returns_business_error(self) -> None:
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "session.sync.audit.list",
                    "arguments": {"project_id": "proj_a", "limit": 0},
                },
            }
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32010)
        self.assertEqual(response["error"]["data"]["error_code"], "INVALID_AUDIT_QUERY")


if __name__ == "__main__":
    unittest.main()
