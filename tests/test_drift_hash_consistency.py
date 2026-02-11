import tempfile
import unittest
from pathlib import Path

from memory_hub.catalog_indexer import build_catalog_snapshot
from memory_hub.drift import detect_drift


class DriftHashConsistencyTests(unittest.TestCase):
    def test_snapshot_hash_matches_drift_hash_path_for_crlf_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "main.py"
            file_path.write_bytes(b"print('x')\r\n")

            snapshot = build_catalog_snapshot(root)
            known_hashes = {item["file_path"]: item["file_hash"] for item in snapshot["files"]}

            # Not a git repo -> drift detector must fallback to hash compare.
            result = detect_drift(root, known_hashes)
            self.assertEqual(result["method"], "hash_compare")
            self.assertEqual(result["drift_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
