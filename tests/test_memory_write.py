"""Tests for memory.write"""

import json
import pytest
from pathlib import Path
from io import StringIO
from unittest.mock import patch
import sys

from lib import paths


@pytest.fixture
def initialized_project(tmp_path):
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
    return tmp_path


def run_write(args, stdin_content):
    old_stdout = sys.stdout
    old_stdin = sys.stdin
    sys.stdout = StringIO()
    sys.stdin = StringIO(stdin_content)
    try:
        from lib.memory_write import run
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        return json.loads(sys.stdout.getvalue()), exc_info.value.code
    finally:
        sys.stdout = old_stdout
        sys.stdin = old_stdin


class TestWrite:
    def test_overwrite_base_file(self, initialized_project):
        result, code = run_write(
            ["architect", "tech-stack.md", "--topic", "tech-stack",
             "--summary", "技术栈", "--mode", "overwrite",
             "--project-root", str(initialized_project)],
            "## Tech Stack\n\n- Python\n"
        )
        assert code == 0
        content = (initialized_project / ".memory" / "architect" / "tech-stack.md").read_text(encoding="utf-8")
        assert "Python" in content

    def test_append_mode(self, initialized_project):
        # Write initial content
        run_write(
            ["dev", "conventions.md", "--topic", "conventions",
             "--summary", "代码约定", "--mode", "overwrite",
             "--project-root", str(initialized_project)],
            "## Naming\n\nsnake_case\n"
        )
        # Append
        result, code = run_write(
            ["dev", "conventions.md", "--topic", "conventions",
             "--summary", "代码约定", "--mode", "append",
             "--project-root", str(initialized_project)],
            "\n## Imports\n\nstdlib first\n"
        )
        assert code == 0
        content = (initialized_project / ".memory" / "dev" / "conventions.md").read_text(encoding="utf-8")
        assert "snake_case" in content
        assert "stdlib first" in content

    def test_creates_new_file(self, initialized_project):
        result, code = run_write(
            ["architect", "caching.md", "--topic", "caching",
             "--summary", "缓存策略", "--mode", "overwrite",
             "--project-root", str(initialized_project)],
            "## Caching\n\nRedis\n"
        )
        assert code == 0
        assert (initialized_project / ".memory" / "architect" / "caching.md").exists()

    def test_updates_topics_md(self, initialized_project):
        run_write(
            ["architect", "tech-stack.md", "--topic", "tech-stack",
             "--summary", "技术栈与依赖", "--mode", "overwrite",
             "--project-root", str(initialized_project)],
            "## Tech\n"
        )
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "tech-stack" in topics
        assert "技术栈与依赖" in topics

    def test_invalid_bucket(self, initialized_project):
        result, code = run_write(
            ["bad", "file.md", "--topic", "t", "--summary", "s",
             "--project-root", str(initialized_project)],
            "content"
        )
        assert code == 1
        assert result["code"] == "INVALID_BUCKET"
