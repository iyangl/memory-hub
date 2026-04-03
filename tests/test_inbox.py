"""Tests for inbox-list and inbox-clean commands."""

import json
import os
import time
import pytest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import sys

from lib import paths


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


@pytest.fixture
def inbox_project(tmp_path):
    inbox = tmp_path / ".memory" / "inbox"
    inbox.mkdir(parents=True)
    return tmp_path


class TestInboxList:
    def test_list_empty_inbox(self, inbox_project):
        result, code = run_cmd("lib.inbox_list", ["--project-root", str(inbox_project)])
        assert code == 0
        assert result["data"]["files"] == []
        assert result["data"]["count"] == 0

    def test_list_inbox_with_files(self, inbox_project):
        inbox = inbox_project / ".memory" / "inbox"
        (inbox / "2026-01-01T00_00_00Z_note1.md").write_text("note 1")
        (inbox / "2026-01-02T00_00_00Z_note2.md").write_text("note 2 content")

        result, code = run_cmd("lib.inbox_list", ["--project-root", str(inbox_project)])
        assert code == 0
        assert result["data"]["count"] == 2
        names = [f["name"] for f in result["data"]["files"]]
        assert "2026-01-01T00_00_00Z_note1.md" in names
        assert "2026-01-02T00_00_00Z_note2.md" in names
        for f in result["data"]["files"]:
            assert "size_bytes" in f
            assert "modified_iso" in f

    def test_list_ignores_non_md_files(self, inbox_project):
        inbox = inbox_project / ".memory" / "inbox"
        (inbox / "note.md").write_text("md file")
        (inbox / "note.txt").write_text("txt file")

        result, code = run_cmd("lib.inbox_list", ["--project-root", str(inbox_project)])
        assert code == 0
        assert result["data"]["count"] == 1

    def test_list_no_inbox_dir(self, tmp_path):
        (tmp_path / ".memory").mkdir(parents=True)
        result, code = run_cmd("lib.inbox_list", ["--project-root", str(tmp_path)])
        assert code == 0
        assert result["data"]["files"] == []


class TestInboxClean:
    def test_clean_removes_all(self, inbox_project):
        inbox = inbox_project / ".memory" / "inbox"
        (inbox / "a.md").write_text("a")
        (inbox / "b.md").write_text("b")

        result, code = run_cmd("lib.inbox_clean", ["--project-root", str(inbox_project)])
        assert code == 0
        assert sorted(result["data"]["removed"]) == ["a.md", "b.md"]
        assert result["data"]["kept"] == []
        assert not list(inbox.glob("*.md"))

    def test_clean_with_before_filter(self, inbox_project):
        inbox = inbox_project / ".memory" / "inbox"
        old_file = inbox / "old.md"
        new_file = inbox / "new.md"
        old_file.write_text("old")
        new_file.write_text("new")

        # Set old_file mtime to a past time
        past = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
        os.utime(old_file, (past, past))

        cutoff = "2025-01-01T00:00:00+00:00"
        result, code = run_cmd("lib.inbox_clean", [
            "--before", cutoff,
            "--project-root", str(inbox_project),
        ])
        assert code == 0
        assert result["data"]["removed"] == ["old.md"]
        assert result["data"]["kept"] == ["new.md"]
        assert new_file.exists()
        assert not old_file.exists()

    def test_clean_keeps_non_md_files(self, inbox_project):
        inbox = inbox_project / ".memory" / "inbox"
        (inbox / "note.md").write_text("md")
        (inbox / "keep.txt").write_text("txt")

        result, code = run_cmd("lib.inbox_clean", ["--project-root", str(inbox_project)])
        assert code == 0
        assert result["data"]["removed"] == ["note.md"]
        assert (inbox / "keep.txt").exists()

    def test_clean_empty_inbox(self, inbox_project):
        result, code = run_cmd("lib.inbox_clean", ["--project-root", str(inbox_project)])
        assert code == 0
        assert result["data"]["removed"] == []
        assert result["data"]["kept"] == []

    def test_clean_invalid_before_returns_business_error(self, inbox_project):
        result, code = run_cmd("lib.inbox_clean", [
            "--before", "not-an-iso",
            "--project-root", str(inbox_project),
        ])
        assert code == 1
        assert result["ok"] is False
        assert result["code"] == "INVALID_TIMESTAMP"
