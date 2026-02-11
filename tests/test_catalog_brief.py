import tempfile
import unittest
from pathlib import Path

from memory_hub.catalog import catalog_brief_generate
from memory_hub.store import MemoryStore


class CatalogBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "service.py").write_text(
            "import requests\nfrom src.repo import load_data\n",
            encoding="utf-8",
        )
        (self.workspace / "src" / "repo.py").write_text(
            "import sqlite3\n",
            encoding="utf-8",
        )
        self.store = MemoryStore(root_dir=self.root / "db", workspace_root=self.workspace)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_generate_brief_returns_evidence_contract(self) -> None:
        result = catalog_brief_generate(
            self.store,
            {
                "project_id": "proj_catalog",
                "task_prompt": "implement repo loading flow",
                "task_type": "implement",
                "token_budget": 500,
            },
        )

        self.assertIn("catalog_brief", result)
        self.assertIn("catalog_version", result)
        self.assertIn("freshness", result)
        self.assertIsInstance(result["evidence"], list)
        self.assertTrue(result["evidence"])
        first = result["evidence"][0]
        self.assertIn("file", first)
        self.assertIn("reason", first)


if __name__ == "__main__":
    unittest.main()
