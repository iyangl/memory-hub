from __future__ import annotations

import argparse
import json
import sys
from uuid import uuid4
from pathlib import Path

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
    tail_events,
    record_decision,
    supersede_decision,
)

DEFAULT_ROOT = Path.home() / ".memory-hub"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory Hub CLI")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Storage root (default: ~/.memory-hub)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    append_parser = subparsers.add_parser("append", help="Append a raw event")
    append_group = append_parser.add_mutually_exclusive_group(required=True)
    append_group.add_argument("--json", help="Event JSON payload")
    append_group.add_argument("--file", type=Path, help="Path to event JSON file")
    append_parser.add_argument("--ack-token", required=True, help="Ack token from turn.begin")

    begin_parser = subparsers.add_parser("turn-begin", help="Begin a new turn")
    begin_parser.add_argument("--project-id", required=True)
    begin_parser.add_argument("--session-id", required=True)
    begin_parser.add_argument("--turn-id", required=True)
    begin_parser.add_argument("--ttl-seconds", type=int)

    end_parser = subparsers.add_parser("turn-end", help="End an open turn")
    end_parser.add_argument("--project-id", required=True)
    end_parser.add_argument("--session-id", required=True)
    end_parser.add_argument("--turn-id", required=True)
    end_parser.add_argument("--ack-token", required=True)

    replay_parser = subparsers.add_parser("replay", help="Replay raw events")
    replay_parser.add_argument("--project-id", required=True)
    replay_parser.add_argument("--session-id")
    replay_parser.add_argument("--turn-id")
    replay_parser.add_argument("--since")
    replay_parser.add_argument("--until")
    replay_parser.add_argument("--limit", type=int)

    tail_parser = subparsers.add_parser("tail", help="Show recent raw events")
    tail_parser.add_argument("--project-id", required=True)
    tail_parser.add_argument("--session-id")
    tail_parser.add_argument("--turn-id")
    tail_parser.add_argument("--limit", type=int, default=20)

    search_parser = subparsers.add_parser("search", help="Search memory facts")
    search_parser.add_argument("--project-id", required=True)
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--limit", type=int, default=10)

    pack_parser = subparsers.add_parser("context-pack", help="Build a context pack")
    pack_parser.add_argument("--project-id", required=True)
    pack_parser.add_argument("--session-id")
    pack_parser.add_argument("--turn-id")
    pack_parser.add_argument("--query")
    pack_parser.add_argument("--recent-limit", type=int, default=20)
    pack_parser.add_argument("--fact-limit", type=int, default=20)
    pack_parser.add_argument("--decision-limit", type=int, default=10)

    log_parser = subparsers.add_parser("turn-log", help="Begin, append, and end a turn")
    log_parser.add_argument("--project-id", required=True)
    log_parser.add_argument("--session-id", required=True)
    log_parser.add_argument("--turn-id")
    log_parser.add_argument("--stream-id")
    log_parser.add_argument("--event-type", default="message")
    log_parser.add_argument("--actor", default="user")
    log_parser.add_argument("--source", default="cli")
    log_parser.add_argument("--message")
    log_parser.add_argument("--payload-json")

    record_parser = subparsers.add_parser("decision-record", help="Record a decision")
    record_group = record_parser.add_mutually_exclusive_group(required=True)
    record_group.add_argument("--json", help="Decision JSON payload")
    record_group.add_argument("--file", type=Path, help="Path to decision JSON file")
    record_parser.add_argument("--ack-token", required=True, help="Ack token from turn.begin")

    supersede_parser = subparsers.add_parser("decision-supersede", help="Supersede a decision")
    supersede_group = supersede_parser.add_mutually_exclusive_group(required=True)
    supersede_group.add_argument("--json", help="Decision supersede JSON payload")
    supersede_group.add_argument("--file", type=Path, help="Path to decision supersede JSON file")
    supersede_parser.add_argument("--ack-token", required=True, help="Ack token from turn.begin")

    return parser.parse_args()


def _load_event(args: argparse.Namespace) -> dict:
    if args.json:
        return json.loads(args.json)
    return json.loads(args.file.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    store = MemoryHubStore(root_dir=args.root)

    if args.command == "append":
        event = _load_event(args)
        project_id = event.get("project_id")
        if not project_id:
            raise SystemExit("project_id is required in event payload")
        conn = store.connect(project_id)
        try:
            event["ack_token"] = args.ack_token
            stored = append_event(conn, event, require_ack=True)
        finally:
            conn.close()
        sys.stdout.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return

    if args.command == "turn-begin":
        conn = store.connect(args.project_id)
        try:
            result = begin_turn(
                conn,
                project_id=args.project_id,
                session_id=args.session_id,
                turn_id=args.turn_id,
                ttl_seconds=args.ttl_seconds or DEFAULT_ACK_TTL_SECONDS,
            )
        finally:
            conn.close()
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        return

    if args.command == "turn-end":
        conn = store.connect(args.project_id)
        try:
            result = end_turn(
                conn,
                project_id=args.project_id,
                session_id=args.session_id,
                turn_id=args.turn_id,
                ack_token=args.ack_token,
            )
        finally:
            conn.close()
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        return

    if args.command == "replay":
        conn = store.connect(args.project_id)
        try:
            events = replay_events(
                conn,
                project_id=args.project_id,
                session_id=args.session_id,
                turn_id=args.turn_id,
                since=args.since,
                until=args.until,
                limit=args.limit,
            )
        finally:
            conn.close()
        sys.stdout.write(json.dumps(events, ensure_ascii=False) + "\n")
        return

    if args.command == "tail":
        conn = store.connect(args.project_id)
        try:
            events = tail_events(
                conn,
                project_id=args.project_id,
                session_id=args.session_id,
                turn_id=args.turn_id,
                limit=args.limit,
            )
        finally:
            conn.close()
        sys.stdout.write(json.dumps(events, ensure_ascii=False) + "\n")
        return

    if args.command == "search":
        conn = store.connect(args.project_id)
        try:
            project_facts(conn, args.project_id)
            facts = search_facts(conn, args.project_id, args.query, limit=args.limit)
        finally:
            conn.close()
        sys.stdout.write(json.dumps(facts, ensure_ascii=False) + "\n")
        return

    if args.command == "context-pack":
        conn = store.connect(args.project_id)
        try:
            pack = context_pack(
                conn,
                project_id=args.project_id,
                session_id=args.session_id,
                turn_id=args.turn_id,
                query=args.query,
                recent_limit=args.recent_limit,
                fact_limit=args.fact_limit,
                decision_limit=args.decision_limit,
            )
        finally:
            conn.close()
        sys.stdout.write(json.dumps(pack, ensure_ascii=False) + "\n")
        return

    if args.command == "turn-log":
        project_id = args.project_id
        session_id = args.session_id
        turn_id = args.turn_id or f"turn_{uuid4().hex}"
        stream_id = args.stream_id or f"{project_id}:{session_id}"

        if args.payload_json:
            payload = json.loads(args.payload_json)
        elif args.message is not None:
            payload = {"text": args.message}
        else:
            raise SystemExit("message or payload-json is required for turn-log")

        conn = store.connect(project_id)
        try:
            begin = begin_turn(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ttl_seconds=DEFAULT_ACK_TTL_SECONDS,
            )
            event = {
                "project_id": project_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "stream_id": stream_id,
                "event_type": args.event_type,
                "event_version": 1,
                "actor": args.actor,
                "source": args.source,
                "ack_token": begin["ack_token"],
                "payload": payload,
            }
            stored = append_event(conn, event, require_ack=True)
            end_turn(conn, project_id, session_id, turn_id, begin["ack_token"])
        finally:
            conn.close()

        sys.stdout.write(
            json.dumps(
                {
                    "turn_id": turn_id,
                    "event": stored,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return

    if args.command == "decision-record":
        payload = _load_event(args)
        project_id = payload.get("project_id")
        session_id = payload.get("session_id")
        turn_id = payload.get("turn_id")
        title = payload.get("title")
        if not project_id or not session_id or not turn_id or not title:
            raise SystemExit("project_id, session_id, turn_id, title are required in decision payload")
        conn = store.connect(project_id)
        try:
            result = record_decision(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ack_token=args.ack_token,
                title=title,
                rationale=payload.get("rationale"),
                status=payload.get("status"),
                decision_id=payload.get("decision_id"),
                artifacts=payload.get("artifacts"),
                actor=payload.get("actor") or "assistant",
                source=payload.get("source") or "decision.record",
                stream_id=payload.get("stream_id"),
            )
        finally:
            conn.close()
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        return

    if args.command == "decision-supersede":
        payload = _load_event(args)
        project_id = payload.get("project_id")
        session_id = payload.get("session_id")
        turn_id = payload.get("turn_id")
        from_decision_id = payload.get("from_decision_id")
        title = payload.get("title")
        if not project_id or not session_id or not turn_id or not from_decision_id or not title:
            raise SystemExit(
                "project_id, session_id, turn_id, from_decision_id, title are required in decision payload"
            )
        conn = store.connect(project_id)
        try:
            result = supersede_decision(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ack_token=args.ack_token,
                from_decision_id=from_decision_id,
                title=title,
                rationale=payload.get("rationale"),
                status=payload.get("status"),
                to_decision_id=payload.get("to_decision_id"),
                artifacts=payload.get("artifacts"),
                actor=payload.get("actor") or "assistant",
                source=payload.get("source") or "decision.supersede",
                stream_id=payload.get("stream_id"),
            )
        finally:
            conn.close()
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
