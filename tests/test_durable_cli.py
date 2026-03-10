"""CLI tests for durable memory review and rollback commands."""

from __future__ import annotations

import json
import sys
from io import StringIO

import pytest

from lib.durable_repo import insert_create_proposal, insert_update_proposal
from tests.durable_test_support import bootstrap_project, fetch_one, seed_approved_memory


def run_cli(args: list[str]) -> tuple[dict[str, object], int]:
    """Run lib.cli.main with captured stdout."""
    from lib.cli import main

    old_stdout = sys.stdout
    old_argv = sys.argv
    sys.stdout = StringIO()
    sys.argv = ["memory-hub", *args]
    try:
        with pytest.raises(SystemExit) as exc_info:
            main()
        return json.loads(sys.stdout.getvalue()), exc_info.value.code
    finally:
        sys.stdout = old_stdout
        sys.argv = old_argv


def test_review_list_returns_pending_items(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="constraint://review-flow",
        memory_type="constraint",
        title="Review Flow",
        content="line a\nline b",
    )
    insert_create_proposal(
        project_root,
        type="decision",
        title="Contract First",
        content="Adopt contract first review flow.",
        recall_when="when planning",
        why_not_in_code="rationale is outside code",
        source_reason="manual review",
        created_by="tester",
    )
    insert_update_proposal(
        project_root,
        uri="constraint://review-flow",
        old_string="line b",
        new_string="line b updated",
        source_reason="manual correction",
        created_by="tester",
    )

    result, code = run_cli(["review", "list", "--project-root", str(project_root)])

    assert code == 0
    assert result["code"] == "REVIEW_QUEUE_OK"
    assert len(result["data"]["items"]) == 2


def test_review_show_create_proposal_returns_empty_baseline_diff(tmp_path):
    project_root = bootstrap_project(tmp_path)
    proposal = insert_create_proposal(
        project_root,
        type="preference",
        title="Review Notes",
        content="Prefer explicit review notes.",
        recall_when="when reviewing",
        why_not_in_code="preference is outside code",
        source_reason="manual review",
        created_by="tester",
    )

    result, code = run_cli(["review", "show", str(proposal["proposal_id"]), "--project-root", str(project_root)])

    assert code == 0
    assert result["code"] == "PROPOSAL_DETAIL_OK"
    assert result["data"]["current_memory"] is None
    assert result["data"]["base_version"] is None
    assert "+Prefer explicit review notes." in result["data"]["computed_diff"]


def test_review_show_update_proposal_returns_current_memory_and_base_version(tmp_path):
    project_root = bootstrap_project(tmp_path)
    version_id = seed_approved_memory(
        project_root,
        uri="constraint://show-update",
        memory_type="constraint",
        title="Show Update",
        content="line a\nline b",
    )
    proposal = insert_update_proposal(
        project_root,
        uri="constraint://show-update",
        old_string="line b",
        new_string="line b updated",
        source_reason="manual correction",
        created_by="tester",
    )

    result, code = run_cli(["review", "show", str(proposal["proposal_id"]), "--project-root", str(project_root)])

    assert code == 0
    assert result["data"]["current_memory"]["uri"] == "constraint://show-update"
    assert result["data"]["base_version"]["version_id"] == version_id


def test_review_show_missing_proposal_returns_business_error(tmp_path):
    project_root = bootstrap_project(tmp_path)

    result, code = run_cli(["review", "show", "999", "--project-root", str(project_root)])

    assert code == 1
    assert result["code"] == "PROPOSAL_NOT_FOUND"


def test_review_approve_success_and_duplicate_approve_error(tmp_path):
    project_root = bootstrap_project(tmp_path)
    proposal = insert_create_proposal(
        project_root,
        type="decision",
        title="Approve Once",
        content="Only approve this proposal once.",
        recall_when="when reviewing",
        why_not_in_code="workflow rationale is outside code",
        source_reason="manual review",
        created_by="tester",
    )

    success, success_code = run_cli(
        ["review", "approve", str(proposal["proposal_id"]), "--project-root", str(project_root)]
    )
    duplicate, duplicate_code = run_cli(
        ["review", "approve", str(proposal["proposal_id"]), "--project-root", str(project_root)]
    )

    assert success_code == 0
    assert success["code"] == "PROPOSAL_APPROVED"
    assert duplicate_code == 1
    assert duplicate["code"] == "PROPOSAL_NOT_PENDING"


def test_review_reject_requires_note(tmp_path):
    project_root = bootstrap_project(tmp_path)
    proposal = insert_create_proposal(
        project_root,
        type="preference",
        title="Reject No Note",
        content="This proposal should require a note.",
        recall_when="when reviewing",
        why_not_in_code="preference is outside code",
        source_reason="manual review",
        created_by="tester",
    )

    result, code = run_cli(["review", "reject", str(proposal["proposal_id"]), "--project-root", str(project_root)])

    assert code == 1
    assert result["code"] == "MISSING_REVIEW_NOTE"


def test_review_reject_success(tmp_path):
    project_root = bootstrap_project(tmp_path)
    proposal = insert_create_proposal(
        project_root,
        type="preference",
        title="Reject Me",
        content="Reject this proposal with a note.",
        recall_when="when reviewing",
        why_not_in_code="preference is outside code",
        source_reason="manual review",
        created_by="tester",
    )

    result, code = run_cli(
        [
            "review",
            "reject",
            str(proposal["proposal_id"]),
            "--note",
            "not accepted",
            "--project-root",
            str(project_root),
        ]
    )
    proposal_row = fetch_one(
        project_root,
        "SELECT status, review_note FROM memory_proposals WHERE proposal_id = ?",
        (proposal["proposal_id"],),
    )

    assert code == 0
    assert result["code"] == "PROPOSAL_REJECTED"
    assert proposal_row is not None
    assert proposal_row["status"] == "rejected"
    assert proposal_row["review_note"] == "not accepted"


def test_rollback_success(tmp_path):
    project_root = bootstrap_project(tmp_path)
    version1 = seed_approved_memory(
        project_root,
        uri="decision://rollback-cli",
        memory_type="decision",
        title="Rollback CLI",
        content="version one",
    )
    seed_approved_memory(
        project_root,
        uri="decision://rollback-cli",
        memory_type="decision",
        title="Rollback CLI",
        content="version two",
    )

    result, code = run_cli(
        [
            "rollback",
            "decision://rollback-cli",
            "--to-version",
            str(version1),
            "--note",
            "rollback requested",
            "--project-root",
            str(project_root),
        ]
    )

    assert code == 0
    assert result["code"] == "ROLLBACK_APPLIED"
    assert result["data"]["from_version_id"] != result["data"]["to_version_id"]


def test_rollback_missing_version_returns_business_error(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="decision://rollback-missing",
        memory_type="decision",
        title="Rollback Missing",
        content="current version",
    )

    result, code = run_cli(
        [
            "rollback",
            "decision://rollback-missing",
            "--to-version",
            "999",
            "--note",
            "rollback requested",
            "--project-root",
            str(project_root),
        ]
    )

    assert code == 1
    assert result["code"] == "VERSION_NOT_FOUND"


def test_review_list_system_error_returns_exit_code_2(tmp_path, monkeypatch):
    project_root = bootstrap_project(tmp_path)
    from lib import review_cli

    def boom(_project_root):
        raise RuntimeError("boom")

    monkeypatch.setattr(review_cli, "list_pending_proposals", boom)

    result, code = run_cli(["review", "list", "--project-root", str(project_root)])

    assert code == 2
    assert result["code"] == "SYSTEM_ERROR"
