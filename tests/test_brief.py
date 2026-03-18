"""Tests for lib/brief.py — BRIEF.md mechanical generation."""

import json
import pytest
import sys
from io import StringIO
from pathlib import Path

from lib import paths
from lib.brief import (
    generate_brief,
    _extract_first_section,
    _is_empty_doc,
    BUCKET_ORDER,
    MAX_TOTAL_LINES,
)


@pytest.fixture
def mem_root(tmp_path):
    """Create a minimal .memory/docs/ structure."""
    root = tmp_path / ".memory" / "docs"
    for bucket in BUCKET_ORDER:
        (root / bucket).mkdir(parents=True)
    return tmp_path


def _write_doc(mem_root: Path, bucket: str, name: str, content: str) -> None:
    mem_root.joinpath(".memory", "docs", bucket, name).write_text(
        content, encoding="utf-8"
    )


# --- Unit tests for helpers ---


class TestIsEmptyDoc:
    def test_empty_string(self):
        assert _is_empty_doc("") is True

    def test_whitespace_only(self):
        assert _is_empty_doc("   \n\n  \t  ") is True

    def test_non_empty(self):
        assert _is_empty_doc("hello") is False


class TestExtractFirstSection:
    def test_with_h2_heading(self):
        content = "## Title\n\nFirst paragraph line.\nSecond line.\n\n## Next"
        result = _extract_first_section(content)
        assert result.startswith("## Title")
        assert "First paragraph line." in result
        assert "## Next" not in result

    def test_truncates_to_max_lines(self):
        content = "## Heading\n\nLine 1\nLine 2\nLine 3\nLine 4\nLine 5"
        result = _extract_first_section(content, max_lines=2)
        body_lines = result.split("\n")[1:]  # skip heading
        assert len(body_lines) <= 2

    def test_no_h2_takes_first_5(self):
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7"
        result = _extract_first_section(content, max_lines=5)
        assert "Line 5" in result
        assert "Line 6" not in result

    def test_no_h2_truncated_to_max_lines(self):
        content = "A\nB\nC\nD\nE\nF"
        result = _extract_first_section(content, max_lines=2)
        lines = result.split("\n")
        assert len(lines) <= 2

    def test_skips_blank_lines_between_heading_and_paragraph(self):
        content = "## Title\n\n\n\nActual content here."
        result = _extract_first_section(content)
        assert "Actual content here." in result

    def test_empty_after_heading(self):
        content = "## Title\n\n"
        result = _extract_first_section(content)
        assert result.startswith("## Title")


# --- Integration tests for generate_brief ---


class TestGenerateBrief:
    def test_empty_docs(self, mem_root):
        content = generate_brief(mem_root)
        assert content.startswith("# Project Brief")
        # Only the title, no bucket sections
        assert "## architect" not in content

    def test_skips_empty_files(self, mem_root):
        _write_doc(mem_root, "architect", "empty.md", "   \n")
        _write_doc(mem_root, "architect", "real.md", "## Stack\n\nPython 3.10+")
        content = generate_brief(mem_root)
        assert "empty.md" not in content
        assert "real.md" in content

    def test_bucket_order(self, mem_root):
        _write_doc(mem_root, "qa", "a.md", "## QA\n\nQA content")
        _write_doc(mem_root, "architect", "a.md", "## Arch\n\nArch content")
        _write_doc(mem_root, "dev", "a.md", "## Dev\n\nDev content")
        _write_doc(mem_root, "pm", "a.md", "## PM\n\nPM content")
        content = generate_brief(mem_root)

        idx_arch = content.index("## architect")
        idx_dev = content.index("## dev")
        idx_pm = content.index("## pm")
        idx_qa = content.index("## qa")
        assert idx_arch < idx_dev < idx_pm < idx_qa

    def test_alphabetical_file_order(self, mem_root):
        _write_doc(mem_root, "dev", "zebra.md", "## Z\n\nZebra")
        _write_doc(mem_root, "dev", "alpha.md", "## A\n\nAlpha")
        content = generate_brief(mem_root)
        idx_alpha = content.index("### alpha.md")
        idx_zebra = content.index("### zebra.md")
        assert idx_alpha < idx_zebra

    def test_writes_brief_file(self, mem_root):
        _write_doc(mem_root, "architect", "stack.md", "## Stack\n\nPython")
        generate_brief(mem_root)
        brief = paths.brief_path(mem_root)
        assert brief.exists()
        assert "Python" in brief.read_text(encoding="utf-8")

    def test_truncation_on_overflow(self, mem_root):
        # Create enough docs so 3-line entries exceed MAX_TOTAL_LINES,
        # but 2-line entries fit within the limit.
        # Each entry at 3 lines: ~6 output lines (### heading + 3 body + blank)
        # 40 files × 6 lines = ~240 > 200 → triggers regeneration
        # At 2 lines: ~5 output lines × 40 = ~200 → within limit
        for i in range(40):
            _write_doc(
                mem_root,
                "dev",
                f"doc-{i:03d}.md",
                f"## Title {i}\n\nLine A of {i}\nLine B of {i}\nLine C of {i}",
            )
        content_3line = generate_brief(mem_root)
        # Should have triggered 2-line fallback
        # Verify truncation happened: no "Line C" in output
        assert "Line C" not in content_3line

    def test_no_h2_fallback(self, mem_root):
        _write_doc(
            mem_root, "pm", "notes.md", "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"
        )
        content = generate_brief(mem_root)
        assert "notes.md" in content
        assert "Line 1" in content


class TestBriefCli:
    def test_cli_returns_ok(self, mem_root):
        _write_doc(mem_root, "dev", "test.md", "## Test\n\nHello")

        from lib.brief import run

        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            with pytest.raises(SystemExit) as exc_info:
                run(["--project-root", str(mem_root)])
            output = sys.stdout.getvalue()
            result = json.loads(output)
            assert result["ok"] is True
            assert "brief_path" in result["data"]
            assert exc_info.value.code == 0
        finally:
            sys.stdout = old_stdout
