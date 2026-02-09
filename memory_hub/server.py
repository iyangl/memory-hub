from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import DEFAULT_ROOT, MemoryStore
from .sync import session_sync_pull, session_sync_push, session_sync_resolve_conflict


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


TOOLS: List[Tool] = [
    Tool(
        name="session.sync.pull",
        description="Pull role-isolated context before task execution.",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "client_id": {"type": "string"},
                "session_id": {"type": "string"},
                "task_prompt": {"type": "string"},
                "task_type": {
                    "type": ["string", "null"],
                    "enum": ["auto", "planning", "design", "implement", "test", "review", None],
                },
                "max_tokens": {"type": ["integer", "null"]},
            },
            "required": ["project_id", "client_id", "session_id", "task_prompt"],
        },
    ),
    Tool(
        name="session.sync.push",
        description="Push session deltas to role memory and handoff packet.",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "client_id": {"type": "string"},
                "session_id": {"type": "string"},
                "context_stamp": {"type": ["string", "null"]},
                "session_summary": {"type": "string"},
                "role_deltas": {"type": ["array", "null"]},
                "decisions_delta": {"type": ["array", "null"]},
                "open_loops_new": {"type": ["array", "null"]},
                "open_loops_closed": {"type": ["array", "null"]},
                "files_touched": {"type": ["array", "null"]},
            },
            "required": ["project_id", "client_id", "session_id", "session_summary"],
        },
    ),
    Tool(
        name="session.sync.resolve_conflict",
        description="Resolve push conflicts with accept_theirs, keep_mine, or merge_note.",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "client_id": {"type": "string"},
                "session_id": {"type": "string"},
                "strategy": {
                    "type": "string",
                    "enum": ["accept_theirs", "keep_mine", "merge_note"],
                },
                "session_summary": {"type": ["string", "null"]},
                "role_deltas": {"type": "array"},
                "decisions_delta": {"type": ["array", "null"]},
                "open_loops_new": {"type": ["array", "null"]},
                "open_loops_closed": {"type": ["array", "null"]},
                "files_touched": {"type": ["array", "null"]},
            },
            "required": ["project_id", "client_id", "session_id", "strategy", "role_deltas"],
        },
    ),
]

TOOL_MAP = {tool.name: tool for tool in TOOLS}


class MCPServer:
    def __init__(self, store: MemoryStore):
        self.store = store

    def run(self) -> None:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                self._send(self._error(None, -32700, "Parse error", str(exc)))
                continue

            response = self.handle_request(request)
            if response is not None:
                self._send(response)

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if method == "initialize":
            return self._result(
                request_id,
                {
                    "protocolVersion": "0.1",
                    "serverInfo": {"name": "memory-hubd", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )

        if method == "tools/list":
            return self._result(request_id, {"tools": [tool.to_dict() for tool in TOOLS]})

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            try:
                result = self.handle_tool_call(name, arguments)
                return self._result(request_id, {"content": result})
            except Exception as exc:  # pylint: disable=broad-except
                return self._error(request_id, -32000, "Tool call failed", str(exc))

        if method in ("shutdown", "exit"):
            return self._result(request_id, {"ok": True})

        if request_id is None:
            return None
        return self._error(request_id, -32601, "Method not found", method)

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "session.sync.pull":
            return session_sync_pull(self.store, arguments)
        if name == "session.sync.push":
            return session_sync_push(self.store, arguments)
        if name == "session.sync.resolve_conflict":
            return session_sync_resolve_conflict(self.store, arguments)
        if name in TOOL_MAP:
            raise NotImplementedError(f"Tool '{name}' is declared but not implemented")
        raise ValueError(f"Unknown tool '{name}'")

    @staticmethod
    def _result(request_id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    @staticmethod
    def _send(payload: Dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory Hub MCP server")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Storage root, default: ~/.memory-hub",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = MCPServer(MemoryStore(root_dir=args.root))
    server.run()


if __name__ == "__main__":
    main()
