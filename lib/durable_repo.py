"""Repository functions for durable memory storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.durable_db import connect, ensure_schema as ensure_db_schema, rows_to_dicts, transaction
from lib.durable_errors import DurableMemoryError
from lib.durable_guard import evaluate_write_guard
from lib.durable_proposal_utils import guard_result, insert_proposal, materialize_candidate_content, validate_update_mode
from lib.durable_store import get_approved, get_proposal, get_version, require_text, reserved_create_uris
from lib.durable_uri import TYPE_ORDER, parse_memory_uri, reserve_memory_uri, validate_memory_type


def ensure_schema(project_root: Path | None = None) -> Path:
    """Ensure durable memory schema exists."""
    return ensure_db_schema(project_root)


def get_approved_by_uri(project_root: Path | None, uri: str) -> dict[str, Any] | None:
    """Return an approved memory by URI."""
    parse_memory_uri(uri)
    ensure_schema(project_root)
    with connect(project_root) as conn:
        return get_approved(conn, uri, required=False)


def get_approved_by_doc_ref(project_root: Path | None, doc_ref: str) -> dict[str, Any] | None:
    """Return an approved dual-write memory by doc ref."""
    ensure_schema(project_root)
    with connect(project_root) as conn:
        row = conn.execute(
            "SELECT * FROM approved_memories WHERE doc_ref = ? ORDER BY updated_at DESC LIMIT 1",
            (doc_ref,),
        ).fetchone()
    return None if row is None else dict(row)


def get_boot_memories(project_root: Path | None) -> list[dict[str, Any]]:
    """Return boot memories in stable order."""
    ensure_schema(project_root)
    clauses = " ".join(f"WHEN '{memory_type}' THEN {order}" for memory_type, order in TYPE_ORDER.items())
    with connect(project_root) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM approved_memories
            WHERE type IN ('identity', 'constraint')
            ORDER BY CASE type {clauses} END, created_at ASC
            """
        ).fetchall()
    return rows_to_dicts(rows)


def search_approved(
    project_root: Path | None,
    query: str,
    type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search approved memories only."""
    ensure_schema(project_root)
    normalized_query = require_text(query, "EMPTY_QUERY", "Search query must not be empty.")
    if type is not None:
        type = validate_memory_type(type)
    if limit <= 0 or limit > 50:
        raise DurableMemoryError("INVALID_LIMIT", "Search limit must be between 1 and 50.")

    sql = """
        SELECT uri, type, storage_lane, doc_ref, title, content, recall_when, updated_at
        FROM approved_memories
        WHERE (lower(title) LIKE lower(?) OR lower(content) LIKE lower(?))
    """
    params: list[Any] = [f"%{normalized_query}%", f"%{normalized_query}%"]
    if type is not None:
        sql += " AND type = ?"
        params.append(type)
    sql += " ORDER BY updated_at DESC, uri ASC LIMIT ?"
    params.append(limit)

    with connect(project_root) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    results = rows_to_dicts(rows)
    for item in results:
        item["snippet"] = item["content"][:160]
        del item["content"]
    return results


def insert_create_proposal(
    project_root: Path | None,
    *,
    type: str,
    title: str,
    content: str,
    recall_when: str,
    why_not_in_code: str,
    source_reason: str,
    created_by: str,
    storage_lane: str = "durable",
    doc_ref: str | None = None,
) -> dict[str, Any]:
    """Insert a create proposal or return guard result."""
    ensure_schema(project_root)
    memory_type = validate_memory_type(type)
    clean_title = require_text(title, "EMPTY_TITLE", "Title must not be empty.")
    clean_content = require_text(content, "EMPTY_CONTENT", "Content must not be empty.")
    clean_why = require_text(
        why_not_in_code,
        "MISSING_WHY_NOT_IN_CODE",
        "why_not_in_code must not be empty.",
    )
    clean_source = require_text(
        source_reason,
        "MISSING_SOURCE_REASON",
        "source_reason must not be empty.",
    )
    guard = evaluate_write_guard(project_root, memory_type=memory_type, title=clean_title, content=clean_content)
    if guard["action"] != "PENDING_REVIEW":
        return guard_result(guard)

    with transaction(project_root) as conn:
        target_uri = reserve_memory_uri(memory_type, clean_title, reserved_create_uris(conn))
        proposal_id = insert_proposal(
            conn,
            proposal_kind="create",
            target_uri=target_uri,
            base_version_id=None,
            memory_type=memory_type,
            storage_lane=storage_lane,
            doc_ref=doc_ref,
            title=clean_title,
            content=clean_content,
            recall_when=recall_when or "",
            why_not_in_code=clean_why,
            source_reason=clean_source,
            guard_reason=guard["reason"],
            created_by=created_by,
        )
    return {
        "code": "PROPOSAL_CREATED",
        "proposal_id": proposal_id,
        "proposal_kind": "create",
        "status": "pending",
        "target_uri": target_uri,
        "guard_decision": "PENDING_REVIEW",
    }


def insert_dual_write_update_proposal(
    project_root: Path | None,
    *,
    uri: str,
    content: str,
    recall_when: str | None,
    why_not_in_code: str | None,
    source_reason: str,
    created_by: str,
    doc_ref: str,
) -> dict[str, Any]:
    """Insert an update proposal for a dual-write durable summary."""
    ensure_schema(project_root)
    approved = get_approved_by_uri(project_root, uri)
    if approved is None:
        raise DurableMemoryError("MEMORY_NOT_FOUND", f"Approved memory not found: {uri}")
    candidate_content = require_text(content, "EMPTY_CONTENT", "Content must not be empty.")
    candidate_recall = approved["recall_when"] if recall_when is None else recall_when
    candidate_why = approved["why_not_in_code"] if why_not_in_code is None else why_not_in_code
    require_text(candidate_why, "MISSING_WHY_NOT_IN_CODE", "why_not_in_code must not be empty.")
    clean_source = require_text(source_reason, "MISSING_SOURCE_REASON", "source_reason must not be empty.")
    if (
        approved["content"] == candidate_content
        and approved["recall_when"] == candidate_recall
        and approved["why_not_in_code"] == candidate_why
    ):
        return {
            "code": "NOOP",
            "proposal_kind": "update",
            "target_uri": uri,
            "status": "skipped",
            "guard_decision": "NOOP",
            "guard_reason": "summary_unchanged",
        }

    with transaction(project_root) as conn:
        proposal_id = insert_proposal(
            conn,
            proposal_kind="update",
            target_uri=uri,
            base_version_id=approved["current_version_id"],
            memory_type=approved["type"],
            storage_lane="dual",
            doc_ref=doc_ref,
            title=approved["title"],
            content=candidate_content,
            recall_when=candidate_recall or "",
            why_not_in_code=candidate_why,
            source_reason=clean_source,
            guard_reason="dual_write_sync_requires_review",
            created_by=created_by,
        )
    return {
        "code": "PROPOSAL_CREATED",
        "proposal_id": proposal_id,
        "proposal_kind": "update",
        "target_uri": uri,
        "base_version_id": approved["current_version_id"],
        "status": "pending",
    }


def insert_update_proposal(
    project_root: Path | None,
    *,
    uri: str,
    old_string: str | None = None,
    new_string: str | None = None,
    append: str | None = None,
    recall_when: str | None = None,
    why_not_in_code: str | None = None,
    source_reason: str,
    created_by: str,
) -> dict[str, Any]:
    """Insert an update proposal with materialized content."""
    ensure_schema(project_root)
    parse_memory_uri(uri)
    validate_update_mode(old_string, new_string, append)
    clean_source = require_text(source_reason, "MISSING_SOURCE_REASON", "source_reason must not be empty.")

    approved = get_approved_by_uri(project_root, uri)
    if approved is None:
        raise DurableMemoryError("MEMORY_NOT_FOUND", f"Approved memory not found: {uri}")
    candidate_content = materialize_candidate_content(approved["content"], old_string, new_string, append)
    candidate_recall = approved["recall_when"] if recall_when is None else recall_when
    candidate_why = approved["why_not_in_code"] if why_not_in_code is None else why_not_in_code
    require_text(candidate_why, "MISSING_WHY_NOT_IN_CODE", "why_not_in_code must not be empty.")
    require_text(candidate_content, "EMPTY_CONTENT", "Content must not be empty.")
    if old_string in (None, "") and append is None and recall_when is None and why_not_in_code is None:
        raise DurableMemoryError("NO_UPDATE_FIELDS", "At least one update field must be provided.")

    with transaction(project_root) as conn:
        proposal_id = insert_proposal(
            conn,
            proposal_kind="update",
            target_uri=uri,
            base_version_id=approved["current_version_id"],
            memory_type=approved["type"],
            storage_lane=approved.get("storage_lane", "durable"),
            doc_ref=approved.get("doc_ref"),
            title=approved["title"],
            content=candidate_content,
            recall_when=candidate_recall or "",
            why_not_in_code=candidate_why,
            source_reason=clean_source,
            patch_old_string=old_string,
            patch_new_string=new_string,
            append_content=append,
            guard_reason="proposal_requires_review",
            created_by=created_by,
        )
    return {
        "code": "PROPOSAL_CREATED",
        "proposal_id": proposal_id,
        "proposal_kind": "update",
        "target_uri": uri,
        "base_version_id": approved["current_version_id"],
        "status": "pending",
    }


def list_pending_proposals(project_root: Path | None) -> list[dict[str, Any]]:
    """List pending proposals."""
    ensure_schema(project_root)
    with connect(project_root) as conn:
        rows = conn.execute(
            """
            SELECT mp.proposal_id, mp.proposal_kind, mp.status, mp.type, mp.title,
                   mp.target_uri, mp.created_at, mp.base_version_id,
                   am.current_version_id
            FROM memory_proposals AS mp
            LEFT JOIN approved_memories AS am ON am.uri = mp.target_uri
            WHERE mp.status = 'pending'
            ORDER BY mp.created_at ASC
            """
        ).fetchall()
    items = rows_to_dicts(rows)
    for item in items:
        item["is_stale"] = item["proposal_kind"] == "update" and item["current_version_id"] != item["base_version_id"]
        item.pop("base_version_id", None)
        item.pop("current_version_id", None)
    return items


def get_proposal_detail(project_root: Path | None, proposal_id: int) -> dict[str, Any]:
    """Get proposal detail with current memory and base version."""
    ensure_schema(project_root)
    with connect(project_root) as conn:
        proposal = get_proposal(conn, proposal_id)
        current_memory = get_approved(conn, proposal["target_uri"], required=False)
        base_version = None if proposal["base_version_id"] is None else get_version(conn, proposal["base_version_id"])
    return {"proposal": proposal, "current_memory": current_memory, "base_version": base_version}
