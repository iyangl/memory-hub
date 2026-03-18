"""Generate BRIEF.md from docs/ by mechanical concatenation.

Usage: memory-hub brief [--project-root <path>]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib import envelope, paths
from lib.utils import atomic_write

# Fixed bucket order for BRIEF.md generation.
BUCKET_ORDER = ("architect", "dev", "pm", "qa")

MAX_TOTAL_LINES = 200


def _is_empty_doc(content: str) -> bool:
    """Return True if content is empty or whitespace-only."""
    return not content.strip()


def _extract_first_section(content: str, max_lines: int = 3) -> str:
    """Extract summary from markdown content.

    Rules (D7 decision):
    - Find first ``## `` heading and the first non-empty paragraph after it.
    - If no ``## `` heading, take first 5 non-empty lines.
    - Truncate result to *max_lines* lines.
    """
    lines = content.splitlines()

    # Try to find first ## heading
    heading_idx = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            heading_idx = i
            break

    if heading_idx is not None:
        heading = lines[heading_idx]
        # Collect first non-empty paragraph after heading
        para_lines: list[str] = []
        in_paragraph = False
        for line in lines[heading_idx + 1 :]:
            stripped = line.strip()
            if not stripped:
                if in_paragraph:
                    break
                continue
            in_paragraph = True
            para_lines.append(line)

        result = heading + "\n" + "\n".join(para_lines[:max_lines])
        return result.rstrip()

    # No ## heading: take first 5 non-empty lines
    non_empty = [l for l in lines if l.strip()]
    taken = non_empty[:5]
    return "\n".join(taken[:max_lines]).rstrip()


def generate_brief(project_root: Path | None = None) -> str:
    """Generate BRIEF.md content from docs/ and write to file.

    Returns the generated content.
    """
    content = _build_brief(project_root, max_lines_per_entry=3)

    if content.count("\n") + 1 > MAX_TOTAL_LINES:
        content = _build_brief(project_root, max_lines_per_entry=2)

    brief_file = paths.brief_path(project_root)
    atomic_write(brief_file, content)
    return content


def _build_brief(
    project_root: Path | None, max_lines_per_entry: int
) -> str:
    """Build BRIEF.md content with given per-entry truncation."""
    sections: list[str] = ["# Project Brief"]

    for bucket in BUCKET_ORDER:
        bucket_dir = paths.bucket_path(bucket, project_root)
        if not bucket_dir.is_dir():
            continue

        md_files = sorted(
            f for f in bucket_dir.iterdir()
            if f.suffix == ".md" and f.is_file()
        )

        entries: list[str] = []
        for md_file in md_files:
            raw = md_file.read_text(encoding="utf-8")
            if _is_empty_doc(raw):
                continue
            summary = _extract_first_section(raw, max_lines_per_entry)
            entries.append(f"### {md_file.name}\n{summary}")

        if entries:
            sections.append(f"## {bucket}")
            sections.extend(entries)

    return "\n\n".join(sections) + "\n"


def run(args: list[str]) -> None:
    """CLI entry: memory-hub brief [--project-root <path>]"""
    parser = argparse.ArgumentParser(prog="memory-hub brief")
    parser.add_argument(
        "--project-root", help="Project root directory", default=None
    )
    parsed = parser.parse_args(args)
    project_root = Path(parsed.project_root) if parsed.project_root else None

    content = generate_brief(project_root)
    line_count = content.count("\n") + 1
    envelope.ok({"brief_path": str(paths.brief_path(project_root)), "lines": line_count})
