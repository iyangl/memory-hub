"""working-set — build a task-scoped session working set from a recall plan.

Usage: memory-hub working-set --plan-file <path> [--project-root <path>] [--out <file>]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lib import envelope, paths
from lib.utils import (
    COMMON_FACET_KEYWORDS,
    COMMON_FACET_ORDER_BY_BUCKET,
    COMMON_GENERIC_SECTION_HEADINGS,
    atomic_write,
    sanitize_module_name,
)

WORKING_SET_VERSION = "2"
MAX_ITEMS = 6
MAX_PRIORITY_READS = 4
MAX_BULLETS_PER_ITEM = 4
MAX_TOTAL_BULLETS = 16
MAX_EVIDENCE_GAPS = 5
MAX_DURABLE_CANDIDATES = 3
MAX_FACETS_PER_FIELD = 4
DURABLE_CANDIDATE_PLACEHOLDER = "仅当 working set 中的结论被确认会影响未来动作时，才在 /save 阶段提炼进长期 docs。"
DOC_KIND_BY_BUCKET = {"architect": "decision", "pm": "decision", "qa": "verification", "dev": "constraint"}
KIND_TO_FACET = {"decision": "decision_points", "constraint": "constraints", "verification": "verification_focus"}
FACET_FIELDS = ("decision_points", "constraints", "risks", "verification_focus")
FACET_LABELS = {"decision_points": "决策", "constraints": "约束", "risks": "风险", "verification_focus": "验证"}
FACET_ORDER_BY_BUCKET = {
    bucket: tuple(KIND_TO_FACET.get(name, "risks") for name in order)
    for bucket, order in COMMON_FACET_ORDER_BY_BUCKET.items()
}
FACET_KEYWORDS = {
    KIND_TO_FACET.get(name, "risks"): keywords
    for name, keywords in COMMON_FACET_KEYWORDS.items()
}
GENERIC_SECTION_HEADINGS = COMMON_GENERIC_SECTION_HEADINGS


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


def _empty_facets() -> dict[str, list[str]]:
    return {field: [] for field in FACET_FIELDS}


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
        section_map.setdefault(heading, [])
        section_map[heading] = _unique_strings(section_map[heading] + body)
    return section_map


def _facet_rank(bucket: str, facet: str) -> int:
    order = FACET_ORDER_BY_BUCKET.get(bucket, FACET_FIELDS)
    try:
        return order.index(facet)
    except ValueError:
        return len(order)


def _classify_doc_section(bucket: str, heading: str, body: list[str]) -> tuple[str | None, int]:
    body_text = " ".join(body[:2])
    best_facet: str | None = None
    best_score = 0
    for facet, keywords in FACET_KEYWORDS.items():
        score = sum(100 - idx * 10 for idx, keyword in enumerate(keywords) if keyword in heading)
        score += sum(15 - idx * 2 for idx, keyword in enumerate(keywords) if keyword in body_text)
        if score <= 0:
            continue
        if best_facet is None or score > best_score or (score == best_score and _facet_rank(bucket, facet) < _facet_rank(bucket, best_facet)):
            best_facet = facet
            best_score = score
    return best_facet, best_score


def _is_generic_heading_for_facet(heading: str, facet: str) -> bool:
    normalized = re.sub(r"[\s:：\-_/()（）]", "", heading)
    if heading in GENERIC_SECTION_HEADINGS:
        return True
    if len(normalized) > 4:
        return False
    return any(keyword in normalized for keyword in FACET_KEYWORDS.get(facet, ()))



def _section_values(heading: str, body: list[str], facet: str) -> list[str]:
    if not body:
        return [heading] if heading else []
    if _is_generic_heading_for_facet(heading, facet):
        return _unique_strings(body)
    return _unique_strings([f"{heading}：{line}" for line in body])


def _doc_item(bucket: str, file: str, project_root: Path | None, reason: str, priority: int) -> dict:
    file_path = paths.file_path(bucket, file, project_root)
    content = _read_text(file_path)
    kind = DOC_KIND_BY_BUCKET.get(bucket, "constraint")
    default_facet = KIND_TO_FACET[kind]
    facets = _empty_facets()
    ranked_sections: list[tuple[int, int, str, list[str]]] = []

    for index, (heading, body) in enumerate(_parse_sections(content)):
        summary = f"{heading}：{body[0]}" if heading and body else ""
        facet, score = _classify_doc_section(bucket, heading, body)
        if facet:
            facets[facet].extend(_section_values(heading, body, facet))
            ranked_sections.append((_facet_rank(bucket, facet), -score, summary or heading, body))

    for field in FACET_FIELDS:
        facets[field] = _unique_strings(facets[field])
    if not any(facets.values()):
        fallback = _extract_section_summary(content) or reason
        facets[default_facet] = [fallback]

    summary = reason
    if ranked_sections:
        _, _, preferred, _ = sorted(ranked_sections, key=lambda item: (item[0], item[1], item[2]))[0]
        summary = preferred or summary
    else:
        summary = _extract_section_summary(content) or reason

    bullets = []
    for field in FACET_FIELDS:
        if facets[field]:
            bullets.append(f"{FACET_LABELS[field]}: {facets[field][0]}")
    return {
        "kind": kind,
        "title": f"{bucket}/{file}",
        "summary": summary,
        "bullets": bullets or [reason],
        "sources": [{"type": "doc", "path": str(file_path)}],
        "selected_because": reason,
        "decision_points": facets["decision_points"],
        "constraints": facets["constraints"],
        "risks": facets["risks"],
        "verification_focus": facets["verification_focus"],
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
        "decision_points": [],
        "constraints": _unique_strings(constraints),
        "risks": _unique_strings(risks),
        "verification_focus": _unique_strings(verification),
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
    for field in FACET_FIELDS:
        existing[field] = _unique_strings(existing.get(field, []) + new_item.get(field, []))
    reasons = _unique_strings([*existing["selected_because"].split("；"), *new_item["selected_because"].split("；")])
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
        trimmed["bullets"] = bullets or [trimmed["selected_because"]]
        trimmed.pop("_priority", None)
        trimmed.pop("_source_order", None)
        limited.append(trimmed)
        total_bullets += len(trimmed["bullets"])
    return limited


def _build_priority_reads(plan: dict, project_root: Path | None) -> list[dict]:
    candidates: list[tuple[int, int, dict]] = []
    for doc in plan.get("recommended_docs", []):
        file_path = paths.file_path(doc["bucket"], doc["file"], project_root)
        if file_path.exists():
            candidates.append((int(doc.get("priority", 999)), 0, {"type": "doc", "path": str(file_path), "reason": doc["reason"]}))
    for module in plan.get("recommended_modules", []):
        module_file = paths.module_file_path(sanitize_module_name(module["name"]), project_root)
        if module_file.exists():
            candidates.append((int(module.get("priority", 999)), 1, {"type": "module", "path": str(module_file), "reason": module["reason"]}))

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


def _aggregate_facets(items: list[dict]) -> dict[str, list[str]]:
    aggregated = _empty_facets()
    for item in items:
        for field in FACET_FIELDS:
            aggregated[field].extend(item.get(field, []))
    return {
        field: _unique_strings(values)[:MAX_FACETS_PER_FIELD]
        for field, values in aggregated.items()
    }


def _build_durable_candidates(items: list[dict]) -> list[str]:
    candidates: list[str] = []
    for item in items:
        for field in FACET_FIELDS:
            label = FACET_LABELS[field]
            for value in item.get(field, []):
                candidates.append(f"{item['title']}：{label}: {value}")
                if len(_unique_strings(candidates)) >= MAX_DURABLE_CANDIDATES:
                    result = _unique_strings(candidates)[:MAX_DURABLE_CANDIDATES]
                    return result or [DURABLE_CANDIDATE_PLACEHOLDER]
    result = _unique_strings(candidates)[:MAX_DURABLE_CANDIDATES]
    return result or [DURABLE_CANDIDATE_PLACEHOLDER]


def build_working_set(plan: dict, project_root: Path | None = None, source_plan: str | None = None) -> dict:
    if plan.get("recall_level") != "deep":
        envelope.fail("WORKING_SET_NOT_NEEDED", "working-set only applies to deep recall plans.", details={"recall_level": plan.get("recall_level")})

    merged_items: dict[tuple[str, str], dict] = {}
    for doc in plan.get("recommended_docs", []):
        file_path = paths.file_path(doc["bucket"], doc["file"], project_root)
        if not file_path.exists():
            continue
        item = _doc_item(doc["bucket"], doc["file"], project_root, doc["reason"], int(doc.get("priority", 999)))
        merged_items.setdefault((item["kind"], item["title"]), item)
        if merged_items[(item["kind"], item["title"])] is not item:
            _merge_item(merged_items[(item["kind"], item["title"])], item)
    for module in plan.get("recommended_modules", []):
        module_file = paths.module_file_path(sanitize_module_name(module["name"]), project_root)
        if not module_file.exists():
            continue
        item = _module_item(module["name"], project_root, module["reason"], int(module.get("priority", 999)))
        merged_items.setdefault((item["kind"], item["title"]), item)
        if merged_items[(item["kind"], item["title"])] is not item:
            _merge_item(merged_items[(item["kind"], item["title"])], item)

    ordered_items = sorted(merged_items.values(), key=lambda item: (item["_priority"], item["_source_order"], item["title"]))
    aggregated_facets = _aggregate_facets(ordered_items)
    items = _compress_items(ordered_items)
    why_these = _unique_strings(plan.get("why_these", []))
    return {
        "version": WORKING_SET_VERSION,
        "task": plan.get("task", ""),
        "source_plan": source_plan or "<direct-build>",
        "summary": " ".join(why_these[:2]).strip() or "当前任务需要多源 recall 后再执行。",
        "items": items,
        "priority_reads": _build_priority_reads(plan, project_root),
        "evidence_gaps": _unique_strings(plan.get("evidence_gaps", []))[:MAX_EVIDENCE_GAPS],
        "primary_evidence_gap": plan.get("primary_evidence_gap"),
        "decision_points": aggregated_facets["decision_points"],
        "constraints": aggregated_facets["constraints"],
        "risks": aggregated_facets["risks"],
        "verification_focus": aggregated_facets["verification_focus"],
        "durable_candidates": _build_durable_candidates(ordered_items),
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
