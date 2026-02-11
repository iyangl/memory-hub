from __future__ import annotations

import sqlite3
import sys
import time
from typing import Any, Dict

from .catalog_indexer import build_catalog_snapshot
from .store import (
    MemoryStore,
    claim_next_catalog_job,
    get_memory_version,
    insert_consistency_link,
    mark_catalog_job_done,
    mark_catalog_job_failed,
    replace_catalog_snapshot,
    resolve_project_workspace,
)

_LOCK_RETRY_MAX = 3
_LOCK_RETRY_BASE_DELAY = 0.1


def _begin_immediate_with_retry(conn: sqlite3.Connection) -> None:
    """Execute BEGIN IMMEDIATE with exponential-backoff retry on lock contention."""
    for attempt in range(_LOCK_RETRY_MAX):
        try:
            conn.execute("BEGIN IMMEDIATE")
            return
        except sqlite3.OperationalError as exc:
            if "database is locked" not in str(exc).lower():
                raise
            if attempt == _LOCK_RETRY_MAX - 1:
                raise
            delay = _LOCK_RETRY_BASE_DELAY * (2 ** attempt)
            time.sleep(delay)

def process_catalog_jobs(
    store: MemoryStore,
    project_id: str,
    *,
    limit: int = 20,
) -> Dict[str, Any]:
    processed = 0
    succeeded = 0
    failed = 0
    lock_failures = 0

    conn = store.connect(project_id)
    try:
        while processed < limit:
            try:
                _begin_immediate_with_retry(conn)
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower():
                    lock_failures += 1
                    sys.stderr.write(
                        f"catalog_worker: lock contention after {_LOCK_RETRY_MAX} retries, "
                        f"stopping batch ({processed} processed so far)\n"
                    )
                    break
                raise
            try:
                job = claim_next_catalog_job(conn, project_id=project_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

            if not job:
                break

            processed += 1
            job_id = str(job["job_id"])
            payload = job.get("payload") or {}
            try:
                workspace_root = resolve_project_workspace(conn, store.project_workspace(project_id))
                snapshot = build_catalog_snapshot(
                    workspace_root,
                    files_hint=payload.get("files_touched") or [],
                )
                conn.execute("BEGIN")
                try:
                    meta = replace_catalog_snapshot(
                        conn,
                        project_id=project_id,
                        source_root=snapshot["workspace_root"],
                        files=snapshot["files"],
                        edges=snapshot["edges"],
                        full_rebuild=bool(snapshot.get("full_rebuild", False)),
                    )

                    memory_version = int(payload.get("memory_version") or get_memory_version(conn))
                    sync_id = str(payload.get("sync_id") or f"job:{job_id}")
                    insert_consistency_link(
                        conn,
                        project_id=project_id,
                        sync_id=sync_id,
                        memory_version=memory_version,
                        catalog_version=meta["catalog_version"],
                        consistency_status="ok",
                    )

                    mark_catalog_job_done(conn, job_id)
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                succeeded += 1
            except Exception as exc:  # pylint: disable=broad-except
                conn.execute("BEGIN")
                try:
                    mark_catalog_job_failed(conn, job_id, str(exc))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                failed += 1

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "lock_failures": lock_failures,
        }
    finally:
        conn.close()
