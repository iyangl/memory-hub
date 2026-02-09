from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_ROOT = Path.home() / ".memory-hub"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


@dataclass(frozen=True)
class MemoryStore:
    root_dir: Path = DEFAULT_ROOT

    def db_path(self, project_id: str) -> Path:
        validate_project_id(project_id)
        return self.root_dir / "projects" / project_id / "memory.db"

    def connect(self, project_id: str) -> sqlite3.Connection:
        db_path = self.db_path(project_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        init_db(conn)
        return conn


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_project_id(project_id: str) -> None:
    if not project_id:
        raise ValueError("project_id is required")
    if project_id != project_id.strip():
        raise ValueError("project_id has leading/trailing whitespace")
    if ".." in project_id:
        raise ValueError("project_id cannot contain '..'")
    if not PROJECT_ID_PATTERN.match(project_id):
        raise ValueError("project_id has invalid characters")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    row = conn.execute("SELECT memory_version FROM project_meta WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO project_meta (id, memory_version, updated_at) VALUES (1, 0, ?)",
            (now_utc(),),
        )
        conn.commit()


def parse_context_stamp(context_stamp: Optional[str]) -> Optional[int]:
    if not context_stamp:
        return None
    stamp = context_stamp.strip().lower()
    if not stamp.startswith("v"):
        raise ValueError("context_stamp must use format v<integer>")
    try:
        value = int(stamp[1:])
    except ValueError as exc:
        raise ValueError("context_stamp must use format v<integer>") from exc
    if value < 0:
        raise ValueError("context_stamp cannot be negative")
    return value


def make_context_stamp(version: int) -> str:
    return f"v{version}"


def get_memory_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT memory_version FROM project_meta WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("project_meta is not initialized")
    return int(row["memory_version"])


def bump_memory_version(conn: sqlite3.Connection) -> int:
    current = get_memory_version(conn)
    next_version = current + 1
    conn.execute(
        "UPDATE project_meta SET memory_version = ?, updated_at = ? WHERE id = 1",
        (next_version, now_utc()),
    )
    return next_version


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _latest_version_id(
    conn: sqlite3.Connection,
    project_id: str,
    role: str,
    memory_key: str,
) -> Optional[str]:
    row = conn.execute(
        """
        SELECT version_id
        FROM role_state_versions
        WHERE project_id = ? AND role = ? AND memory_key = ?
        ORDER BY memory_version DESC, created_at DESC
        LIMIT 1
        """,
        (project_id, role, memory_key),
    ).fetchone()
    return None if row is None else str(row["version_id"])


def upsert_role_delta(
    conn: sqlite3.Connection,
    project_id: str,
    role: str,
    memory_key: str,
    value: Any,
    confidence: float,
    source_refs: Sequence[Any],
    client_id: str,
    memory_version: int,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    created = created_at or now_utc()
    version_id = f"ver_{uuid4().hex}"
    supersedes = _latest_version_id(conn, project_id, role, memory_key)

    conn.execute(
        """
        INSERT INTO role_state_versions (
            version_id,
            project_id,
            role,
            memory_key,
            value_json,
            confidence,
            created_at,
            created_by_client,
            source_refs_json,
            supersedes_version_id,
            memory_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            project_id,
            role,
            memory_key,
            json_dumps(value),
            float(confidence),
            created,
            client_id,
            json_dumps(list(source_refs)),
            supersedes,
            memory_version,
        ),
    )

    conn.execute(
        """
        INSERT INTO role_state_current (
            project_id,
            role,
            memory_key,
            value_json,
            confidence,
            version,
            updated_at,
            updated_by_client,
            source_refs_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id, role, memory_key)
        DO UPDATE SET
            value_json = excluded.value_json,
            confidence = excluded.confidence,
            version = excluded.version,
            updated_at = excluded.updated_at,
            updated_by_client = excluded.updated_by_client,
            source_refs_json = excluded.source_refs_json
        """,
        (
            project_id,
            role,
            memory_key,
            json_dumps(value),
            float(confidence),
            memory_version,
            created,
            client_id,
            json_dumps(list(source_refs)),
        ),
    )

    return {
        "version_id": version_id,
        "role": role,
        "memory_key": memory_key,
        "memory_version": memory_version,
    }


def fetch_role_payloads(
    conn: sqlite3.Connection,
    project_id: str,
    roles: Sequence[str],
    per_role_limit: int = 8,
) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    for role in roles:
        rows = conn.execute(
            """
            SELECT memory_key, value_json, confidence, version, updated_at, updated_by_client, source_refs_json
            FROM role_state_current
            WHERE project_id = ? AND role = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (project_id, role, per_role_limit),
        ).fetchall()

        items = []
        for row in rows:
            items.append(
                {
                    "memory_key": row["memory_key"],
                    "value": json_loads(row["value_json"], row["value_json"]),
                    "confidence": float(row["confidence"]),
                    "version": int(row["version"]),
                    "updated_at": row["updated_at"],
                    "updated_by_client": row["updated_by_client"],
                    "source_refs": json_loads(row["source_refs_json"], []),
                }
            )

        payloads.append({"role": role, "items": items})
    return payloads


def fetch_open_loops_top(
    conn: sqlite3.Connection,
    project_id: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT loop_id, title, details, priority, owner_role, created_at
        FROM open_loops
        WHERE project_id = ? AND status = 'open'
        ORDER BY priority ASC, created_at ASC
        LIMIT ?
        """,
        (project_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_latest_handoff(conn: sqlite3.Connection, project_id: str) -> Optional[Dict[str, Any]]:
    now = now_utc()
    row = conn.execute(
        """
        SELECT handoff_id, session_id, summary_json, ttl_expires_at, created_at, created_by_client, memory_version
        FROM handoff_packets
        WHERE project_id = ? AND ttl_expires_at > ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id, now),
    ).fetchone()
    if row is None:
        return None
    return {
        "handoff_id": row["handoff_id"],
        "session_id": row["session_id"],
        "summary": json_loads(row["summary_json"], {}),
        "ttl_expires_at": row["ttl_expires_at"],
        "created_at": row["created_at"],
        "created_by_client": row["created_by_client"],
        "memory_version": int(row["memory_version"]),
    }


def detect_conflicts(
    conn: sqlite3.Connection,
    project_id: str,
    base_version: Optional[int],
    role_deltas: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if base_version is None:
        return []

    current_version = get_memory_version(conn)
    if base_version >= current_version:
        return []

    conflicts: List[Dict[str, Any]] = []
    seen = set()
    for delta in role_deltas:
        role = str(delta["role"])
        memory_key = str(delta["memory_key"])
        key = (role, memory_key)
        if key in seen:
            continue
        seen.add(key)

        row = conn.execute(
            """
            SELECT value_json, memory_version, created_at, created_by_client, version_id
            FROM role_state_versions
            WHERE project_id = ?
              AND role = ?
              AND memory_key = ?
              AND memory_version > ?
            ORDER BY memory_version DESC, created_at DESC
            LIMIT 1
            """,
            (project_id, role, memory_key, base_version),
        ).fetchone()
        if row is None:
            continue

        conflicts.append(
            {
                "role": role,
                "memory_key": memory_key,
                "base_version": base_version,
                "current_version": int(row["memory_version"]),
                "theirs": json_loads(row["value_json"], row["value_json"]),
                "updated_at": row["created_at"],
                "updated_by_client": row["created_by_client"],
                "version_id": row["version_id"],
            }
        )

    return conflicts


def insert_handoff_packet(
    conn: sqlite3.Connection,
    project_id: str,
    session_id: str,
    summary: Dict[str, Any],
    created_by_client: str,
    memory_version: int,
    ttl_hours: int = 72,
) -> Dict[str, Any]:
    created_at = now_utc()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    handoff_id = f"handoff_{uuid4().hex}"
    conn.execute(
        """
        INSERT INTO handoff_packets (
            handoff_id,
            project_id,
            session_id,
            summary_json,
            ttl_expires_at,
            created_at,
            created_by_client,
            memory_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            handoff_id,
            project_id,
            session_id,
            json_dumps(summary),
            expires_at,
            created_at,
            created_by_client,
            memory_version,
        ),
    )
    return {
        "handoff_id": handoff_id,
        "ttl_expires_at": expires_at,
    }


def insert_open_loops(
    conn: sqlite3.Connection,
    project_id: str,
    open_loops_new: Iterable[Dict[str, Any]],
    client_id: str,
    memory_version: int,
) -> List[Dict[str, Any]]:
    created_at = now_utc()
    inserted = []
    for item in open_loops_new:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        loop_id = str(item.get("loop_id") or f"loop_{uuid4().hex}")
        details = item.get("details")
        priority = int(item.get("priority", 3))
        owner_role = item.get("owner_role")
        conn.execute(
            """
            INSERT INTO open_loops (
                loop_id,
                project_id,
                title,
                details,
                status,
                priority,
                owner_role,
                created_at,
                created_by_client,
                closed_at,
                closed_by_client,
                memory_version
            ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                loop_id,
                project_id,
                title,
                details,
                priority,
                owner_role,
                created_at,
                client_id,
                memory_version,
            ),
        )
        inserted.append({"loop_id": loop_id, "title": title, "priority": priority})
    return inserted


def close_open_loops(
    conn: sqlite3.Connection,
    project_id: str,
    open_loops_closed: Iterable[Any],
    client_id: str,
    memory_version: int,
) -> List[str]:
    closed_at = now_utc()
    closed_ids: List[str] = []
    for item in open_loops_closed:
        loop_id: Optional[str] = None
        title: Optional[str] = None

        if isinstance(item, dict):
            if item.get("loop_id"):
                loop_id = str(item["loop_id"])
            elif item.get("title"):
                title = str(item["title"])
        elif isinstance(item, str):
            loop_id = item

        if loop_id:
            cursor = conn.execute(
                """
                UPDATE open_loops
                SET status = 'closed', closed_at = ?, closed_by_client = ?, memory_version = ?
                WHERE project_id = ? AND loop_id = ? AND status = 'open'
                """,
                (closed_at, client_id, memory_version, project_id, loop_id),
            )
            if cursor.rowcount > 0:
                closed_ids.append(loop_id)
            continue

        if title:
            rows = conn.execute(
                """
                SELECT loop_id FROM open_loops
                WHERE project_id = ? AND title = ? AND status = 'open'
                """,
                (project_id, title),
            ).fetchall()
            if not rows:
                continue
            for row in rows:
                loop_id = str(row["loop_id"])
                conn.execute(
                    """
                    UPDATE open_loops
                    SET status = 'closed', closed_at = ?, closed_by_client = ?, memory_version = ?
                    WHERE project_id = ? AND loop_id = ?
                    """,
                    (closed_at, client_id, memory_version, project_id, loop_id),
                )
                closed_ids.append(loop_id)
    return closed_ids


def fetch_current_value(
    conn: sqlite3.Connection,
    project_id: str,
    role: str,
    memory_key: str,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT value_json, confidence, version, updated_at, updated_by_client
        FROM role_state_current
        WHERE project_id = ? AND role = ? AND memory_key = ?
        """,
        (project_id, role, memory_key),
    ).fetchone()
    if row is None:
        return None
    return {
        "value": json_loads(row["value_json"], row["value_json"]),
        "confidence": float(row["confidence"]),
        "version": int(row["version"]),
        "updated_at": row["updated_at"],
        "updated_by_client": row["updated_by_client"],
    }


def insert_sync_audit(
    conn: sqlite3.Connection,
    *,
    sync_id: str,
    project_id: str,
    direction: str,
    client_id: str,
    session_id: str,
    request_payload: Dict[str, Any],
    response_payload: Dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO sync_audit (
            sync_id,
            project_id,
            direction,
            client_id,
            session_id,
            request_json,
            response_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sync_id,
            project_id,
            direction,
            client_id,
            session_id,
            json_dumps(request_payload),
            json_dumps(response_payload),
            now_utc(),
        ),
    )
