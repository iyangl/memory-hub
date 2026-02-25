"""Tests for memory.list and memory.search"""

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
    (root / "architect" / "tech-stack.md").write_text("## Tech\n\n- Python 3.10+\n", encoding="utf-8")
    catalog = root / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "modules").mkdir(exist_ok=True)
    (catalog / "topics.md").write_text("# Topics\n", encoding="utf-8")
    return tmp_path


def run_cmd(module_name, args):
    import importlib
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        mod = importlib.import_module(module_name)
        with pytest.raises(SystemExit) as exc_info:
            mod.run(args)
        return json.loads(sys.stdout.getvalue()), exc_info.value.code
    finally:
        sys.stdout = old_stdout


class TestList:
    def test_list_bucket(self, initialized_project):
        result, code = run_cmd("lib.memory_list", ["architect", "--project-root", str(initialized_project)])
        assert code == 0
        assert "decisions.md" in result["data"]["files"]
        assert "tech-stack.md" in result["data"]["files"]

    def test_list_invalid_bucket(self, initialized_project):
        result, code = run_cmd("lib.memory_list", ["bad", "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "INVALID_BUCKET"


class TestSearch:
    def test_search_finds_match(self, initialized_project):
        result, code = run_cmd("lib.memory_search", ["Python", "--project-root", str(initialized_project)])
        assert code == 0
        assert result["data"]["total"] >= 1
        assert any("Python" in m["line_content"] for m in result["data"]["matches"])

    def test_search_no_match(self, initialized_project):
        result, code = run_cmd("lib.memory_search", ["zzzznotfound", "--project-root", str(initialized_project)])
        assert code == 0
        assert result["data"]["total"] == 0
