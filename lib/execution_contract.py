"""execution-contract — build an act-boundary contract from a working set.

Usage: memory-hub execution-contract --working-set-file <path> [--project-root <path>] [--out <file>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lib import envelope, paths
from lib.session_working_set import DURABLE_CANDIDATE_PLACEHOLDER
from lib.utils import atomic_write, sanitize_module_name

REQUIRED_WORKING_SET_FIELDS = (
    "version",
    "task",
    "source_plan",
    "summary",
    "items",
    "priority_reads",
    "primary_evidence_gap",
    "verification_focus",
    "durable_candidates",
)

DISALLOWED_BEHAVIORS = [
    "不要仅凭 task 文本猜来源；先基于 working-set 提供的来源与上下文补证据。",
    "允许 noop；没有值得 durable save 的结论时不要为了保存而保存。",
    "任何非 noop durable 写入都必须先 search 并 read 目标 doc。",
    "不要把 working-set、execution-contract 等 session artifact 原样写回 durable docs。",
    "durable 写回必须通过 memory-hub save --file <save.json>，不要绕过 save correctness core。",
]


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()



def _dedupe_texts(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = _normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result



def _fail_invalid_working_set(message: str, *, details: dict | None = None) -> None:
    envelope.fail("INVALID_WORKING_SET", message, details=details)



def _require_string(value: object, field: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        _fail_invalid_working_set(
            "Working set fields must match the expected types.",
            details={"field": field},
        )
    normalized = _normalize_text(value)
    if not allow_empty and not normalized:
        _fail_invalid_working_set(
            "Working set fields must not be empty.",
            details={"field": field},
        )
    return normalized



def _validate_working_set(working_set: dict) -> None:
    if not isinstance(working_set, dict):
        _fail_invalid_working_set("Working set must be a JSON object.")

    missing_fields = [field for field in REQUIRED_WORKING_SET_FIELDS if field not in working_set]
    if missing_fields:
        _fail_invalid_working_set(
            "Working set is missing required fields.",
            details={"missing_fields": missing_fields},
        )

    _require_string(working_set.get("version"), "version", allow_empty=False)
    _require_string(working_set.get("task"), "task", allow_empty=False)
    _require_string(working_set.get("source_plan"), "source_plan", allow_empty=False)
    _require_string(working_set.get("summary"), "summary", allow_empty=False)

    list_fields = ("items", "priority_reads", "verification_focus", "durable_candidates")
    invalid_list_fields = [field for field in list_fields if not isinstance(working_set.get(field), list)]
    if invalid_list_fields:
        _fail_invalid_working_set(
            "Working set fields must match the expected types.",
            details={"invalid_list_fields": invalid_list_fields},
        )

    for index, item in enumerate(working_set["items"]):
        if not isinstance(item, dict):
            _fail_invalid_working_set(
                "Working set item must be a JSON object.",
                details={"field": f"items[{index}]"},
            )
        _require_string(item.get("summary"), f"items[{index}].summary")
        _require_string(item.get("selected_because"), f"items[{index}].selected_because")
        sources = item.get("sources")
        if not isinstance(sources, list):
            _fail_invalid_working_set(
                "Working set item sources must be a list.",
                details={"field": f"items[{index}].sources"},
            )
        for source_index, source in enumerate(sources):
            _validate_source(source, f"items[{index}].sources[{source_index}]", allow_missing_reason=True)

    for index, source in enumerate(working_set["priority_reads"]):
        _validate_source(source, f"priority_reads[{index}]", allow_missing_reason=False)

    for index, value in enumerate(working_set["verification_focus"]):
        _require_string(value, f"verification_focus[{index}]", allow_empty=False)

    for index, value in enumerate(working_set["durable_candidates"]):
        _require_string(value, f"durable_candidates[{index}]", allow_empty=False)



def _build_known_context(items: list[dict]) -> list[str]:
    return _dedupe_texts([_require_string(item.get("summary"), "items[].summary") for item in items])



def _validate_source(source: object, field: str, *, allow_missing_reason: bool) -> None:
    if not isinstance(source, dict):
        _fail_invalid_working_set(
            "Working set source must be a JSON object.",
            details={"field": field},
        )
    _require_string(source.get("type"), f"{field}.type", allow_empty=False)
    _require_string(source.get("path"), f"{field}.path", allow_empty=False)
    reason = source.get("reason")
    if reason is None and allow_missing_reason:
        return
    _require_string(reason, f"{field}.reason", allow_empty=False)



def _append_allowed_source(allowed_sources: list[dict], seen: set[tuple[str, str]], source: dict, fallback_reason: str) -> None:
    source_type = _require_string(source.get("type"), "allowed_source.type", allow_empty=False)
    path = _require_string(source.get("path"), "allowed_source.path", allow_empty=False)
    reason_value = source.get("reason")
    reason = _require_string(reason_value if reason_value is not None else fallback_reason, "allowed_source.reason", allow_empty=False)
    key = (source_type, path)
    if key in seen:
        return
    seen.add(key)
    allowed_sources.append({
        "type": source_type,
        "path": path,
        "reason": reason,
    })



def _build_allowed_sources(working_set: dict) -> list[dict]:
    allowed_sources: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for source in working_set.get("priority_reads", []):
        _append_allowed_source(allowed_sources, seen, source, "priority read")

    for item in working_set.get("items", []):
        fallback_reason = _require_string(item.get("selected_because"), "items[].selected_because", allow_empty=False)
        for source in item.get("sources", []):
            _append_allowed_source(allowed_sources, seen, source, fallback_reason)

    return allowed_sources



def build_execution_contract(working_set: dict, source_working_set: str) -> dict:
    _validate_working_set(working_set)

    primary_evidence_gap = working_set.get("primary_evidence_gap")
    if primary_evidence_gap is not None:
        primary_evidence_gap = _require_string(primary_evidence_gap, "primary_evidence_gap", allow_empty=False)

    verification_focus = _dedupe_texts([
        _require_string(value, "verification_focus[]", allow_empty=False)
        for value in working_set.get("verification_focus", [])
    ])
    durable_candidates = [
        candidate
        for candidate in (
            _require_string(value, "durable_candidates[]", allow_empty=False)
            for value in working_set.get("durable_candidates", [])
        )
        if candidate != DURABLE_CANDIDATE_PLACEHOLDER
    ]

    task = _require_string(working_set.get("task"), "task", allow_empty=False)
    source_plan = _require_string(working_set.get("source_plan"), "source_plan", allow_empty=False)
    goal = task

    return {
        "version": "1",
        "task": task,
        "source_working_set": source_working_set,
        "source_plan": source_plan,
        "goal": goal,
        "known_context": _build_known_context(working_set.get("items", [])),
        "primary_evidence_gap": primary_evidence_gap,
        "allowed_sources": _build_allowed_sources(working_set),
        "disallowed_behaviors": list(DISALLOWED_BEHAVIORS),
        "verification_focus": verification_focus,
        "success_criteria": [f"解决 {primary_evidence_gap}"] if primary_evidence_gap else [],
        "required_evidence": [primary_evidence_gap] if primary_evidence_gap else [],
        "durable_candidates": durable_candidates,
    }



def _default_output_path(working_set: dict, project_root: Path | None) -> Path:
    task = _require_string(working_set.get("task"), "task", allow_empty=False)
    slug = sanitize_module_name(task[:80])
    if slug == "unnamed":
        task_hash = hashlib.sha1(task.encode("utf-8")).hexdigest()[:8]
        slug = f"execution-contract-{task_hash}"
    return paths.session_file_path(f"{slug}-execution-contract", project_root=project_root)



def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub execution-contract")
    parser.add_argument("--working-set-file", required=True, help="Path to working-set JSON file")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parser.add_argument("--out", help="Optional output file for execution-contract JSON")
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    working_set_file = Path(parsed.working_set_file)

    try:
        working_set = json.loads(working_set_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        envelope.fail("FILE_NOT_FOUND", f"Working set file not found: {parsed.working_set_file}")
    except json.JSONDecodeError as exc:
        envelope.fail("INVALID_JSON", f"Failed to parse working set file: {exc}")

    result = build_execution_contract(working_set, str(working_set_file))

    if parsed.out:
        out_path = Path(parsed.out)
    else:
        out_path = _default_output_path(working_set, project_root)
    atomic_write(out_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    payload = dict(result)
    payload["output_file"] = str(out_path)
    envelope.ok(payload)
