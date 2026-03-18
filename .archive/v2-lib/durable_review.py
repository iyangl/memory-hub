"""Review and rollback services for durable memory."""

from __future__ import annotations

from pathlib import Path

from lib.durable_db import transaction, utc_now
from lib.durable_errors import DurableMemoryError
from lib.durable_store import (
    get_approved,
    get_proposal,
    get_version,
    insert_version,
    next_version_number,
    require_text,
    upsert_approved,
)
from lib.durable_uri import parse_memory_uri


def _require_note(note: str, code: str) -> str:
    return require_text(note, code, "Review note must not be empty.")


def _insert_audit_event(
    conn,
    *,
    event_type: str,
    proposal_id: int | None,
    uri: str,
    from_version_id: int | None,
    to_version_id: int | None,
    actor: str,
    note: str,
) -> int:
    return conn.execute(
        """
        INSERT INTO audit_events(
            event_type, proposal_id, uri, from_version_id, to_version_id, actor, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_type, proposal_id, uri, from_version_id, to_version_id, actor or "", note, utc_now()),
    ).lastrowid


def _mark_reviewed(conn, proposal_id: int, status: str, reviewer: str, note: str) -> None:
    conn.execute(
        """
        UPDATE memory_proposals
        SET status = ?, reviewed_at = ?, reviewed_by = ?, review_note = ?
        WHERE proposal_id = ?
        """,
        (status, utc_now(), reviewer or "", note, proposal_id),
    )


def _raise_transaction_error(code: str, message: str, exc: Exception) -> None:
    raise DurableMemoryError(code, message, {"reason": type(exc).__name__}) from exc


def approve_proposal(
    project_root: Path | None,
    proposal_id: int,
    reviewer: str,
    note: str = "",
) -> dict[str, int | str | None]:
    """Approve a pending proposal transactionally."""
    try:
        with transaction(project_root) as conn:
            proposal = get_proposal(conn, proposal_id, pending_only=True)
            approved = None if proposal["proposal_kind"] == "create" else get_approved(conn, proposal["target_uri"])
            from_version_id = None if approved is None else approved["current_version_id"]
            if from_version_id != proposal["base_version_id"]:
                raise DurableMemoryError("STALE_PROPOSAL", "Proposal base version is stale.")
            version_id = insert_version(
                conn,
                uri=proposal["target_uri"],
                version_number=next_version_number(conn, proposal["target_uri"]),
                type=proposal["type"],
                storage_lane=proposal.get("storage_lane", "durable"),
                doc_ref=proposal.get("doc_ref"),
                title=proposal["title"],
                content=proposal["content"],
                recall_when=proposal["recall_when"],
                why_not_in_code=proposal["why_not_in_code"],
                source_reason=proposal["source_reason"],
                supersedes_version_id=proposal["base_version_id"],
                created_by=reviewer,
                created_via="approve",
            )
            upsert_approved(conn, uri=proposal["target_uri"], data=proposal, version_id=version_id)
            _mark_reviewed(conn, proposal_id, "approved", reviewer, note)
            audit_id = _insert_audit_event(
                conn,
                event_type="approve",
                proposal_id=proposal_id,
                uri=proposal["target_uri"],
                from_version_id=from_version_id,
                to_version_id=version_id,
                actor=reviewer,
                note=note,
            )
    except DurableMemoryError:
        raise
    except Exception as exc:
        _raise_transaction_error("APPROVE_TRANSACTION_FAILED", "Approve transaction failed.", exc)
    from lib.project_memory_projection import refresh_projections

    refresh_projections(project_root)
    return {
        "proposal_id": proposal_id,
        "uri": proposal["target_uri"],
        "from_version_id": from_version_id,
        "to_version_id": version_id,
        "audit_event_id": audit_id,
    }


def reject_proposal(
    project_root: Path | None,
    proposal_id: int,
    reviewer: str,
    note: str,
) -> dict[str, int | str]:
    """Reject a pending proposal."""
    review_note = _require_note(note, "MISSING_REVIEW_NOTE")
    with transaction(project_root) as conn:
        proposal = get_proposal(conn, proposal_id, pending_only=True)
        _mark_reviewed(conn, proposal_id, "rejected", reviewer, review_note)
        audit_id = _insert_audit_event(
            conn,
            event_type="reject",
            proposal_id=proposal_id,
            uri=proposal["target_uri"],
            from_version_id=proposal["base_version_id"],
            to_version_id=None,
            actor=reviewer,
            note=review_note,
        )
    return {"proposal_id": proposal_id, "status": "rejected", "audit_event_id": audit_id}


def rollback_memory(
    project_root: Path | None,
    uri: str,
    to_version_id: int,
    reviewer: str,
    note: str,
) -> dict[str, int | str]:
    """Rollback approved memory by creating a new version from a historical one."""
    parse_memory_uri(uri)
    review_note = _require_note(note, "MISSING_REVIEW_NOTE")
    try:
        with transaction(project_root) as conn:
            approved = get_approved(conn, uri)
            target_version = get_version(conn, to_version_id)
            if target_version["uri"] != uri:
                raise DurableMemoryError("ROLLBACK_TARGET_MISMATCH", "Rollback target does not belong to the requested URI.")
            version_id = insert_version(
                conn,
                uri=uri,
                version_number=next_version_number(conn, uri),
                type=target_version["type"],
                storage_lane=target_version.get("storage_lane", "durable"),
                doc_ref=target_version.get("doc_ref"),
                title=target_version["title"],
                content=target_version["content"],
                recall_when=target_version["recall_when"],
                why_not_in_code=target_version["why_not_in_code"],
                source_reason=target_version["source_reason"],
                supersedes_version_id=approved["current_version_id"],
                created_by=reviewer,
                created_via="rollback",
            )
            upsert_approved(conn, uri=uri, data=target_version, version_id=version_id)
            audit_id = _insert_audit_event(
                conn,
                event_type="rollback",
                proposal_id=None,
                uri=uri,
                from_version_id=approved["current_version_id"],
                to_version_id=version_id,
                actor=reviewer,
                note=review_note,
            )
    except DurableMemoryError:
        raise
    except Exception as exc:
        _raise_transaction_error("ROLLBACK_TRANSACTION_FAILED", "Rollback transaction failed.", exc)
    from lib.project_memory_projection import refresh_projections

    refresh_projections(project_root)
    return {
        "uri": uri,
        "from_version_id": approved["current_version_id"],
        "to_version_id": version_id,
        "audit_event_id": audit_id,
    }
