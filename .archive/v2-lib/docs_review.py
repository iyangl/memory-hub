"""Persistent docs change review flow for project memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib import paths
from lib.docs_memory import diff_contents, ensure_doc_registered, parse_doc_ref
from lib.durable_db import connect, ensure_schema, transaction, utc_now
from lib.durable_errors import DurableMemoryError
from lib.durable_review import approve_proposal, reject_proposal
from lib.durable_store import require_text
from lib.utils import atomic_write


def get_pending_doc_review_by_ref(project_root: Path | None, doc_ref: str) -> dict[str, Any] | None:
    """Return the pending docs review for a doc ref, if any."""
    ensure_schema(project_root)
    with connect(project_root) as conn:
        row = conn.execute(
            """
            SELECT * FROM docs_change_reviews
            WHERE doc_ref = ? AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (doc_ref,),
        ).fetchone()
    return None if row is None else dict(row)


def get_doc_review_by_id(
    project_root: Path | None,
    review_id: int,
    *,
    pending_only: bool = False,
) -> dict[str, Any]:
    """Load a docs review by numeric identifier."""
    ensure_schema(project_root)
    sql = "SELECT * FROM docs_change_reviews WHERE review_id = ?"
    params: tuple[Any, ...] = (review_id,)
    if pending_only:
        sql += " AND status = 'pending'"
    with connect(project_root) as conn:
        row = conn.execute(sql, params).fetchone()
    if row is None:
        code = "DOC_REVIEW_NOT_PENDING" if pending_only else "DOC_REVIEW_NOT_FOUND"
        raise DurableMemoryError(code, f"Docs review not found: {review_id}")
    return dict(row)


def list_pending_doc_reviews(project_root: Path | None) -> list[dict[str, Any]]:
    """List pending docs change reviews in creation order."""
    ensure_schema(project_root)
    with connect(project_root) as conn:
        rows = conn.execute(
            """
            SELECT review_id, doc_ref, title, reason, linked_proposal_id, created_at, created_by
            FROM docs_change_reviews
            WHERE status = 'pending'
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_doc_review(
    project_root: Path | None,
    *,
    doc_ref: str,
    title: str,
    before_content: str,
    after_content: str,
    reason: str,
    created_by: str,
    linked_proposal_id: int | None = None,
) -> dict[str, Any]:
    """Create a persistent pending docs change review."""
    ensure_schema(project_root)
    clean_title = require_text(title, "EMPTY_TITLE", "Title must not be empty.")
    clean_after = require_text(after_content, "EMPTY_CONTENT", "Content must not be empty.")
    clean_reason = require_text(reason, "MISSING_REASON", "reason must not be empty.")
    if get_pending_doc_review_by_ref(project_root, doc_ref) is not None:
        raise DurableMemoryError("DOC_REVIEW_ALREADY_PENDING", f"Pending docs review already exists: {doc_ref}")

    with transaction(project_root) as conn:
        review_id = conn.execute(
            """
            INSERT INTO docs_change_reviews(
                status, doc_ref, title, before_content, after_content, reason,
                linked_proposal_id, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pending",
                doc_ref,
                clean_title,
                before_content,
                clean_after,
                clean_reason,
                linked_proposal_id,
                utc_now(),
                created_by,
            ),
        ).lastrowid
    return {
        "review_id": review_id,
        "doc_ref": doc_ref,
        "title": clean_title,
        "computed_diff": diff_contents(before_content, clean_after),
        "linked_proposal_id": linked_proposal_id,
        "status": "pending",
    }


def approve_doc_review(
    project_root: Path | None,
    *,
    review_id: int | None = None,
    ref: str | None = None,
    reviewer: str,
    note: str = "",
) -> dict[str, Any]:
    """Apply a docs change review and optionally approve its linked durable proposal."""
    review = _resolve_pending_doc_review(project_root, review_id=review_id, ref=ref)
    bucket, name = parse_doc_ref(review["doc_ref"])
    file_path = paths.file_path(bucket, f"{name}.md", project_root)
    atomic_write(file_path, review["after_content"])
    catalog_result = ensure_doc_registered(
        project_root,
        bucket=bucket,
        filename=f"{name}.md",
        summary=review["reason"],
    )
    linked_result = None
    if review["linked_proposal_id"] is not None:
        linked_result = approve_proposal(project_root, int(review["linked_proposal_id"]), reviewer, note)
    with transaction(project_root) as conn:
        conn.execute(
            """
            UPDATE docs_change_reviews
            SET status = 'approved', reviewed_at = ?, reviewed_by = ?, review_note = ?
            WHERE review_id = ? AND status = 'pending'
            """,
            (utc_now(), reviewer or "", note, review["review_id"]),
        )
        if conn.total_changes != 1:
            raise DurableMemoryError("DOC_REVIEW_NOT_PENDING", f"Docs review is not pending: {review['review_id']}")
    from lib.project_memory_projection import refresh_projections

    refresh_projections(project_root)
    return {
        "review_id": review["review_id"],
        "ref": review["doc_ref"],
        "path": str(file_path),
        "linked_durable_result": linked_result,
        "catalog_result": catalog_result,
    }


def reject_doc_review(
    project_root: Path | None,
    *,
    review_id: int | None = None,
    ref: str | None = None,
    reviewer: str,
    note: str,
) -> dict[str, Any]:
    """Reject a docs change review and its linked durable proposal if present."""
    clean_note = require_text(note, "MISSING_REVIEW_NOTE", "Review note must not be empty.")
    review = _resolve_pending_doc_review(project_root, review_id=review_id, ref=ref)
    linked_result = None
    if review["linked_proposal_id"] is not None:
        linked_result = reject_proposal(project_root, int(review["linked_proposal_id"]), reviewer, clean_note)
    with transaction(project_root) as conn:
        conn.execute(
            """
            UPDATE docs_change_reviews
            SET status = 'rejected', reviewed_at = ?, reviewed_by = ?, review_note = ?
            WHERE review_id = ? AND status = 'pending'
            """,
            (utc_now(), reviewer or "", clean_note, review["review_id"]),
        )
        if conn.total_changes != 1:
            raise DurableMemoryError("DOC_REVIEW_NOT_PENDING", f"Docs review is not pending: {review['review_id']}")
    return {
        "review_id": review["review_id"],
        "ref": review["doc_ref"],
        "status": "rejected",
        "linked_durable_result": linked_result,
    }


def _resolve_pending_doc_review(
    project_root: Path | None,
    *,
    review_id: int | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    if review_id is not None:
        return get_doc_review_by_id(project_root, review_id, pending_only=True)
    target = require_text(ref or "", "INVALID_MEMORY_REF", "ref is required.")
    review = get_pending_doc_review_by_ref(project_root, target)
    if review is None:
        raise DurableMemoryError("DOC_REVIEW_NOT_FOUND", f"No pending docs review found for ref: {target}")
    return review
