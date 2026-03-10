"""Durable memory tool handlers used by the MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.durable_errors import DurableMemoryError
from lib.durable_repo import (
    get_approved_by_uri,
    get_boot_memories,
    insert_create_proposal,
    insert_update_proposal,
    search_approved,
)
from lib.durable_uri import SYSTEM_BOOT_URI, is_system_boot_uri


def _success(code: str, message: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "code": code,
        "message": message,
        "data": data,
        "degraded": False,
        "degrade_reasons": [],
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


def read_memory_tool(project_root: Path | None, uri: str) -> dict[str, Any]:
    """Read system://boot or an approved durable memory."""
    try:
        if is_system_boot_uri(uri):
            items = get_boot_memories(project_root)
            return _success(
                "MEMORY_READ",
                "Boot memory loaded.",
                {"uri": SYSTEM_BOOT_URI, "items": items},
            )

        memory = get_approved_by_uri(project_root, uri)
        if memory is None:
            raise DurableMemoryError("MEMORY_NOT_FOUND", f"Approved memory not found: {uri}")
        data = {
            "uri": memory["uri"],
            "type": memory["type"],
            "title": memory["title"],
            "content": memory["content"],
            "recall_when": memory["recall_when"],
            "current_version_id": memory["current_version_id"],
            "updated_at": memory["updated_at"],
        }
        return _success("MEMORY_READ", "Memory loaded.", data)
    except DurableMemoryError as exc:
        return _error(exc)


def search_memory_tool(
    project_root: Path | None,
    query: str,
    memory_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search approved durable memories."""
    try:
        results = search_approved(project_root, query, type=memory_type, limit=limit)
        return _success(
            "SEARCH_OK",
            "Search completed.",
            {"query": query, "results": results},
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
