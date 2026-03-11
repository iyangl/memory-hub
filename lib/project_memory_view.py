"""Unified read/search helpers for project memory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lib import paths
from lib.durable_errors import DurableMemoryError
from lib.durable_repo import get_approved_by_uri
from lib.durable_uri import SYSTEM_BOOT_URI, is_system_boot_uri, parse_memory_uri
from lib.memory_read import find_anchor
from lib.project_memory_projection import hybrid_search, load_boot_projection

SEARCH_SCOPES = {"docs", "durable", "all"}


def _require_ref(ref: str | None, uri: str | None = None) -> str:
    value = (ref or uri or "").strip()
    if not value:
        raise DurableMemoryError("INVALID_MEMORY_REF", "ref is required.")
    return value


def _parse_doc_ref(ref: str) -> tuple[str, str] | None:
    if not ref.startswith("doc://"):
        return None
    body = ref.removeprefix("doc://")
    parts = body.split("/")
    if len(parts) != 2 or parts[0] not in paths.BUCKETS or not parts[1]:
        raise DurableMemoryError("INVALID_MEMORY_REF", f"Invalid doc ref: {ref}")
    return parts[0], parts[1]


def _parse_catalog_ref(ref: str) -> tuple[str, str | None] | None:
    if ref == "catalog://topics":
        return "topics", None
    if not ref.startswith("catalog://modules/"):
        return None
    module_name = ref.removeprefix("catalog://modules/").strip()
    if not module_name:
        raise DurableMemoryError("INVALID_MEMORY_REF", f"Invalid catalog ref: {ref}")
    return "module", module_name


def _first_heading(content: str, fallback: str) -> str:
    for line in content.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line)
        if match:
            return match.group(1).strip()
    return fallback


def _read_doc(project_root: Path | None, ref: str, anchor: str | None) -> dict[str, Any]:
    parsed = _parse_doc_ref(ref)
    if parsed is None:
        raise DurableMemoryError("INVALID_MEMORY_REF", f"Invalid doc ref: {ref}")
    bucket, name = parsed
    file_path = paths.file_path(bucket, f"{name}.md", project_root)
    if not file_path.exists():
        raise DurableMemoryError("DOC_NOT_FOUND", f"Document not found: {ref}")
    content = file_path.read_text(encoding="utf-8")
    data = {
        "ref": ref,
        "lane": "docs",
        "source_kind": "doc",
        "bucket": bucket,
        "name": name,
        "content": content,
        "title": _first_heading(content, name),
    }
    if anchor is not None:
        data["anchor"] = anchor
        data["anchor_valid"] = find_anchor(content, anchor)
    return data


def _read_catalog(project_root: Path | None, ref: str) -> dict[str, Any]:
    parsed = _parse_catalog_ref(ref)
    if parsed is None:
        raise DurableMemoryError("INVALID_MEMORY_REF", f"Invalid catalog ref: {ref}")
    target, name = parsed
    file_path = paths.topics_path(project_root) if target == "topics" else paths.module_file_path(name or "", project_root)
    if not file_path.exists():
        raise DurableMemoryError("CATALOG_NOT_FOUND", f"Catalog file not found: {ref}")
    content = file_path.read_text(encoding="utf-8")
    return {
        "ref": ref,
        "lane": "catalog",
        "source_kind": "catalog",
        "target": target,
        "name": name,
        "content": content,
        "title": _first_heading(content, name or "topics"),
    }


def read_project_memory(
    project_root: Path | None,
    *,
    ref: str | None = None,
    uri: str | None = None,
    anchor: str | None = None,
) -> dict[str, Any]:
    """Read system boot, docs, catalog, or durable memory by unified ref."""
    target = _require_ref(ref, uri)
    if is_system_boot_uri(target):
        return load_boot_projection(project_root)

    if target.startswith("doc://"):
        return _read_doc(project_root, target, anchor)

    if target.startswith("catalog://"):
        return _read_catalog(project_root, target)

    try:
        parse_memory_uri(target)
    except DurableMemoryError as exc:
        raise DurableMemoryError("INVALID_MEMORY_REF", exc.message, exc.details) from exc
    memory = get_approved_by_uri(project_root, target)
    if memory is None:
        raise DurableMemoryError("MEMORY_NOT_FOUND", f"Approved memory not found: {target}")
    return {
        "ref": target,
        "uri": memory["uri"],
        "lane": "durable",
        "source_kind": "durable",
        "type": memory["type"],
        "storage_lane": memory.get("storage_lane", "durable"),
        "doc_ref": memory.get("doc_ref"),
        "title": memory["title"],
        "content": memory["content"],
        "recall_when": memory["recall_when"],
        "current_version_id": memory["current_version_id"],
        "updated_at": memory["updated_at"],
    }


def search_project_memory(
    project_root: Path | None,
    *,
    query: str,
    scope: str = "durable",
    memory_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search docs lane, durable lane, or both."""
    normalized_scope = scope or "durable"
    if normalized_scope not in SEARCH_SCOPES:
        raise DurableMemoryError("INVALID_SCOPE", f"Invalid search scope: {normalized_scope}")
    return hybrid_search(
        project_root,
        query=query,
        scope=normalized_scope,
        memory_type=memory_type,
        limit=limit,
    )
