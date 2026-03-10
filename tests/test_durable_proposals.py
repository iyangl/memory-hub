"""Tests for durable memory proposals and write guard."""

from __future__ import annotations

import pytest

from lib.durable_errors import DurableMemoryError
from lib.durable_repo import insert_create_proposal, insert_update_proposal, search_approved
from tests.durable_test_support import bootstrap_project, count_rows, fetch_one, seed_approved_memory


def test_insert_create_proposal_creates_pending_row_with_stable_target_uri(tmp_path):
    project_root = bootstrap_project(tmp_path)

    result = insert_create_proposal(
        project_root,
        type="decision",
        title="Contract First Plan",
        content="Adopt a contract first implementation plan for durable memory.",
        recall_when="when designing phase1a",
        why_not_in_code="decision rationale is not derivable from code",
        source_reason="manual design review",
        created_by="tester",
    )

    proposal = fetch_one(
        project_root,
        "SELECT * FROM memory_proposals WHERE proposal_id = ?",
        (result["proposal_id"],),
    )
    assert result["code"] == "PROPOSAL_CREATED"
    assert result["target_uri"] == "decision://contract-first-plan"
    assert proposal is not None
    assert proposal["status"] == "pending"
    assert proposal["target_uri"] == "decision://contract-first-plan"


def test_insert_create_proposal_returns_noop_without_inserting_row(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="decision://contract-first",
        memory_type="decision",
        title="Contract First",
        content="Use a contract first plan for durable memory changes.",
    )

    result = insert_create_proposal(
        project_root,
        type="decision",
        title="Contract First Duplicate",
        content="Use a contract first plan for durable memory changes.",
        recall_when="when planning",
        why_not_in_code="duplicate rationale",
        source_reason="manual review",
        created_by="tester",
    )

    assert result["code"] == "NOOP"
    assert result["guard_target_uri"] == "decision://contract-first"
    assert count_rows(project_root, "memory_proposals") == 0


def test_insert_create_proposal_returns_update_target_without_inserting_row(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="decision://contract-first",
        memory_type="decision",
        title="Contract First Strategy",
        content="Adopt contract first design for durable memory review queue and schema.",
    )

    result = insert_create_proposal(
        project_root,
        type="decision",
        title="Contract First Plan",
        content="Adopt contract first design for durable memory review queue and schema with minimal changes.",
        recall_when="when planning",
        why_not_in_code="the rationale is not visible in code",
        source_reason="manual review",
        created_by="tester",
    )

    assert result["code"] == "UPDATE_TARGET"
    assert result["guard_target_uri"] == "decision://contract-first"
    assert count_rows(project_root, "memory_proposals") == 0


def test_insert_update_proposal_materializes_candidate_content(tmp_path):
    project_root = bootstrap_project(tmp_path)
    version_id = seed_approved_memory(
        project_root,
        uri="constraint://review-flow",
        memory_type="constraint",
        title="Review Flow",
        content="line a\nline b\nline c",
    )

    result = insert_update_proposal(
        project_root,
        uri="constraint://review-flow",
        old_string="line b",
        new_string="line b updated",
        source_reason="manual reviewer correction",
        created_by="tester",
    )

    proposal = fetch_one(
        project_root,
        "SELECT * FROM memory_proposals WHERE proposal_id = ?",
        (result["proposal_id"],),
    )
    assert result["code"] == "PROPOSAL_CREATED"
    assert result["base_version_id"] == version_id
    assert proposal is not None
    assert proposal["content"] == "line a\nline b updated\nline c"


def test_insert_update_proposal_rejects_non_unique_old_string(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="constraint://dup-line",
        memory_type="constraint",
        title="Duplicated Line",
        content="repeat\nkeep\nrepeat",
    )

    with pytest.raises(DurableMemoryError) as exc_info:
        insert_update_proposal(
            project_root,
            uri="constraint://dup-line",
            old_string="repeat",
            new_string="changed",
            source_reason="manual correction",
            created_by="tester",
        )

    assert exc_info.value.code == "OLD_STRING_NOT_UNIQUE"


def test_insert_update_proposal_rejects_empty_append(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="constraint://append-empty",
        memory_type="constraint",
        title="Append Empty",
        content="base content",
    )

    with pytest.raises(DurableMemoryError) as exc_info:
        insert_update_proposal(
            project_root,
            uri="constraint://append-empty",
            append="",
            source_reason="manual correction",
            created_by="tester",
        )

    assert exc_info.value.code == "EMPTY_APPEND"


def test_search_approved_never_returns_pending_or_rejected_proposals(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="identity://assistant-role",
        memory_type="identity",
        title="Assistant Role",
        content="Assistant answers repository questions.",
    )
    insert_create_proposal(
        project_root,
        type="identity",
        title="Assistant Role Draft",
        content="Assistant answers repository questions and updates durable memory.",
        recall_when="when starting session",
        why_not_in_code="role contract is not in code",
        source_reason="manual design",
        created_by="tester",
    )

    results = search_approved(project_root, "assistant")

    assert [item["uri"] for item in results] == ["identity://assistant-role"]
