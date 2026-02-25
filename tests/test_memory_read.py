"""Tests for memory.read"""

import json
import pytest
from pathlib import Path
from io import StringIO
import sys

from lib import paths


@pytest.fixture
def initialized_project(tmp_path):
    """Create an initialized .memory/ structure."""
    root = tmp_path / ".memory"
    for bucket, files in paths.BASE_FILES.items():
        for f in files:
            fp = root / bucket / f
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("", encoding="utf-8")
    catalog = root / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "modules").mkdir(exist_ok=True)
    (catalog / "topics.md").write_text("# Topics\n\n## 代码模块\n\n## 知识文件\n", encoding="utf-8")
    # Write some content to test
    (root / "architect" / "tech-stack.md").write_text(
        "## 技术栈\n\n- Python 3.10+\n", encoding="utf-8"
    )
    return tmp_path


def run_read(args):
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        from lib.memory_read import run
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        return json.loads(sys.stdout.getvalue()), exc_info.value.code
    finally:
        sys.stdout = old_stdout


class TestRead:
    def test_read_existing_file(self, initialized_project):
        result, code = run_read(["architect", "tech-stack.md", "--project-root", str(initialized_project)])
        assert code == 0
        assert "Python 3.10+" in result["data"]["content"]

    def test_read_nonexistent_file(self, initialized_project):
        result, code = run_read(["architect", "nope.md", "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "FILE_NOT_FOUND"

    def test_read_invalid_bucket(self, initialized_project):
        result, code = run_read(["invalid", "file.md", "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "INVALID_BUCKET"

    def test_read_with_valid_anchor(self, initialized_project):
        result, code = run_read(["architect", "tech-stack.md", "--anchor", "技术栈",
                                  "--project-root", str(initialized_project)])
        assert code == 0
        assert result["data"]["anchor_valid"] is True

    def test_read_with_invalid_anchor(self, initialized_project):
        result, code = run_read(["architect", "tech-stack.md", "--anchor", "不存在的标题",
                                  "--project-root", str(initialized_project)])
        assert code == 0
        assert result["data"]["anchor_valid"] is False
        assert result["data"]["repair_triggered"] is True
