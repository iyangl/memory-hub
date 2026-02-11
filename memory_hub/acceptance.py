from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .errors import BusinessError

CATEGORIES = ("goal", "constraints", "decisions")


@dataclass(frozen=True)
class LabeledSample:
    project_id: str
    expected: Dict[str, int]
    correct: Dict[str, int]

    @property
    def expected_total(self) -> int:
        return sum(self.expected.values())

    @property
    def correct_total(self) -> int:
        return sum(self.correct.values())


def _ensure_non_negative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise BusinessError(
            error_code="INVALID_ACCEPTANCE_SAMPLE",
            message=f"'{field}' must be a non-negative integer",
            details={"field": field, "value": value},
            retryable=False,
        )
    return value


def _parse_category_map(raw: Any, field: str) -> Dict[str, int]:
    if not isinstance(raw, dict):
        raise BusinessError(
            error_code="INVALID_ACCEPTANCE_SAMPLE",
            message=f"'{field}' must be an object",
            details={"field": field},
            retryable=False,
        )
    parsed: Dict[str, int] = {}
    for category in CATEGORIES:
        parsed[category] = _ensure_non_negative_int(raw.get(category, 0), f"{field}.{category}")
    return parsed


def parse_labeled_sample(raw: Dict[str, Any], line_no: int) -> LabeledSample:
    project_id = raw.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        raise BusinessError(
            error_code="INVALID_ACCEPTANCE_SAMPLE",
            message="project_id must be a non-empty string",
            details={"line": line_no},
            retryable=False,
        )

    expected = _parse_category_map(raw.get("expected"), "expected")
    correct = _parse_category_map(raw.get("correct"), "correct")

    for category in CATEGORIES:
        if correct[category] > expected[category]:
            raise BusinessError(
                error_code="INVALID_ACCEPTANCE_SAMPLE",
                message=f"correct.{category} cannot exceed expected.{category}",
                details={"line": line_no, "category": category},
                retryable=False,
            )

    return LabeledSample(project_id=project_id.strip(), expected=expected, correct=correct)


def load_labeled_samples(path: Path) -> List[LabeledSample]:
    rows: List[LabeledSample] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        content = line.strip()
        if not content:
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise BusinessError(
                error_code="INVALID_ACCEPTANCE_SAMPLE",
                message="invalid json line",
                details={"line": line_no, "error": str(exc)},
                retryable=False,
            ) from exc
        if not isinstance(payload, dict):
            raise BusinessError(
                error_code="INVALID_ACCEPTANCE_SAMPLE",
                message="each line must be a JSON object",
                details={"line": line_no},
                retryable=False,
            )
        rows.append(parse_labeled_sample(payload, line_no))
    return rows


def _rate(correct: int, expected: int) -> float:
    if expected <= 0:
        return 1.0
    return correct / expected


def summarize_hit_rate(
    samples: Iterable[LabeledSample],
    *,
    min_projects: int = 2,
    min_samples_per_project: int = 10,
    overall_threshold: float = 0.9,
    project_threshold: float = 0.85,
) -> Dict[str, Any]:
    project_stats: Dict[str, Dict[str, Any]] = {}
    total_expected = 0
    total_correct = 0

    for sample in samples:
        stats = project_stats.setdefault(
            sample.project_id,
            {"samples": 0, "expected": 0, "correct": 0},
        )
        stats["samples"] += 1
        stats["expected"] += sample.expected_total
        stats["correct"] += sample.correct_total

        total_expected += sample.expected_total
        total_correct += sample.correct_total

    project_results = {}
    min_sample_failures = []
    threshold_failures = []
    for project_id, stats in sorted(project_stats.items()):
        hit_rate = _rate(int(stats["correct"]), int(stats["expected"]))
        project_results[project_id] = {
            "samples": int(stats["samples"]),
            "expected": int(stats["expected"]),
            "correct": int(stats["correct"]),
            "hit_rate": hit_rate,
        }
        if int(stats["samples"]) < min_samples_per_project:
            min_sample_failures.append(project_id)
        if hit_rate < project_threshold:
            threshold_failures.append(project_id)

    overall_hit_rate = _rate(total_correct, total_expected)
    has_min_projects = len(project_results) >= min_projects
    overall_pass = overall_hit_rate >= overall_threshold
    project_pass = not threshold_failures
    sample_count_pass = not min_sample_failures

    return {
        "pass": bool(has_min_projects and overall_pass and project_pass and sample_count_pass),
        "summary": {
            "project_count": len(project_results),
            "overall_expected": total_expected,
            "overall_correct": total_correct,
            "overall_hit_rate": overall_hit_rate,
            "overall_threshold": overall_threshold,
            "project_threshold": project_threshold,
            "min_projects": min_projects,
            "min_samples_per_project": min_samples_per_project,
        },
        "projects": project_results,
        "violations": {
            "insufficient_projects": not has_min_projects,
            "overall_threshold_failed": not overall_pass,
            "project_threshold_failed": threshold_failures,
            "insufficient_samples_projects": min_sample_failures,
        },
    }
