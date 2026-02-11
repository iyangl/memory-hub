from __future__ import annotations

from typing import Any, Dict, List

from .errors import BusinessError


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_non_empty_string(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BusinessError(
            error_code="INVALID_PUSH_PAYLOAD",
            message=f"'{key}' must be a non-empty string",
            details={"field": key},
            retryable=False,
        )
    return value.strip()


def _ensure_list(payload: Dict[str, Any], key: str) -> List[Any]:
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise BusinessError(
            error_code="INVALID_PUSH_PAYLOAD",
            message=f"'{key}' must be a list",
            details={"field": key},
            retryable=False,
        )
    return value


def _validate_context_stamp(value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str):
        return
    if not isinstance(value, dict):
        raise BusinessError(
            error_code="INVALID_CONTEXT_STAMP",
            message="context_stamp must be an object or null",
            details={"field": "context_stamp"},
            retryable=False,
        )
    memory_version = value.get("memory_version")
    if not isinstance(memory_version, int) or memory_version < 0:
        raise BusinessError(
            error_code="INVALID_CONTEXT_STAMP",
            message="context_stamp.memory_version must be a non-negative integer",
            details={"field": "context_stamp.memory_version"},
            retryable=False,
        )


def validate_push_payload(arguments: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = dict(arguments)

    normalized["project_id"] = _require_non_empty_string(normalized, "project_id")
    normalized["client_id"] = _require_non_empty_string(normalized, "client_id")
    normalized["session_id"] = _require_non_empty_string(normalized, "session_id")
    normalized["session_summary"] = _require_non_empty_string(normalized, "session_summary")

    _validate_context_stamp(normalized.get("context_stamp"))

    role_deltas = _ensure_list(normalized, "role_deltas")
    for index, item in enumerate(role_deltas):
        if not isinstance(item, dict):
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="role_deltas items must be objects",
                details={"field": f"role_deltas[{index}]"},
            )
        role = item.get("role")
        if not isinstance(role, str) or not role.strip():
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="role_deltas.role must be a non-empty string",
                details={"field": f"role_deltas[{index}].role"},
            )
        memory_key = item.get("memory_key")
        if not isinstance(memory_key, str) or not memory_key.strip():
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="role_deltas.memory_key must be a non-empty string",
                details={"field": f"role_deltas[{index}].memory_key"},
            )
        confidence = item.get("confidence", 0.7)
        if not _is_number(confidence) or float(confidence) < 0.0 or float(confidence) > 1.0:
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="role_deltas.confidence must be between 0 and 1",
                details={"field": f"role_deltas[{index}].confidence"},
            )
        source_refs = item.get("source_refs")
        if source_refs is not None and not isinstance(source_refs, list):
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="role_deltas.source_refs must be a list",
                details={"field": f"role_deltas[{index}].source_refs"},
            )

    decisions_delta = _ensure_list(normalized, "decisions_delta")
    for index, item in enumerate(decisions_delta):
        if not isinstance(item, dict):
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="decisions_delta items must be objects",
                details={"field": f"decisions_delta[{index}]"},
            )
        title = item.get("title")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="decisions_delta.title must be a non-empty string when provided",
                details={"field": f"decisions_delta[{index}].title"},
            )

    open_loops_new = _ensure_list(normalized, "open_loops_new")
    for index, item in enumerate(open_loops_new):
        if not isinstance(item, dict):
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="open_loops_new items must be objects",
                details={"field": f"open_loops_new[{index}]"},
            )
        title = item.get("title")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="open_loops_new.title must be a non-empty string when provided",
                details={"field": f"open_loops_new[{index}].title"},
            )

    open_loops_closed = _ensure_list(normalized, "open_loops_closed")
    for index, item in enumerate(open_loops_closed):
        if isinstance(item, str):
            continue
        if isinstance(item, dict):
            has_loop_id = isinstance(item.get("loop_id"), str) and bool(item["loop_id"].strip())
            has_title = isinstance(item.get("title"), str) and bool(item["title"].strip())
            if has_loop_id or has_title:
                continue
        raise BusinessError(
            error_code="INVALID_PUSH_PAYLOAD",
            message="open_loops_closed items must be loop_id string or object with loop_id/title",
            details={"field": f"open_loops_closed[{index}]"},
        )

    files_touched = _ensure_list(normalized, "files_touched")
    for index, item in enumerate(files_touched):
        if not isinstance(item, str) or not item.strip():
            raise BusinessError(
                error_code="INVALID_PUSH_PAYLOAD",
                message="files_touched items must be non-empty strings",
                details={"field": f"files_touched[{index}]"},
            )

    normalized["role_deltas"] = role_deltas
    normalized["decisions_delta"] = decisions_delta
    normalized["open_loops_new"] = open_loops_new
    normalized["open_loops_closed"] = open_loops_closed
    normalized["files_touched"] = files_touched
    return normalized
