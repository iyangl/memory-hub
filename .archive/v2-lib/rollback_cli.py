"""rollback CLI for durable memory.

Usage:
  memory-hub rollback <uri> --to-version <version_id> --note <text> [--reviewer <id>]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope
from lib.durable_errors import DurableMemoryError
from lib.durable_review import rollback_memory


class EnvelopeArgumentParser(argparse.ArgumentParser):
    """Argument parser that emits business-error envelopes."""

    def error(self, message: str) -> None:
        envelope.fail("INVALID_ARGUMENTS", message)


def _project_root(value: str | None) -> Path | None:
    return Path(value) if value else None


def _version_id(value: str | None) -> int:
    if value is None:
        envelope.fail("INVALID_ARGUMENTS", "--to-version is required.")
    try:
        return int(value)
    except ValueError:
        envelope.fail("INVALID_ARGUMENTS", f"--to-version must be an integer: {value}")
    return 0


def run(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub rollback")
    parser.add_argument("uri", nargs="?")
    parser.add_argument("--to-version", default=None)
    parser.add_argument("--note", default=None)
    parser.add_argument("--reviewer", default="cli")
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)

    if parsed.uri is None:
        envelope.fail("INVALID_ARGUMENTS", "uri is required.")
    if parsed.note is None or not parsed.note.strip():
        envelope.fail("MISSING_REVIEW_NOTE", "Review note must not be empty.")

    try:
        result = rollback_memory(
            _project_root(parsed.project_root),
            parsed.uri,
            _version_id(parsed.to_version),
            parsed.reviewer,
            parsed.note,
        )
        envelope.ok(result, code="ROLLBACK_APPLIED", message="Rollback applied.")
    except DurableMemoryError as exc:
        envelope.fail(exc.code, exc.message, details=exc.details)
    except Exception as exc:
        envelope.system_error(str(exc))
