from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from store import MemoryHubStore, begin_turn, append_event, end_turn, DEFAULT_ACK_TTL_SECONDS

DEFAULT_ROOT = Path.home() / ".memory-hub"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log a user/assistant turn in one command")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--turn-id")
    parser.add_argument("--stream-id")
    parser.add_argument("--event-type", default="dialog.turn")
    parser.add_argument("--actor", default="assistant")
    parser.add_argument("--source", default="agent.md")

    parser.add_argument("--user")
    parser.add_argument("--assistant")
    parser.add_argument("--user-file", type=Path)
    parser.add_argument("--assistant-file", type=Path)
    parser.add_argument("--extra-json")

    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_payload(args: argparse.Namespace) -> dict:
    user_text = None
    assistant_text = None

    if args.user_file:
        user_text = _read_text(args.user_file)
    elif args.user is not None:
        user_text = args.user

    if args.assistant_file:
        assistant_text = _read_text(args.assistant_file)
    elif args.assistant is not None:
        assistant_text = args.assistant

    if user_text is None or assistant_text is None:
        raise SystemExit("both user and assistant text are required")

    payload = {
        "user": user_text,
        "assistant": assistant_text,
    }

    if args.extra_json:
        extra = json.loads(args.extra_json)
        if isinstance(extra, dict):
            payload.update(extra)

    return payload


def main() -> None:
    args = parse_args()
    payload = _load_payload(args)

    project_id = args.project_id
    session_id = args.session_id
    turn_id = args.turn_id or f"turn_{uuid4().hex}"
    stream_id = args.stream_id or f"{project_id}:{session_id}"

    store = MemoryHubStore(root_dir=args.root)
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

    sys.stdout.write(json.dumps({"turn_id": turn_id, "event": stored}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
