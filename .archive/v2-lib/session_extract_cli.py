"""CLI entry for local session distillation."""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope
from lib.durable_errors import DurableMemoryError
from lib.session_extract import extract_session_memory


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub session-extract")
    parser.add_argument("--file", required=True, help="Path to a plain-text session transcript.")
    parser.add_argument("--source-label", default="manual-session", help="Stable label recorded in capture/update reason.")
    parser.add_argument("--created-by", default="session-extract", help="Actor recorded on generated reviews/proposals.")
    parser.add_argument("--max-candidates", type=int, default=8, help="Maximum number of candidates to extract.")
    parser.add_argument("--project-root", default=None, help="Project root directory")
    parsed = parser.parse_args(args)

    transcript_file = Path(parsed.file)
    if not transcript_file.exists():
        envelope.fail("FILE_NOT_FOUND", f"Session transcript not found: {parsed.file}")
    transcript = transcript_file.read_text(encoding="utf-8")
    try:
        data = extract_session_memory(
            Path(parsed.project_root) if parsed.project_root else None,
            transcript=transcript,
            source_label=parsed.source_label,
            created_by=parsed.created_by,
            max_candidates=parsed.max_candidates,
        )
    except DurableMemoryError as exc:
        envelope.fail(exc.code, exc.message, details=exc.details)
    except Exception as exc:
        envelope.system_error(str(exc))
    envelope.ok(data, code="SESSION_EXTRACT_OK", message="Session extraction completed.")
