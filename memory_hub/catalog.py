from __future__ import annotations

import hashlib
import re
import time
from collections import OrderedDict
from typing import Any, Dict, List, Tuple

from .catalog_indexer import build_catalog_snapshot
from .catalog_worker import process_catalog_jobs
from .drift import detect_drift
from .errors import BusinessError
from .policy import resolve_task_type
from .store import (
    MemoryStore,
    build_catalog_health,
    count_pending_catalog_jobs,
    enqueue_catalog_job,
    fetch_catalog_edges,
    fetch_catalog_files,
    fetch_catalog_hash_map,
    get_catalog_meta,
    insert_drift_report,
    replace_catalog_snapshot,
    resolve_project_workspace,
)

_DEFAULT_TOKEN_BUDGET = 600
_CACHE_MAX_SIZE = 256
_CACHE_TTL_SECONDS = 1800
_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _required(arguments: Dict[str, Any], keys: List[str]) -> None:
    missing = [key for key in keys if not arguments.get(key)]
    if missing:
        raise BusinessError(
            error_code="MISSING_REQUIRED_FIELDS",
            message=f"missing required fields: {', '.join(missing)}",
            details={"missing": missing},
        )


def _truncate_to_budget(text: str, token_budget: int) -> str:
    max_chars = max(300, token_budget * 4)
    if len(text) <= max_chars:
        return text
    suffix = "\n... (truncated)"
    return text[: max_chars - len(suffix)] + suffix


def _prompt_terms(task_prompt: str) -> List[str]:
    chunks = re.findall(r"[A-Za-z0-9_./-]+|[\u4e00-\u9fff]{2,}", task_prompt.lower())
    terms = []
    for chunk in chunks:
        value = chunk.strip()
        if len(value) < 2:
            continue
        terms.append(value)
    return terms[:20]


def _cache_key(
    project_id: str,
    task_prompt: str,
    task_type: str,
    token_budget: int,
    catalog_version: str,
) -> str:
    prompt_hash = hashlib.sha256(task_prompt.strip().lower().encode("utf-8")).hexdigest()
    return f"{project_id}:{task_type}:{token_budget}:{catalog_version}:{prompt_hash}"


def _cache_get(key: str) -> Dict[str, Any] | None:
    entry = _CACHE.get(key)
    if not entry:
        return None

    now = time.time()
    expires_at = float(entry.get("_expires_at", 0))
    if expires_at <= now:
        _CACHE.pop(key, None)
        return None

    _CACHE.move_to_end(key)
    payload = entry.get("payload")
    return dict(payload) if isinstance(payload, dict) else None


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    now = time.time()
    _CACHE[key] = {
        "payload": dict(payload),
        "_expires_at": now + _CACHE_TTL_SECONDS,
    }
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX_SIZE:
        _CACHE.popitem(last=False)


def _score_files(
    files: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    task_prompt: str,
    task_type: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], List[Dict[str, Any]]]:
    terms = _prompt_terms(task_prompt)
    score_map: Dict[str, float] = {}
    reasons_map: Dict[str, List[str]] = {}

    for file in files:
        path = str(file["file_path"]).lower()
        score = float(file.get("import_count", 0)) * 0.05
        reasons: List[str] = []

        for term in terms:
            if term in path:
                score += 3.0
                reasons.append(f"路径命中关键词 {term}")

        if task_type in {"test", "review"} and ("test" in path or "spec" in path):
            score += 2.0
            reasons.append("测试/评审任务优先测试文件")

        if task_type == "implement" and ("src/" in path or "lib/" in path):
            score += 1.0
            reasons.append("实现任务优先核心源码")

        score_map[path] = score
        reasons_map[path] = reasons

    for edge in edges:
        from_file = str(edge["from_file"]).lower()
        to_module = str(edge["to_module"]).lower()
        if from_file not in score_map:
            continue
        for term in terms:
            if term in to_module:
                score_map[from_file] += 1.5
                reasons_map[from_file].append(f"依赖命中关键词 {term}")

    ranked = sorted(
        files,
        key=lambda item: (
            score_map.get(str(item["file_path"]).lower(), 0.0),
            float(item.get("import_count", 0)),
            str(item["file_path"]),
        ),
        reverse=True,
    )

    top_files = ranked[:8]
    selected_paths = {str(item["file_path"]) for item in top_files}
    selected_edges = [
        edge
        for edge in edges
        if str(edge["from_file"]) in selected_paths and float(edge["confidence"]) >= 0.5
    ][:16]

    evidence: List[Dict[str, str]] = []
    for item in top_files:
        path = str(item["file_path"])
        reason_candidates = reasons_map.get(path.lower(), [])
        reason = reason_candidates[0] if reason_candidates else "高连接度/高相关性文件"
        evidence.append({"file": path, "reason": reason})

    return top_files, evidence, selected_edges


def _render_catalog_brief(
    task_type: str,
    catalog_version: str,
    files: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    token_budget: int,
) -> str:
    lines: List[str] = ["[Catalog Brief]"]
    lines.append(f"TaskType: {task_type}")
    lines.append(f"CatalogVersion: {catalog_version}")

    lines.append("Top Files:")
    if not files:
        lines.append("- (no indexed files)")
    else:
        for item in files:
            lines.append(
                f"- {item['file_path']} (lang={item['language']}, imports={item['import_count']})"
            )

    lines.append("Key Dependencies (confidence >= 0.5):")
    if not edges:
        lines.append("- (no dependencies)")
    else:
        for edge in edges[:12]:
            lines.append(
                f"- {edge['from_file']} -> {edge['to_module']} "
                f"(confidence={edge['confidence']:.2f}, source={edge['source_type']})"
            )

    return _truncate_to_budget("\n".join(lines), token_budget)


def _ensure_catalog_seeded(store: MemoryStore, project_id: str) -> None:
    conn = store.connect(project_id)
    try:
        meta = get_catalog_meta(conn, project_id)
        if meta is not None and int(meta.get("indexed_files", 0)) > 0:
            return

        snapshot = build_catalog_snapshot(resolve_project_workspace(conn, store.project_workspace(project_id)))
        replace_catalog_snapshot(
            conn,
            project_id=project_id,
            source_root=snapshot["workspace_root"],
            files=snapshot["files"],
            edges=snapshot["edges"],
            full_rebuild=True,
        )
        conn.commit()
    finally:
        conn.close()


def catalog_health_check(store: MemoryStore, arguments: Dict[str, Any]) -> Dict[str, Any]:
    _required(arguments, ["project_id"])
    project_id = str(arguments["project_id"])

    conn = store.connect(project_id)
    try:
        known_hashes = fetch_catalog_hash_map(conn, project_id)
        if known_hashes:
            drift = detect_drift(resolve_project_workspace(conn, store.project_workspace(project_id)), known_hashes)
            insert_drift_report(
                conn,
                project_id=project_id,
                method=str(drift.get("method", "unknown")),
                drift_score=float(drift.get("drift_score", 0.0)),
                details={"changed_files": drift.get("changed_files", [])},
            )

        health = build_catalog_health(conn, project_id)
        conn.commit()
        return health
    finally:
        conn.close()


def _build_catalog_brief_payload(
    store: MemoryStore,
    project_id: str,
    task_prompt: str,
    task_type: str,
    token_budget: int,
) -> Dict[str, Any]:
    _ensure_catalog_seeded(store, project_id)

    health = catalog_health_check(store, {"project_id": project_id})

    if health["freshness"] in {"stale", "unknown"}:
        # Best effort async-like refresh by processing queued jobs if any.
        process_catalog_jobs(store, project_id, limit=5)
        health = catalog_health_check(store, {"project_id": project_id})

    conn = store.connect(project_id)
    try:
        files = fetch_catalog_files(conn, project_id)
        edges = fetch_catalog_edges(conn, project_id, min_confidence=0.5)
        pending_jobs = count_pending_catalog_jobs(conn, project_id)

        top_files, evidence, selected_edges = _score_files(files, edges, task_prompt, task_type)
        catalog_version = str(health["catalog_version"])

        key = _cache_key(project_id, task_prompt, task_type, token_budget, catalog_version)
        if health["freshness"] == "fresh":
            cached_payload = _cache_get(key)
        else:
            cached_payload = None

        if cached_payload is not None:
            cached = dict(cached_payload)
            cached["cache_hit"] = True
            cached["pending_jobs"] = pending_jobs
            cached["consistency_status"] = health["consistency_status"]
            return cached

        brief_text = _render_catalog_brief(
            task_type=task_type,
            catalog_version=catalog_version,
            files=top_files,
            edges=selected_edges,
            token_budget=token_budget,
        )
        payload = {
            "catalog_brief": brief_text,
            "evidence": evidence,
            "catalog_version": catalog_version,
            "freshness": health["freshness"],
            "pending_jobs": pending_jobs,
            "consistency_status": health["consistency_status"],
            "cache_hit": False,
        }
        _cache_set(key, payload)

        if health["freshness"] in {"stale", "unknown"} and pending_jobs == 0:
            enqueue_catalog_job(
                conn,
                project_id=project_id,
                job_type="incremental_refresh",
                payload={"reason": "pull_stale_refresh", "files_touched": []},
            )
            payload["refresh_requested"] = True
        else:
            payload["refresh_requested"] = False

        conn.commit()
        return payload
    finally:
        conn.close()


def catalog_brief_generate(store: MemoryStore, arguments: Dict[str, Any]) -> Dict[str, Any]:
    _required(arguments, ["project_id", "task_prompt"])

    project_id = str(arguments["project_id"])
    task_prompt = str(arguments["task_prompt"])
    requested_task_type = arguments.get("task_type")
    token_budget = int(arguments.get("token_budget") or _DEFAULT_TOKEN_BUDGET)

    task_type = resolve_task_type(task_prompt, requested_task_type)

    return _build_catalog_brief_payload(
        store,
        project_id=project_id,
        task_prompt=task_prompt,
        task_type=task_type,
        token_budget=token_budget,
    )


def catalog_brief_for_pull(
    store: MemoryStore,
    *,
    project_id: str,
    task_prompt: str,
    task_type: str,
    token_budget: int,
) -> Dict[str, Any]:
    return _build_catalog_brief_payload(
        store,
        project_id=project_id,
        task_prompt=task_prompt,
        task_type=task_type,
        token_budget=token_budget,
    )
