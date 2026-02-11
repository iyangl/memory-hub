import tempfile
import unittest
from pathlib import Path

from memory_hub.acceptance import load_labeled_samples, summarize_hit_rate


def _sample_line(project_id: str, expected: tuple[int, int, int], correct: tuple[int, int, int]) -> str:
    return (
        "{"
        f"\"project_id\":\"{project_id}\","
        "\"expected\":{"
        f"\"goal\":{expected[0]},\"constraints\":{expected[1]},\"decisions\":{expected[2]}"
        "},"
        "\"correct\":{"
        f"\"goal\":{correct[0]},\"constraints\":{correct[1]},\"decisions\":{correct[2]}"
        "}"
        "}"
    )


class AcceptanceMetricsTests(unittest.TestCase):
    def test_hit_rate_passes_with_two_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.jsonl"
            lines = []
            for _ in range(10):
                lines.append(_sample_line("project_a", (1, 1, 1), (1, 1, 1)))
                lines.append(_sample_line("project_b", (1, 1, 1), (1, 1, 1)))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            samples = load_labeled_samples(path)
            result = summarize_hit_rate(samples)
            self.assertTrue(result["pass"])
            self.assertGreaterEqual(result["summary"]["overall_hit_rate"], 0.9)

    def test_hit_rate_fails_when_project_sample_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.jsonl"
            lines = []
            for _ in range(10):
                lines.append(_sample_line("project_a", (1, 1, 1), (1, 1, 1)))
            for _ in range(9):
                lines.append(_sample_line("project_b", (1, 1, 1), (1, 1, 1)))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            samples = load_labeled_samples(path)
            result = summarize_hit_rate(samples)
            self.assertFalse(result["pass"])
            self.assertIn("project_b", result["violations"]["insufficient_samples_projects"])


if __name__ == "__main__":
    unittest.main()
