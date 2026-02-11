from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .catalog import catalog_brief_generate, catalog_health_check
from .errors import BusinessError
from .store import DEFAULT_ROOT, MemoryStore, insert_sync_audit
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
        description="Push session deltas to role memory and enqueue catalog refresh job.",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "client_id": {"type": "string"},
                "session_id": {"type": "string"},
                "context_stamp": {"type": ["object", "string", "null"]},
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
    Tool(
        name="catalog.brief.generate",
        description="Generate task-scoped catalog brief from indexed project structure.",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_prompt": {"type": "string"},
                "task_type": {
                    "type": ["string", "null"],
                    "enum": ["auto", "planning", "design", "implement", "test", "review", None],
                },
                "token_budget": {"type": ["integer", "null"]},
            },
            "required": ["project_id", "task_prompt"],
        },
    ),
    Tool(
        name="catalog.health.check",
        description="Return freshness, coverage, pending jobs and consistency status.",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
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
                    "serverInfo": {"name": "memory-hubd", "version": "0.2.0"},
                    "capabilities": {"tools": {}},
                },
            )

        if method == "tools/list":
            return self._result(request_id, {"tools": [tool.to_dict() for tool in TOOLS]})

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            started = perf_counter()
            try:
                result = self.handle_tool_call(name, arguments)
                return self._result(request_id, {"content": result})
            except BusinessError as exc:
                latency_ms = max(int((perf_counter() - started) * 1000), 0)
                self._audit_tool_error(name, arguments, exc.error_code, exc.message, latency_ms)
                return self._error(request_id, -32010, exc.message, exc.to_payload())
            except ValueError as exc:
                latency_ms = max(int((perf_counter() - started) * 1000), 0)
                self._audit_tool_error(name, arguments, "INVALID_PARAMS", str(exc), latency_ms)
                return self._error(request_id, -32602, "Invalid params", str(exc))
            except Exception as exc:  # pylint: disable=broad-except
                latency_ms = max(int((perf_counter() - started) * 1000), 0)
                self._audit_tool_error(name, arguments, "TOOL_CALL_FAILED", str(exc), latency_ms)
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
        if name == "catalog.brief.generate":
            return catalog_brief_generate(self.store, arguments)
        if name == "catalog.health.check":
            return catalog_health_check(self.store, arguments)
        if name in TOOL_MAP:
            raise NotImplementedError(f"Tool '{name}' is declared but not implemented")
        raise ValueError(f"Unknown tool '{name}'")

    def _audit_tool_error(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        error_code: str,
        message: str,
        latency_ms: int,
    ) -> None:
        project_id = arguments.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            return

        client_id = arguments.get("client_id")
        session_id = arguments.get("session_id")
        client = client_id if isinstance(client_id, str) and client_id.strip() else "unknown"
        session = session_id if isinstance(session_id, str) and session_id.strip() else "unknown"

        if tool_name == "session.sync.pull":
            direction = "pull"
        elif tool_name == "session.sync.push":
            direction = "push"
        elif tool_name == "session.sync.resolve_conflict":
            direction = "resolve_conflict"
        elif tool_name == "catalog.brief.generate":
            direction = "catalog_brief"
        elif tool_name == "catalog.health.check":
            direction = "catalog_health"
        else:
            direction = "tool_error"

        conn = None
        try:
            conn = self.store.connect(project_id)
            insert_sync_audit(
                conn,
                sync_id=f"err_{uuid4().hex}",
                project_id=project_id,
                direction=direction,
                client_id=client,
                session_id=session,
                request_payload={"tool": tool_name, "arguments": arguments},
                response_payload={"status": "error", "error_code": error_code, "message": message},
                error_code=error_code,
                latency_ms=latency_ms,
            )
            conn.commit()
        except Exception as exc:
            sys.stderr.write(
                f"_audit_tool_error: failed to write audit for tool={tool_name} "
                f"project={project_id}: {exc}\n"
            )
            if conn is not None:
                conn.rollback()
        finally:
            if conn is not None:
                conn.close()

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
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Workspace root for catalog indexing, default current directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = MCPServer(MemoryStore(root_dir=args.root, workspace_root=args.workspace_root))
    server.run()


if __name__ == "__main__":
    main()
