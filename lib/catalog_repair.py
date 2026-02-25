"""catalog.repair — Check and fix consistency of topics.md index.

Usage: memory-hub catalog-repair [--project-root <path>]

Checks:
1. Dead links: topics.md references non-existent files → auto-delete (fixed)
2. Missing registration: bucket files not in topics.md → ai_actions
3. Duplicate topics: same topic appears multiple times → manual_actions
4. Invalid anchors: #anchor not found in target file → ai_actions or manual_actions
"""

from __future__ import annotations

import argparse
import re
from difflib import get_close_matches
from pathlib import Path

from lib import envelope, paths


def _parse_topics_entries(content: str) -> list[dict]:
    """Parse topics.md and extract all file references with their line numbers."""
    entries = []
    lines = content.splitlines()
    current_topic = None

    for i, line in enumerate(lines):
        # Track topic headers
        m_topic = re.match(r"^###\s+(.+)$", line)
        if m_topic:
            current_topic = m_topic.group(1).strip()
            continue

        # Match entry lines: - path/file.md [#anchor] — description
        m_entry = re.match(r"^-\s+(\S+?)(?:\s+#(\S+))?\s+—\s+(.+)$", line)
        if m_entry:
            entries.append({
                "line_number": i,
                "file_ref": m_entry.group(1),
                "anchor": m_entry.group(2),
                "description": m_entry.group(3).strip(),
                "topic": current_topic,
                "raw_line": line,
            })

    return entries


def _get_headings(content: str) -> list[str]:
    """Extract all heading texts from markdown content."""
    headings = []
    for line in content.splitlines():
        m = re.match(r"^#{1,6}\s+(.+)$", line)
        if m:
            headings.append(m.group(1).strip())
    return headings


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    return text


def repair(project_root: Path | None = None) -> dict:
    """Run repair checks and return results dict (does not call envelope)."""
    root = paths.memory_root(project_root)
    topics_file = paths.topics_path(project_root)

    fixed = []
    ai_actions = []
    manual_actions = []

    if not topics_file.exists():
        return {"fixed": fixed, "ai_actions": ai_actions, "manual_actions": manual_actions}

    content = topics_file.read_text(encoding="utf-8")
    entries = _parse_topics_entries(content)
    lines = content.splitlines()

    # --- Check 1: Dead links ---
    lines_to_remove = set()
    for entry in entries:
        ref = entry["file_ref"]
        # Check if it's a bucket file reference (bucket/file.md)
        parts = ref.split("/", 1)
        if len(parts) == 2 and parts[0] in paths.BUCKETS:
            target = root / ref
            if not target.exists():
                lines_to_remove.add(entry["line_number"])
                fixed.append({
                    "type": "dead_link_removed",
                    "file_ref": ref,
                    "line": entry["line_number"] + 1,
                })

    # --- Check 2: Missing registration ---
    registered_files = set()
    for entry in entries:
        registered_files.add(entry["file_ref"])

    for bucket in paths.BUCKETS:
        bp = root / bucket
        if not bp.exists():
            continue
        for md_file in sorted(bp.iterdir()):
            if md_file.suffix != ".md":
                continue
            rel = f"{bucket}/{md_file.name}"
            if rel not in registered_files:
                ai_actions.append({
                    "type": "missing_registration",
                    "file": rel,
                    "action": f"Read {rel} and register in topics.md with appropriate topic/summary via memory.write",
                })

    # --- Check 3: Duplicate topics ---
    # Count topic headers, not entries
    topic_header_lines: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        m = re.match(r"^###\s+(.+)$", line)
        if m:
            t = m.group(1).strip()
            topic_header_lines.setdefault(t, []).append(i)

    for topic, line_nums in topic_header_lines.items():
        if len(line_nums) > 1:
            manual_actions.append({
                "type": "duplicate_topic",
                "topic": topic,
                "lines": [n + 1 for n in line_nums],
                "action": f"Merge duplicate topic '{topic}' sections manually",
            })

    # --- Check 4: Invalid anchors ---
    for entry in entries:
        if not entry["anchor"]:
            continue
        if entry["line_number"] in lines_to_remove:
            continue  # Already flagged as dead link

        ref = entry["file_ref"]
        parts = ref.split("/", 1)
        if len(parts) != 2 or parts[0] not in paths.BUCKETS:
            continue

        target = root / ref
        if not target.exists():
            continue

        file_content = target.read_text(encoding="utf-8")
        headings = _get_headings(file_content)
        heading_slugs = [_slugify(h) for h in headings]

        anchor = entry["anchor"]
        if anchor in headings or anchor in heading_slugs:
            continue  # Valid

        # Try to find close match
        close = get_close_matches(anchor, headings, n=1, cutoff=0.6)
        close_slugs = get_close_matches(anchor, heading_slugs, n=1, cutoff=0.6)

        if close:
            ai_actions.append({
                "type": "invalid_anchor_fixable",
                "file_ref": ref,
                "anchor": anchor,
                "suggested": close[0],
                "action": f"Update anchor #{anchor} to #{close[0]} in topics.md",
            })
        elif close_slugs:
            ai_actions.append({
                "type": "invalid_anchor_fixable",
                "file_ref": ref,
                "anchor": anchor,
                "suggested": close_slugs[0],
                "action": f"Update anchor #{anchor} to #{close_slugs[0]} in topics.md",
            })
        else:
            manual_actions.append({
                "type": "invalid_anchor",
                "file_ref": ref,
                "anchor": anchor,
                "available_headings": headings[:10],
                "action": f"Anchor #{anchor} not found in {ref}, no close match. Manual fix needed.",
            })

    # --- Apply fixes: remove dead link lines ---
    if lines_to_remove:
        new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
        # Clean up empty topic sections (### header followed by another ### or ##)
        cleaned = []
        for i, line in enumerate(new_lines):
            if re.match(r"^###\s+", line):
                # Check if next non-empty line is another header or end
                j = i + 1
                while j < len(new_lines) and not new_lines[j].strip():
                    j += 1
                if j >= len(new_lines) or new_lines[j].startswith("## ") or new_lines[j].startswith("### "):
                    continue  # Skip empty topic header
            cleaned.append(line)

        from lib.memory_write import _atomic_write
        _atomic_write(topics_file, "\n".join(cleaned) + "\n")

    return {"fixed": fixed, "ai_actions": ai_actions, "manual_actions": manual_actions}


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub catalog-repair")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    result = repair(project_root)

    envelope.ok(
        result,
        ai_actions=result["ai_actions"],
        manual_actions=result["manual_actions"],
    )
