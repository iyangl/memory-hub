"""Unified JSON envelope for all Memory Hub commands.

Every command returns JSON in this format:
  ok=True:  {"ok": true, "code": "SUCCESS", "data": {...}, "ai_actions": [...], "manual_actions": [...]}
  ok=False: {"ok": false, "code": "<ERROR_CODE>", "message": "...", "details": {...}}

Exit codes: 0=success, 1=business error, 2=system error.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def ok(data: dict[str, Any] | None = None, *,
       ai_actions: list[dict[str, Any]] | None = None,
       manual_actions: list[dict[str, Any]] | None = None) -> None:
    """Print success envelope and exit 0."""
    payload = {
        "ok": True,
        "code": "SUCCESS",
        "data": data or {},
        "ai_actions": ai_actions or [],
        "manual_actions": manual_actions or [],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(0)


def fail(code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
    """Print error envelope and exit 1 (business error)."""
    payload = {
        "ok": False,
        "code": code,
        "message": message,
        "details": details or {},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(1)


def system_error(message: str) -> None:
    """Print system error envelope and exit 2."""
    payload = {
        "ok": False,
        "code": "SYSTEM_ERROR",
        "message": message,
        "details": {},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(2)
