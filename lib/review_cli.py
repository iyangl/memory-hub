"""review CLI for durable memory proposals.

Usage:
  memory-hub review list
  memory-hub review show <proposal_id>
  memory-hub review approve <proposal_id> [--reviewer <id>] [--note <text>]
  memory-hub review reject <proposal_id> --note <text> [--reviewer <id>]
"""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path

from lib import envelope
from lib.durable_errors import DurableMemoryError
from lib.durable_repo import get_proposal_detail, list_pending_proposals
from lib.durable_review import approve_proposal, reject_proposal


class EnvelopeArgumentParser(argparse.ArgumentParser):
    """Argument parser that emits business-error envelopes."""

    def error(self, message: str) -> None:
        envelope.fail("INVALID_ARGUMENTS", message)


def _project_root(value: str | None) -> Path | None:
    return Path(value) if value else None


def _proposal_id(value: str | None) -> int:
    if value is None:
        envelope.fail("INVALID_ARGUMENTS", "proposal_id is required.")
    try:
        return int(value)
    except ValueError:
        envelope.fail("INVALID_ARGUMENTS", f"proposal_id must be an integer: {value}")
    return 0


def _computed_diff(base_content: str, proposal_content: str) -> str:
    diff = difflib.unified_diff(
        base_content.splitlines(),
        proposal_content.splitlines(),
        fromfile="base",
        tofile="proposal",
        lineterm="",
    )
    return "\n".join(diff)


def _handle_list(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review list")
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    items = list_pending_proposals(_project_root(parsed.project_root))
    envelope.ok({"items": items}, code="REVIEW_QUEUE_OK", message="Review queue loaded.")


def _handle_show(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review show")
    parser.add_argument("proposal_id", nargs="?")
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    detail = get_proposal_detail(_project_root(parsed.project_root), _proposal_id(parsed.proposal_id))
    base_content = "" if detail["base_version"] is None else detail["base_version"]["content"]
    data = {**detail, "computed_diff": _computed_diff(base_content, detail["proposal"]["content"])}
    envelope.ok(data, code="PROPOSAL_DETAIL_OK", message="Proposal detail loaded.")


def _handle_approve(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review approve")
    parser.add_argument("proposal_id", nargs="?")
    parser.add_argument("--reviewer", default="cli")
    parser.add_argument("--note", default="")
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    result = approve_proposal(
        _project_root(parsed.project_root),
        _proposal_id(parsed.proposal_id),
        parsed.reviewer,
        parsed.note,
    )
    envelope.ok(result, code="PROPOSAL_APPROVED", message="Proposal approved.")


def _handle_reject(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review reject")
    parser.add_argument("proposal_id", nargs="?")
    parser.add_argument("--reviewer", default="cli")
    parser.add_argument("--note", default=None)
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    if parsed.note is None or not parsed.note.strip():
        envelope.fail("MISSING_REVIEW_NOTE", "Review note must not be empty.")
    result = reject_proposal(
        _project_root(parsed.project_root),
        _proposal_id(parsed.proposal_id),
        parsed.reviewer,
        parsed.note,
    )
    envelope.ok(result, code="PROPOSAL_REJECTED", message="Proposal rejected.")


def run(args: list[str]) -> None:
    if not args:
        envelope.fail("INVALID_REVIEW_ACTION", "Usage: memory-hub review <list|show|approve|reject> ...")

    action = args[0]
    handlers = {
        "list": _handle_list,
        "show": _handle_show,
        "approve": _handle_approve,
        "reject": _handle_reject,
    }
    if action not in handlers:
        envelope.fail("INVALID_REVIEW_ACTION", f"Unknown review action: {action}")

    try:
        handlers[action](args[1:])
    except DurableMemoryError as exc:
        envelope.fail(exc.code, exc.message, details=exc.details)
    except Exception as exc:
        envelope.system_error(str(exc))
