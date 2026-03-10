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


def test_tools_list_exposes_four_durable_tools(tmp_path):
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


def test_unknown_tool_returns_jsonrpc_invalid_params(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        },
        project_root,
    )

    assert response["error"]["code"] == -32602
    assert "Unknown tool" in response["error"]["message"]


def test_invalid_jsonrpc_request_returns_protocol_error(tmp_path):
    project_root = bootstrap_project(tmp_path)

    response = handle_message({"id": 8, "method": "tools/list"}, project_root)

    assert response["error"]["code"] == -32600
