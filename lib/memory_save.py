"""memory.save — Execute guarded durable-save actions from a structured request.

Usage: memory-hub save --file <save.json> [--project-root <path>]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from lib import envelope, paths
from lib.memory_index import refresh_doc_summary, register_doc, summarize_markdown
from lib.memory_read import find_anchor, read_doc
from lib.memory_search import search_docs
from lib.utils import atomic_write, sanitize_module_name

ALLOWED_ACTIONS = frozenset({"noop", "create", "append", "merge", "update"})
NON_NOOP_ACTIONS = ALLOWED_ACTIONS - {"noop"}
WORKING_SET_SOURCE_TYPES = frozenset({"working_set", "working_set_item"})


class SaveError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\r\n?", "\n", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line)


def _require_non_empty_string(value: Any, *, field: str, entry_id: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SaveError(
            "INVALID_SAVE_REQUEST",
            f"{field} must be a non-empty string.",
            details={"field": field, "entry_id": entry_id},
        )
    return value.strip()


def _normalize_source_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _repo_session_json_ref(path: str) -> str | None:
    normalized_path = _normalize_source_path(path)
    if not normalized_path:
        return None

    marker = "/.memory/session/"
    if normalized_path.startswith(".memory/session/"):
        session_ref = normalized_path
    elif marker in normalized_path:
        session_ref = ".memory/session/" + normalized_path.split(marker, 1)[1]
    else:
        return None

    return session_ref if session_ref.endswith(".json") else None


def _looks_like_working_set_source(source: dict[str, Any], project_root: Path | None = None) -> bool:
    source_type = str(source.get("type", "")).strip().lower()
    if source_type in WORKING_SET_SOURCE_TYPES:
        return True

    path = _normalize_source_path(str(source.get("path", "")))
    if not path:
        return False

    return _repo_session_json_ref(path) is not None


def _normalize_source_refs(source_refs: Any, *, entry_id: str) -> list[dict[str, Any]]:
    if source_refs is None:
        return []
    if not isinstance(source_refs, list):
        raise SaveError(
            "INVALID_SAVE_REQUEST",
            "evidence.source_refs must be a list when provided.",
            details={"entry_id": entry_id},
        )

    normalized: list[dict[str, Any]] = []
    for index, source in enumerate(source_refs):
        if not isinstance(source, dict):
            raise SaveError(
                "INVALID_SAVE_REQUEST",
                "evidence.source_refs[] must be JSON objects.",
                details={"entry_id": entry_id, "source_ref_index": index},
            )
        normalized.append(source)
    return normalized


def _effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def _resolve_runtime_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _session_ref_path(path: Path, project_root: Path | None) -> str:
    resolved_path = _resolve_runtime_path(path)
    try:
        return resolved_path.relative_to(_effective_project_root(project_root)).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _request_ref(path: Path | None, project_root: Path | None) -> str | None:
    if path is None:
        return None

    resolved_path = path.resolve() if path.is_absolute() else (_effective_project_root(project_root) / path).resolve()
    try:
        return resolved_path.relative_to(_effective_project_root(project_root)).as_posix()
    except ValueError:
        pass

    name = resolved_path.name.strip()
    return name or None


def _save_trace_filename(request_file: Path | None) -> str:
    request_stem = request_file.stem if request_file is not None else "save-request"
    normalized_stem = sanitize_module_name(request_stem)[:40] or "save-request"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}_{uuid4().hex}_{normalized_stem}.json"


def _ensure_not_verbatim_working_set(
    payload_text: str,
    source_refs: list[dict[str, Any]],
    *,
    entry_id: str,
    project_root: Path | None,
) -> None:
    normalized_payload = _normalize_text(payload_text)
    candidate_sources = [source for source in source_refs if _looks_like_working_set_source(source, project_root)]

    seen: set[tuple[str, str]] = set()
    for source in candidate_sources:
        excerpt = source.get("excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip():
            continue

        normalized_excerpt = _normalize_text(excerpt)
        if not normalized_excerpt:
            continue

        source_key = (str(source.get("path") or source.get("type")), normalized_excerpt)
        if source_key in seen:
            continue
        seen.add(source_key)

        if normalized_payload == normalized_excerpt:
            raise SaveError(
                "WORKING_SET_VERBATIM_FORBIDDEN",
                "Working set content cannot be written back verbatim into durable docs.",
                details={"entry_id": entry_id, "source": source.get("path") or source.get("type")},
            )

        is_session_source = _looks_like_working_set_source(source, project_root)
        if (
            ("\n" in excerpt or len(normalized_excerpt) >= 60 or (is_session_source and len(normalized_excerpt) >= 20))
            and normalized_excerpt in normalized_payload
        ):
            raise SaveError(
                "WORKING_SET_VERBATIM_FORBIDDEN",
                "Working set content cannot be embedded verbatim into durable docs.",
                details={"entry_id": entry_id, "source": source.get("path") or source.get("type")},
            )


def _extract_first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return None


def _ensure_doc_text(text: str) -> str:
    return text.rstrip() + "\n"


def _append_section(existing_content: str, section_markdown: str) -> str:
    existing = existing_content.rstrip()
    section = section_markdown.strip()
    if not existing:
        return section + "\n"
    return existing + "\n\n" + section + "\n"


def _validate_request(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SaveError("INVALID_SAVE_REQUEST", "Save request must be a JSON object.")

    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise SaveError("INVALID_SAVE_REQUEST", "Save request must include an entries array.")

    return {
        "version": str(raw.get("version", "1")),
        "task": raw.get("task", "") if isinstance(raw.get("task", ""), str) else "",
        "entries": entries,
    }


def _validate_target(entry: dict[str, Any], *, entry_id: str, project_root: Path | None) -> tuple[str, str, str, Path, bool, str | None]:
    action = entry["action"]
    if action == "noop":
        return "", "", "", Path(), False, None

    target = entry.get("target")
    if not isinstance(target, dict):
        raise SaveError(
            "INVALID_SAVE_REQUEST",
            "Non-noop save entries must include target.bucket and target.file.",
            details={"entry_id": entry_id},
        )

    bucket = _require_non_empty_string(target.get("bucket"), field="target.bucket", entry_id=entry_id)
    filename = _require_non_empty_string(target.get("file"), field="target.file", entry_id=entry_id)

    err = paths.validate_bucket(bucket)
    if err:
        raise SaveError(
            "INVALID_BUCKET",
            f"Invalid bucket: {bucket}. Valid: {', '.join(paths.BUCKETS)}",
            details={"entry_id": entry_id, "bucket": bucket},
        )

    filename_err = paths.validate_docs_filename(filename)
    if filename_err:
        raise SaveError(
            filename_err,
            f"Invalid target.file: {filename}",
            details={"entry_id": entry_id, "file": filename},
        )

    target_ref = paths.docs_file_ref(bucket, filename)
    return bucket, filename, target_ref, paths.file_path(bucket, filename, project_root), True, action


def _validate_index(entry: dict[str, Any], *, entry_id: str) -> dict[str, str | None] | None:
    if entry["action"] != "create":
        return None

    index = entry.get("index")
    if index is None:
        return None
    if not isinstance(index, dict):
        raise SaveError(
            "INVALID_SAVE_REQUEST",
            "index must be a JSON object when provided.",
            details={"entry_id": entry_id},
        )

    return {
        "topic": _require_non_empty_string(index.get("topic"), field="index.topic", entry_id=entry_id),
        "summary": _require_non_empty_string(index.get("summary"), field="index.summary", entry_id=entry_id),
        "anchor": index.get("anchor") if isinstance(index.get("anchor"), str) and index.get("anchor").strip() else None,
    }


def _validate_evidence(entry: dict[str, Any], *, entry_id: str, target_ref: str, project_root: Path | None) -> dict[str, Any]:
    if entry["action"] == "noop":
        return {"searches": [], "reads": [], "source_refs": []}

    evidence = entry.get("evidence")
    if not isinstance(evidence, dict):
        raise SaveError(
            "SAVE_GUARD_FAILED",
            "Non-noop save entries must include evidence.",
            details={"entry_id": entry_id},
        )

    queries = evidence.get("search_queries")
    if not isinstance(queries, list) or not queries:
        raise SaveError(
            "SAVE_GUARD_FAILED",
            "Non-noop save entries must include at least one search query.",
            details={"entry_id": entry_id},
        )

    verified_searches = []
    for query in queries:
        query_text = _require_non_empty_string(query, field="evidence.search_queries[]", entry_id=entry_id)
        matches = search_docs(query_text, project_root)
        verified_searches.append({
            "query": query_text,
            "total": len(matches),
            "matched_files": sorted({item["file"] for item in matches})[:5],
        })

    read_refs = evidence.get("read_refs")
    if not isinstance(read_refs, list) or not read_refs:
        raise SaveError(
            "SAVE_GUARD_FAILED",
            "Non-noop save entries must include at least one read ref.",
            details={"entry_id": entry_id},
        )

    normalized_read_refs = []
    verified_reads = []
    for ref in read_refs:
        ref_text = _require_non_empty_string(ref, field="evidence.read_refs[]", entry_id=entry_id)
        parsed = paths.parse_docs_file_ref(ref_text)
        if parsed is None:
            raise SaveError(
                "SAVE_GUARD_FAILED",
                f"Invalid read ref: {ref_text}",
                details={"entry_id": entry_id, "read_ref": ref_text},
            )

        bucket, filename = parsed
        try:
            content = read_doc(bucket, filename, project_root)
        except FileNotFoundError:
            raise SaveError(
                "SAVE_GUARD_FAILED",
                f"Read ref does not exist: {ref_text}",
                details={"entry_id": entry_id, "read_ref": ref_text},
            )

        normalized_read_refs.append(ref_text)
        verified_reads.append({
            "ref": ref_text,
            "lines": len(content.splitlines()),
        })

    if entry["action"] in {"append", "merge", "update"} and target_ref not in normalized_read_refs:
        raise SaveError(
            "SAVE_GUARD_FAILED",
            "Append/merge/update actions must read the target doc before writing.",
            details={"entry_id": entry_id, "target": target_ref},
        )

    return {
        "searches": verified_searches,
        "reads": verified_reads,
        "source_refs": _normalize_source_refs(evidence.get("source_refs"), entry_id=entry_id),
    }


def _validate_payload(entry: dict[str, Any], *, entry_id: str, target_exists: bool, current_content: str) -> dict[str, Any]:
    action = entry["action"]
    if action == "noop":
        return {"text": ""}

    payload = entry.get("payload")
    if not isinstance(payload, dict):
        raise SaveError(
            "INVALID_SAVE_REQUEST",
            "Non-noop save entries must include payload.",
            details={"entry_id": entry_id},
        )

    if action == "create":
        if target_exists:
            raise SaveError(
                "SAVE_TARGET_EXISTS",
                "Create action requires a new target file.",
                details={"entry_id": entry_id},
            )
        text = _require_non_empty_string(payload.get("doc_markdown"), field="payload.doc_markdown", entry_id=entry_id)
        return {"text": text}

    if not target_exists:
        raise SaveError(
            "FILE_NOT_FOUND",
            "Target doc does not exist for this save action.",
            details={"entry_id": entry_id},
        )

    if action == "append":
        section = _require_non_empty_string(payload.get("section_markdown"), field="payload.section_markdown", entry_id=entry_id)
        heading = _extract_first_heading(section)
        if not heading:
            raise SaveError(
                "INVALID_SAVE_REQUEST",
                "Append action requires section_markdown to include a markdown heading.",
                details={"entry_id": entry_id},
            )
        if find_anchor(current_content, heading):
            raise SaveError(
                "APPEND_HEADING_EXISTS",
                f"Heading already exists in target doc: {heading}",
                details={"entry_id": entry_id, "heading": heading},
            )
        return {"text": section, "heading": heading}

    text = _require_non_empty_string(payload.get("doc_markdown"), field="payload.doc_markdown", entry_id=entry_id)
    if action == "update":
        supersedes = _require_non_empty_string(payload.get("supersedes"), field="payload.supersedes", entry_id=entry_id)
        return {"text": text, "supersedes": supersedes}
    return {"text": text}


def _validate_entry(
    entry: Any,
    *,
    index: int,
    project_root: Path | None,
    seen_targets: set[str],
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise SaveError(
            "INVALID_SAVE_REQUEST",
            "Each save entry must be a JSON object.",
            details={"entry_index": index},
        )

    entry_id = _require_non_empty_string(entry.get("id") or f"entry-{index + 1}", field="id", entry_id=None)
    action = _require_non_empty_string(entry.get("action"), field="action", entry_id=entry_id)
    if action not in ALLOWED_ACTIONS:
        raise SaveError(
            "INVALID_SAVE_REQUEST",
            f"Unsupported save action: {action}",
            details={"entry_id": entry_id, "action": action},
        )

    reason = _require_non_empty_string(entry.get("reason"), field="reason", entry_id=entry_id)
    normalized = {"id": entry_id, "action": action, "reason": reason}

    bucket, filename, target_ref, target_path, _, _ = _validate_target(
        {**entry, "action": action},
        entry_id=entry_id,
        project_root=project_root,
    )
    normalized.update({
        "bucket": bucket,
        "filename": filename,
        "target_ref": target_ref,
        "target_path": target_path,
    })

    if action in NON_NOOP_ACTIONS:
        if target_ref in seen_targets:
            raise SaveError(
                "DUPLICATE_SAVE_TARGET",
                f"Multiple non-noop entries target the same doc: {target_ref}",
                details={"entry_id": entry_id, "target": target_ref},
            )
        seen_targets.add(target_ref)

    current_content = ""
    target_exists = False
    if action in {"append", "merge", "update"}:
        try:
            current_content = read_doc(bucket, filename, project_root)
            target_exists = True
        except FileNotFoundError:
            target_exists = False
    elif action == "create":
        target_exists = target_path.exists()

    index_data = _validate_index({**entry, "action": action}, entry_id=entry_id)
    evidence = _validate_evidence({**entry, "action": action}, entry_id=entry_id, target_ref=target_ref, project_root=project_root)
    payload = _validate_payload({**entry, "action": action}, entry_id=entry_id, target_exists=target_exists, current_content=current_content)

    if action in NON_NOOP_ACTIONS:
        _ensure_not_verbatim_working_set(
            payload["text"],
            evidence["source_refs"],
            entry_id=entry_id,
            project_root=project_root,
        )

    normalized.update({
        "index": index_data,
        "payload": payload,
        "verified_evidence": {
            "searches": evidence["searches"],
            "reads": evidence["reads"],
        },
        "current_content": current_content,
    })
    return normalized


def _entry_summary_override(entry: dict[str, Any]) -> str | None:
    action = entry["action"]
    if action == "noop":
        return None
    if action == "create":
        index_data = entry.get("index")
        if isinstance(index_data, dict):
            return index_data["summary"]
        content = _ensure_doc_text(entry["payload"]["text"])
        return summarize_markdown(entry["bucket"], content, fallback=entry["filename"])
    if action == "append":
        return summarize_markdown(entry["bucket"], entry["payload"]["text"], fallback=entry["filename"])
    content = _ensure_doc_text(entry["payload"]["text"])
    return summarize_markdown(entry["bucket"], content, fallback=entry["filename"])


def _build_update_trace(entry: dict[str, Any]) -> dict[str, Any] | None:
    if entry["action"] != "update":
        return None

    current_content = entry.get("current_content", "")
    previous_summary = summarize_markdown(entry["bucket"], current_content, fallback=entry["filename"])
    new_content = _ensure_doc_text(entry["payload"]["text"])
    new_summary = summarize_markdown(entry["bucket"], new_content, fallback=entry["filename"])
    return {
        "target": entry["target_ref"],
        "supersedes": entry["payload"]["supersedes"],
        "previous_summary": previous_summary,
        "new_summary": new_summary,
    }


def _update_traces(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [trace for trace in (_build_update_trace(entry) for entry in entries) if trace is not None]


def _write_save_trace_artifact(
    traces: list[dict[str, Any]],
    *,
    task: str | None,
    request_file: Path | None,
    project_root: Path | None,
) -> str | None:
    if not traces:
        return None

    filename = _save_trace_filename(request_file)
    trace_path = paths.save_trace_file_path(filename, project_root=project_root)
    relative_trace_path = _session_ref_path(trace_path, project_root)
    payload = {
        "version": "1",
        "kind": "save_trace",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "task": task,
        "request_ref": _request_ref(request_file, project_root),
        "update_supersedes": traces,
    }
    atomic_write(trace_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return relative_trace_path


def _restore_entry_summary(entry: dict[str, Any], project_root: Path | None) -> bool:
    action = entry["action"]
    if action == "noop":
        return False

    summary_override = _entry_summary_override(entry)
    if action == "create":
        index_data = entry.get("index")
        if not isinstance(index_data, dict):
            return False
        register_doc(
            entry["bucket"],
            entry["filename"],
            index_data["topic"],
            summary_override or index_data["summary"],
            index_data["anchor"],
            project_root,
        )
        return True

    return refresh_doc_summary(entry["bucket"], entry["filename"], project_root, summary=summary_override)


def _apply_entry(entry: dict[str, Any], project_root: Path | None) -> dict[str, Any]:
    action = entry["action"]
    if action == "noop":
        return {"id": entry["id"], "action": action, "reason": entry["reason"]}

    target_path: Path = entry["target_path"]
    written_ref = entry["target_ref"]

    if action == "create":
        atomic_write(target_path, _ensure_doc_text(entry["payload"]["text"]))
        indexed = _restore_entry_summary(entry, project_root)
        return {
            "id": entry["id"],
            "action": action,
            "target": written_ref,
            "indexed": indexed,
            "summary_refreshed": indexed,
        }

    summary_override = _entry_summary_override(entry)
    if action == "append":
        content = _append_section(entry["current_content"], entry["payload"]["text"])
    else:
        content = _ensure_doc_text(entry["payload"]["text"])

    atomic_write(target_path, content)
    summary_refreshed = refresh_doc_summary(entry["bucket"], entry["filename"], project_root, summary=summary_override)
    return {
        "id": entry["id"],
        "action": action,
        "target": written_ref,
        "indexed": False,
        "summary_refreshed": summary_refreshed,
    }


def execute_save(
    request: dict[str, Any],
    project_root: Path | None = None,
    *,
    request_file: Path | None = None,
) -> tuple[dict[str, Any], str, list[dict[str, Any]], list[dict[str, Any]]]:
    if not paths.memory_root(project_root).exists():
        raise SaveError("NOT_INITIALIZED", ".memory/ directory not found. Run memory-hub init first.")

    normalized = _validate_request(request)
    seen_targets: set[str] = set()
    validated_entries = [
        _validate_entry(
            entry,
            index=idx,
            project_root=project_root,
            seen_targets=seen_targets,
        )
        for idx, entry in enumerate(normalized["entries"])
    ]

    applied = []
    noop_entries = []
    writes = []
    indexed = []
    verified_evidence = []
    changed = False

    for entry in validated_entries:
        verified_evidence.append({
            "id": entry["id"],
            "searches": entry["verified_evidence"]["searches"],
            "reads": entry["verified_evidence"]["reads"],
        })
        result = _apply_entry(entry, project_root)
        applied.append(result)
        if entry["action"] == "noop":
            noop_entries.append({"id": entry["id"], "reason": entry["reason"]})
            continue
        changed = True
        writes.append(result["target"])
        if result["indexed"]:
            indexed.append(result["target"])

    rebuild = {"brief": False, "catalog_repair": None}
    ai_actions: list[dict[str, Any]] = []
    manual_actions: list[dict[str, Any]] = []
    response_code = "NOOP"
    trace_output: dict[str, Any] = {"update_supersedes": [], "trace_file": None, "warning": None}
    if changed:
        update_traces = _update_traces(validated_entries)
        trace_output = {
            "update_supersedes": update_traces,
            "trace_file": None,
            "warning": None,
        }
        if update_traces:
            try:
                trace_output["trace_file"] = _write_save_trace_artifact(
                    update_traces,
                    task=normalized.get("task"),
                    request_file=request_file,
                    project_root=project_root,
                )
            except (OSError, UnicodeError) as exc:
                trace_output["warning"] = f"save trace not persisted: {exc}"
        response_code = "SUCCESS"

    data = {
        "version": normalized["version"],
        "task": normalized["task"],
        "applied": applied,
        "noop": noop_entries,
        "writes": writes,
        "indexed": indexed,
        "rebuild": rebuild,
        "verified_evidence": verified_evidence,
        "trace": trace_output,
    }
    return data, response_code, ai_actions, manual_actions


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub save")
    parser.add_argument("--file", required=True, help="Path to save JSON file")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = _effective_project_root(Path(parsed.project_root)) if parsed.project_root else _effective_project_root(None)
    request_file = _resolve_runtime_path(Path(parsed.file))
    if not request_file.exists():
        envelope.fail("FILE_NOT_FOUND", f"Save file not found: {parsed.file}")

    try:
        request = json.loads(request_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        envelope.fail("INVALID_JSON", f"Failed to parse save file: {exc}")

    try:
        data, code, ai_actions, manual_actions = execute_save(request, project_root, request_file=request_file)
    except SaveError as exc:
        envelope.fail(exc.code, exc.message, details=exc.details)

    envelope.ok(data, code=code, ai_actions=ai_actions, manual_actions=manual_actions)
