"""Minimal stdio MCP server for durable memory tools."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from lib.durable_mcp_tools import (
    propose_memory_tool,
    propose_memory_update_tool,
    read_memory_tool,
    search_memory_tool,
)

PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "memory-hub"
SERVER_VERSION = "0.1.0"

TOOLS = [
    {
        "name": "read_memory",
        "description": "Read system://boot or an approved durable memory by URI.",
        "inputSchema": {
            "type": "object",
            "properties": {"uri": {"type": "string"}},
            "required": ["uri"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_memory",
        "description": "Search approved durable memories with substring matching.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "type": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_memory",
        "description": "Create a durable memory proposal instead of writing directly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "recall_when": {"type": "string"},
                "why_not_in_code": {"type": "string"},
                "source_reason": {"type": "string"},
            },
            "required": ["type", "title", "content", "recall_when", "why_not_in_code", "source_reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_memory_update",
        "description": "Create a patch/append update proposal for an approved durable memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "append": {"type": "string"},
                "recall_when": {"type": "string"},
                "why_not_in_code": {"type": "string"},
                "source_reason": {"type": "string"},
            },
            "required": ["uri", "source_reason"],
            "additionalProperties": False,
        },
    },
]


def _project_root() -> Path | None:
    value = os.environ.get("MEMORY_HUB_PROJECT_ROOT")
    return Path(value) if value else Path.cwd()


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    if data:
        payload["error"]["data"] = data
    return payload


def _server_info() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": "Call read_memory(system://boot) before durable memory operations. Direct filesystem writes are forbidden.",
    }


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "structuredContent": payload,
        "isError": not payload["ok"],
    }


def _require_args(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    return arguments


def _call_tool(name: str, arguments: dict[str, Any], project_root: Path | None) -> dict[str, Any]:
    if name == "read_memory":
        return read_memory_tool(project_root, uri=arguments.get("uri", ""))
    if name == "search_memory":
        return search_memory_tool(
            project_root,
            query=arguments.get("query", ""),
            memory_type=arguments.get("type"),
            limit=arguments.get("limit", 10),
        )
    if name == "propose_memory":
        return propose_memory_tool(
            project_root,
            type=arguments.get("type", ""),
            title=arguments.get("title", ""),
            content=arguments.get("content", ""),
            recall_when=arguments.get("recall_when", ""),
            why_not_in_code=arguments.get("why_not_in_code", ""),
            source_reason=arguments.get("source_reason", ""),
        )
    if name == "propose_memory_update":
        return propose_memory_update_tool(
            project_root,
            uri=arguments.get("uri", ""),
            old_string=arguments.get("old_string"),
            new_string=arguments.get("new_string"),
            append=arguments.get("append"),
            recall_when=arguments.get("recall_when"),
            why_not_in_code=arguments.get("why_not_in_code"),
            source_reason=arguments.get("source_reason", ""),
        )
    raise KeyError(name)


def handle_message(message: dict[str, Any], project_root: Path | None = None) -> dict[str, Any] | None:
    """Handle one JSON-RPC message and return a response payload if needed."""
    if message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id"), -32600, "Invalid Request")

    method = message.get("method")
    if not isinstance(method, str):
        return _jsonrpc_error(message.get("id"), -32600, "Invalid Request")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _jsonrpc_result(message.get("id"), _server_info())
    if method == "ping":
        return _jsonrpc_result(message.get("id"), {})
    if method == "tools/list":
        return _jsonrpc_result(message.get("id"), {"tools": TOOLS})
    if method != "tools/call":
        return _jsonrpc_error(message.get("id"), -32601, f"Method not found: {method}")

    params = message.get("params")
    if not isinstance(params, dict):
        return _jsonrpc_error(message.get("id"), -32602, "params must be an object")
    name = params.get("name")
    if not isinstance(name, str):
        return _jsonrpc_error(message.get("id"), -32602, "tool name must be a string")

    try:
        arguments = _require_args(params.get("arguments"))
        payload = _call_tool(name, arguments, project_root or _project_root())
    except ValueError as exc:
        return _jsonrpc_error(message.get("id"), -32602, str(exc))
    except KeyError:
        return _jsonrpc_error(message.get("id"), -32602, f"Unknown tool: {name}")
    except Exception as exc:
        return _jsonrpc_error(message.get("id"), -32603, "Internal error", {"reason": type(exc).__name__})
    return _jsonrpc_result(message.get("id"), _tool_result(payload))


def main() -> None:
    """Run the MCP server over newline-delimited JSON-RPC on stdio."""
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = _jsonrpc_error(None, -32700, "Parse error")
        else:
            response = handle_message(message)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
