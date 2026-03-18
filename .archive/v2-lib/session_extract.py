"""Session distillation helpers for unified project memory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lib.durable_errors import DurableMemoryError
from lib.project_memory_view import read_project_memory, search_project_memory
from lib.project_memory_write import capture_memory, update_memory

EXPLICIT_PATTERN = re.compile(r"^(docs|durable|dual)\[([^\]]+)\]:\s*(.+)$", re.IGNORECASE)
SPLIT_PATTERN = re.compile(r"\n\s*\n+")
DOC_HINTS = {
    "qa": ("测试", "验收", "quality", "qa", "回归"),
    "dev": ("命名", "风格", "约定", "格式", "lint"),
    "pm": ("需求", "范围", "backlog", "roadmap", "里程碑", "计划", "mvp"),
}
CONSTRAINT_HINTS = ("必须", "禁止", "不允许", "只能", "不能", "必须先", "required", "must", "never")
DECISION_HINTS = ("决定", "采用", "选择", "固定", "路线", "方案", "roadmap")
PREFERENCE_HINTS = ("我偏好", "我习惯", "prefer", "默认使用", "倾向于")
IDENTITY_HINTS = ("我是", "我使用", "我的环境", "我在", "mac", "windows", "linux")
DOC_MATCH_THRESHOLD = 8
DURABLE_MATCH_THRESHOLD = 8


def extract_session_memory(
    project_root: Path | None,
    *,
    transcript: str,
    source_label: str,
    created_by: str = "session-extract",
    max_candidates: int = 8,
) -> dict[str, Any]:
    """Extract candidate memory items from a session transcript."""
    candidates = extract_session_candidates(transcript, max_candidates=max_candidates)
    items = [_apply_candidate(project_root, candidate, source_label=source_label, created_by=created_by) for candidate in candidates]
    return {
        "source_label": source_label,
        "transcript_length": len(transcript),
        "candidate_count": len(candidates),
        "applied_count": len(items),
        "items": items,
    }


def extract_session_candidates(transcript: str, *, max_candidates: int) -> list[dict[str, Any]]:
    """Extract candidate items from transcript paragraphs."""
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for chunk in _split_chunks(transcript):
        candidate = _build_candidate(chunk)
        if candidate is None:
            continue
        marker = (candidate["route"], candidate["title"].strip().lower())
        if marker in seen:
            continue
        seen.add(marker)
        candidates.append(candidate)
        if len(candidates) >= max_candidates:
            break
    return candidates


def _split_chunks(transcript: str) -> list[str]:
    normalized = transcript.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    chunks: list[str] = []
    for block in SPLIT_PATTERN.split(normalized):
        lines = [re.sub(r"^\s*[-*]\s*", "", line).strip() for line in block.splitlines()]
        text = " ".join(line for line in lines if line)
        if text:
            chunks.append(text)
    return chunks


def _build_candidate(chunk: str) -> dict[str, Any] | None:
    explicit = _parse_explicit(chunk)
    if explicit is not None:
        return explicit
    route = _infer_route(chunk)
    if route is None:
        return None
    doc_domain = _infer_doc_domain(chunk, route)
    memory_type = _infer_memory_type(chunk, route)
    return _candidate_payload(
        route=route,
        doc_domain=doc_domain,
        memory_type=memory_type,
        title=_title_from_text(chunk),
        content=chunk,
    )


def _parse_explicit(chunk: str) -> dict[str, Any] | None:
    match = EXPLICIT_PATTERN.match(chunk.strip())
    if match is None:
        return None
    route_name, raw_meta, content = match.groups()
    title, meta_text = _split_meta(raw_meta)
    route = {"docs": "docs-only", "durable": "durable-only", "dual": "dual-write"}[route_name.lower()]
    meta_items = [item.strip().lower() for item in meta_text.split(",") if item.strip()]
    doc_domain = meta_items[0] if route != "durable-only" and meta_items else None
    memory_type = meta_items[-1] if route != "docs-only" and meta_items else None
    return _candidate_payload(
        route=route,
        doc_domain=doc_domain,
        memory_type=memory_type,
        title=title or _title_from_text(content),
        content=content.strip(),
    )


def _split_meta(raw_meta: str) -> tuple[str | None, str]:
    if "|" not in raw_meta:
        return None, raw_meta
    meta_text, title = raw_meta.split("|", 1)
    clean_title = title.strip() or None
    return clean_title, meta_text.strip()


def _candidate_payload(
    *,
    route: str,
    doc_domain: str | None,
    memory_type: str | None,
    title: str,
    content: str,
) -> dict[str, Any]:
    return {
        "route": route,
        "doc_domain": doc_domain,
        "memory_type": memory_type,
        "title": title,
        "content": content,
        "recall_when": _recall_when(memory_type),
        "why_not_in_code": _why_not_in_code(route, memory_type),
    }


def _infer_route(chunk: str) -> str | None:
    lowered = chunk.lower()
    if any(token in lowered for token in PREFERENCE_HINTS):
        return "durable-only"
    if any(token in lowered for token in IDENTITY_HINTS):
        return "durable-only"
    if any(token in lowered for token in CONSTRAINT_HINTS):
        return "dual-write"
    if any(token in lowered for token in DECISION_HINTS):
        return "dual-write"
    if _infer_doc_domain(chunk, "docs-only") is not None:
        return "docs-only"
    return None


def _infer_doc_domain(chunk: str, route: str) -> str | None:
    lowered = chunk.lower()
    for domain, keywords in DOC_HINTS.items():
        if any(token in lowered for token in keywords):
            return domain
    if route == "dual-write":
        return "architect"
    return None


def _infer_memory_type(chunk: str, route: str) -> str | None:
    if route == "docs-only":
        return None
    lowered = chunk.lower()
    if any(token in lowered for token in PREFERENCE_HINTS):
        return "preference"
    if any(token in lowered for token in IDENTITY_HINTS):
        return "identity"
    if any(token in lowered for token in CONSTRAINT_HINTS):
        return "constraint"
    return "decision"


def _title_from_text(chunk: str) -> str:
    sentence = re.split(r"[。！？:：;；]", chunk, maxsplit=1)[0].strip()
    return sentence[:48] or "Session Candidate"


def _recall_when(memory_type: str | None) -> str | None:
    mapping = {
        "constraint": "when planning or implementing related work",
        "decision": "when revisiting architecture or roadmap choices",
        "preference": "when tailoring responses or workflow choices",
        "identity": "when adapting to the user or project environment",
    }
    return mapping.get(memory_type)


def _why_not_in_code(route: str, memory_type: str | None) -> str | None:
    if route == "docs-only":
        return None
    if memory_type == "preference":
        return "user preference is not fully derivable from code"
    if memory_type == "identity":
        return "user or environment identity is not fully derivable from code"
    return "cross-session recall should not depend on rediscovering the same context from code"


def _apply_candidate(
    project_root: Path | None,
    candidate: dict[str, Any],
    *,
    source_label: str,
    created_by: str,
) -> dict[str, Any]:
    target_ref = _find_target_ref(project_root, candidate)
    reason = f"session extract: {source_label}"
    if target_ref is not None:
        result = _apply_update(project_root, candidate, target_ref, reason=reason, created_by=created_by)
        return {"title": candidate["title"], "route": candidate["route"], "action": "update", "target_ref": target_ref, "result": result}
    result = _apply_create(project_root, candidate, reason=reason, created_by=created_by)
    redirect = _redirect_ref(project_root, candidate, result)
    if redirect is not None:
        updated = _apply_update(project_root, candidate, redirect, reason=reason, created_by=created_by)
        return {"title": candidate["title"], "route": candidate["route"], "action": "update", "target_ref": redirect, "result": updated}
    return {"title": candidate["title"], "route": candidate["route"], "action": "create", "target_ref": None, "result": result}


def _find_target_ref(project_root: Path | None, candidate: dict[str, Any]) -> str | None:
    scope = "durable" if candidate["route"] == "durable-only" else "all"
    results = search_project_memory(project_root, query=candidate["title"], scope=scope, memory_type=candidate["memory_type"], limit=5)["results"]
    for item in results:
        if candidate["route"] == "durable-only" and item["lane"] == "durable" and item["type"] == candidate["memory_type"] and item["score"] >= DURABLE_MATCH_THRESHOLD:
            return str(item["ref"])
        if candidate["route"] in {"docs-only", "dual-write"} and item["lane"] == "docs" and item["score"] >= DOC_MATCH_THRESHOLD:
            if candidate["doc_domain"] is None or str(item["ref"]).startswith(f"doc://{candidate['doc_domain']}/"):
                return str(item["ref"])
        if candidate["route"] == "dual-write" and item["lane"] == "durable" and item.get("doc_ref") and item["score"] >= DURABLE_MATCH_THRESHOLD:
            return str(item["doc_ref"])
    return None


def _apply_create(project_root: Path | None, candidate: dict[str, Any], *, reason: str, created_by: str) -> dict[str, Any]:
    kind = {"docs-only": "docs", "durable-only": "durable", "dual-write": "auto"}[candidate["route"]]
    return capture_memory(
        project_root,
        kind=kind,
        title=candidate["title"],
        content=candidate["content"],
        reason=reason,
        doc_domain=candidate["doc_domain"],
        memory_type=candidate["memory_type"],
        recall_when=candidate["recall_when"],
        why_not_in_code=candidate["why_not_in_code"],
        created_by=created_by,
    )


def _apply_update(project_root: Path | None, candidate: dict[str, Any], target_ref: str, *, reason: str, created_by: str) -> dict[str, Any]:
    append = f"\n\n{candidate['content']}" if target_ref.startswith("doc://") else f"\n{candidate['content']}"
    return update_memory(
        project_root,
        ref=target_ref,
        mode="append",
        append=append,
        reason=reason,
        recall_when=candidate["recall_when"],
        why_not_in_code=candidate["why_not_in_code"],
        created_by=created_by,
    )


def _redirect_ref(project_root: Path | None, candidate: dict[str, Any], result: dict[str, Any]) -> str | None:
    durable_result = result.get("durable_result")
    if not isinstance(durable_result, dict) or durable_result.get("code") != "UPDATE_TARGET":
        return None
    target_uri = durable_result.get("guard_target_uri")
    if not isinstance(target_uri, str) or not target_uri:
        return None
    if candidate["route"] == "durable-only":
        return target_uri
    target = read_project_memory(project_root, ref=target_uri)
    doc_ref = target.get("doc_ref")
    return doc_ref if isinstance(doc_ref, str) and doc_ref else None
