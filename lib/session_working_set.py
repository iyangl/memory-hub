"""working-set — build a task-scoped session working set from a recall plan.

Usage: memory-hub working-set --plan-file <path> [--project-root <path>] [--out <file>]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lib import envelope, paths
from lib.utils import atomic_write, sanitize_module_name

MAX_ITEMS = 6
MAX_PRIORITY_READS = 4
MAX_BULLETS_PER_ITEM = 4
MAX_TOTAL_BULLETS = 16
MAX_EVIDENCE_GAPS = 5
MAX_DURABLE_CANDIDATES = 3
DURABLE_CANDIDATE_PLACEHOLDER = "仅当 working set 中的结论被确认会影响未来动作时，才在 /save 阶段提炼进长期 docs。"
DOC_KIND_BY_BUCKET = {
    "architect": "decision",
    "pm": "decision",
    "qa": "verification",
    "dev": "constraint",
}
DOC_SECTION_PRIORITY = {
    "decision": ("决策", "规则", "结论", "口径", "范围", "原则"),
    "verification": ("验证", "测试", "策略", "回归", "风险"),
    "constraint": ("约束", "约定", "规范", "流程", "命名"),
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_line(line: str) -> str:
    return _normalize_text(line.lstrip("- "))


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _extract_section_summary(content: str) -> str:
    lines = [_normalize_line(line) for line in content.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            rest = [item for item in lines[idx + 1: idx + 4] if not item.startswith("## ")]
            return " ".join(rest[:2]).strip() or line[3:].strip()
    return " ".join(lines[:2]).strip()


def _parse_sections(content: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_body
        if current_heading is None:
            return
        sections.append((current_heading, _unique_strings(current_body)))
        current_heading = None
        current_body = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            flush()
            current_heading = stripped[3:].strip()
            continue
        if current_heading is not None and stripped:
            current_body.append(_normalize_line(stripped))

    flush()
    return sections


def _section_map(content: str) -> dict[str, list[str]]:
    section_map: dict[str, list[str]] = {}
    for heading, body in _parse_sections(content):
        if heading not in section_map:
            section_map[heading] = []
        section_map[heading].extend(body)
        section_map[heading] = _unique_strings(section_map[heading])
    return section_map


def _doc_item(bucket: str, file: str, project_root: Path | None, reason: str, priority: int) -> dict:
    file_path = paths.file_path(bucket, file, project_root)
    content = _read_text(file_path)
    sections = _parse_sections(content)
    kind = DOC_KIND_BY_BUCKET.get(bucket, "constraint")
    keywords = DOC_SECTION_PRIORITY.get(kind, ())

    ranked: list[tuple[int, str, list[str]]] = []
    for heading, body in sections:
        score = sum(100 - idx * 10 for idx, keyword in enumerate(keywords) if keyword in heading)
        if body:
            score += min(len(body), 3)
        ranked.append((score, heading, body))

    ranked.sort(key=lambda item: (item[0], len(item[2])), reverse=True)
    heading = ""
    body: list[str] = []
    if ranked:
        _, heading, body = ranked[0]

    summary = f"{heading}：{body[0]}" if heading and body else (_extract_section_summary(content) or reason)
    bullets = body[:3] if body else [reason]
    return {
        "kind": kind,
        "title": f"{bucket}/{file}",
        "summary": summary,
        "bullets": bullets,
        "sources": [{"type": "doc", "path": str(file_path)}],
        "selected_because": reason,
        "_priority": priority,
        "_source_order": 0,
    }


def _module_item(module_name: str, project_root: Path | None, reason: str, priority: int) -> dict:
    module_file = paths.module_file_path(sanitize_module_name(module_name), project_root)
    content = _read_text(module_file)
    sections = _section_map(content)
    read_when = " ".join(sections.get("何时阅读", [])[:2]).strip()
    entry_points = [item.strip("`") for item in sections.get("推荐入口", [])]
    constraints = sections.get("隐含约束", [])
    risks = sections.get("主要风险", [])
    verification = sections.get("验证重点", [])

    bullets = []
    if constraints:
        bullets.append(f"约束: {constraints[0]}")
    if risks:
        bullets.append(f"风险: {risks[0]}")
    if verification:
        bullets.append(f"验证: {verification[0]}")
    for entry_point in entry_points[:2]:
        bullets.append(f"入口: {entry_point}")

    return {
        "kind": "navigation",
        "title": module_name,
        "summary": read_when or _extract_section_summary(content) or reason,
        "bullets": _unique_strings(bullets) or [reason],
        "sources": [{"type": "module", "path": str(module_file)}],
        "selected_because": reason,
        "_priority": priority,
        "_source_order": 1,
    }


def _merge_sources(existing: list[dict], new_sources: list[dict]) -> list[dict]:
    merged = list(existing)
    seen = {(item.get("type"), item.get("path")) for item in merged}
    for source in new_sources:
        key = (source.get("type"), source.get("path"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(source)
    return merged


def _merge_item(existing: dict, new_item: dict) -> None:
    existing["summary"] = existing["summary"] or new_item["summary"]
    existing["bullets"] = _unique_strings(existing["bullets"] + new_item["bullets"])
    existing["sources"] = _merge_sources(existing["sources"], new_item["sources"])
    reasons = _unique_strings([
        *existing["selected_because"].split("；"),
        *new_item["selected_because"].split("；"),
    ])
    existing["selected_because"] = "；".join(reasons)
    existing["_priority"] = min(existing["_priority"], new_item["_priority"])
    existing["_source_order"] = min(existing["_source_order"], new_item["_source_order"])


def _compress_items(items: list[dict]) -> list[dict]:
    limited: list[dict] = []
    total_bullets = 0

    for item in items[:MAX_ITEMS]:
        remaining = MAX_TOTAL_BULLETS - total_bullets
        if remaining <= 0:
            break
        trimmed = dict(item)
        bullets = _unique_strings(trimmed.get("bullets", []))[: min(MAX_BULLETS_PER_ITEM, remaining)]
        if not bullets:
            bullets = [trimmed["selected_because"]]
        trimmed["bullets"] = bullets
        trimmed.pop("_priority", None)
        trimmed.pop("_source_order", None)
        limited.append(trimmed)
        total_bullets += len(bullets)

    return limited


def _build_priority_reads(plan: dict, project_root: Path | None) -> list[dict]:
    candidates: list[tuple[int, int, dict]] = []

    for doc in plan.get("recommended_docs", []):
        file_path = paths.file_path(doc["bucket"], doc["file"], project_root)
        if not file_path.exists():
            continue
        candidates.append((
            int(doc.get("priority", 999)),
            0,
            {
                "type": "doc",
                "path": str(file_path),
                "reason": doc["reason"],
            },
        ))

    for module in plan.get("recommended_modules", []):
        module_file = paths.module_file_path(sanitize_module_name(module["name"]), project_root)
        if not module_file.exists():
            continue
        candidates.append((
            int(module.get("priority", 999)),
            1,
            {
                "type": "module",
                "path": str(module_file),
                "reason": module["reason"],
            },
        ))

    priority_reads: list[dict] = []
    seen_paths: set[str] = set()
    for _, _, item in sorted(candidates, key=lambda candidate: (candidate[0], candidate[1], candidate[2]["path"])):
        if item["path"] in seen_paths:
            continue
        seen_paths.add(item["path"])
        priority_reads.append(item)
        if len(priority_reads) >= MAX_PRIORITY_READS:
            break
    return priority_reads


def _build_durable_candidates(items: list[dict]) -> list[str]:
    candidates: list[str] = []
    for item in items:
        if item["kind"] in {"decision", "constraint", "verification"}:
            candidates.append(f"{item['title']}：{item['summary']}")
            continue
        for bullet in item.get("bullets", []):
            if bullet.startswith(("约束:", "风险:", "验证:")):
                candidates.append(f"{item['title']}：{bullet}")
        if len(candidates) >= MAX_DURABLE_CANDIDATES:
            break

    candidates = _unique_strings(candidates)[:MAX_DURABLE_CANDIDATES]
    if candidates:
        return candidates
    return [DURABLE_CANDIDATE_PLACEHOLDER]


def _build_verification_focus(items: list[dict]) -> list[str]:
    focus: list[str] = []
    for item in items:
        for bullet in item.get("bullets", []):
            if not bullet.startswith("验证:"):
                continue
            focus.append(bullet[len("验证:"):].strip())
    return _unique_strings(focus)


def build_working_set(plan: dict, project_root: Path | None = None, source_plan: str | None = None) -> dict:
    if plan.get("recall_level") != "deep":
        envelope.fail(
            "WORKING_SET_NOT_NEEDED",
            "working-set only applies to deep recall plans.",
            details={"recall_level": plan.get("recall_level")},
        )

    merged_items: dict[tuple[str, str], dict] = {}

    for doc in plan.get("recommended_docs", []):
        file_path = paths.file_path(doc["bucket"], doc["file"], project_root)
        if not file_path.exists():
            continue
        item = _doc_item(doc["bucket"], doc["file"], project_root, doc["reason"], int(doc.get("priority", 999)))
        key = (item["kind"], item["title"])
        if key in merged_items:
            _merge_item(merged_items[key], item)
        else:
            merged_items[key] = item

    for module in plan.get("recommended_modules", []):
        module_file = paths.module_file_path(sanitize_module_name(module["name"]), project_root)
        if not module_file.exists():
            continue
        item = _module_item(module["name"], project_root, module["reason"], int(module.get("priority", 999)))
        key = (item["kind"], item["title"])
        if key in merged_items:
            _merge_item(merged_items[key], item)
        else:
            merged_items[key] = item

    ordered_items = sorted(
        merged_items.values(),
        key=lambda item: (item["_priority"], item["_source_order"], item["title"]),
    )
    items = _compress_items(ordered_items)
    evidence_gaps = _unique_strings(plan.get("evidence_gaps", []))[:MAX_EVIDENCE_GAPS]
    primary_evidence_gap = plan.get("primary_evidence_gap")
    why_these = _unique_strings(plan.get("why_these", []))

    return {
        "version": "1",
        "task": plan.get("task", ""),
        "source_plan": source_plan or "",
        "summary": " ".join(why_these[:2]).strip() or "当前任务需要多源 recall 后再执行。",
        "items": items,
        "priority_reads": _build_priority_reads(plan, project_root),
        "evidence_gaps": evidence_gaps,
        "primary_evidence_gap": primary_evidence_gap,
        "verification_focus": _build_verification_focus(items),
        "durable_candidates": _build_durable_candidates(items),
    }


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub working-set")
    parser.add_argument("--plan-file", required=True, help="Path to recall-plan JSON file")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parser.add_argument("--out", help="Optional output file for working set JSON")
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    plan_file = Path(parsed.plan_file)
    if not plan_file.exists():
        envelope.fail("FILE_NOT_FOUND", f"Plan file not found: {parsed.plan_file}")

    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        envelope.fail("INVALID_JSON", f"Failed to parse plan file: {e}")

    result = build_working_set(plan, project_root, str(plan_file))

    if parsed.out:
        out_path = Path(parsed.out)
    else:
        slug = sanitize_module_name(plan.get("task", "working-set")[:80])
        out_path = paths.session_file_path(slug or "working-set", project_root=project_root)
    atomic_write(out_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    payload = dict(result)
    payload["output_file"] = str(out_path)
    envelope.ok(payload)
