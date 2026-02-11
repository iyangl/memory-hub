import tempfile
import unittest
from pathlib import Path

from memory_hub.server import MCPServer
from memory_hub.store import MemoryStore


class ServerErrorAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)
        self.server = MCPServer(self.store)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_business_error_is_audited(self) -> None:
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "session.sync.push",
                    "arguments": {
                        "project_id": "proj_err",
                        "client_id": "codex",
                        "session_id": "s1",
                        "role_deltas": [],
                    },
                },
            }
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32010)

        conn = self.store.connect("proj_err")
        try:
            row = conn.execute(
                """
                SELECT direction, error_code, latency_ms
                FROM sync_audit
                WHERE project_id = 'proj_err'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["direction"], "push")
            self.assertEqual(row["error_code"], "INVALID_PUSH_PAYLOAD")
            self.assertGreaterEqual(int(row["latency_ms"]), 0)
        finally:
            conn.close()

    def test_catalog_error_uses_catalog_direction(self) -> None:
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "catalog.brief.generate",
                    "arguments": {
                        "project_id": "proj_catalog_err",
                    },
                },
            }
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32010)

        conn = self.store.connect("proj_catalog_err")
        try:
            row = conn.execute(
                """
                SELECT direction, error_code, latency_ms
                FROM sync_audit
                WHERE project_id = 'proj_catalog_err'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["direction"], "catalog_brief")
            self.assertEqual(row["error_code"], "MISSING_REQUIRED_FIELDS")
            self.assertGreaterEqual(int(row["latency_ms"]), 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
