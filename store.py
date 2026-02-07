from __future__ import annotations

import json
import secrets
import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

import db as db_module

REQUIRED_FIELDS = [
    "project_id",
    "session_id",
    "turn_id",
    "stream_id",
    "event_type",
    "event_version",
    "actor",
    "source",
]

TURN_STATUS_OPEN = "open"
TURN_STATUS_CLOSED = "closed"
TURN_STATUS_INCOMPLETE = "incomplete"

DEFAULT_ACK_TTL_SECONDS = 300
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass
class MemoryHubStore:
    root_dir: Path

    def db_path(self, project_id: str) -> Path:
        _validate_project_id(project_id)
        return self.root_dir / "projects" / project_id / "events.db"

    def connect(self, project_id: str):
        return db_module.ensure_db(self.db_path(project_id))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _validate_project_id(project_id: str) -> None:
    if not project_id:
        raise ValueError("project_id is required")
    if project_id != project_id.strip():
        raise ValueError("project_id contains leading/trailing whitespace")
    if ".." in project_id:
        raise ValueError("project_id cannot contain '..'")
    if not PROJECT_ID_PATTERN.match(project_id):
        raise ValueError("project_id has invalid characters")

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_expired(expires_at: str) -> bool:
    return _utc_now_dt() >= datetime.fromisoformat(expires_at)


def begin_turn(
    conn,
    project_id: str,
    session_id: str,
    turn_id: str,
    ttl_seconds: int = DEFAULT_ACK_TTL_SECONDS,
) -> Dict[str, str]:
    existing = conn.execute(
        """
        SELECT status, expires_at
        FROM turns
        WHERE project_id = ? AND session_id = ? AND turn_id = ?
        """,
        (project_id, session_id, turn_id),
    ).fetchone()

    if existing is not None:
        status = existing["status"]
        expires_at = existing["expires_at"]
        if status == TURN_STATUS_OPEN and expires_at and _is_expired(expires_at):
            conn.execute(
                """
                UPDATE turns
                SET status = ?
                WHERE project_id = ? AND session_id = ? AND turn_id = ?
                """,
                (TURN_STATUS_INCOMPLETE, project_id, session_id, turn_id),
            )
            conn.commit()
        raise ValueError("turn already exists")

    ack_token = secrets.token_urlsafe(32)
    ack_token_hash = _hash_token(ack_token)
    expires_at_dt = _utc_now_dt() + timedelta(seconds=ttl_seconds)
    expires_at = expires_at_dt.isoformat()

    conn.execute(
        """
        INSERT INTO turns (
            project_id, session_id, turn_id, status, ack_token_hash, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            session_id,
            turn_id,
            TURN_STATUS_OPEN,
            ack_token_hash,
            expires_at,
        ),
    )
    conn.commit()

    return {"ack_token": ack_token, "expires_at": expires_at}


def _require_valid_ack(
    conn,
    project_id: str,
    session_id: str,
    turn_id: str,
    ack_token: str,
) -> None:
    row = conn.execute(
        """
        SELECT status, ack_token_hash, expires_at
        FROM turns
        WHERE project_id = ? AND session_id = ? AND turn_id = ?
        """,
        (project_id, session_id, turn_id),
    ).fetchone()

    if row is None:
        raise ValueError("turn not found")

    if row["status"] != TURN_STATUS_OPEN:
        raise ValueError("turn is not open")

    expires_at = row["expires_at"]
    if expires_at and _is_expired(expires_at):
        conn.execute(
            """
            UPDATE turns
            SET status = ?
            WHERE project_id = ? AND session_id = ? AND turn_id = ?
            """,
            (TURN_STATUS_INCOMPLETE, project_id, session_id, turn_id),
        )
        conn.commit()
        raise ValueError("ack_token expired")

    ack_hash = _hash_token(ack_token)
    if not hmac.compare_digest(ack_hash, row["ack_token_hash"] or ""):
        raise ValueError("ack_token invalid")


def end_turn(
    conn,
    project_id: str,
    session_id: str,
    turn_id: str,
    ack_token: str,
) -> Dict[str, str]:
    _require_valid_ack(conn, project_id, session_id, turn_id, ack_token)

    conn.execute(
        """
        UPDATE turns
        SET status = ?
        WHERE project_id = ? AND session_id = ? AND turn_id = ?
        """,
        (TURN_STATUS_CLOSED, project_id, session_id, turn_id),
    )
    conn.commit()
    return {"status": TURN_STATUS_CLOSED}



def _next_stream_seq(conn, stream_id: str) -> int:
    row = conn.execute(
        "SELECT MAX(stream_seq) AS max_seq FROM raw_events WHERE stream_id = ?",
        (stream_id,),
    ).fetchone()
    if row is None or row["max_seq"] is None:
        return 1
    return int(row["max_seq"]) + 1


def _normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    missing = [key for key in REQUIRED_FIELDS if key not in event]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    normalized = dict(event)
    normalized.setdefault("event_id", f"evt_{uuid4().hex}")
    normalized.setdefault("occurred_at", _utc_now())

    if "stream_seq" not in normalized or normalized["stream_seq"] is None:
        normalized["stream_seq"] = None

    payload_json = normalized.get("payload_json")
    if payload_json is None:
        payload = normalized.get("payload", {})
        payload_json = json.dumps(payload, ensure_ascii=False)
    normalized["payload_json"] = payload_json
    normalized.setdefault("idempotency_key", None)
    normalized.setdefault("trace_id", None)

    return normalized


def append_event(
    conn,
    event: Dict[str, Any],
    require_ack: bool = False,
    commit: bool = True,
) -> Dict[str, Any]:
    normalized = _normalize_event(event)
    if require_ack:
        ack_token = event.get("ack_token")
        if not ack_token:
            raise ValueError("ack_token is required")
        _require_valid_ack(
            conn,
            normalized["project_id"],
            normalized["session_id"],
            normalized["turn_id"],
            ack_token,
        )
    normalized.pop("ack_token", None)

    if normalized["stream_seq"] is None:
        normalized["stream_seq"] = _next_stream_seq(conn, normalized["stream_id"])

    conn.execute(
        """
        INSERT INTO raw_events (
            event_id,
            project_id,
            session_id,
            turn_id,
            stream_id,
            stream_seq,
            event_type,
            event_version,
            occurred_at,
            actor,
            source,
            payload_json,
            idempotency_key,
            trace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized["event_id"],
            normalized["project_id"],
            normalized["session_id"],
            normalized["turn_id"],
            normalized["stream_id"],
            normalized["stream_seq"],
            normalized["event_type"],
            normalized["event_version"],
            normalized["occurred_at"],
            normalized["actor"],
            normalized["source"],
            normalized["payload_json"],
            normalized["idempotency_key"],
            normalized["trace_id"],
        ),
    )
    if commit:
        conn.commit()
    return normalized


def _row_to_event(row) -> Dict[str, Any]:
    event = dict(row)
    payload_json = event.get("payload_json", "{}")
    event["payload_json"] = payload_json
    try:
        event["payload"] = json.loads(payload_json)
    except json.JSONDecodeError:
        event["payload"] = payload_json
    return event


def replay_events(
    conn,
    project_id: str,
    session_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    clauses = ["project_id = ?"]
    params: List[Any] = [project_id]

    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if turn_id:
        clauses.append("turn_id = ?")
        params.append(turn_id)
    if since:
        clauses.append("occurred_at >= ?")
        params.append(since)
    if until:
        clauses.append("occurred_at <= ?")
        params.append(until)

    sql = "SELECT * FROM raw_events WHERE " + " AND ".join(clauses)
    sql += " ORDER BY stream_id, stream_seq"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_event(row) for row in rows]


def tail_events(
    conn,
    project_id: str,
    session_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    clauses = ["project_id = ?"]
    params: List[Any] = [project_id]

    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if turn_id:
        clauses.append("turn_id = ?")
        params.append(turn_id)

    sql = "SELECT * FROM raw_events WHERE " + " AND ".join(clauses)
    sql += " ORDER BY occurred_at DESC, stream_id DESC, stream_seq DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_event(row) for row in rows]


FACTS_PROJECTOR_ID = "facts_v1"


def _projector_key(stream_id: str) -> str:
    return f"{FACTS_PROJECTOR_ID}:{stream_id}"


def _extract_fact_entries(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = event.get("payload", {})
    facts: List[Dict[str, Any]] = []

    def add_fact(text: Any, confidence: Any = None) -> None:
        if not isinstance(text, str):
            return
        text = text.strip()
        if not text:
            return
        conf = confidence
        if not isinstance(conf, (int, float)):
            conf = payload.get("confidence", 0.6)
        if not isinstance(conf, (int, float)):
            conf = 0.6
        facts.append({"fact_text": text, "confidence": float(conf)})

    if isinstance(payload, dict):
        if "fact_text" in payload:
            add_fact(payload.get("fact_text"), payload.get("confidence"))
        elif "fact" in payload:
            add_fact(payload.get("fact"), payload.get("confidence"))

        raw_facts = payload.get("facts")
        if isinstance(raw_facts, list):
            for item in raw_facts:
                if isinstance(item, dict):
                    add_fact(item.get("text") or item.get("fact_text"), item.get("confidence"))
                else:
                    add_fact(item)

        if not facts and event.get("event_type", "").startswith("memory.fact"):
            add_fact(payload.get("text") or payload.get("fact_text") or payload.get("fact"))

    return facts


def project_facts(conn, project_id: str) -> int:
    streams = conn.execute(
        "SELECT DISTINCT stream_id FROM raw_events WHERE project_id = ?",
        (project_id,),
    ).fetchall()

    inserted = 0
    for row in streams:
        stream_id = row["stream_id"]
        projector_id = _projector_key(stream_id)
        offset_row = conn.execute(
            "SELECT stream_seq FROM projection_offsets WHERE projector_id = ?",
            (projector_id,),
        ).fetchone()
        last_seq = offset_row["stream_seq"] if offset_row else 0

        events = conn.execute(
            """
            SELECT * FROM raw_events
            WHERE project_id = ? AND stream_id = ? AND stream_seq > ?
            ORDER BY stream_seq
            """,
            (project_id, stream_id, last_seq),
        ).fetchall()

        if not events:
            continue

        for event_row in events:
            event = _row_to_event(event_row)
            fact_entries = _extract_fact_entries(event)
            for idx, fact in enumerate(fact_entries):
                fact_id = f"fact_{event['event_id']}_{idx}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO memory_facts (
                        fact_id, project_id, fact_text, confidence, source_event_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact_id,
                        project_id,
                        fact["fact_text"],
                        fact["confidence"],
                        event["event_id"],
                        event["occurred_at"],
                    ),
                )
                inserted += 1

            last_seq = event["stream_seq"]

        conn.execute(
            """
            INSERT OR REPLACE INTO projection_offsets (
                projector_id, stream_id, stream_seq, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                projector_id,
                stream_id,
                last_seq,
                _utc_now(),
            ),
        )

    conn.commit()
    return inserted


def search_facts(
    conn,
    project_id: str,
    query: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    if not query:
        return []

    terms = [term.strip().lower() for term in query.split() if term.strip()]
    if not terms:
        return []

    where = " AND ".join(["LOWER(fact_text) LIKE ?"] * len(terms))
    params: List[Any] = [project_id]
    params.extend([f"%{term}%" for term in terms])
    params.append(limit)

    sql = (
        "SELECT * FROM memory_facts WHERE project_id = ? AND "
        + where
        + " ORDER BY created_at DESC LIMIT ?"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def context_pack(
    conn,
    project_id: str,
    session_id: Optional[str] = None,
    turn_id: Optional[str] = None,
    query: Optional[str] = None,
    recent_limit: int = 20,
    fact_limit: int = 20,
    decision_limit: int = 10,
) -> Dict[str, Any]:
    project_facts(conn, project_id)

    clauses = ["project_id = ?"]
    params: List[Any] = [project_id]
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if turn_id:
        clauses.append("turn_id = ?")
        params.append(turn_id)

    event_sql = "SELECT * FROM raw_events WHERE " + " AND ".join(clauses)
    event_sql += " ORDER BY occurred_at DESC LIMIT ?"
    event_rows = conn.execute(event_sql, params + [recent_limit]).fetchall()
    recent_events = [_row_to_event(row) for row in event_rows]

    if query:
        facts = search_facts(conn, project_id, query, limit=fact_limit)
    else:
        facts = conn.execute(
            """
            SELECT * FROM memory_facts
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (project_id, fact_limit),
        ).fetchall()
        facts = [dict(row) for row in facts]

    decision_rows = conn.execute(
        """
        SELECT * FROM decisions
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (project_id, decision_limit),
    ).fetchall()
    decisions = [dict(row) for row in decision_rows]

    decision_ids = [row["decision_id"] for row in decision_rows]
    edges: List[Dict[str, Any]] = []
    if decision_ids:
        placeholder = ",".join(["?"] * len(decision_ids))
        edge_rows = conn.execute(
            f"""
            SELECT * FROM decision_edges
            WHERE project_id = ?
              AND (from_decision_id IN ({placeholder}) OR to_decision_id IN ({placeholder}))
            """,
            [project_id, *decision_ids, *decision_ids],
        ).fetchall()
        edges = [dict(row) for row in edge_rows]

    return {
        "project_id": project_id,
        "generated_at": _utc_now(),
        "recent_events": recent_events,
        "facts": facts,
        "decisions": {"nodes": decisions, "edges": edges},
        "query": query,
    }


DECISION_STATUS_ACTIVE = "active"
DECISION_STATUS_SUPERSEDED = "superseded"


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _normalize_artifacts(artifacts: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not artifacts:
        return []
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be a list")
    normalized: List[Dict[str, Any]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        artifact_type = item.get("artifact_type") or item.get("type")
        artifact_ref = item.get("artifact_ref") or item.get("ref")
        note = item.get("note")
        if not artifact_type or not artifact_ref:
            continue
        normalized.append(
            {
                "artifact_type": str(artifact_type),
                "artifact_ref": str(artifact_ref),
                "note": note,
            }
        )
    return normalized


def _insert_artifact_links(
    conn,
    project_id: str,
    decision_id: str,
    artifacts: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    entries = _normalize_artifacts(artifacts)
    if not entries:
        return []
    created_at = _utc_now()
    links: List[Dict[str, Any]] = []
    for entry in entries:
        link_id = _generate_id("link")
        conn.execute(
            """
            INSERT INTO artifact_links (
                link_id, project_id, decision_id, artifact_type, artifact_ref, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link_id,
                project_id,
                decision_id,
                entry["artifact_type"],
                entry["artifact_ref"],
                entry.get("note"),
                created_at,
            ),
        )
        links.append(
            {
                "link_id": link_id,
                "artifact_type": entry["artifact_type"],
                "artifact_ref": entry["artifact_ref"],
                "note": entry.get("note"),
                "created_at": created_at,
            }
        )
    return links


def record_decision(
    conn,
    project_id: str,
    session_id: str,
    turn_id: str,
    ack_token: str,
    title: str,
    rationale: Optional[str] = None,
    status: Optional[str] = None,
    decision_id: Optional[str] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    actor: str = "assistant",
    source: str = "decision.record",
    stream_id: Optional[str] = None,
    event_version: int = 1,
) -> Dict[str, Any]:
    if not title:
        raise ValueError("title is required")
    _require_valid_ack(conn, project_id, session_id, turn_id, ack_token)

    decision_id = decision_id or _generate_id("dec")
    created_at = _utc_now()
    status_value = status or DECISION_STATUS_ACTIVE

    event_payload = {
        "decision_id": decision_id,
        "title": title,
        "rationale": rationale,
        "status": status_value,
        "artifacts": artifacts or [],
    }
    event = {
        "project_id": project_id,
        "session_id": session_id,
        "turn_id": turn_id,
        "stream_id": stream_id or f"{project_id}:{session_id}",
        "event_type": "decision.recorded",
        "event_version": event_version,
        "actor": actor,
        "source": source,
        "payload": event_payload,
    }

    try:
        append_event(conn, event, require_ack=False, commit=False)
        conn.execute(
            """
            INSERT INTO decisions (
                decision_id, project_id, title, rationale, status, created_at, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                project_id,
                title,
                rationale,
                status_value,
                created_at,
                None,
            ),
        )
        links = _insert_artifact_links(conn, project_id, decision_id, artifacts)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "decision_id": decision_id,
        "created_at": created_at,
        "links": links,
    }


def supersede_decision(
    conn,
    project_id: str,
    session_id: str,
    turn_id: str,
    ack_token: str,
    from_decision_id: str,
    title: str,
    rationale: Optional[str] = None,
    status: Optional[str] = None,
    to_decision_id: Optional[str] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
    actor: str = "assistant",
    source: str = "decision.supersede",
    stream_id: Optional[str] = None,
    event_version: int = 1,
) -> Dict[str, Any]:
    if not from_decision_id:
        raise ValueError("from_decision_id is required")
    if not title:
        raise ValueError("title is required")
    _require_valid_ack(conn, project_id, session_id, turn_id, ack_token)

    existing = conn.execute(
        "SELECT decision_id FROM decisions WHERE project_id = ? AND decision_id = ?",
        (project_id, from_decision_id),
    ).fetchone()
    if existing is None:
        raise ValueError("from_decision_id not found")

    to_decision_id = to_decision_id or _generate_id("dec")
    created_at = _utc_now()
    status_value = status or DECISION_STATUS_ACTIVE
    edge_id = _generate_id("edge")

    event_payload = {
        "from_decision_id": from_decision_id,
        "to_decision_id": to_decision_id,
        "title": title,
        "rationale": rationale,
        "status": status_value,
        "artifacts": artifacts or [],
    }
    event = {
        "project_id": project_id,
        "session_id": session_id,
        "turn_id": turn_id,
        "stream_id": stream_id or f"{project_id}:{session_id}",
        "event_type": "decision.superseded",
        "event_version": event_version,
        "actor": actor,
        "source": source,
        "payload": event_payload,
    }

    try:
        append_event(conn, event, require_ack=False, commit=False)
        conn.execute(
            """
            INSERT INTO decisions (
                decision_id, project_id, title, rationale, status, created_at, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                to_decision_id,
                project_id,
                title,
                rationale,
                status_value,
                created_at,
                None,
            ),
        )
        conn.execute(
            """
            UPDATE decisions
            SET status = ?, superseded_by = ?
            WHERE project_id = ? AND decision_id = ?
            """,
            (
                DECISION_STATUS_SUPERSEDED,
                to_decision_id,
                project_id,
                from_decision_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO decision_edges (
                edge_id, project_id, from_decision_id, to_decision_id, relation, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                edge_id,
                project_id,
                from_decision_id,
                to_decision_id,
                "supersedes",
                created_at,
            ),
        )
        links = _insert_artifact_links(conn, project_id, to_decision_id, artifacts)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "from_decision_id": from_decision_id,
        "to_decision_id": to_decision_id,
        "edge_id": edge_id,
        "created_at": created_at,
        "links": links,
    }
