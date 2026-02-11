import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from memory_hub.drift import detect_drift


class DriftFallbackTests(unittest.TestCase):
    def test_fallback_to_hash_when_git_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "main.py"
            file_path.write_text("print('hello')\n", encoding="utf-8")
            known_hash = hashlib.sha256(file_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()

            result = detect_drift(root, {"main.py": known_hash})
            self.assertEqual(result["method"], "hash_compare")
            self.assertEqual(result["drift_score"], 0.0)

            file_path.write_text("print('hello world')\n", encoding="utf-8")
            changed = detect_drift(root, {"main.py": known_hash})
            self.assertEqual(changed["method"], "hash_compare")
            self.assertGreater(changed["drift_score"], 0.0)

    def test_git_mode_includes_untracked_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "-C", str(root), "init"], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "memory-hub@example.com"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Memory Hub"],
                check=True,
                capture_output=True,
                text=True,
            )

            tracked = root / "main.py"
            tracked.write_text("print('tracked')\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "main.py"], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-m", "init"],
                check=True,
                capture_output=True,
                text=True,
            )
            known_hash = hashlib.sha256(tracked.read_bytes()).hexdigest()

            untracked = root / "new_file.py"
            untracked.write_text("print('new')\n", encoding="utf-8")

            result = detect_drift(root, {"main.py": known_hash})
            self.assertEqual(result["method"], "git_diff")
            self.assertIn("new_file.py", result["changed_files"])
            self.assertGreater(result["drift_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
