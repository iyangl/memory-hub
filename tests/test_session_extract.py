"""Tests for Phase 2F session extraction."""

from __future__ import annotations

from pathlib import Path

from lib.docs_review import approve_doc_review
from tests.durable_test_support import (
    bootstrap_project,
    count_rows,
    fetch_one,
    run_cli_command,
)


def _write_transcript(tmp_path: Path, content: str) -> Path:
    transcript = tmp_path / "session.txt"
    transcript.write_text(content, encoding="utf-8")
    return transcript


def test_session_extract_creates_docs_review(tmp_path):
    project_root = bootstrap_project(tmp_path)
    transcript = _write_transcript(tmp_path, "docs[qa|QA Strategy]: 所有 memory 相关改动都必须补回归测试。")

    result, code = run_cli_command(
        ["session-extract", "--file", str(transcript), "--project-root", str(project_root)]
    )

    review = fetch_one(project_root, "SELECT doc_ref, title, status FROM docs_change_reviews")
    assert code == 0
    assert result["code"] == "SESSION_EXTRACT_OK"
    assert result["data"]["items"][0]["route"] == "docs-only"
    assert review is not None
    assert review["doc_ref"] == "doc://qa/qa-strategy"
    assert review["status"] == "pending"


def test_session_extract_creates_durable_only_proposal(tmp_path):
    project_root = bootstrap_project(tmp_path)
    transcript = _write_transcript(tmp_path, "durable[preference|Chinese Replies]: 用户偏好中文回复，除非明确要求其他语言。")

    result, code = run_cli_command(
        ["session-extract", "--file", str(transcript), "--project-root", str(project_root)]
    )

    proposal = fetch_one(
        project_root,
        "SELECT type, status, title FROM memory_proposals WHERE title = ?",
        ("Chinese Replies",),
    )
    assert code == 0
    assert result["data"]["items"][0]["route"] == "durable-only"
    assert proposal is not None
    assert proposal["type"] == "preference"
    assert proposal["status"] == "pending"


def test_session_extract_creates_dual_write_review_and_proposal(tmp_path):
    project_root = bootstrap_project(tmp_path)
    transcript = _write_transcript(
        tmp_path,
        "dual[architect,constraint|Unified Write Lane]: 所有记忆相关写入都必须走 unified write lane，不能直接改 store。",
    )

    result, code = run_cli_command(
        ["session-extract", "--file", str(transcript), "--project-root", str(project_root)]
    )

    review = fetch_one(
        project_root,
        "SELECT doc_ref, linked_proposal_id, status FROM docs_change_reviews WHERE doc_ref = ?",
        ("doc://architect/unified-write-lane",),
    )
    proposal = fetch_one(
        project_root,
        "SELECT storage_lane, doc_ref, status FROM memory_proposals WHERE doc_ref = ?",
        ("doc://architect/unified-write-lane",),
    )
    assert code == 0
    assert result["data"]["items"][0]["route"] == "dual-write"
    assert review is not None and review["linked_proposal_id"] is not None
    assert proposal is not None
    assert proposal["storage_lane"] == "dual"
    assert proposal["status"] == "pending"


def test_session_extract_updates_existing_doc_review(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed = _write_transcript(tmp_path, "docs[qa|QA Strategy]: 初始测试策略。")
    run_cli_command(["session-extract", "--file", str(seed), "--project-root", str(project_root)])
    approve_doc_review(project_root, ref="doc://qa/qa-strategy", reviewer="tester", note="seed")

    transcript = _write_transcript(tmp_path, "docs[qa|QA Strategy]: 新增一条回归规则。")
    result, code = run_cli_command(
        ["session-extract", "--file", str(transcript), "--project-root", str(project_root)]
    )

    review = fetch_one(
        project_root,
        "SELECT status, after_content FROM docs_change_reviews WHERE doc_ref = ? ORDER BY review_id DESC LIMIT 1",
        ("doc://qa/qa-strategy",),
    )
    assert code == 0
    assert result["data"]["items"][0]["action"] == "update"
    assert review is not None
    assert review["status"] == "pending"
    assert "新增一条回归规则。" in review["after_content"]


def test_session_extract_empty_transcript_produces_no_candidates(tmp_path):
    project_root = bootstrap_project(tmp_path)
    transcript = _write_transcript(tmp_path, "只是普通的进度闲聊，没有稳定知识。")

    result, code = run_cli_command(
        ["session-extract", "--file", str(transcript), "--project-root", str(project_root)]
    )

    assert code == 0
    assert result["data"]["candidate_count"] == 0
    assert result["data"]["items"] == []
    assert count_rows(project_root, "docs_change_reviews") == 0
    assert count_rows(project_root, "memory_proposals") == 0
