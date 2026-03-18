"""Unified review view and actions for durable and docs review lanes."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from lib.docs_review import (
    approve_doc_review,
    get_doc_review_by_id,
    get_pending_doc_review_by_ref,
    list_pending_doc_reviews,
    reject_doc_review,
)
from lib.durable_errors import DurableMemoryError
from lib.durable_repo import get_proposal_detail, list_pending_proposals
from lib.durable_review import approve_proposal, reject_proposal
from lib.durable_uri import is_system_boot_uri
from lib.project_memory_view import _require_ref


def list_pending_reviews(project_root: Path | None) -> list[dict[str, Any]]:
    """List pending durable proposals and docs change reviews together."""
    durable_items = [
        {
            **item,
            "review_kind": "durable_review",
            "review_target": str(item["proposal_id"]),
        }
        for item in list_pending_proposals(project_root)
    ]
    docs_items = [
        {
            **item,
            "review_kind": "docs_change_review",
            "review_target": item["doc_ref"],
            "ref": item["doc_ref"],
        }
        for item in list_pending_doc_reviews(project_root)
    ]
    merged = durable_items + docs_items
    merged.sort(key=lambda item: (str(item["created_at"]), str(item["review_target"])))
    return merged


def show_review_summary(
    project_root: Path | None,
    *,
    proposal_id: int | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """Return a structured review summary for durable or docs review."""
    if proposal_id is not None:
        return _show_durable_review(project_root, proposal_id)

    target = _require_ref(ref)
    if target.startswith("doc://"):
        return _show_docs_review(project_root, target)
    if target.startswith("catalog://") or is_system_boot_uri(target):
        raise DurableMemoryError("REVIEW_REF_NOT_SUPPORTED", f"Review ref is not supported: {target}")
    items = [item for item in list_pending_proposals(project_root) if item["target_uri"] == target]
    if not items:
        raise DurableMemoryError("PROPOSAL_NOT_FOUND", f"No pending proposal found for ref: {target}")
    if len(items) > 1:
        raise DurableMemoryError("AMBIGUOUS_PENDING_PROPOSAL", f"Multiple pending proposals found for ref: {target}")
    return _show_durable_review(project_root, int(items[0]["proposal_id"]))


def approve_review(
    project_root: Path | None,
    *,
    proposal_id: int | None = None,
    ref: str | None = None,
    reviewer: str,
    note: str = "",
) -> dict[str, Any]:
    """Approve a review target from either lane."""
    if proposal_id is not None:
        return approve_proposal(project_root, proposal_id, reviewer, note)
    target = _require_ref(ref)
    if target.startswith("doc://"):
        return approve_doc_review(project_root, ref=target, reviewer=reviewer, note=note)
    return approve_proposal(project_root, _resolve_durable_id_by_ref(project_root, target), reviewer, note)


def reject_review(
    project_root: Path | None,
    *,
    proposal_id: int | None = None,
    ref: str | None = None,
    reviewer: str,
    note: str,
) -> dict[str, Any]:
    """Reject a review target from either lane."""
    if proposal_id is not None:
        return reject_proposal(project_root, proposal_id, reviewer, note)
    target = _require_ref(ref)
    if target.startswith("doc://"):
        return reject_doc_review(project_root, ref=target, reviewer=reviewer, note=note)
    return reject_proposal(project_root, _resolve_durable_id_by_ref(project_root, target), reviewer, note)


def _computed_diff(base_content: str, proposal_content: str) -> str:
    diff = difflib.unified_diff(
        base_content.splitlines(),
        proposal_content.splitlines(),
        fromfile="base",
        tofile="proposal",
        lineterm="",
    )
    return "\n".join(diff)


def _resolve_durable_id_by_ref(project_root: Path | None, ref: str) -> int:
    items = [item for item in list_pending_proposals(project_root) if item["target_uri"] == ref]
    if not items:
        raise DurableMemoryError("PROPOSAL_NOT_FOUND", f"No pending proposal found for ref: {ref}")
    if len(items) > 1:
        raise DurableMemoryError("AMBIGUOUS_PENDING_PROPOSAL", f"Multiple pending proposals found for ref: {ref}")
    return int(items[0]["proposal_id"])


def _show_durable_review(project_root: Path | None, proposal_id: int) -> dict[str, Any]:
    detail = get_proposal_detail(project_root, proposal_id)
    base_content = "" if detail["base_version"] is None else detail["base_version"]["content"]
    return {
        "proposal_id": proposal_id,
        "ref": detail["proposal"]["target_uri"],
        "lane": "durable",
        "review_kind": "durable_review",
        "proposal": detail["proposal"],
        "current_memory": detail["current_memory"],
        "base_version": detail["base_version"],
        "computed_diff": _computed_diff(base_content, detail["proposal"]["content"]),
        "allowed_actions": ["approve", "reject"],
    }


def _show_docs_review(project_root: Path | None, ref: str) -> dict[str, Any]:
    review = get_pending_doc_review_by_ref(project_root, ref)
    if review is None:
        raise DurableMemoryError("DOC_REVIEW_NOT_FOUND", f"No pending docs review found for ref: {ref}")
    linked = None
    if review["linked_proposal_id"] is not None:
        proposal = get_proposal_detail(project_root, int(review["linked_proposal_id"]))
        base_content = "" if proposal["base_version"] is None else proposal["base_version"]["content"]
        linked = {
            "proposal_id": review["linked_proposal_id"],
            "target_uri": proposal["proposal"]["target_uri"],
            "computed_diff": _computed_diff(base_content, proposal["proposal"]["content"]),
            "status": proposal["proposal"]["status"],
        }
    return {
        "review_id": review["review_id"],
        "ref": review["doc_ref"],
        "lane": "docs",
        "review_kind": "docs_change_review",
        "doc_review": review,
        "current_memory": None,
        "base_version": None,
        "computed_diff": _computed_diff(review["before_content"], review["after_content"]),
        "linked_durable_review": linked,
        "allowed_actions": ["approve", "reject"],
    }
