"""CLI entry for decision discovery."""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope
from lib.decision_discovery import discover_decisions
from lib.durable_errors import DurableMemoryError


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub discover")
    parser.add_argument("--project-root", default=None, help="Project root directory")
    parser.add_argument("--summary-file", default=None, help="Optional plain-text summary file")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of candidates to return")
    parsed = parser.parse_args(args)

    summary = ""
    if parsed.summary_file:
        summary_path = Path(parsed.summary_file)
        if not summary_path.exists():
            envelope.fail("FILE_NOT_FOUND", f"Summary file not found: {parsed.summary_file}")
        summary = summary_path.read_text(encoding="utf-8")

    try:
        data = discover_decisions(
            Path(parsed.project_root) if parsed.project_root else None,
            summary=summary,
            limit=parsed.limit,
        )
    except DurableMemoryError as exc:
        envelope.fail(exc.code, exc.message, details=exc.details)
    except Exception as exc:
        envelope.system_error(str(exc))
    envelope.ok(data, code="DISCOVERY_OK", message="Decision discovery completed.")
