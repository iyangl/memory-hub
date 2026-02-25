"""Tests for memory.init"""

import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch

from lib import paths


@pytest.fixture
def tmp_project(tmp_path):
    return tmp_path


def run_init(project_root):
    """Run init and capture output."""
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
    def test_creates_directory_structure(self, tmp_project):
        result, code = run_init(tmp_project)
        assert code == 0
        assert result["ok"] is True

        root = tmp_project / ".memory"
        assert root.exists()
        assert (root / "pm" / "decisions.md").exists()
        assert (root / "architect" / "tech-stack.md").exists()
        assert (root / "architect" / "decisions.md").exists()
        assert (root / "dev" / "conventions.md").exists()
        assert (root / "qa" / "strategy.md").exists()
        assert (root / "catalog" / "topics.md").exists()
        assert (root / "catalog" / "modules").is_dir()

    def test_topics_has_skeleton(self, tmp_project):
        run_init(tmp_project)
        content = (tmp_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "## 代码模块" in content
        assert "## 知识文件" in content

    def test_already_initialized(self, tmp_project):
        run_init(tmp_project)
        result, code = run_init(tmp_project)
        assert code == 1
        assert result["code"] == "ALREADY_INITIALIZED"

    def test_repair_auto_triggered(self, tmp_project):
        result, _ = run_init(tmp_project)
        assert "repair_result" in result["data"]
