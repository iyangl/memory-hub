from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, List, Sequence
from uuid import uuid4

from .catalog import catalog_brief_for_pull
from .errors import BusinessError
from .policy import build_context_brief, normalize_role, resolve_task_type, roles_for_task
from .store import (
    MemoryStore,
    bump_memory_version,
    detect_conflicts,
    enqueue_catalog_job,
    fetch_current_value,
    fetch_latest_consistency,
    fetch_latest_handoff,
    fetch_open_loops_top,
    fetch_role_payloads,
    get_catalog_meta,
    get_memory_version,
    insert_consistency_link,
    insert_handoff_packet,
    insert_open_loops,
    insert_sync_audit,
    make_consistency_stamp,
    parse_context_stamp,
    resolve_project_workspace,
    upsert_role_delta,
    close_open_loops,
)
from .validation import validate_push_payload

DEFAULT_MAX_TOKENS = 1200
DEFAULT_HANDOFF_TTL_HOURS = 72


def _required(arguments: Dict[str, Any], keys: Sequence[str]) -> None:
    missing = [k for k in keys if not arguments.get(k)]
    if missing:
        raise BusinessError(
            error_code="MISSING_REQUIRED_FIELDS",
            message=f"missing required fields: {', '.join(missing)}",
            details={"missing": missing},
        )


def _slug(text: str) -> str:
    value = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    value = "-".join(chunk for chunk in value.split("-") if chunk)
    return value[:48] or "decision"


def _normalize_role_deltas(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    role_deltas = arguments.get("role_deltas") or []
    decisions_delta = arguments.get("decisions_delta") or []

    if not isinstance(role_deltas, list):
        raise BusinessError(
            error_code="INVALID_PUSH_PAYLOAD",
            message="role_deltas must be a list",
            details={"field": "role_deltas"},
        )
    if not isinstance(decisions_delta, list):
        raise BusinessError(
            error_code="INVALID_PUSH_PAYLOAD",
            message="decisions_delta must be a list",
            details={"field": "decisions_delta"},
        )

    normalized: List[Dict[str, Any]] = []

    for item in role_deltas:
        if not isinstance(item, dict):
            continue
        role = normalize_role(str(item.get("role", "")))
        memory_key = str(item.get("memory_key", "")).strip()
        if not memory_key:
            continue
        normalized.append(
            {
                "role": role,
                "memory_key": memory_key,
                "value": item.get("value"),
                "confidence": float(item.get("confidence", 0.7)),
                "source_refs": item.get("source_refs") or [],
            }
        )

    for index, item in enumerate(decisions_delta):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        key = item.get("decision_id") or f"decision::{_slug(title)}::{index}"
        normalized.append(
            {
                "role": "architect",
                "memory_key": str(key),
                "value": {
                    "title": title,
                    "rationale": item.get("rationale"),
                    "status": item.get("status", "active"),
                },
                "confidence": float(item.get("confidence", 0.8)),
                "source_refs": item.get("source_refs") or [],
            }
        )

    return normalized


def session_sync_pull(store: MemoryStore, arguments: Dict[str, Any]) -> Dict[str, Any]:
    started = perf_counter()
    _required(arguments, ["project_id", "client_id", "session_id", "task_prompt"])

    project_id = str(arguments["project_id"])
    client_id = str(arguments["client_id"])
    session_id = str(arguments["session_id"])
    task_prompt = str(arguments.get("task_prompt", ""))
    requested_task_type = arguments.get("task_type")
    max_tokens = int(arguments.get("max_tokens") or DEFAULT_MAX_TOKENS)

    resolved_task_type = resolve_task_type(task_prompt, requested_task_type)
    roles = roles_for_task(resolved_task_type)

    conn = store.connect(project_id)
    try:
        role_payloads = fetch_role_payloads(conn, project_id, roles)
        open_loops_top = fetch_open_loops_top(conn, project_id, limit=3)
        handoff_latest = fetch_latest_handoff(conn, project_id)
        current_version = get_memory_version(conn)

        memory_context_brief = build_context_brief(
            role_payloads=role_payloads,
            open_loops_top=open_loops_top,
            handoff_latest=handoff_latest,
            max_tokens=max_tokens,
        )

        catalog_payload = catalog_brief_for_pull(
            store,
            project_id=project_id,
            task_prompt=task_prompt,
            task_type=resolved_task_type,
            token_budget=max(300, max_tokens // 2),
        )

        catalog_brief = str(catalog_payload.get("catalog_brief", ""))
        context_brief = memory_context_brief
        if catalog_brief:
            context_brief = f"{memory_context_brief}\n\n{catalog_brief}".strip()

        catalog_version = str(catalog_payload.get("catalog_version", "sha256:unknown"))
        consistency_status = str(catalog_payload.get("consistency_status", "unknown"))
        consistency_stamp = make_consistency_stamp(
            memory_version=current_version,
            catalog_version=catalog_version,
            consistency_status=consistency_status,
        )

        sources = []
        for block in role_payloads:
            for item in block.get("items", []):
                sources.append(
                    {
                        "type": "role_state",
                        "role": block.get("role"),
                        "memory_key": item.get("memory_key"),
                        "version": item.get("version"),
                    }
                )
        for loop in open_loops_top:
            sources.append({"type": "open_loop", "loop_id": loop.get("loop_id")})
        if handoff_latest:
            sources.append({"type": "handoff", "handoff_id": handoff_latest.get("handoff_id")})

        response = {
            "context_brief": context_brief,
            "memory_context_brief": memory_context_brief,
            "catalog_brief": catalog_brief,
            "evidence": catalog_payload.get("evidence", []),
            "role_payloads": role_payloads,
            "open_loops_top": open_loops_top,
            "handoff_latest": handoff_latest or {},
            "consistency_stamp": consistency_stamp,
            "trace": {
                "policy": "task_adaptive",
                "requested_task_type": requested_task_type or "auto",
                "resolved_task_type": resolved_task_type,
                "sources": sources,
                "catalog": {
                    "freshness": catalog_payload.get("freshness", "unknown"),
                    "cache_hit": bool(catalog_payload.get("cache_hit", False)),
                    "refresh_requested": bool(catalog_payload.get("refresh_requested", False)),
                },
            },
        }

        sync_id = f"sync_{uuid4().hex}"
        insert_sync_audit(
            conn,
            sync_id=sync_id,
            project_id=project_id,
            direction="pull",
            client_id=client_id,
            session_id=session_id,
            request_payload=arguments,
            response_payload=response,
            latency_ms=max(int((perf_counter() - started) * 1000), 0),
        )
        conn.commit()

        return {
            "sync_id": sync_id,
            **response,
        }
    finally:
        conn.close()


def session_sync_push(store: MemoryStore, arguments: Dict[str, Any]) -> Dict[str, Any]:
    started = perf_counter()
    normalized_args = validate_push_payload(arguments)
    _required(normalized_args, ["project_id", "client_id", "session_id", "session_summary"])

    project_id = str(normalized_args["project_id"])
    client_id = str(normalized_args["client_id"])
    session_id = str(normalized_args["session_id"])

    base_version = parse_context_stamp(normalized_args.get("context_stamp"))

    role_deltas = _normalize_role_deltas(normalized_args)
    open_loops_new = normalized_args.get("open_loops_new") or []
    open_loops_closed = normalized_args.get("open_loops_closed") or []
    files_touched = normalized_args.get("files_touched") or []
    session_summary = str(normalized_args.get("session_summary", "")).strip()

    conn = store.connect(project_id)
    try:
        # Enforce per-project workspace binding before any write transaction.
        resolve_project_workspace(conn, store.project_workspace(project_id))
        conn.execute("BEGIN")

        current_version = get_memory_version(conn)
        latest_consistency = fetch_latest_consistency(conn, project_id)
        conflicts = detect_conflicts(conn, project_id, base_version, role_deltas)
        sync_id = f"sync_{uuid4().hex}"

        if conflicts:
            consistency_stamp = make_consistency_stamp(
                memory_version=current_version,
                catalog_version=str(latest_consistency["catalog_version"]),
                consistency_status=str(latest_consistency["consistency_status"]),
            )
            response = {
                "sync_id": sync_id,
                "memory_version": current_version,
                "consistency_stamp": consistency_stamp,
                "conflicts": conflicts,
                "status": "needs_resolution",
            }
            insert_sync_audit(
                conn,
                sync_id=sync_id,
                project_id=project_id,
                direction="push",
                client_id=client_id,
                session_id=session_id,
                request_payload=normalized_args,
                response_payload=response,
                error_code="CONFLICT_DETECTED",
                latency_ms=max(int((perf_counter() - started) * 1000), 0),
            )
            conn.commit()
            return response

        new_version = bump_memory_version(conn)

        applied_role_deltas = []
        for delta in role_deltas:
            applied = upsert_role_delta(
                conn,
                project_id=project_id,
                role=str(delta["role"]),
                memory_key=str(delta["memory_key"]),
                value=delta.get("value"),
                confidence=float(delta.get("confidence", 0.7)),
                source_refs=delta.get("source_refs") or [],
                client_id=client_id,
                memory_version=new_version,
            )
            applied_role_deltas.append(applied)

        inserted_loops = insert_open_loops(
            conn,
            project_id=project_id,
            open_loops_new=open_loops_new,
            client_id=client_id,
            memory_version=new_version,
        )
        closed_loop_ids = close_open_loops(
            conn,
            project_id=project_id,
            open_loops_closed=open_loops_closed,
            client_id=client_id,
            memory_version=new_version,
        )

        handoff_summary = {
            "session_summary": session_summary,
            "role_delta_count": len(applied_role_deltas),
            "decision_delta_count": len(normalized_args.get("decisions_delta") or []),
            "files_touched": files_touched,
            "open_loops_new": inserted_loops,
            "open_loops_closed": closed_loop_ids,
            "next_actions": [item.get("title") for item in inserted_loops[:3]],
        }
        handoff = insert_handoff_packet(
            conn,
            project_id=project_id,
            session_id=session_id,
            summary=handoff_summary,
            created_by_client=client_id,
            memory_version=new_version,
            ttl_hours=DEFAULT_HANDOFF_TTL_HOURS,
        )

        job_id = enqueue_catalog_job(
            conn,
            project_id=project_id,
            job_type="incremental_refresh",
            payload={
                "files_touched": files_touched,
                "memory_version": new_version,
                "sync_id": sync_id,
                "session_id": session_id,
            },
        )

        catalog_meta = get_catalog_meta(conn, project_id)
        catalog_version = "sha256:unknown" if catalog_meta is None else str(catalog_meta["catalog_version"])
        insert_consistency_link(
            conn,
            project_id=project_id,
            sync_id=sync_id,
            memory_version=new_version,
            catalog_version=catalog_version,
            consistency_status="degraded",
        )

        consistency_stamp = make_consistency_stamp(
            memory_version=new_version,
            catalog_version=catalog_version,
            consistency_status="degraded",
        )

        response = {
            "sync_id": sync_id,
            "memory_version": new_version,
            "consistency_stamp": consistency_stamp,
            "conflicts": [],
            "status": "ok",
            "applied": {
                "role_deltas": applied_role_deltas,
                "open_loops_new": inserted_loops,
                "open_loops_closed": closed_loop_ids,
                "handoff": handoff,
            },
            "catalog_job": {
                "job_id": job_id,
                "status": "pending",
            },
        }

        insert_sync_audit(
            conn,
            sync_id=sync_id,
            project_id=project_id,
            direction="push",
            client_id=client_id,
            session_id=session_id,
            request_payload=normalized_args,
            response_payload=response,
            latency_ms=max(int((perf_counter() - started) * 1000), 0),
        )
        conn.commit()
        return response
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def session_sync_resolve_conflict(store: MemoryStore, arguments: Dict[str, Any]) -> Dict[str, Any]:
    started = perf_counter()
    _required(arguments, ["project_id", "client_id", "session_id", "strategy", "role_deltas"])

    strategy = str(arguments.get("strategy", "")).strip().lower()
    if strategy not in {"accept_theirs", "keep_mine", "merge_note"}:
        raise BusinessError(
            error_code="INVALID_CONFLICT_STRATEGY",
            message="strategy must be one of: accept_theirs, keep_mine, merge_note",
            details={"strategy": strategy},
        )

    project_id = str(arguments["project_id"])
    client_id = str(arguments["client_id"])
    session_id = str(arguments["session_id"])

    if strategy == "accept_theirs":
        conn = store.connect(project_id)
        try:
            sync_id = f"sync_{uuid4().hex}"
            latest = fetch_latest_consistency(conn, project_id)
            response = {
                "sync_id": sync_id,
                "status": "ok",
                "strategy": strategy,
                "memory_version": int(latest["memory_version"]),
                "consistency_stamp": make_consistency_stamp(
                    memory_version=int(latest["memory_version"]),
                    catalog_version=str(latest["catalog_version"]),
                    consistency_status=str(latest["consistency_status"]),
                ),
                "applied": "no_write",
            }
            insert_sync_audit(
                conn,
                sync_id=sync_id,
                project_id=project_id,
                direction="resolve_conflict",
                client_id=client_id,
                session_id=session_id,
                request_payload=arguments,
                response_payload=response,
                latency_ms=max(int((perf_counter() - started) * 1000), 0),
            )
            conn.commit()
            return response
        finally:
            conn.close()

    if strategy == "keep_mine":
        force_args = dict(arguments)
        force_args["context_stamp"] = None
        force_args["session_summary"] = str(arguments.get("session_summary") or "conflict resolved: keep_mine")
        push_response = session_sync_push(store, force_args)
        return {
            "sync_id": push_response["sync_id"],
            "status": push_response["status"],
            "strategy": strategy,
            "memory_version": push_response["memory_version"],
            "consistency_stamp": push_response.get("consistency_stamp"),
            "conflicts": push_response.get("conflicts", []),
        }

    role_deltas = arguments.get("role_deltas") or []
    if not isinstance(role_deltas, list):
        raise BusinessError(
            error_code="INVALID_PUSH_PAYLOAD",
            message="role_deltas must be a list",
            details={"field": "role_deltas"},
        )

    conn = store.connect(project_id)
    try:
        merged_deltas = []
        for delta in role_deltas:
            if not isinstance(delta, dict):
                continue
            role = normalize_role(str(delta.get("role", "")))
            memory_key = str(delta.get("memory_key", "")).strip()
            if not memory_key:
                continue

            mine_value = delta.get("value")
            theirs = fetch_current_value(conn, project_id, role, memory_key)
            merged_value = {
                "resolution": "merge_note",
                "mine": mine_value,
                "theirs": None if theirs is None else theirs.get("value"),
                "note": delta.get("note") or "auto merged by merge_note strategy",
            }
            merged_deltas.append(
                {
                    "role": role,
                    "memory_key": memory_key,
                    "value": merged_value,
                    "confidence": float(delta.get("confidence", 0.7)),
                    "source_refs": delta.get("source_refs") or [],
                }
            )
    finally:
        conn.close()

    force_args = dict(arguments)
    force_args["context_stamp"] = None
    force_args["role_deltas"] = merged_deltas
    force_args["session_summary"] = str(arguments.get("session_summary") or "conflict resolved: merge_note")

    push_response = session_sync_push(store, force_args)
    return {
        "sync_id": push_response["sync_id"],
        "status": push_response["status"],
        "strategy": strategy,
        "memory_version": push_response["memory_version"],
        "consistency_stamp": push_response.get("consistency_stamp"),
        "conflicts": push_response.get("conflicts", []),
    }
