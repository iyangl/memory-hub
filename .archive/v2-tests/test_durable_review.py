"""Tests for durable memory review and rollback services."""

from __future__ import annotations

import pytest

from lib.durable_errors import DurableMemoryError
from lib.durable_repo import insert_create_proposal, insert_update_proposal
from lib.durable_review import approve_proposal, reject_proposal, rollback_memory
from tests.durable_test_support import bootstrap_project, count_rows, fetch_one, seed_approved_memory


def test_approve_proposal_create_writes_version_approved_and_audit(tmp_path):
    project_root = bootstrap_project(tmp_path)
    proposal = insert_create_proposal(
        project_root,
        type="decision",
        title="Contract First",
        content="Adopt contract first durable memory implementation.",
        recall_when="when planning",
        why_not_in_code="design rationale is outside code",
        source_reason="manual review",
        created_by="tester",
    )

    result = approve_proposal(project_root, proposal["proposal_id"], "reviewer")

    approved = fetch_one(
        project_root,
        "SELECT * FROM approved_memories WHERE uri = ?",
        (proposal["target_uri"],),
    )
    proposal_row = fetch_one(
        project_root,
        "SELECT * FROM memory_proposals WHERE proposal_id = ?",
        (proposal["proposal_id"],),
    )
    audit = fetch_one(
        project_root,
        "SELECT * FROM audit_events WHERE event_id = ?",
        (result["audit_event_id"],),
    )
    assert result["from_version_id"] is None
    assert approved is not None
    assert approved["current_version_id"] == result["to_version_id"]
    assert proposal_row is not None
    assert proposal_row["status"] == "approved"
    assert audit is not None
    assert count_rows(project_root, "memory_versions") == 1


def test_approve_proposal_update_creates_new_version_and_switches_current(tmp_path):
    project_root = bootstrap_project(tmp_path)
    version_id = seed_approved_memory(
        project_root,
        uri="constraint://review-flow",
        memory_type="constraint",
        title="Review Flow",
        content="line a\nline b",
    )
    proposal = insert_update_proposal(
        project_root,
        uri="constraint://review-flow",
        old_string="line b",
        new_string="line b updated",
        source_reason="manual reviewer correction",
        created_by="tester",
    )

    result = approve_proposal(project_root, proposal["proposal_id"], "reviewer")

    approved = fetch_one(
        project_root,
        "SELECT * FROM approved_memories WHERE uri = ?",
        ("constraint://review-flow",),
    )
    assert result["from_version_id"] == version_id
    assert result["to_version_id"] != version_id
    assert approved is not None
    assert approved["current_version_id"] == result["to_version_id"]
    assert approved["content"] == "line a\nline b updated"
    assert count_rows(project_root, "memory_versions") == 2


def test_approve_proposal_rejects_stale_update_without_partial_commit(tmp_path):
    project_root = bootstrap_project(tmp_path)
    initial_version = seed_approved_memory(
        project_root,
        uri="constraint://stale-check",
        memory_type="constraint",
        title="Stale Check",
        content="header\nold content\nfooter",
    )
    proposal = insert_update_proposal(
        project_root,
        uri="constraint://stale-check",
        old_string="old content",
        new_string="updated content",
        source_reason="manual update",
        created_by="tester",
    )
    current_version = seed_approved_memory(
        project_root,
        uri="constraint://stale-check",
        memory_type="constraint",
        title="Stale Check",
        content="header\nnew current content\nfooter",
    )

    with pytest.raises(DurableMemoryError) as exc_info:
        approve_proposal(project_root, proposal["proposal_id"], "reviewer")

    proposal_row = fetch_one(
        project_root,
        "SELECT * FROM memory_proposals WHERE proposal_id = ?",
        (proposal["proposal_id"],),
    )
    approved = fetch_one(
        project_root,
        "SELECT * FROM approved_memories WHERE uri = ?",
        ("constraint://stale-check",),
    )
    assert initial_version != current_version
    assert exc_info.value.code == "STALE_PROPOSAL"
    assert proposal_row is not None
    assert proposal_row["status"] == "pending"
    assert approved is not None
    assert approved["current_version_id"] == current_version
    assert count_rows(project_root, "memory_versions") == 2


def test_reject_proposal_only_updates_status_and_audit(tmp_path):
    project_root = bootstrap_project(tmp_path)
    proposal = insert_create_proposal(
        project_root,
        type="preference",
        title="Review Preference",
        content="Prefer explicit review notes.",
        recall_when="when reviewing",
        why_not_in_code="personal preference is outside code",
        source_reason="manual review",
        created_by="tester",
    )

    result = reject_proposal(project_root, proposal["proposal_id"], "reviewer", "not accepted")

    proposal_row = fetch_one(
        project_root,
        "SELECT * FROM memory_proposals WHERE proposal_id = ?",
        (proposal["proposal_id"],),
    )
    approved = fetch_one(
        project_root,
        "SELECT * FROM approved_memories WHERE uri = ?",
        (proposal["target_uri"],),
    )
    assert result["status"] == "rejected"
    assert proposal_row is not None
    assert proposal_row["status"] == "rejected"
    assert approved is None
    assert count_rows(project_root, "audit_events") == 1


def test_rollback_memory_creates_new_version_instead_of_repointing_old_one(tmp_path):
    project_root = bootstrap_project(tmp_path)
    version1 = seed_approved_memory(
        project_root,
        uri="decision://rollback-plan",
        memory_type="decision",
        title="Rollback Plan",
        content="version one",
    )
    version2 = seed_approved_memory(
        project_root,
        uri="decision://rollback-plan",
        memory_type="decision",
        title="Rollback Plan",
        content="version two",
    )

    result = rollback_memory(project_root, "decision://rollback-plan", version1, "reviewer", "rollback requested")

    approved = fetch_one(
        project_root,
        "SELECT * FROM approved_memories WHERE uri = ?",
        ("decision://rollback-plan",),
    )
    latest_version = fetch_one(
        project_root,
        "SELECT * FROM memory_versions WHERE version_id = ?",
        (result["to_version_id"],),
    )
    assert result["from_version_id"] == version2
    assert result["to_version_id"] not in {version1, version2}
    assert approved is not None
    assert approved["current_version_id"] == result["to_version_id"]
    assert latest_version is not None
    assert latest_version["content"] == "version one"
    assert latest_version["supersedes_version_id"] == version2


def test_rollback_memory_failure_does_not_leave_partial_commit(tmp_path, monkeypatch):
    project_root = bootstrap_project(tmp_path)
    version1 = seed_approved_memory(
        project_root,
        uri="decision://rollback-failure",
        memory_type="decision",
        title="Rollback Failure",
        content="version one",
    )
    version2 = seed_approved_memory(
        project_root,
        uri="decision://rollback-failure",
        memory_type="decision",
        title="Rollback Failure",
        content="version two",
    )

    from lib import durable_review

    def fail_audit(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(durable_review, "_insert_audit_event", fail_audit)

    with pytest.raises(DurableMemoryError) as exc_info:
        rollback_memory(project_root, "decision://rollback-failure", version1, "reviewer", "rollback requested")

    approved = fetch_one(
        project_root,
        "SELECT * FROM approved_memories WHERE uri = ?",
        ("decision://rollback-failure",),
    )
    assert exc_info.value.code == "ROLLBACK_TRANSACTION_FAILED"
    assert approved is not None
    assert approved["current_version_id"] == version2
    assert count_rows(project_root, "memory_versions") == 2
    assert count_rows(project_root, "audit_events") == 0
