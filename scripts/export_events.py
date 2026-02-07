from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from store import MemoryHubStore, replay_events

DEFAULT_ROOT = Path.home() / ".memory-hub"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export raw events to JSONL")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--session-id")
    parser.add_argument("--turn-id")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, help="Output JSONL file (default: stdout)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = MemoryHubStore(root_dir=args.root)
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

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output = args.output.open("w", encoding="utf-8")
        close_output = True
    else:
        output = sys.stdout
        close_output = False

    try:
        for event in events:
            output.write(json.dumps(event, ensure_ascii=False) + "\n")
    finally:
        if close_output:
            output.close()


if __name__ == "__main__":
    main()
