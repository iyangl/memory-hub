"""Tests for lib/brief.py — recall-first base brief generation."""

import json
import pytest
import sys
from io import StringIO
from pathlib import Path

from lib import paths
from lib.brief import (
    generate_brief,
    _extract_best_section,
    _is_empty_doc,
    BUCKET_ORDER,
)


@pytest.fixture
def mem_root(tmp_path):
    root = tmp_path / ".memory" / "docs"
    for bucket in BUCKET_ORDER:
        (root / bucket).mkdir(parents=True)
    return tmp_path


def _write_doc(mem_root: Path, bucket: str, name: str, content: str) -> None:
    mem_root.joinpath(".memory", "docs", bucket, name).write_text(
        content, encoding="utf-8"
    )


class TestIsEmptyDoc:
    def test_empty_string(self):
        assert _is_empty_doc("") is True

    def test_whitespace_only(self):
        assert _is_empty_doc("   \n\n  \t  ") is True

    def test_non_empty(self):
        assert _is_empty_doc("hello") is False


class TestExtractBestSection:
    def test_prefers_decision_like_sections(self):
        content = "## 目录结构\n\nfoo\n\n## 决策原则\n\nshould pick me"
        result = _extract_best_section(content, "architect")
        assert result.startswith("## 决策原则")
        assert "should pick me" in result

    def test_fallback_without_h2(self):
        content = "Line 1\nLine 2\nLine 3"
        result = _extract_best_section(content, "pm", 2)
        assert result == "Line 1\nLine 2"


class TestGenerateBrief:
    def test_empty_docs(self, mem_root):
        content = generate_brief(mem_root)
        assert content.startswith("# Project Brief")
        assert "Recall-first base brief" in content

    def test_bucket_order(self, mem_root):
        _write_doc(mem_root, "qa", "a.md", "## 测试策略\n\nQA content")
        _write_doc(mem_root, "architect", "a.md", "## 决策\n\nArch content")
        _write_doc(mem_root, "dev", "a.md", "## 约定\n\nDev content")
        _write_doc(mem_root, "pm", "a.md", "## 结论\n\nPM content")
        content = generate_brief(mem_root)
        idx_arch = content.index("## architect")
        idx_dev = content.index("## dev")
        idx_pm = content.index("## pm")
        idx_qa = content.index("## qa")
        assert idx_arch < idx_dev < idx_pm < idx_qa

    def test_prefers_high_value_sections(self, mem_root):
        _write_doc(mem_root, "architect", "stack.md", "## 目录结构\n\nboring\n\n## 决策\n\nUse recall-first")
        content = generate_brief(mem_root)
        assert "Use recall-first" in content
        assert "boring" not in content

    def test_writes_brief_file(self, mem_root):
        _write_doc(mem_root, "architect", "stack.md", "## 决策\n\nPython")
        generate_brief(mem_root)
        brief = paths.brief_path(mem_root)
        assert brief.exists()
        assert "Python" in brief.read_text(encoding="utf-8")


class TestBriefCli:
    def test_cli_returns_ok(self, mem_root):
        _write_doc(mem_root, "dev", "test.md", "## 约定\n\nHello")
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
