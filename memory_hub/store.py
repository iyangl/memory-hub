from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from .errors import BusinessError

PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_ROOT = Path.home() / ".memory-hub"
MIGRATIONS_DIR = Path(__file__).with_name("migrations")
DEFAULT_LEASE_SECONDS = 300


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_utc(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(seconds, 0))).isoformat()


@dataclass(frozen=True)
class MemoryStore:
    root_dir: Path = DEFAULT_ROOT
    workspace_root: Optional[Path] = None

    def db_path(self, project_id: str) -> Path:
        validate_project_id(project_id)
        return self.root_dir / "projects" / project_id / "memory.db"

    def project_workspace(self, project_id: str) -> Path:
        validate_project_id(project_id)
        root = self.workspace_root or Path.cwd()
        return root.resolve()

    def connect(self, project_id: str) -> sqlite3.Connection:
        db_path = self.db_path(project_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 3000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        init_db(conn)
        return conn


def validate_project_id(project_id: str) -> None:
    if not project_id:
        raise BusinessError(
            error_code="INVALID_PROJECT_ID",
            message="project_id is required",
            retryable=False,
        )
    if project_id != project_id.strip():
        raise BusinessError(
            error_code="INVALID_PROJECT_ID",
            message="project_id has leading/trailing whitespace",
            retryable=False,
        )
    if ".." in project_id:
        raise BusinessError(
            error_code="INVALID_PROJECT_ID",
            message="project_id cannot contain '..'",
            retryable=False,
        )
    if not PROJECT_ID_PATTERN.match(project_id):
        raise BusinessError(
            error_code="INVALID_PROJECT_ID",
            message="project_id has invalid characters",
            retryable=False,
        )


def _ensure_schema_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def _migration_version(path: Path) -> str:
    stem = path.stem
    if "_" not in stem:
        return stem
    return stem.split("_", 1)[0]


def _migration_files() -> List[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise RuntimeError(f"no migrations found in {MIGRATIONS_DIR}")
    return files


def _split_sql_statements(script: str) -> List[str]:
    statements: List[str] = []
    chunks = script.split(";")
    for chunk in chunks:
        statement = chunk.strip()
        if not statement:
            continue
        statements.append(statement)
    return statements


def _execute_migration_script(conn: sqlite3.Connection, script: str) -> None:
    for statement in _split_sql_statements(script):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "duplicate column name" in message:
                # Idempotency for partially-applied schemas where the column already exists.
                continue
            raise


def _heal_half_migrated(conn: sqlite3.Connection) -> None:
    """Detect and auto-repair half-migrated states from destructive migrations.

    Migration 006 drops sync_audit and renames sync_audit_new.  If the process
    is killed between DROP and RENAME the DB is left with sync_audit_new only.
    """
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "sync_audit_new" in tables and "sync_audit" not in tables:
        conn.execute("ALTER TABLE sync_audit_new RENAME TO sync_audit")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sync_audit_project_time "
            "ON sync_audit (project_id, created_at DESC)"
        )
        conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    _ensure_schema_migrations_table(conn)
    _heal_half_migrated(conn)

    applied_rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    applied_versions = {str(row["version"]) for row in applied_rows}

    for path in _migration_files():
        version = _migration_version(path)
        if version in applied_versions:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            _execute_migration_script(conn, path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, now_utc()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    row = conn.execute("SELECT memory_version FROM project_meta WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO project_meta (id, memory_version, updated_at) VALUES (1, 0, ?)",
            (now_utc(),),
        )
        conn.commit()


def resolve_project_workspace(
    conn: sqlite3.Connection,
    fallback_root: Path,
) -> Path:
    """Return the workspace root for the current project, binding it on first use.

    On first catalog operation the *fallback_root* (typically from
    ``--workspace-root`` or ``cwd``) is persisted in ``project_meta``.  On
    subsequent calls the stored path is compared with *fallback_root*; a
    mismatch raises ``BusinessError`` to prevent indexing the wrong directory.
    """
    resolved = fallback_root.resolve()
    row = conn.execute(
        "SELECT workspace_root FROM project_meta WHERE id = 1"
    ).fetchone()
    if row is None:
        # project_meta not yet initialised – caller should run init_db first.
        return resolved

    stored: str | None = row["workspace_root"]
    if stored is None:
        conn.execute(
            "UPDATE project_meta SET workspace_root = ?, updated_at = ? WHERE id = 1",
            (str(resolved), now_utc()),
        )
        conn.commit()
        return resolved

    stored_path = Path(stored).resolve()
    if stored_path != resolved:
        raise BusinessError(
            error_code="WORKSPACE_MISMATCH",
            message=(
                f"project is bound to workspace {stored_path}, "
                f"but current workspace is {resolved}"
            ),
            retryable=False,
        )
    return stored_path

def parse_context_stamp(context_stamp: Any) -> Optional[int]:
    if context_stamp is None:
        return None
    if isinstance(context_stamp, dict):
        value = context_stamp.get("memory_version")
        if not isinstance(value, int) or value < 0:
            raise BusinessError(
                error_code="INVALID_CONTEXT_STAMP",
                message="context_stamp.memory_version must be a non-negative integer",
                details={"context_stamp": context_stamp},
            )
        return value

    if isinstance(context_stamp, str):
        stamp = context_stamp.strip().lower()
        if stamp.startswith("v"):
            try:
                value = int(stamp[1:])
            except ValueError as exc:
                raise BusinessError(
                    error_code="INVALID_CONTEXT_STAMP",
                    message="legacy string context_stamp must match v<integer>",
                    details={"context_stamp": context_stamp},
                ) from exc
            if value < 0:
                raise BusinessError(
                    error_code="INVALID_CONTEXT_STAMP",
                    message="context_stamp cannot be negative",
                    details={"context_stamp": context_stamp},
                )
            return value
    raise BusinessError(
        error_code="INVALID_CONTEXT_STAMP",
        message="context_stamp must be object or null",
        details={"context_stamp": context_stamp},
    )


def make_consistency_stamp(
    memory_version: int,
    catalog_version: str,
    consistency_status: str,
) -> Dict[str, Any]:
    return {
        "memory_version": int(memory_version),
        "catalog_version": catalog_version,
        "consistency": consistency_status,
    }


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
                matched = str(row["loop_id"])
                conn.execute(
                    """
                    UPDATE open_loops
                    SET status = 'closed', closed_at = ?, closed_by_client = ?, memory_version = ?
                    WHERE project_id = ? AND loop_id = ?
                    """,
                    (closed_at, client_id, memory_version, project_id, matched),
                )
                closed_ids.append(matched)
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
    error_code: Optional[str] = None,
    latency_ms: Optional[int] = None,
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
            error_code,
            latency_ms,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sync_id,
            project_id,
            direction,
            client_id,
            session_id,
            json_dumps(request_payload),
            json_dumps(response_payload),
            error_code,
            latency_ms,
            now_utc(),
        ),
    )


def list_sync_audit_entries(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    limit: int,
    direction: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = (
        """
        SELECT sync_id, project_id, direction, client_id, session_id,
               request_json, response_json, error_code, latency_ms, created_at
        FROM sync_audit
        WHERE project_id = ?
        """
    )
    params: List[Any] = [project_id]
    if direction:
        query += " AND direction = ?"
        params.append(direction)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))

    rows = conn.execute(query, tuple(params)).fetchall()
    payload: List[Dict[str, Any]] = []
    for row in rows:
        payload.append(
            {
                "sync_id": row["sync_id"],
                "project_id": row["project_id"],
                "direction": row["direction"],
                "client_id": row["client_id"],
                "session_id": row["session_id"],
                "request": json_loads(row["request_json"], {}),
                "response": json_loads(row["response_json"], {}),
                "error_code": row["error_code"],
                "latency_ms": row["latency_ms"],
                "created_at": row["created_at"],
            }
        )
    return payload


def get_catalog_meta(conn: sqlite3.Connection, project_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT project_id, catalog_version, source_root, total_files, indexed_files, coverage_pct,
               last_indexed_at, last_full_rebuild, updated_at
        FROM catalog_meta
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def _catalog_version_from_snapshot(
    files: Sequence[Dict[str, Any]],
    edges: Sequence[Dict[str, Any]],
) -> str:
    hasher = hashlib.sha256()
    for item in sorted(files, key=lambda x: x["file_path"]):
        hasher.update(item["file_path"].encode("utf-8"))
        hasher.update(item["file_hash"].encode("utf-8"))
    for edge in sorted(edges, key=lambda x: (x["from_file"], x["to_module"], x["source_type"])):
        hasher.update(edge["from_file"].encode("utf-8"))
        hasher.update(edge["to_module"].encode("utf-8"))
        hasher.update(str(edge["confidence"]).encode("utf-8"))
        hasher.update(edge["source_type"].encode("utf-8"))
    return "sha256:" + hasher.hexdigest()


def replace_catalog_snapshot(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    source_root: Path,
    files: Sequence[Dict[str, Any]],
    edges: Sequence[Dict[str, Any]],
    full_rebuild: bool,
) -> Dict[str, Any]:
    now = now_utc()
    conn.execute("DELETE FROM catalog_files WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM catalog_edges WHERE project_id = ?", (project_id,))

    for item in files:
        conn.execute(
            """
            INSERT INTO catalog_files (project_id, file_path, file_hash, language, import_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                item["file_path"],
                item["file_hash"],
                item["language"],
                int(item.get("import_count", 0)),
                now,
            ),
        )

    for edge in edges:
        conn.execute(
            """
            INSERT INTO catalog_edges (edge_id, project_id, from_file, to_module, edge_type, confidence, source_type, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge.get("edge_id") or f"edge_{uuid4().hex}",
                project_id,
                edge["from_file"],
                edge["to_module"],
                edge.get("edge_type", "import"),
                float(edge["confidence"]),
                edge["source_type"],
                now,
            ),
        )

    total_files = len(files)
    indexed_files = len(files)
    coverage_pct = 100.0 if total_files > 0 else 0.0
    catalog_version = _catalog_version_from_snapshot(files, edges)

    existing = get_catalog_meta(conn, project_id)
    last_full_rebuild = now if full_rebuild else (existing or {}).get("last_full_rebuild")

    conn.execute(
        """
        INSERT INTO catalog_meta (
            project_id, catalog_version, source_root, total_files, indexed_files,
            coverage_pct, last_indexed_at, last_full_rebuild, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET
            catalog_version = excluded.catalog_version,
            source_root = excluded.source_root,
            total_files = excluded.total_files,
            indexed_files = excluded.indexed_files,
            coverage_pct = excluded.coverage_pct,
            last_indexed_at = excluded.last_indexed_at,
            last_full_rebuild = excluded.last_full_rebuild,
            updated_at = excluded.updated_at
        """,
        (
            project_id,
            catalog_version,
            str(source_root),
            total_files,
            indexed_files,
            coverage_pct,
            now,
            last_full_rebuild,
            now,
        ),
    )

    return {
        "catalog_version": catalog_version,
        "total_files": total_files,
        "indexed_files": indexed_files,
        "coverage_pct": coverage_pct,
        "last_indexed_at": now,
        "last_full_rebuild": last_full_rebuild,
    }


def fetch_catalog_files(conn: sqlite3.Connection, project_id: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT file_path, file_hash, language, import_count, updated_at
        FROM catalog_files
        WHERE project_id = ?
        ORDER BY file_path ASC
        """,
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_catalog_edges(
    conn: sqlite3.Connection,
    project_id: str,
    *,
    min_confidence: float = 0.0,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT from_file, to_module, edge_type, confidence, source_type, updated_at
        FROM catalog_edges
        WHERE project_id = ? AND confidence >= ?
        ORDER BY confidence DESC, from_file ASC
        """,
        (project_id, min_confidence),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_catalog_hash_map(conn: sqlite3.Connection, project_id: str) -> Dict[str, str]:
    rows = conn.execute(
        """
        SELECT file_path, file_hash
        FROM catalog_files
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchall()
    return {str(row["file_path"]): str(row["file_hash"]) for row in rows}


def enqueue_catalog_job(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    job_type: str,
    payload: Dict[str, Any],
    max_attempts: int = 5,
) -> str:
    job_id = f"job_{uuid4().hex}"
    now = now_utc()
    conn.execute(
        """
        INSERT INTO catalog_jobs (
            job_id, project_id, job_type, payload_json, status, attempts, max_attempts,
            last_error, next_retry_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'pending', 0, ?, NULL, ?, ?, ?)
        """,
        (job_id, project_id, job_type, json_dumps(payload), max_attempts, now, now, now),
    )
    return job_id


def claim_next_catalog_job(
    conn: sqlite3.Connection,
    *,
    project_id: Optional[str] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> Optional[Dict[str, Any]]:
    # Optimistic retry loop:
    # multiple workers may select the same pending row, so claim uses
    # conditional update (status still pending) to guarantee single winner.
    # Also reclaims running jobs whose lease has expired (crash recovery).
    for _ in range(8):
        now = now_utc()
        lease_expires = _future_utc(lease_seconds)
        if project_id:
            row = conn.execute(
                """
                SELECT job_id, project_id, job_type, payload_json, status, attempts, max_attempts, last_error, next_retry_at
                FROM catalog_jobs
                WHERE project_id = ?
                  AND (
                    (status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= ?))
                    OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
                    OR (status = 'running' AND lease_expires_at IS NULL)
                  )
                ORDER BY COALESCE(next_retry_at, created_at) ASC, created_at ASC
                LIMIT 1
                """,
                (project_id, now, now),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT job_id, project_id, job_type, payload_json, status, attempts, max_attempts, last_error, next_retry_at
                FROM catalog_jobs
                WHERE (
                    (status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= ?))
                    OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
                    OR (status = 'running' AND lease_expires_at IS NULL)
                  )
                ORDER BY COALESCE(next_retry_at, created_at) ASC, created_at ASC
                LIMIT 1
                """,
                (now, now),
            ).fetchone()

        if row is None:
            return None

        old_status = str(row["status"])
        cursor = conn.execute(
            """
            UPDATE catalog_jobs
            SET status = 'running', attempts = attempts + 1, updated_at = ?,
                next_retry_at = NULL, lease_expires_at = ?
            WHERE job_id = ?
              AND status = ?
              AND (
                (? = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= ?))
                OR (? = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
                OR (? = 'running' AND lease_expires_at IS NULL)
              )
            """,
            (now_utc(), lease_expires, row["job_id"],
             old_status, old_status, now, old_status, now, old_status),
        )
        if cursor.rowcount == 0:
            # Lost race to another worker; retry selecting another pending job.
            continue

        claimed = dict(row)
        claimed["attempts"] = int(claimed["attempts"]) + 1
        claimed["payload"] = json_loads(str(row["payload_json"]), {})
        return claimed

    return None


def mark_catalog_job_done(conn: sqlite3.Connection, job_id: str) -> None:
    conn.execute(
        """
        UPDATE catalog_jobs
        SET status = 'done', last_error = NULL, next_retry_at = NULL,
            lease_expires_at = NULL, updated_at = ?
        WHERE job_id = ?
        """,
        (now_utc(), job_id),
    )


def mark_catalog_job_failed(conn: sqlite3.Connection, job_id: str, error: str) -> None:
    row = conn.execute(
        "SELECT attempts, max_attempts FROM catalog_jobs WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if row is None:
        return
    attempts = int(row["attempts"])
    max_attempts = int(row["max_attempts"])
    status = "failed" if attempts >= max_attempts else "pending"
    retry_delay_seconds = min(300, 2 ** max(attempts, 0))
    next_retry_at = None if status == "failed" else _future_utc(retry_delay_seconds)
    conn.execute(
        """
        UPDATE catalog_jobs
        SET status = ?, last_error = ?, next_retry_at = ?,
            lease_expires_at = NULL, updated_at = ?
        WHERE job_id = ?
        """,
        (status, error[:1000], next_retry_at, now_utc(), job_id),
    )


def count_pending_catalog_jobs(conn: sqlite3.Connection, project_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(1) AS cnt FROM catalog_jobs WHERE project_id = ? AND status IN ('pending', 'running')",
        (project_id,),
    ).fetchone()
    return 0 if row is None else int(row["cnt"])


def insert_consistency_link(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    sync_id: str,
    memory_version: int,
    catalog_version: str,
    consistency_status: str,
) -> str:
    link_id = f"link_{uuid4().hex}"
    conn.execute(
        """
        INSERT INTO consistency_links (
            link_id, project_id, sync_id, memory_version, catalog_version, consistency_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            link_id,
            project_id,
            sync_id,
            int(memory_version),
            catalog_version,
            consistency_status,
            now_utc(),
        ),
    )
    return link_id


def fetch_latest_consistency(conn: sqlite3.Connection, project_id: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT memory_version, catalog_version, consistency_status, created_at
        FROM consistency_links
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        memory_version = get_memory_version(conn)
        meta = get_catalog_meta(conn, project_id)
        catalog_version = "sha256:unknown" if not meta else str(meta["catalog_version"])
        return {
            "memory_version": memory_version,
            "catalog_version": catalog_version,
            "consistency_status": "unknown",
            "created_at": None,
        }

    return {
        "memory_version": int(row["memory_version"]),
        "catalog_version": str(row["catalog_version"]),
        "consistency_status": str(row["consistency_status"]),
        "created_at": row["created_at"],
    }


def insert_drift_report(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    method: str,
    drift_score: float,
    details: Dict[str, Any],
) -> str:
    report_id = f"drift_{uuid4().hex}"
    conn.execute(
        """
        INSERT INTO drift_reports (report_id, project_id, method, drift_score, details_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (report_id, project_id, method, float(drift_score), json_dumps(details), now_utc()),
    )
    return report_id


def fetch_latest_drift_report(conn: sqlite3.Connection, project_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT report_id, method, drift_score, details_json, created_at
        FROM drift_reports
        WHERE project_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "report_id": row["report_id"],
        "method": row["method"],
        "drift_score": float(row["drift_score"]),
        "details": json_loads(row["details_json"], {}),
        "created_at": row["created_at"],
    }


def build_catalog_health(conn: sqlite3.Connection, project_id: str) -> Dict[str, Any]:
    meta = get_catalog_meta(conn, project_id)
    pending_jobs = count_pending_catalog_jobs(conn, project_id)
    latest_consistency = fetch_latest_consistency(conn, project_id)
    latest_drift = fetch_latest_drift_report(conn, project_id)

    if meta is None:
        drift_score = latest_drift["drift_score"] if latest_drift else 0.0
        return {
            "freshness": "unknown",
            "catalog_version": "sha256:unknown",
            "total_files": 0,
            "indexed_files": 0,
            "coverage_pct": 0.0,
            "coverage": 0.0,
            "pending_jobs": pending_jobs,
            "last_full_rebuild": None,
            "drift_score": drift_score,
            "consistency_status": latest_consistency["consistency_status"],
        }

    last_indexed_at = meta.get("last_indexed_at")
    freshness = "fresh"
    if pending_jobs > 0:
        freshness = "stale"
    elif not last_indexed_at:
        freshness = "unknown"

    drift_score = latest_drift["drift_score"] if latest_drift else 0.0
    if drift_score > 0.0 and freshness == "fresh":
        freshness = "stale"

    return {
        "freshness": freshness,
        "catalog_version": str(meta["catalog_version"]),
        "total_files": int(meta["total_files"]),
        "indexed_files": int(meta["indexed_files"]),
        "coverage_pct": float(meta["coverage_pct"]),
        "coverage": float(meta["coverage_pct"]),
        "pending_jobs": pending_jobs,
        "last_full_rebuild": meta.get("last_full_rebuild"),
        "drift_score": drift_score,
        "consistency_status": latest_consistency["consistency_status"],
    }
