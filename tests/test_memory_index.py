"""Tests for memory.index"""

import json
import pytest
from pathlib import Path
from io import StringIO
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


def run_index(args):
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        from lib.memory_index import run
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        return json.loads(sys.stdout.getvalue()), exc_info.value.code
    finally:
        sys.stdout = old_stdout


class TestIndex:
    def test_index_updates_topics(self, initialized_project):
        # AI writes the file directly first
        fp = initialized_project / ".memory" / "architect" / "tech-stack.md"
        fp.write_text("## Tech Stack\n\n- Python\n", encoding="utf-8")

        result, code = run_index(
            ["architect", "tech-stack.md", "--topic", "tech-stack",
             "--summary", "技术栈与依赖",
             "--project-root", str(initialized_project)]
        )
        assert code == 0
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "tech-stack" in topics
        assert "技术栈与依赖" in topics

    def test_index_fails_when_file_missing(self, initialized_project):
        result, code = run_index(
            ["architect", "nonexistent.md", "--topic", "ghost",
             "--summary", "不存在",
             "--project-root", str(initialized_project)]
        )
        assert code == 1
        assert result["code"] == "FILE_NOT_FOUND"

    def test_index_invalid_bucket(self, initialized_project):
        result, code = run_index(
            ["bad", "file.md", "--topic", "t", "--summary", "s",
             "--project-root", str(initialized_project)]
        )
        assert code == 1
        assert result["code"] == "INVALID_BUCKET"

    def test_index_with_anchor(self, initialized_project):
        fp = initialized_project / ".memory" / "dev" / "conventions.md"
        fp.write_text("## Naming\n\nsnake_case\n", encoding="utf-8")

        result, code = run_index(
            ["dev", "conventions.md", "--topic", "conventions",
             "--summary", "代码约定", "--anchor", "naming",
             "--project-root", str(initialized_project)]
        )
        assert code == 0
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "#naming" in topics

    def test_index_creates_new_file_entry(self, initialized_project):
        # Create a new knowledge file
        fp = initialized_project / ".memory" / "architect" / "caching.md"
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("## Caching\n\nRedis\n", encoding="utf-8")

        result, code = run_index(
            ["architect", "caching.md", "--topic", "caching",
             "--summary", "缓存策略",
             "--project-root", str(initialized_project)]
        )
        assert code == 0
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "caching" in topics
        assert "缓存策略" in topics

    def test_index_updates_existing_entry(self, initialized_project):
        fp = initialized_project / ".memory" / "architect" / "tech-stack.md"
        fp.write_text("## Tech\n", encoding="utf-8")

        # Index once
        run_index(
            ["architect", "tech-stack.md", "--topic", "tech-stack",
             "--summary", "旧描述",
             "--project-root", str(initialized_project)]
        )
        # Index again with updated summary
        result, code = run_index(
            ["architect", "tech-stack.md", "--topic", "tech-stack",
             "--summary", "新描述",
             "--project-root", str(initialized_project)]
        )
        assert code == 0
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "新描述" in topics
        # Old summary should be replaced, not duplicated
        assert topics.count("architect/tech-stack.md") == 1
