"""Shared docs-lane helpers for project memory."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from lib import paths
from lib.catalog_repair import _parse_topics_entries, repair
from lib.memory_index import _update_topics_knowledge
from lib.utils import atomic_write


def slugify_doc_title(title: str) -> str:
    """Build a stable docs filename stem from a title."""
    text = str(title or "").strip().lower()
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    slug = text.strip("-")
    return slug or "item"


def parse_doc_ref(ref: str) -> tuple[str, str]:
    """Parse doc://<bucket>/<name> refs."""
    if not ref.startswith("doc://"):
        raise ValueError(f"Invalid doc ref: {ref}")
    parts = ref.removeprefix("doc://").split("/")
    if len(parts) != 2 or parts[0] not in paths.BUCKETS or not parts[1]:
        raise ValueError(f"Invalid doc ref: {ref}")
    return parts[0], parts[1]


def render_doc(title: str, content: str) -> str:
    """Render docs-lane content with a title heading when missing."""
    clean = str(content or "").strip()
    return clean if clean.startswith("#") else f"# {title}\n\n{clean}\n"


def diff_contents(before: str, after: str) -> str:
    """Render a unified diff for docs review display."""
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    return "\n".join(lines)


def summary_from_doc(title: str, content: str) -> str:
    """Extract a compact durable summary from a docs body."""
    body_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body_lines.append(stripped)
    body = " ".join(body_lines).strip() or title
    return body[:240]


def ensure_doc_registered(
    project_root: Path | None,
    *,
    bucket: str,
    filename: str,
    summary: str,
) -> dict[str, object]:
    """Ensure a docs-lane file is registered in topics.md and repair catalog."""
    topics_file = paths.topics_path(project_root)
    if not topics_file.exists():
        atomic_write(topics_file, "# Memory Hub — Topics Index\n\n## 知识文件\n")
    file_ref = paths.docs_file_ref(bucket, filename)
    content = topics_file.read_text(encoding="utf-8") if topics_file.exists() else ""
    if any(entry["file_ref"] == file_ref for entry in _parse_topics_entries(content)):
        return {"registered": False, "repair_result": repair(project_root)}

    _update_topics_knowledge(
        topics_file,
        topic=Path(filename).stem,
        summary=summary,
        bucket=bucket,
        filename=filename,
        anchor=None,
    )
    return {"registered": True, "repair_result": repair(project_root)}
