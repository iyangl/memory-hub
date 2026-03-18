"""Tests for the minimal durable memory MCP server."""

from __future__ import annotations

from lib.mcp_server import handle_message
from tests.durable_test_support import bootstrap_project, seed_approved_memory


def test_initialize_returns_server_info(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        project_root,
    )

    assert response is not None
    assert response["result"]["protocolVersion"] == "2025-11-25"
    assert response["result"]["capabilities"]["tools"]["listChanged"] is False


def test_tools_list_exposes_phase2b_tools(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        project_root,
    )

    tools = response["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "read_memory",
        "search_memory",
        "propose_memory",
        "propose_memory_update",
        "capture_memory",
        "update_memory",
        "show_memory_review",
    ]


def test_read_memory_system_boot_returns_identity_and_constraint_only(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="identity://assistant-role",
        memory_type="identity",
        title="Assistant Role",
        content="Answer repository questions.",
    )
    seed_approved_memory(
        project_root,
        uri="constraint://contract-first",
        memory_type="constraint",
        title="Contract First",
        content="Contracts before implementation.",
    )
    seed_approved_memory(
        project_root,
        uri="decision://phase1b",
        memory_type="decision",
        title="Phase 1B",
        content="Review CLI is required.",
    )

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "read_memory", "arguments": {"uri": "system://boot"}},
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["code"] == "MEMORY_READ"
    assert [item["type"] for item in payload["data"]["items"]] == ["identity", "constraint"]
    assert (project_root / ".memory" / "_store" / "projections" / "boot.json").exists()


def test_propose_memory_returns_pending_review_payload(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "propose_memory",
                "arguments": {
                    "type": "decision",
                    "title": "Contract First",
                    "content": "Adopt contract-first development.",
                    "recall_when": "when planning",
                    "why_not_in_code": "rationale is outside code",
                    "source_reason": "manual mcp test",
                },
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["code"] == "PROPOSAL_CREATED"
    assert payload["data"]["proposal_kind"] == "create"
    assert payload["data"]["status"] == "pending"


def test_propose_memory_update_returns_business_error_in_tool_result(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "propose_memory_update",
                "arguments": {
                    "uri": "decision://missing",
                    "old_string": "old",
                    "new_string": "new",
                    "source_reason": "manual mcp test",
                },
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is True
    assert payload["code"] == "MEMORY_NOT_FOUND"


def test_search_memory_returns_approved_matches_only(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="identity://assistant-role",
        memory_type="identity",
        title="Assistant Role",
        content="Assistant answers repository questions.",
    )

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": {"query": "assistant", "limit": 5},
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["code"] == "SEARCH_OK"
    assert payload["data"]["results"][0]["uri"] == "identity://assistant-role"
    assert payload["data"]["scope"] == "durable"


def test_read_memory_supports_doc_refs(tmp_path):
    project_root = bootstrap_project(tmp_path)
    doc_file = project_root / ".memory" / "docs" / "architect" / "decisions.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text("# Decisions\n\n## Contract\nUse unified refs.\n", encoding="utf-8")

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "read_memory",
                "arguments": {"ref": "doc://architect/decisions", "anchor": "contract"},
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["data"]["lane"] == "docs"
    assert payload["data"]["ref"] == "doc://architect/decisions"
    assert payload["data"]["anchor_valid"] is True


def test_read_memory_supports_catalog_refs(tmp_path):
    project_root = bootstrap_project(tmp_path)
    topics = project_root / ".memory" / "catalog" / "topics.md"
    topics.parent.mkdir(parents=True, exist_ok=True)
    topics.write_text("# Topics\n", encoding="utf-8")

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "read_memory", "arguments": {"ref": "catalog://topics"}},
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["data"]["lane"] == "catalog"
    assert payload["data"]["ref"] == "catalog://topics"


def test_search_memory_scope_all_returns_docs_and_durable(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="constraint://mixed-search",
        memory_type="constraint",
        title="Mixed Search",
        content="Use unified refs across durable memory.",
    )
    doc_file = project_root / ".memory" / "docs" / "dev" / "conventions.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text("# Conventions\n\nUse unified refs in docs too.\n", encoding="utf-8")

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": {"query": "unified refs", "scope": "all", "limit": 10},
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    refs = {item["ref"] for item in payload["data"]["results"]}
    assert response["result"]["isError"] is False
    assert payload["data"]["scope"] == "all"
    assert payload["data"]["search_kind"] == "hybrid"
    assert "constraint://mixed-search" in refs
    assert "doc://dev/conventions" in refs
    assert all("lexical_score" in item for item in payload["data"]["results"])
    assert all("semantic_score" in item for item in payload["data"]["results"])
    assert (project_root / ".memory" / "_store" / "projections" / "search.json").exists()


def test_search_memory_degrades_explicitly_when_hybrid_disabled(tmp_path, monkeypatch):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="constraint://lexical-only",
        memory_type="constraint",
        title="Lexical Only",
        content="Use lexical fallback when hybrid is disabled.",
    )
    monkeypatch.setenv("MEMORY_HUB_DISABLE_HYBRID_SEARCH", "1")

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": {"query": "lexical fallback", "scope": "all", "limit": 10},
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["degraded"] is True
    assert payload["degrade_reasons"] == ["hybrid_search_disabled"]
    assert payload["data"]["search_kind"] == "lexical"


def test_show_memory_review_returns_structured_detail(tmp_path):
    project_root = bootstrap_project(tmp_path)
    seed_approved_memory(
        project_root,
        uri="constraint://review-target",
        memory_type="constraint",
        title="Review Target",
        content="line a\nline b",
    )
    create_response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "propose_memory_update",
                "arguments": {
                    "uri": "constraint://review-target",
                    "old_string": "line b",
                    "new_string": "line b updated",
                    "source_reason": "review detail",
                },
            },
        },
        project_root,
    )
    proposal_id = create_response["result"]["structuredContent"]["data"]["proposal_id"]

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "show_memory_review", "arguments": {"proposal_id": proposal_id}},
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["code"] == "REVIEW_DETAIL_OK"
    assert payload["data"]["review_kind"] == "durable_review"
    assert "line b updated" in payload["data"]["computed_diff"]


def test_capture_memory_docs_only_creates_pending_docs_review(tmp_path):
    project_root = bootstrap_project(tmp_path)
    topics = project_root / ".memory" / "catalog" / "topics.md"
    topics.parent.mkdir(parents=True, exist_ok=True)
    topics.write_text("# Topics\n\n## 知识文件\n", encoding="utf-8")

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "capture_memory",
                "arguments": {
                    "kind": "docs",
                    "title": "Phase 2C Notes",
                    "content": "Docs lane becomes the canonical project knowledge surface.",
                    "reason": "phase2c summary",
                    "doc_domain": "pm",
                },
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    doc_file = project_root / ".memory" / "docs" / "pm" / "phase-2c-notes.md"
    assert response["result"]["isError"] is False
    assert payload["code"] == "CAPTURE_OK"
    assert payload["data"]["route"] == "docs-only"
    assert payload["data"]["review_kind"] == "docs_change_review"
    assert payload["data"]["review_ref"] == "doc://pm/phase-2c-notes"
    assert not doc_file.exists()


def test_capture_memory_dual_write_creates_docs_review_and_durable_proposal(tmp_path):
    project_root = bootstrap_project(tmp_path)
    topics = project_root / ".memory" / "catalog" / "topics.md"
    topics.parent.mkdir(parents=True, exist_ok=True)
    topics.write_text("# Topics\n\n## 知识文件\n", encoding="utf-8")

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "capture_memory",
                "arguments": {
                    "kind": "auto",
                    "title": "Contract First",
                    "content": "External contracts must be frozen before implementation.",
                    "reason": "phase2c dual write",
                    "doc_domain": "architect",
                    "memory_type": "constraint",
                    "recall_when": "when planning",
                    "why_not_in_code": "governance rule is outside code",
                },
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["data"]["route"] == "dual-write"
    assert payload["data"]["review_kind"] == "docs_change_review"
    assert payload["data"]["durable_result"]["code"] == "PROPOSAL_CREATED"
    assert payload["data"]["review_ref"] == "doc://architect/contract-first"

    review = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {"name": "show_memory_review", "arguments": {"ref": "doc://architect/contract-first"}},
        },
        project_root,
    )

    review_payload = review["result"]["structuredContent"]
    assert review["result"]["isError"] is False
    assert review_payload["data"]["review_kind"] == "docs_change_review"
    assert review_payload["data"]["linked_durable_review"]["proposal_id"] == payload["data"]["durable_result"]["proposal_id"]


def test_update_memory_doc_ref_syncs_dual_write_summary(tmp_path):
    project_root = bootstrap_project(tmp_path)
    topics = project_root / ".memory" / "catalog" / "topics.md"
    topics.parent.mkdir(parents=True, exist_ok=True)
    topics.write_text("# Topics\n\n## 知识文件\n", encoding="utf-8")

    capture = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "capture_memory",
                "arguments": {
                    "kind": "auto",
                    "title": "Phase 2C Dual",
                    "content": "Docs are canonical.",
                    "reason": "initial",
                    "doc_domain": "architect",
                    "memory_type": "constraint",
                    "recall_when": "when planning",
                    "why_not_in_code": "governance rule is outside code",
                },
            },
        },
        project_root,
    )
    proposal_id = capture["result"]["structuredContent"]["data"]["durable_result"]["proposal_id"]
    from tests.test_durable_cli import run_cli

    approve_result, exit_code = run_cli(
        ["review", "approve", "doc://architect/phase-2c-dual", "--project-root", str(project_root)]
    )
    assert exit_code == 0
    assert approve_result["code"] == "PROPOSAL_APPROVED"
    linked = approve_result["data"]["linked_durable_result"]
    assert linked is not None
    assert linked["proposal_id"] == proposal_id

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {
                "name": "update_memory",
                "arguments": {
                    "ref": "doc://architect/phase-2c-dual",
                    "mode": "append",
                    "append": "\nDurable summaries should stay concise.",
                    "reason": "sync summary",
                },
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["data"]["route"] == "dual-write"
    assert payload["data"]["durable_result"]["code"] == "PROPOSAL_CREATED"
    assert payload["data"]["review_ref"] == "doc://architect/phase-2c-dual"


def test_update_memory_pending_durable_ref_returns_review_handoff(tmp_path):
    project_root = bootstrap_project(tmp_path)
    handle_message(
        {
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/call",
            "params": {
                "name": "propose_memory",
                "arguments": {
                    "type": "decision",
                    "title": "Pending Target",
                    "content": "Pending durable target.",
                    "recall_when": "when planning",
                    "why_not_in_code": "pending review example",
                    "source_reason": "pending setup",
                },
            },
        },
        project_root,
    )

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 18,
            "method": "tools/call",
            "params": {
                "name": "update_memory",
                "arguments": {
                    "ref": "decision://pending-target",
                    "mode": "append",
                    "append": "\nmore detail",
                    "reason": "should hand off",
                },
            },
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["code"] == "UPDATE_OK"
    assert payload["data"]["route"] == "pending-review"
    assert payload["data"]["review"]["review_kind"] == "durable_review"


def test_show_memory_review_doc_ref_returns_docs_review(tmp_path):
    project_root = bootstrap_project(tmp_path)
    topics = project_root / ".memory" / "catalog" / "topics.md"
    topics.parent.mkdir(parents=True, exist_ok=True)
    topics.write_text("# Topics\n\n## 知识文件\n", encoding="utf-8")
    handle_message(
        {
            "jsonrpc": "2.0",
            "id": 19,
            "method": "tools/call",
            "params": {
                "name": "capture_memory",
                "arguments": {
                    "kind": "docs",
                    "title": "Docs Review",
                    "content": "Require docs review before applying.",
                    "reason": "docs review",
                    "doc_domain": "pm",
                },
            },
        },
        project_root,
    )

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "show_memory_review", "arguments": {"ref": "doc://pm/docs-review"}},
        },
        project_root,
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["code"] == "REVIEW_DETAIL_OK"
    assert payload["data"]["review_kind"] == "docs_change_review"
    assert "+Require docs review before applying." in payload["data"]["computed_diff"]


def test_unknown_tool_returns_jsonrpc_invalid_params(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        },
        project_root,
    )

    assert response["error"]["code"] == -32602
    assert "Unknown tool" in response["error"]["message"]


def test_invalid_jsonrpc_request_returns_protocol_error(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message({"id": 20, "method": "tools/list"}, project_root)

    assert response["error"]["code"] == -32600
