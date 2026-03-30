"""Tests for memory.init"""

import json
import pytest


def run_init(project_root):
    import sys
    from io import StringIO
    from lib.memory_init import run

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            run(["--project-root", str(project_root)])
        output = sys.stdout.getvalue()
        return json.loads(output), exc_info.value.code
    finally:
        sys.stdout = old_stdout


class TestInit:
    def test_creates_directory_structure(self, tmp_path):
        result, code = run_init(tmp_path)
        assert code == 0
        assert result["ok"] is True

        root = tmp_path / ".memory"
        assert root.exists()
        assert (root / "docs" / "pm" / "decisions.md").exists()
        assert (root / "docs" / "architect" / "tech-stack.md").exists()
        assert (root / "docs" / "architect" / "decisions.md").exists()
        assert (root / "docs" / "dev" / "conventions.md").exists()
        assert (root / "docs" / "qa" / "strategy.md").exists()
        assert (root / "catalog" / "topics.md").exists()
        assert (root / "catalog" / "modules").is_dir()
        assert (root / "inbox").is_dir()
        assert (root / "session").is_dir()
        assert (root / "BRIEF.md").exists()
        assert (root / "manifest.json").exists()

    def test_topics_has_skeleton(self, tmp_path):
        run_init(tmp_path)
        content = (tmp_path / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "## 代码模块" in content
        assert "## 知识文件" in content
        manifest = json.loads((tmp_path / ".memory" / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["layout_version"] == "4"
        assert manifest["session_root"] == "session"

    def test_already_initialized(self, tmp_path):
        run_init(tmp_path)
        result, code = run_init(tmp_path)
        assert code == 1
        assert result["code"] == "ALREADY_INITIALIZED"

    def test_repair_auto_triggered(self, tmp_path):
        result, _ = run_init(tmp_path)
        assert "repair_result" in result["data"]

    def test_brief_is_generated(self, tmp_path):
        run_init(tmp_path)
        brief = (tmp_path / ".memory" / "BRIEF.md").read_text(encoding="utf-8")
        assert brief.startswith("# Project Brief")
