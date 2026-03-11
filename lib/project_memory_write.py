"""Unified write routing for project memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib import paths
from lib.docs_memory import parse_doc_ref, render_doc, slugify_doc_title, summary_from_doc
from lib.docs_review import create_doc_review, get_pending_doc_review_by_ref
from lib.durable_errors import DurableMemoryError
from lib.durable_proposal_utils import materialize_candidate_content, validate_update_mode
from lib.durable_repo import (
    get_approved_by_doc_ref,
    get_approved_by_uri,
    insert_create_proposal,
    insert_dual_write_update_proposal,
    insert_update_proposal,
    list_pending_proposals,
)
from lib.durable_store import require_text
from lib.durable_uri import parse_memory_uri
from lib.project_review import show_review_summary

WRITE_KINDS = {"auto", "docs", "durable"}
WRITE_MODES = {"patch", "append"}


def _resolve_route(kind: str, doc_domain: str | None, memory_type: str | None) -> str:
    if kind not in WRITE_KINDS:
        raise DurableMemoryError("INVALID_WRITE_KIND", f"Invalid write kind: {kind}")
    if kind == "docs":
        return "docs-only"
    if kind == "durable":
        return "durable-only"
    has_doc = doc_domain is not None
    has_durable = memory_type is not None
    if has_doc and has_durable:
        return "dual-write"
    if has_doc:
        return "docs-only"
    if has_durable:
        return "durable-only"
    raise DurableMemoryError(
        "INSUFFICIENT_ROUTE_HINTS",
        "auto route requires doc_domain, memory_type, or both.",
    )


def _pending_handoff(project_root: Path | None, ref: str) -> dict[str, Any] | None:
    items = [item for item in list_pending_proposals(project_root) if item["target_uri"] == ref]
    if not items:
        if ref.startswith("doc://"):
            review = get_pending_doc_review_by_ref(project_root, ref)
            if review is None:
                return None
            detail = show_review_summary(project_root, ref=ref)
            return {"route": "pending-review", "review_id": review["review_id"], "review": detail}
        return None
    if len(items) > 1:
        raise DurableMemoryError("AMBIGUOUS_PENDING_PROPOSAL", f"Multiple pending proposals found for ref: {ref}")
    detail = show_review_summary(project_root, proposal_id=int(items[0]["proposal_id"]))
    return {"route": "pending-review", "proposal_id": detail["proposal_id"], "review": detail}


def capture_memory(
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
    created_by: str = "mcp",
) -> dict[str, Any]:
    """Capture new project knowledge through a unified write entry."""
    clean_title = require_text(title, "EMPTY_TITLE", "Title must not be empty.")
    clean_reason = require_text(reason, "MISSING_REASON", "reason must not be empty.")
    route = _resolve_route(kind, doc_domain, memory_type)
    if route == "durable-only":
        if memory_type is None or why_not_in_code is None:
            raise DurableMemoryError("MISSING_DURABLE_FIELDS", "durable capture requires memory_type and why_not_in_code.")
        durable = insert_create_proposal(
            project_root,
            type=memory_type,
            title=clean_title,
            content=require_text(content, "EMPTY_CONTENT", "Content must not be empty."),
            recall_when=recall_when or "",
            why_not_in_code=why_not_in_code,
            source_reason=clean_reason,
            created_by=created_by,
        )
        return {"route": route, "durable_result": durable}

    if doc_domain not in paths.BUCKETS:
        raise DurableMemoryError("INVALID_DOC_DOMAIN", f"Invalid doc_domain: {doc_domain}")
    name = slugify_doc_title(clean_title)
    doc_ref = f"doc://{doc_domain}/{name}"
    doc_content = render_doc(clean_title, content)
    if paths.file_path(doc_domain, f"{name}.md", project_root).exists():
        raise DurableMemoryError("DOC_ALREADY_EXISTS", f"Document already exists: doc://{doc_domain}/{name}")
    existing = _pending_handoff(project_root, doc_ref)
    if existing is not None:
        return existing
    linked_proposal_id = None
    if route == "docs-only":
        durable = None
    else:
        if memory_type is None or why_not_in_code is None:
            raise DurableMemoryError("MISSING_DURABLE_FIELDS", "dual-write capture requires memory_type and why_not_in_code.")
        durable = insert_create_proposal(
            project_root,
            type=memory_type,
            title=clean_title,
            content=summary_from_doc(clean_title, doc_content),
            recall_when=recall_when or "",
            why_not_in_code=why_not_in_code,
            source_reason=clean_reason,
            created_by=created_by,
            storage_lane="dual",
            doc_ref=doc_ref,
        )
        if durable["code"] != "PROPOSAL_CREATED":
            return {"route": route, "durable_result": durable}
        linked_proposal_id = int(durable["proposal_id"])
    docs_result = create_doc_review(
        project_root,
        doc_ref=doc_ref,
        title=clean_title,
        before_content="",
        after_content=doc_content,
        reason=clean_reason,
        created_by=created_by,
        linked_proposal_id=linked_proposal_id,
    )
    result = {
        "route": route,
        "docs_result": docs_result,
        "review_kind": "docs_change_review",
        "review_ref": doc_ref,
    }
    if linked_proposal_id is not None:
        result["durable_result"] = {
            "code": "PROPOSAL_CREATED",
            "proposal_id": linked_proposal_id,
            "proposal_kind": "create",
            "status": "pending",
        }
    return result


def update_memory(
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
    created_by: str = "mcp",
) -> dict[str, Any]:
    """Update docs lane or durable lane through a unified write entry."""
    clean_reason = require_text(reason, "MISSING_REASON", "reason must not be empty.")
    if mode not in WRITE_MODES:
        raise DurableMemoryError("INVALID_UPDATE_MODE", f"Invalid update mode: {mode}")
    validate_update_mode(old_string, new_string, append if mode == "append" else None)

    if ref.startswith("doc://"):
        try:
            bucket, name = parse_doc_ref(ref)
        except ValueError as exc:
            raise DurableMemoryError("INVALID_MEMORY_REF", str(exc)) from exc
        existing = _pending_handoff(project_root, ref)
        if existing is not None:
            return existing
        file_path = paths.file_path(bucket, f"{name}.md", project_root)
        if not file_path.exists():
            raise DurableMemoryError("DOC_NOT_FOUND", f"Document not found: {ref}")
        before = file_path.read_text(encoding="utf-8")
        after = materialize_candidate_content(before, old_string, new_string, append if mode == "append" else None)
        approved = get_approved_by_doc_ref(project_root, ref)
        linked_proposal_id = None
        route = "docs-only"
        durable_result = None
        if approved is not None:
            route = "dual-write"
            durable = insert_dual_write_update_proposal(
                project_root,
                uri=approved["uri"],
                content=summary_from_doc(approved["title"], after),
                recall_when=recall_when,
                why_not_in_code=why_not_in_code,
                source_reason=clean_reason,
                created_by=created_by,
                doc_ref=ref,
            )
            if durable["code"] == "PROPOSAL_CREATED":
                linked_proposal_id = int(durable["proposal_id"])
                durable_result = durable
            else:
                durable_result = durable
        docs_result = create_doc_review(
            project_root,
            doc_ref=ref,
            title=approved["title"] if approved is not None else Path(file_path).stem,
            before_content=before,
            after_content=after,
            reason=clean_reason,
            created_by=created_by,
            linked_proposal_id=linked_proposal_id,
        )
        result = {
            "route": route,
            "docs_result": docs_result,
            "review_kind": "docs_change_review",
            "review_ref": ref,
        }
        if durable_result is not None:
            result["durable_result"] = durable_result
        return result

    parse_memory_uri(ref)
    approved = get_approved_by_uri(project_root, ref)
    if approved is None:
        handoff = _pending_handoff(project_root, ref)
        if handoff is not None:
            return handoff
        raise DurableMemoryError("MEMORY_NOT_FOUND", f"Approved memory not found: {ref}")
    durable = insert_update_proposal(
        project_root,
        uri=ref,
        old_string=old_string,
        new_string=new_string,
        append=append if mode == "append" else None,
        recall_when=recall_when,
        why_not_in_code=why_not_in_code,
        source_reason=clean_reason,
        created_by=created_by,
    )
    return {"route": approved.get("storage_lane", "durable-only"), "durable_result": durable}
