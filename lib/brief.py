"""Generate BRIEF.md as a recall-first base brief.

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
SECTION_PRIORITY = {
    "architect": ("决策", "原则", "约束", "风险", "架构", "技术栈"),
    "pm": ("结论", "决策", "口径", "范围", "需求", "规则"),
    "qa": ("验证", "测试", "策略", "回归", "风险"),
    "dev": ("约定", "规范", "命名", "目录", "流程"),
}
SKIP_HEADINGS = frozenset({"目录结构", "存储结构", "运行模型", "历史结论", "历史决策"})


def _is_empty_doc(content: str) -> bool:
    """Return True if content is empty or whitespace-only."""
    return not content.strip()


def _normalize_line(line: str) -> str:
    return line.strip().lstrip("- ").strip()


def _extract_candidate_sections(content: str) -> list[tuple[str, list[str]]]:
    lines = content.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_body
        if current_heading is None:
            return
        body = [_normalize_line(line) for line in current_body if line.strip()]
        sections.append((current_heading, body))
        current_heading = None
        current_body = []

    for line in lines:
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip()
        elif current_heading is not None:
            current_body.append(line)

    flush()
    return sections


def _score_section(bucket: str, heading: str) -> int:
    score = 0
    for idx, keyword in enumerate(SECTION_PRIORITY.get(bucket, ())):
        if keyword in heading:
            score += 100 - idx * 10
    if heading in SKIP_HEADINGS:
        score -= 100
    return score


def _extract_best_section(content: str, bucket: str, max_lines: int = 3) -> str:
    """Extract the highest-value section summary for recall-first base brief."""
    sections = _extract_candidate_sections(content)
    ranked = sorted(
        sections,
        key=lambda item: (_score_section(bucket, item[0]), -len(item[1])),
        reverse=True,
    )

    for heading, body in ranked:
        if heading in SKIP_HEADINGS:
            continue
        if body:
            return "## " + heading + "\n" + "\n".join(body[:max_lines])
        return "## " + heading

    # Fallback to first few non-empty lines if there are no usable sections.
    non_empty = [_normalize_line(line) for line in content.splitlines() if line.strip()]
    return "\n".join(non_empty[:max_lines]).rstrip()


def generate_brief(project_root: Path | None = None) -> str:
    """Generate BRIEF.md content from docs/ and write to file."""
    content = _build_brief(project_root, max_lines_per_entry=3)
    if content.count("\n") + 1 > MAX_TOTAL_LINES:
        content = _build_brief(project_root, max_lines_per_entry=2)

    brief_file = paths.brief_path(project_root)
    atomic_write(brief_file, content)
    return content


def _build_brief(project_root: Path | None, max_lines_per_entry: int) -> str:
    sections: list[str] = ["# Project Brief", "", "> Recall-first base brief: 只保留会影响后续动作的高价值上下文。"]

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
            summary = _extract_best_section(raw, bucket, max_lines_per_entry)
            if not summary.strip():
                continue
            entries.append(f"### {md_file.name}\n{summary}")

        if entries:
            sections.append(f"## {bucket}")
            sections.extend(entries)

    return "\n\n".join(sections).rstrip() + "\n"


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
