"""Review CLI for durable and docs review targets.

Usage:
  memory-hub review list
  memory-hub review show <proposal_id|ref>
  memory-hub review approve <proposal_id|ref> [--reviewer <id>] [--note <text>]
  memory-hub review reject <proposal_id|ref> --note <text> [--reviewer <id>]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope
from lib.durable_errors import DurableMemoryError
from lib.project_review import approve_review, list_pending_reviews, reject_review, show_review_summary


class EnvelopeArgumentParser(argparse.ArgumentParser):
    """Argument parser that emits business-error envelopes."""

    def error(self, message: str) -> None:
        envelope.fail("INVALID_ARGUMENTS", message)


def _project_root(value: str | None) -> Path | None:
    return Path(value) if value else None


def _review_selector(value: str | None) -> tuple[int | None, str | None]:
    if value is None:
        envelope.fail("INVALID_ARGUMENTS", "review target is required.")
    try:
        return int(value), None
    except ValueError:
        return None, value


def _handle_list(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review list")
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    items = list_pending_reviews(_project_root(parsed.project_root))
    envelope.ok({"items": items}, code="REVIEW_QUEUE_OK", message="Review queue loaded.")


def _handle_show(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review show")
    parser.add_argument("review_target", nargs="?")
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    proposal_id, ref = _review_selector(parsed.review_target)
    data = show_review_summary(_project_root(parsed.project_root), proposal_id=proposal_id, ref=ref)
    envelope.ok(data, code="PROPOSAL_DETAIL_OK", message="Proposal detail loaded.")


def _handle_approve(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review approve")
    parser.add_argument("review_target", nargs="?")
    parser.add_argument("--reviewer", default="cli")
    parser.add_argument("--note", default="")
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    proposal_id, ref = _review_selector(parsed.review_target)
    result = approve_review(
        _project_root(parsed.project_root),
        proposal_id=proposal_id,
        ref=ref,
        reviewer=parsed.reviewer,
        note=parsed.note,
    )
    envelope.ok(result, code="PROPOSAL_APPROVED", message="Proposal approved.")


def _handle_reject(args: list[str]) -> None:
    parser = EnvelopeArgumentParser(prog="memory-hub review reject")
    parser.add_argument("review_target", nargs="?")
    parser.add_argument("--reviewer", default="cli")
    parser.add_argument("--note", default=None)
    parser.add_argument("--project-root", default=None)
    parsed = parser.parse_args(args)
    if parsed.note is None or not parsed.note.strip():
        envelope.fail("MISSING_REVIEW_NOTE", "Review note must not be empty.")
    proposal_id, ref = _review_selector(parsed.review_target)
    result = reject_review(
        _project_root(parsed.project_root),
        proposal_id=proposal_id,
        ref=ref,
        reviewer=parsed.reviewer,
        note=parsed.note,
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
