from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from store import (
    MemoryHubStore,
    begin_turn,
    end_turn,
    append_event,
    replay_events,
    project_facts,
    search_facts,
    context_pack,
    record_decision,
    supersede_decision,
)


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = MemoryHubStore(root_dir=root)
        project_id = "smoke"
        session_id = "s1"

        conn = store.connect(project_id)
        try:
            # Turn 1: fact append
            turn_id = "t1"
            begin = begin_turn(conn, project_id, session_id, turn_id)
            append_event(
                conn,
                {
                    "project_id": project_id,
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "stream_id": f"{project_id}:{session_id}",
                    "event_type": "memory.fact",
                    "event_version": 1,
                    "actor": "user",
                    "source": "smoke",
                    "ack_token": begin["ack_token"],
                    "payload": {"fact_text": "User likes pizza", "confidence": 0.9},
                },
                require_ack=True,
            )
            end_turn(conn, project_id, session_id, turn_id, begin["ack_token"])

            project_facts(conn, project_id)
            facts = search_facts(conn, project_id, "pizza")
            assert facts, "expected facts"

            # Turn 2: decision record + supersede
            turn_id = "t2"
            begin2 = begin_turn(conn, project_id, session_id, turn_id)
            decision = record_decision(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ack_token=begin2["ack_token"],
                title="Use sqlite",
                rationale="local-first persistence",
                artifacts=[{"artifact_type": "file", "artifact_ref": "schema.sql"}],
            )
            supersede_decision(
                conn,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                ack_token=begin2["ack_token"],
                from_decision_id=decision["decision_id"],
                title="Use sqlite with WAL",
                rationale="better concurrency",
                artifacts=[{"artifact_type": "note", "artifact_ref": "WAL improves read/write"}],
            )
            end_turn(conn, project_id, session_id, turn_id, begin2["ack_token"])

            pack = context_pack(conn, project_id)
            assert pack["decisions"]["nodes"], "expected decisions in pack"

            events = replay_events(conn, project_id=project_id)
            assert len(events) >= 3, "expected events"
        finally:
            conn.close()

    print("smoke_test_ok")


if __name__ == "__main__":
    main()
