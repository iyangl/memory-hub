"""Boot projection and hybrid search helpers for project memory."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from lib import paths
from lib.durable_db import connect, ensure_schema, utc_now
from lib.durable_errors import DurableMemoryError
from lib.durable_uri import SYSTEM_BOOT_URI
from lib.utils import atomic_write

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")


def _first_heading(content: str, fallback: str) -> str:
    for line in content.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line)
        if match:
            return match.group(1).strip()
    return fallback


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _phrase_count(text: str, query: str) -> int:
    return text.lower().count(query.lower())


def _snippet(text: str, query: str) -> str:
    haystack = text.lower()
    needle = query.lower()
    index = haystack.find(needle)
    if index == -1:
        return text[:160].strip()
    start = max(index - 40, 0)
    end = min(index + len(query) + 80, len(text))
    return text[start:end].strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_boot_projection(project_root: Path | None) -> dict[str, Any]:
    """Build and persist the unified boot projection."""
    ensure_schema(project_root)
    with connect(project_root) as conn:
        rows = conn.execute(
            """
            SELECT uri, type, storage_lane, doc_ref, title, content, recall_when, updated_at
            FROM approved_memories
            WHERE type IN ('identity', 'constraint')
            ORDER BY CASE type WHEN 'identity' THEN 1 WHEN 'constraint' THEN 2 END, created_at ASC
            """
        ).fetchall()
    payload = {
        "ref": SYSTEM_BOOT_URI,
        "lane": "system",
        "source_kind": "boot",
        "generated_at": utc_now(),
        "projection_path": str(paths.boot_projection_path(project_root)),
        "items": [dict(row) for row in rows],
    }
    target = paths.boot_projection_path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def load_boot_projection(project_root: Path | None) -> dict[str, Any]:
    """Load boot projection, building it when missing."""
    path = paths.boot_projection_path(project_root)
    if not path.exists():
        return refresh_boot_projection(project_root)
    return _read_json(path)


def _docs_entries(project_root: Path | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for bucket in paths.BUCKETS:
        bucket_dir = paths.bucket_path(bucket, project_root)
        if not bucket_dir.exists():
            continue
        for file_path in sorted(bucket_dir.glob("*.md")):
            content = file_path.read_text(encoding="utf-8")
            title = _first_heading(content, file_path.stem)
            entries.append(
                {
                    "ref": f"doc://{bucket}/{file_path.stem}",
                    "lane": "docs",
                    "source_kind": "doc",
                    "type": None,
                    "storage_lane": "docs",
                    "doc_ref": None,
                    "title": title,
                    "content": content,
                    "tokens": _tokens(f"{title}\n{content}"),
                }
            )
    return entries


def _durable_entries(project_root: Path | None) -> list[dict[str, Any]]:
    ensure_schema(project_root)
    with connect(project_root) as conn:
        rows = conn.execute(
            """
            SELECT uri, type, storage_lane, doc_ref, title, content, recall_when, updated_at
            FROM approved_memories
            ORDER BY updated_at DESC, uri ASC
            """
        ).fetchall()
    entries = []
    for row in rows:
        item = dict(row)
        entries.append(
            {
                "ref": item["uri"],
                "lane": "durable",
                "source_kind": "durable",
                "type": item["type"],
                "storage_lane": item.get("storage_lane", "durable"),
                "doc_ref": item.get("doc_ref"),
                "title": item["title"],
                "content": item["content"],
                "tokens": _tokens(f"{item['title']}\n{item['content']}\n{item.get('recall_when', '')}"),
            }
        )
    return entries


def refresh_search_projection(project_root: Path | None) -> dict[str, Any]:
    """Build and persist the unified search projection."""
    payload = {
        "generated_at": utc_now(),
        "projection_path": str(paths.search_projection_path(project_root)),
        "entries": _docs_entries(project_root) + _durable_entries(project_root),
    }
    target = paths.search_projection_path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def load_search_projection(project_root: Path | None) -> dict[str, Any]:
    """Load search projection, building it when missing."""
    path = paths.search_projection_path(project_root)
    if not path.exists():
        return refresh_search_projection(project_root)
    return _read_json(path)


def refresh_projections(project_root: Path | None) -> None:
    """Refresh both boot and search projections."""
    refresh_boot_projection(project_root)
    refresh_search_projection(project_root)


def hybrid_search(
    project_root: Path | None,
    *,
    query: str,
    scope: str,
    memory_type: str | None,
    limit: int,
) -> dict[str, Any]:
    """Search docs and durable entries with lexical + local semantic scoring."""
    normalized = query.strip()
    if not normalized:
        raise DurableMemoryError("EMPTY_QUERY", "Search query must not be empty.")
    if limit <= 0 or limit > 50:
        raise DurableMemoryError("INVALID_LIMIT", "Search limit must be between 1 and 50.")

    hybrid_enabled = os.environ.get("MEMORY_HUB_DISABLE_HYBRID_SEARCH", "").strip().lower() not in {"1", "true", "yes"}
    degrade_reasons = [] if hybrid_enabled else ["hybrid_search_disabled"]
    projection = load_search_projection(project_root)
    query_tokens = _tokens(normalized)
    results: list[dict[str, Any]] = []
    for entry in projection["entries"]:
        if scope != "all" and entry["lane"] != scope:
            continue
        if memory_type is not None and entry["lane"] == "durable" and entry["type"] != memory_type:
            continue

        title = str(entry["title"])
        content = str(entry["content"])
        lexical_score = (
            (_phrase_count(title, normalized) * 8)
            + (_phrase_count(content, normalized) * 4)
            + (content.lower().count(normalized.lower()) * 2)
        )
        overlap = 0
        if query_tokens:
            overlap = len(set(query_tokens) & set(entry["tokens"]))
        semantic_score = 0 if not query_tokens else int((overlap / len(set(query_tokens))) * 12)
        score = lexical_score if not hybrid_enabled else lexical_score + semantic_score
        if score <= 0:
            continue
        results.append(
            {
                "ref": entry["ref"],
                "uri": entry["ref"] if entry["lane"] == "durable" else None,
                "lane": entry["lane"],
                "source_kind": entry["source_kind"],
                "type": entry["type"],
                "storage_lane": entry["storage_lane"],
                "doc_ref": entry["doc_ref"],
                "title": title,
                "snippet": _snippet(content, normalized),
                "score": score,
                "lexical_score": lexical_score,
                "semantic_score": semantic_score if hybrid_enabled else 0,
            }
        )

    lane_priority = {"docs": 1, "durable": 2}
    results.sort(
        key=lambda item: (
            -int(item["score"]),
            -int(item["semantic_score"]),
            -int(item["lexical_score"]),
            lane_priority.get(str(item["lane"]), 9),
            str(item["ref"]),
        )
    )
    return {
        "query": normalized,
        "scope": scope,
        "search_kind": "hybrid" if hybrid_enabled else "lexical",
        "degraded": not hybrid_enabled,
        "degrade_reasons": degrade_reasons,
        "results": results[:limit],
        "projection_path": projection["projection_path"],
        "generated_at": projection["generated_at"],
    }
