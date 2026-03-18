"""Durable memory tool handlers used by the MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.durable_errors import DurableMemoryError
from lib.durable_repo import (
    insert_create_proposal,
    insert_update_proposal,
)
from lib.project_memory_view import read_project_memory, search_project_memory
from lib.project_review import show_review_summary
from lib.project_memory_write import capture_memory, update_memory


def _success(
    code: str,
    message: str,
    data: dict[str, Any],
    *,
    degraded: bool = False,
    degrade_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "code": code,
        "message": message,
        "data": data,
        "degraded": degraded,
        "degrade_reasons": degrade_reasons or [],
    }


def _error(exc: DurableMemoryError) -> dict[str, Any]:
    return {
        "ok": False,
        "code": exc.code,
        "message": exc.message,
        "details": exc.details,
        "degraded": False,
        "degrade_reasons": [],
    }


def read_memory_tool(
    project_root: Path | None,
    *,
    ref: str | None = None,
    uri: str | None = None,
    anchor: str | None = None,
) -> dict[str, Any]:
    """Read system boot, docs, catalog, or an approved durable memory."""
    try:
        data = read_project_memory(project_root, ref=ref, uri=uri, anchor=anchor)
        return _success("MEMORY_READ", "Memory loaded.", data)
    except DurableMemoryError as exc:
        return _error(exc)


def search_memory_tool(
    project_root: Path | None,
    *,
    query: str,
    scope: str = "durable",
    memory_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search docs lane, durable lane, or both."""
    try:
        search_payload = search_project_memory(
            project_root,
            query=query,
            scope=scope,
            memory_type=memory_type,
            limit=limit,
        )
        return _success(
            "SEARCH_OK",
            "Search completed.",
            search_payload,
            degraded=bool(search_payload["degraded"]),
            degrade_reasons=list(search_payload["degrade_reasons"]),
        )
    except DurableMemoryError as exc:
        return _error(exc)


def propose_memory_tool(
    project_root: Path | None,
    *,
    type: str,
    title: str,
    content: str,
    recall_when: str,
    why_not_in_code: str,
    source_reason: str,
) -> dict[str, Any]:
    """Create a durable memory proposal."""
    try:
        result = insert_create_proposal(
            project_root,
            type=type,
            title=title,
            content=content,
            recall_when=recall_when,
            why_not_in_code=why_not_in_code,
            source_reason=source_reason,
            created_by="mcp",
        )
        code = result["code"]
        message = {
            "PROPOSAL_CREATED": "Proposal created.",
            "NOOP": "Proposal was unnecessary.",
            "UPDATE_TARGET": "Existing memory should be updated instead.",
        }[code]
        return _success(code, message, result)
    except DurableMemoryError as exc:
        return _error(exc)


def propose_memory_update_tool(
    project_root: Path | None,
    *,
    uri: str,
    old_string: str | None = None,
    new_string: str | None = None,
    append: str | None = None,
    recall_when: str | None = None,
    why_not_in_code: str | None = None,
    source_reason: str,
) -> dict[str, Any]:
    """Create a durable memory update proposal."""
    try:
        result = insert_update_proposal(
            project_root,
            uri=uri,
            old_string=old_string,
            new_string=new_string,
            append=append,
            recall_when=recall_when,
            why_not_in_code=why_not_in_code,
            source_reason=source_reason,
            created_by="mcp",
        )
        code = result["code"]
        message = {
            "PROPOSAL_CREATED": "Update proposal created.",
            "NOOP": "Update proposal was unnecessary.",
            "UPDATE_TARGET": "Existing memory should be updated instead.",
        }[code]
        return _success(code, message, result)
    except DurableMemoryError as exc:
        return _error(exc)


def show_memory_review_tool(
    project_root: Path | None,
    *,
    proposal_id: int | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """Return a structured review summary for a pending proposal."""
    try:
        data = show_review_summary(project_root, proposal_id=proposal_id, ref=ref)
        return _success("REVIEW_DETAIL_OK", "Review detail loaded.", data)
    except DurableMemoryError as exc:
        return _error(exc)


def capture_memory_tool(
    project_root: Path | None,
    *,
    kind: str,
    title: str,
    content: str,
    reason: str,
    doc_domain: str | None = None,
    memory_type: str | None = None,
    recall_when: str | None = None,
    why_not_in_code: str | None = None,
) -> dict[str, Any]:
    """Capture new project knowledge via the unified write lane."""
    try:
        data = capture_memory(
            project_root,
            kind=kind,
            title=title,
            content=content,
            reason=reason,
            doc_domain=doc_domain,
            memory_type=memory_type,
            recall_when=recall_when,
            why_not_in_code=why_not_in_code,
        )
        return _success("CAPTURE_OK", "Capture completed.", data)
    except DurableMemoryError as exc:
        return _error(exc)


def update_memory_tool(
    project_root: Path | None,
    *,
    ref: str,
    mode: str,
    old_string: str | None = None,
    new_string: str | None = None,
    append: str | None = None,
    reason: str,
    recall_when: str | None = None,
    why_not_in_code: str | None = None,
) -> dict[str, Any]:
    """Update docs or durable memory via the unified write lane."""
    try:
        data = update_memory(
            project_root,
            ref=ref,
            mode=mode,
            old_string=old_string,
            new_string=new_string,
            append=append,
            reason=reason,
            recall_when=recall_when,
            why_not_in_code=why_not_in_code,
        )
        return _success("UPDATE_OK", "Update completed.", data)
    except DurableMemoryError as exc:
        return _error(exc)
