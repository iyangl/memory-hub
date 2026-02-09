from __future__ import annotations

from typing import Any, Dict, List, Sequence
from uuid import uuid4

from .policy import build_context_brief, normalize_role, resolve_task_type, roles_for_task
from .store import (
    MemoryStore,
    bump_memory_version,
    detect_conflicts,
    fetch_current_value,
    fetch_latest_handoff,
    fetch_open_loops_top,
    fetch_role_payloads,
    get_memory_version,
    insert_handoff_packet,
    insert_open_loops,
    insert_sync_audit,
    make_context_stamp,
    parse_context_stamp,
    upsert_role_delta,
    close_open_loops,
)

DEFAULT_MAX_TOKENS = 1200
DEFAULT_HANDOFF_TTL_HOURS = 72


def _required(arguments: Dict[str, Any], keys: Sequence[str]) -> None:
    missing = [k for k in keys if not arguments.get(k)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _slug(text: str) -> str:
    value = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    value = "-".join(chunk for chunk in value.split("-") if chunk)
    return value[:48] or "decision"


def _normalize_role_deltas(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    role_deltas = arguments.get("role_deltas") or []
    decisions_delta = arguments.get("decisions_delta") or []

    if not isinstance(role_deltas, list):
        raise ValueError("role_deltas must be a list")
    if not isinstance(decisions_delta, list):
        raise ValueError("decisions_delta must be a list")

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
        context_stamp = make_context_stamp(current_version)

        context_brief = build_context_brief(
            role_payloads=role_payloads,
            open_loops_top=open_loops_top,
            handoff_latest=handoff_latest,
            max_tokens=max_tokens,
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
            "role_payloads": role_payloads,
            "open_loops_top": open_loops_top,
            "handoff_latest": handoff_latest or {},
            "context_stamp": context_stamp,
            "trace": {
                "policy": "task_adaptive",
                "requested_task_type": requested_task_type or "auto",
                "resolved_task_type": resolved_task_type,
                "sources": sources,
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
        )
        conn.commit()

        return {
            "sync_id": sync_id,
            **response,
        }
    finally:
        conn.close()


def session_sync_push(store: MemoryStore, arguments: Dict[str, Any]) -> Dict[str, Any]:
    _required(arguments, ["project_id", "client_id", "session_id", "session_summary"])

    project_id = str(arguments["project_id"])
    client_id = str(arguments["client_id"])
    session_id = str(arguments["session_id"])

    context_stamp = arguments.get("context_stamp")
    base_version = parse_context_stamp(context_stamp) if context_stamp else None

    role_deltas = _normalize_role_deltas(arguments)
    open_loops_new = arguments.get("open_loops_new") or []
    open_loops_closed = arguments.get("open_loops_closed") or []
    files_touched = arguments.get("files_touched") or []
    session_summary = str(arguments.get("session_summary", "")).strip()

    if not isinstance(open_loops_new, list):
        raise ValueError("open_loops_new must be a list")
    if not isinstance(open_loops_closed, list):
        raise ValueError("open_loops_closed must be a list")
    if not isinstance(files_touched, list):
        raise ValueError("files_touched must be a list")

    conn = store.connect(project_id)
    try:
        conn.execute("BEGIN")

        current_version = get_memory_version(conn)
        conflicts = detect_conflicts(conn, project_id, base_version, role_deltas)
        sync_id = f"sync_{uuid4().hex}"

        if conflicts:
            response = {
                "sync_id": sync_id,
                "memory_version": current_version,
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
                request_payload=arguments,
                response_payload=response,
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
            "decision_delta_count": len(arguments.get("decisions_delta") or []),
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

        response = {
            "sync_id": sync_id,
            "memory_version": new_version,
            "conflicts": [],
            "status": "ok",
            "applied": {
                "role_deltas": applied_role_deltas,
                "open_loops_new": inserted_loops,
                "open_loops_closed": closed_loop_ids,
                "handoff": handoff,
            },
        }

        insert_sync_audit(
            conn,
            sync_id=sync_id,
            project_id=project_id,
            direction="push",
            client_id=client_id,
            session_id=session_id,
            request_payload=arguments,
            response_payload=response,
        )
        conn.commit()
        return response
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def session_sync_resolve_conflict(store: MemoryStore, arguments: Dict[str, Any]) -> Dict[str, Any]:
    _required(arguments, ["project_id", "client_id", "session_id", "strategy", "role_deltas"])

    strategy = str(arguments.get("strategy", "")).strip().lower()
    if strategy not in {"accept_theirs", "keep_mine", "merge_note"}:
        raise ValueError("strategy must be one of: accept_theirs, keep_mine, merge_note")

    project_id = str(arguments["project_id"])
    client_id = str(arguments["client_id"])
    session_id = str(arguments["session_id"])

    if strategy == "accept_theirs":
        conn = store.connect(project_id)
        try:
            sync_id = f"sync_{uuid4().hex}"
            current_version = get_memory_version(conn)
            response = {
                "sync_id": sync_id,
                "status": "ok",
                "strategy": strategy,
                "memory_version": current_version,
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
            "conflicts": push_response.get("conflicts", []),
        }

    # merge_note
    role_deltas = arguments.get("role_deltas") or []
    if not isinstance(role_deltas, list):
        raise ValueError("role_deltas must be a list")

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
        "conflicts": push_response.get("conflicts", []),
    }
