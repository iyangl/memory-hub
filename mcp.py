from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from store import (
    MemoryHubStore,
    append_event,
    replay_events,
    begin_turn,
    end_turn,
    DEFAULT_ACK_TTL_SECONDS,
    project_facts,
    search_facts,
    context_pack,
    record_decision,
    supersede_decision,
)


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


TOOL_REGISTRY: List[Tool] = [
    Tool(
        name="turn.begin",
        description="Begin a new turn (Milestone 2).",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_id": {"type": "string"},
                "turn_id": {"type": "string"},
                "ttl_seconds": {"type": ["integer", "null"]},
            },
            "required": ["project_id", "session_id", "turn_id"],
        },
    ),
    Tool(
        name="event.append",
        description="Append a raw event to the event log.",
        input_schema={
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "project_id": {"type": "string"},
                "session_id": {"type": "string"},
                "turn_id": {"type": "string"},
                "stream_id": {"type": "string"},
                "stream_seq": {"type": "integer"},
                "event_type": {"type": "string"},
                "event_version": {"type": "integer"},
                "occurred_at": {"type": "string"},
                "actor": {"type": "string"},
                "source": {"type": "string"},
                "ack_token": {"type": "string"},
                "payload": {},
                "payload_json": {"type": "string"},
                "idempotency_key": {"type": ["string", "null"]},
                "trace_id": {"type": ["string", "null"]},
            },
            "required": [
                "project_id",
                "session_id",
                "turn_id",
                "stream_id",
                "event_type",
                "event_version",
                "actor",
                "source",
                "ack_token",
            ],
        },
    ),
    Tool(
        name="turn.end",
        description="End an open turn (Milestone 2).",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_id": {"type": "string"},
                "turn_id": {"type": "string"},
                "ack_token": {"type": "string"},
            },
            "required": ["project_id", "session_id", "turn_id", "ack_token"],
        },
    ),
    Tool(
        name="memory.search",
        description="Search memory facts (Milestone 3).",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": ["integer", "null"]},
            },
            "required": ["project_id", "query"],
        },
    ),
    Tool(
        name="context.pack",
        description="Build a context pack (Milestone 3).",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_id": {"type": ["string", "null"]},
                "turn_id": {"type": ["string", "null"]},
                "query": {"type": ["string", "null"]},
                "recent_limit": {"type": ["integer", "null"]},
                "fact_limit": {"type": ["integer", "null"]},
                "decision_limit": {"type": ["integer", "null"]},
            },
            "required": ["project_id"],
        },
    ),
    Tool(
        name="decision.record",
        description="Record a decision (Milestone 4).",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_id": {"type": "string"},
                "turn_id": {"type": "string"},
                "ack_token": {"type": "string"},
                "decision_id": {"type": ["string", "null"]},
                "title": {"type": "string"},
                "rationale": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
                "artifacts": {"type": ["array", "null"]},
                "actor": {"type": ["string", "null"]},
                "source": {"type": ["string", "null"]},
                "stream_id": {"type": ["string", "null"]},
            },
            "required": ["project_id", "session_id", "turn_id", "ack_token", "title"],
        },
    ),
    Tool(
        name="decision.supersede",
        description="Supersede a prior decision (Milestone 4).",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_id": {"type": "string"},
                "turn_id": {"type": "string"},
                "ack_token": {"type": "string"},
                "from_decision_id": {"type": "string"},
                "to_decision_id": {"type": ["string", "null"]},
                "title": {"type": "string"},
                "rationale": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
                "artifacts": {"type": ["array", "null"]},
                "actor": {"type": ["string", "null"]},
                "source": {"type": ["string", "null"]},
                "stream_id": {"type": ["string", "null"]},
            },
            "required": [
                "project_id",
                "session_id",
                "turn_id",
                "ack_token",
                "from_decision_id",
                "title",
            ],
        },
    ),
    Tool(
        name="audit.replay",
        description="Replay raw events for audit.",
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_id": {"type": ["string", "null"]},
                "turn_id": {"type": ["string", "null"]},
                "since": {"type": ["string", "null"]},
                "until": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"]},
            },
            "required": ["project_id"],
        },
    ),
]

TOOL_MAP = {tool.name: tool for tool in TOOL_REGISTRY}


class MCPServer:
    def __init__(self, store: MemoryHubStore):
        self.store = store

    def run(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                self._send_error(None, -32700, "Parse error", str(exc))
                continue

            response = self.handle_request(request)
            if response is not None:
                self._send(response)

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

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
            tools = [tool.to_dict() for tool in TOOL_REGISTRY]
            return self._result(request_id, {"tools": tools})

        if method == "tools/call":
            try:
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = self.handle_tool_call(name, arguments)
                return self._result(request_id, {"content": result})
            except Exception as exc:  # pylint: disable=broad-except
                return self._error(request_id, -32000, "Tool call failed", str(exc))

        if method in ("shutdown", "exit"):
            return self._result(request_id, {"ok": True})

        if request_id is None:
            return None

        return self._error(request_id, -32601, "Method not found", method)

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name == "turn.begin":
            return self._tool_turn_begin(arguments)
        if name == "event.append":
            return self._tool_event_append(arguments)
        if name == "turn.end":
            return self._tool_turn_end(arguments)
        if name == "decision.record":
            return self._tool_decision_record(arguments)
        if name == "decision.supersede":
            return self._tool_decision_supersede(arguments)
        if name == "memory.search":
            return self._tool_memory_search(arguments)
        if name == "context.pack":
            return self._tool_context_pack(arguments)
        if name == "audit.replay":
            return self._tool_audit_replay(arguments)

        if name in TOOL_MAP:
            raise NotImplementedError(f"Tool '{name}' not implemented yet")

        raise ValueError(f"Unknown tool '{name}'")

    def _tool_event_append(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        if not project_id:
            raise ValueError("project_id is required")

        conn = self.store.connect(project_id)
        try:
            event = append_event(conn, arguments, require_ack=True)
            return {
                "status": "ok",
                "event": event,
            }
        finally:
            conn.close()

    def _tool_turn_begin(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        session_id = arguments.get("session_id")
        turn_id = arguments.get("turn_id")
        if not project_id or not session_id or not turn_id:
            raise ValueError("project_id, session_id, and turn_id are required")

        ttl_seconds = arguments.get("ttl_seconds")

        conn = self.store.connect(project_id)
        try:
            result = begin_turn(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ttl_seconds=ttl_seconds or DEFAULT_ACK_TTL_SECONDS,
            )
            return {"status": "ok", **result}
        finally:
            conn.close()

    def _tool_turn_end(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        session_id = arguments.get("session_id")
        turn_id = arguments.get("turn_id")
        ack_token = arguments.get("ack_token")
        if not project_id or not session_id or not turn_id or not ack_token:
            raise ValueError("project_id, session_id, turn_id, ack_token are required")

        conn = self.store.connect(project_id)
        try:
            result = end_turn(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ack_token=ack_token,
            )
            return {"status": "ok", **result}
        finally:
            conn.close()

    def _tool_decision_record(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        session_id = arguments.get("session_id")
        turn_id = arguments.get("turn_id")
        ack_token = arguments.get("ack_token")
        title = arguments.get("title")
        if not project_id or not session_id or not turn_id or not ack_token or not title:
            raise ValueError("project_id, session_id, turn_id, ack_token, title are required")

        conn = self.store.connect(project_id)
        try:
            result = record_decision(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ack_token=ack_token,
                title=title,
                rationale=arguments.get("rationale"),
                status=arguments.get("status"),
                decision_id=arguments.get("decision_id"),
                artifacts=arguments.get("artifacts"),
                actor=arguments.get("actor") or "assistant",
                source=arguments.get("source") or "decision.record",
                stream_id=arguments.get("stream_id"),
            )
            return {"status": "ok", **result}
        finally:
            conn.close()

    def _tool_decision_supersede(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        session_id = arguments.get("session_id")
        turn_id = arguments.get("turn_id")
        ack_token = arguments.get("ack_token")
        from_decision_id = arguments.get("from_decision_id")
        title = arguments.get("title")
        if (
            not project_id
            or not session_id
            or not turn_id
            or not ack_token
            or not from_decision_id
            or not title
        ):
            raise ValueError(
                "project_id, session_id, turn_id, ack_token, from_decision_id, title are required"
            )

        conn = self.store.connect(project_id)
        try:
            result = supersede_decision(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ack_token=ack_token,
                from_decision_id=from_decision_id,
                title=title,
                rationale=arguments.get("rationale"),
                status=arguments.get("status"),
                to_decision_id=arguments.get("to_decision_id"),
                artifacts=arguments.get("artifacts"),
                actor=arguments.get("actor") or "assistant",
                source=arguments.get("source") or "decision.supersede",
                stream_id=arguments.get("stream_id"),
            )
            return {"status": "ok", **result}
        finally:
            conn.close()

    def _tool_audit_replay(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        if not project_id:
            raise ValueError("project_id is required")

        conn = self.store.connect(project_id)
        try:
            events = replay_events(
                conn,
                project_id=project_id,
                session_id=arguments.get("session_id"),
                turn_id=arguments.get("turn_id"),
                since=arguments.get("since"),
                until=arguments.get("until"),
                limit=arguments.get("limit"),
            )
            return {
                "status": "ok",
                "events": events,
            }
        finally:
            conn.close()

    def _tool_memory_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        query = arguments.get("query")
        if not project_id or not query:
            raise ValueError("project_id and query are required")

        limit = arguments.get("limit") or 10

        conn = self.store.connect(project_id)
        try:
            project_facts(conn, project_id)
            facts = search_facts(conn, project_id, query, limit=limit)
            return {"status": "ok", "facts": facts}
        finally:
            conn.close()

    def _tool_context_pack(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        project_id = arguments.get("project_id")
        if not project_id:
            raise ValueError("project_id is required")

        conn = self.store.connect(project_id)
        try:
            pack = context_pack(
                conn,
                project_id=project_id,
                session_id=arguments.get("session_id"),
                turn_id=arguments.get("turn_id"),
                query=arguments.get("query"),
                recent_limit=arguments.get("recent_limit") or 20,
                fact_limit=arguments.get("fact_limit") or 20,
                decision_limit=arguments.get("decision_limit") or 10,
            )
            return {"status": "ok", "pack": pack}
        finally:
            conn.close()

    def _send(self, payload: Dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _send_error(self, request_id: Optional[str], code: int, message: str, data: Any = None) -> None:
        self._send(self._error(request_id, code, message, data))

    def _result(self, request_id: Optional[str], result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(self, request_id: Optional[str], code: int, message: str, data: Any = None) -> Dict[str, Any]:
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}
