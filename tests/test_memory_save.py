"""Tests for memory.save"""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import pytest
from io import StringIO
import sys
from pathlib import Path



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



def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")



def write_working_set(project_root: Path, *, excerpt: str):
    session_dir = project_root / ".memory" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1",
        "task": "save task",
        "source_plan": ".memory/session/recall-plan.json",
        "summary": "working set summary",
        "items": [
            {
                "kind": "decision",
                "title": "architect/decisions.md",
                "summary": excerpt,
                "bullets": [excerpt],
                "sources": [{"type": "doc", "path": "docs/architect/decisions.md"}],
                "selected_because": "test fixture",
            }
        ],
        "priority_reads": [],
        "evidence_gaps": [],
        "durable_candidates": [excerpt],
    }
    write_json(session_dir / "task-working-set.json", payload)


@pytest.fixture
def initialized_project(tmp_path):
    result, code = run_cmd("lib.memory_init", ["--project-root", str(tmp_path)])
    assert code == 0
    docs = tmp_path / ".memory" / "docs"
    (docs / "pm" / "decisions.md").write_text("## 规则\n\n- 旧规则\n", encoding="utf-8")
    (docs / "architect" / "decisions.md").write_text("## 决策\n\n- recall-first\n", encoding="utf-8")
    (docs / "qa" / "strategy.md").write_text("## 验证策略\n\n- 回归关键路径\n", encoding="utf-8")
    return tmp_path


class TestSave:
    def test_noop_success(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "task": "no durable change",
            "entries": [
                {
                    "id": "noop-1",
                    "action": "noop",
                    "reason": "Nothing worth saving.",
                }
            ],
        }
        request_file = tmp_path / "save-noop.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["code"] == "NOOP"
        assert result["data"]["writes"] == []
        assert result["data"]["rebuild"] == {"brief": False, "catalog_repair": None}

    def test_non_noop_requires_search_queries(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "append-1",
                    "action": "append",
                    "reason": "stable rule",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"section_markdown": "## 新规则\n\n- 新内容\n"},
                    "evidence": {
                        "search_queries": [],
                        "read_refs": ["docs/pm/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-missing-search.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "SAVE_GUARD_FAILED"

    def test_append_requires_target_read(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "append-1",
                    "action": "append",
                    "reason": "stable rule",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"section_markdown": "## 新规则\n\n- 新内容\n"},
                    "evidence": {
                        "search_queries": ["规则"],
                        "read_refs": ["docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-missing-target-read.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "SAVE_GUARD_FAILED"

    @pytest.mark.parametrize("filename", ["../secret.md", "nested/file.md", r"nested\\file.md", "/tmp/secret.md", r"C:\\temp\\secret.md"])
    def test_rejects_invalid_target_file(self, initialized_project, tmp_path, filename):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": filename},
                    "payload": {"doc_markdown": "# 缓存策略\n\n## 决策\n\n- 使用本地文件缓存\n"},
                    "index": {"topic": "caching", "summary": "缓存策略"},
                    "evidence": {
                        "search_queries": ["缓存 决策"],
                        "read_refs": ["docs/architect/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-invalid-target-file.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "INVALID_DOCS_FILENAME"

    def test_create_with_index_writes_doc_and_updates_legacy_topics(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "task": "save new decision",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": "caching.md"},
                    "payload": {"doc_markdown": "# 缓存策略\n\n## 决策\n\n- 使用本地文件缓存\n"},
                    "index": {"topic": "caching", "summary": "缓存策略"},
                    "evidence": {
                        "search_queries": ["缓存 决策"],
                        "read_refs": ["docs/architect/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-create.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["code"] == "SUCCESS"
        created = initialized_project / ".memory" / "docs" / "architect" / "caching.md"
        assert created.exists()
        assert "本地文件缓存" in created.read_text(encoding="utf-8")
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "docs/architect/caching.md" in topics
        assert result["data"]["indexed"] == ["docs/architect/caching.md"]
        assert result["data"]["rebuild"] == {"brief": False, "catalog_repair": None}

    def test_create_without_index_writes_doc_and_skips_legacy_index(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": "caching-without-index.md"},
                    "payload": {"doc_markdown": "## 决策\n\n- 使用本地文件缓存\n"},
                    "evidence": {
                        "search_queries": ["缓存 决策"],
                        "read_refs": ["docs/architect/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-create-without-index.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["code"] == "SUCCESS"
        created = initialized_project / ".memory" / "docs" / "architect" / "caching-without-index.md"
        assert created.exists()
        assert "本地文件缓存" in created.read_text(encoding="utf-8")
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "docs/architect/caching-without-index.md" not in topics
        assert result["data"]["indexed"] == []

    def test_append_adds_section(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "append-1",
                    "action": "append",
                    "reason": "stable rule",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"section_markdown": "## 优惠券规则\n\n- 满减后再校验上限\n"},
                    "evidence": {
                        "search_queries": ["优惠券 规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-append.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        content = (initialized_project / ".memory" / "docs" / "pm" / "decisions.md").read_text(encoding="utf-8")
        assert "## 优惠券规则" in content
        assert "满减后再校验上限" in content
        assert result["data"]["writes"] == ["docs/pm/decisions.md"]
        assert result["data"]["trace"] == {"update_supersedes": [], "trace_file": None, "warning": None}

    def test_append_refreshes_registered_topics_summary(self, initialized_project, tmp_path):
        result, code = run_cmd(
            "lib.memory_index",
            [
                "pm",
                "decisions.md",
                "--topic",
                "pm-decisions",
                "--summary",
                "旧摘要",
                "--project-root",
                str(initialized_project),
            ],
        )
        assert code == 0

        request = {
            "version": "1",
            "entries": [
                {
                    "id": "append-1",
                    "action": "append",
                    "reason": "stable rule",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"section_markdown": "## 产品结论\n\n- 新的 durable summary\n"},
                    "evidence": {
                        "search_queries": ["产品结论"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-append-refresh-topics.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "docs/pm/decisions.md — 产品结论：新的 durable summary" in topics
        assert result["data"]["applied"][0]["summary_refreshed"] is True

    def test_append_rejects_duplicate_heading(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "append-1",
                    "action": "append",
                    "reason": "stable rule",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"section_markdown": "## 规则\n\n- 重复标题\n"},
                    "evidence": {
                        "search_queries": ["规则"],
                        "read_refs": ["docs/pm/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-duplicate-heading.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "APPEND_HEADING_EXISTS"

    def test_update_requires_supersedes(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"doc_markdown": "## 规则\n\n- 新规则\n"},
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-update-missing-supersedes.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "INVALID_SAVE_REQUEST"

    def test_merge_writes_merged_doc(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "task": "merge checkout rules",
            "entries": [
                {
                    "id": "merge-1",
                    "action": "merge",
                    "reason": "merge stable checkout rules into existing doc",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"doc_markdown": "## 规则\n\n- 旧规则\n- 新增优惠券口径\n"},
                    "evidence": {
                        "search_queries": ["规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/architect/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-merge.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["code"] == "SUCCESS"
        assert result["data"]["applied"][0]["action"] == "merge"
        assert result["data"]["indexed"] == []
        content = (initialized_project / ".memory" / "docs" / "pm" / "decisions.md").read_text(encoding="utf-8")
        assert "- 旧规则" in content
        assert "- 新增优惠券口径" in content

    def test_merge_refreshes_registered_topics_summary(self, initialized_project, tmp_path):
        result, code = run_cmd(
            "lib.memory_index",
            [
                "pm",
                "decisions.md",
                "--topic",
                "pm-decisions",
                "--summary",
                "旧摘要",
                "--project-root",
                str(initialized_project),
            ],
        )
        assert code == 0

        request = {
            "version": "1",
            "task": "merge checkout rules",
            "entries": [
                {
                    "id": "merge-1",
                    "action": "merge",
                    "reason": "merge stable checkout rules into existing doc",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {"doc_markdown": "## Checkout 优惠券规则\n\n- 合并后的新口径\n"},
                    "evidence": {
                        "search_queries": ["Checkout 优惠券规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/architect/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-merge-refresh-topics.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "docs/pm/decisions.md — Checkout 优惠券规则：合并后的新口径" in topics
        assert result["data"]["applied"][0]["summary_refreshed"] is True

    def test_update_replaces_doc_when_supersedes_is_provided(self, initialized_project, tmp_path):
        result, code = run_cmd(
            "lib.memory_index",
            [
                "pm",
                "decisions.md",
                "--topic",
                "pm-decisions",
                "--summary",
                "旧摘要",
                "--project-root",
                str(initialized_project),
            ],
        )
        assert code == 0

        request = {
            "version": "1",
            "task": "update outdated rule",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {
                        "doc_markdown": "## 产品结论\n\n- 新规则\n",
                        "supersedes": "旧规则的结论已经过时",
                    },
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-update.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["code"] == "SUCCESS"
        assert result["data"]["applied"][0]["action"] == "update"
        assert result["data"]["applied"][0]["summary_refreshed"] is True
        trace = result["data"]["trace"]
        assert trace["trace_file"]
        assert trace["trace_file"].startswith(".memory/session/save-trace/")
        assert trace["trace_file"].endswith(".json")
        assert trace["warning"] is None
        assert trace["update_supersedes"] == [{
            "target": "docs/pm/decisions.md",
            "supersedes": "旧规则的结论已经过时",
            "previous_summary": "规则：旧规则",
            "new_summary": "产品结论：新规则",
        }]
        content = (initialized_project / ".memory" / "docs" / "pm" / "decisions.md").read_text(encoding="utf-8")
        assert "- 新规则" in content
        assert "- 旧规则" not in content
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "docs/pm/decisions.md — 产品结论：新规则" in topics
        trace_file = initialized_project / trace["trace_file"]
        trace_payload = json.loads(trace_file.read_text(encoding="utf-8"))
        assert trace_payload["kind"] == "save_trace"
        assert trace_payload["task"] == "update outdated rule"
        assert trace_payload["request_ref"] == "save-update.json"
        assert trace_payload["update_supersedes"] == trace["update_supersedes"]

    def test_update_trace_uses_repo_relative_request_ref_by_default_cli(self, initialized_project, monkeypatch):
        request = {
            "version": "1",
            "task": "update outdated rule",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {
                        "doc_markdown": "## 产品结论\n\n- 新规则\n",
                        "supersedes": "旧规则的结论已经过时",
                    },
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = initialized_project / ".memory" / "session" / "save-update-default.json"
        write_json(request_file, request)
        monkeypatch.chdir(initialized_project)

        result, code = run_cmd("lib.memory_save", ["--file", ".memory/session/save-update-default.json"])

        assert code == 0
        trace = result["data"]["trace"]
        assert trace["trace_file"].startswith(".memory/session/save-trace/")
        trace_payload = json.loads((initialized_project / trace["trace_file"]).read_text(encoding="utf-8"))
        assert trace_payload["request_ref"] == ".memory/session/save-update-default.json"

    def test_update_trace_uses_repo_relative_request_ref_with_explicit_project_root(self, initialized_project, monkeypatch):
        request = {
            "version": "1",
            "task": "update outdated rule",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {
                        "doc_markdown": "## 产品结论\n\n- 新规则\n",
                        "supersedes": "旧规则的结论已经过时",
                    },
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = initialized_project / ".memory" / "session" / "save-update-explicit.json"
        write_json(request_file, request)
        monkeypatch.chdir(initialized_project)

        result, code = run_cmd(
            "lib.memory_save",
            ["--file", ".memory/session/save-update-explicit.json", "--project-root", str(initialized_project)],
        )

        assert code == 0
        trace = result["data"]["trace"]
        assert trace["trace_file"].startswith(".memory/session/save-trace/")
        trace_payload = json.loads((initialized_project / trace["trace_file"]).read_text(encoding="utf-8"))
        assert trace_payload["request_ref"] == ".memory/session/save-update-explicit.json"

    def test_write_save_trace_artifact_creates_distinct_files_under_concurrency(self, initialized_project):
        from datetime import datetime, timezone
        import lib.memory_save as memory_save

        request_file = initialized_project / ".memory" / "session" / "save-update.json"
        request_file.write_text("{}", encoding="utf-8")
        traces = [{
            "target": "docs/pm/decisions.md",
            "supersedes": "旧规则已经废弃",
            "previous_summary": "规则：旧规则",
            "new_summary": "产品结论：新规则",
        }]
        barrier = Barrier(8)

        class FixedDatetime:
            @staticmethod
            def now(tz=None):
                return datetime(2026, 4, 2, 9, 0, 0, 123456, tzinfo=timezone.utc)

        def write_trace(_: int) -> str | None:
            barrier.wait()
            return memory_save._write_save_trace_artifact(
                traces,
                task="update outdated rule",
                request_file=request_file,
                project_root=initialized_project,
            )

        with patch("lib.memory_save.datetime", FixedDatetime):
            with ThreadPoolExecutor(max_workers=8) as executor:
                trace_files = list(executor.map(write_trace, range(8)))

        assert len(trace_files) == 8
        assert len(set(trace_files)) == 8
        for trace_ref in trace_files:
            assert trace_ref is not None
            trace_file = initialized_project / trace_ref
            assert trace_file.exists()
            trace_payload = json.loads(trace_file.read_text(encoding="utf-8"))
            assert trace_payload["kind"] == "save_trace"
            assert trace_payload["request_ref"] == ".memory/session/save-update.json"
            assert trace_payload["update_supersedes"] == traces

    def test_update_trace_persistence_failure_does_not_fail_save(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "task": "update outdated rule",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {
                        "doc_markdown": "## 产品结论\n\n- 新规则\n",
                        "supersedes": "旧规则的结论已经过时",
                    },
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-update-warning.json"
        write_json(request_file, request)

        with patch("lib.memory_save._write_save_trace_artifact", side_effect=OSError("disk full")):
            result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])

        assert code == 0
        assert result["code"] == "SUCCESS"
        assert result["data"]["trace"]["trace_file"] is None
        assert result["data"]["trace"]["warning"] == "save trace not persisted: disk full"
        content = (initialized_project / ".memory" / "docs" / "pm" / "decisions.md").read_text(encoding="utf-8")
        assert "- 新规则" in content

    def test_update_trace_encoding_failure_does_not_fail_save(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "task": "update outdated rule",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {
                        "doc_markdown": "## 产品结论\n\n- 新规则\n",
                        "supersedes": "旧规则的结论已经过时",
                    },
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-update-encoding-warning.json"
        write_json(request_file, request)

        import lib.memory_save as memory_save

        original_atomic_write = memory_save.atomic_write

        def fail_trace_atomic_write(filepath, content):
            if "/save-trace/" in filepath.as_posix():
                raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogates not allowed")
            return original_atomic_write(filepath, content)

        with patch("lib.memory_save.atomic_write", side_effect=fail_trace_atomic_write):
            result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])

        assert code == 0
        assert result["code"] == "SUCCESS"
        assert result["data"]["trace"]["trace_file"] is None
        assert "save trace not persisted:" in result["data"]["trace"]["warning"]
        content = (initialized_project / ".memory" / "docs" / "pm" / "decisions.md").read_text(encoding="utf-8")
        assert "- 新规则" in content

    def test_legacy_shared_trace_file_is_ignored(self, initialized_project, tmp_path):
        legacy_file = initialized_project / ".memory" / "session" / "save-trace.jsonl"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_file.write_text('{"legacy": true}\n', encoding="utf-8")

        request = {
            "version": "1",
            "task": "update outdated rule",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {
                        "doc_markdown": "## 产品结论\n\n- 新规则\n",
                        "supersedes": "旧规则的结论已经过时",
                    },
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-update-legacy.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["data"]["trace"]["trace_file"].startswith(".memory/session/save-trace/")
        assert legacy_file.read_text(encoding="utf-8") == '{"legacy": true}\n'

    def test_working_set_excerpt_cannot_be_written_verbatim(self, initialized_project, tmp_path):
        excerpt = "## 决策\n\n- Working set raw conclusion\n"
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": "raw-working-set.md"},
                    "payload": {"doc_markdown": excerpt},
                    "evidence": {
                        "search_queries": ["Working set raw conclusion"],
                        "read_refs": ["docs/architect/decisions.md"],
                        "source_refs": [
                            {
                                "type": "working_set_item",
                                "path": ".memory/session/task-working-set.json",
                                "excerpt": excerpt,
                            }
                        ],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-working-set-verbatim.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "WORKING_SET_VERBATIM_FORBIDDEN"

    def test_working_set_session_excerpt_does_not_block_without_explicit_source_refs(self, initialized_project, tmp_path):
        excerpt = "Working set raw conclusion"
        write_working_set(initialized_project, excerpt=excerpt)
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": "raw-working-set.md"},
                    "payload": {"doc_markdown": f"## 决策\n\n- {excerpt}\n"},
                    "evidence": {
                        "search_queries": [excerpt],
                        "read_refs": ["docs/architect/decisions.md"],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-working-set-without-source-refs.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["code"] == "SUCCESS"
        saved = (initialized_project / ".memory" / "docs" / "architect" / "raw-working-set.md").read_text(encoding="utf-8")
        assert excerpt in saved

    def test_missing_session_json_source_ref_is_treated_as_working_set(self, initialized_project, tmp_path):
        excerpt = "## 决策\n\n- Working set raw conclusion\n"
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": "raw-working-set-via-session-ref.md"},
                    "payload": {"doc_markdown": excerpt},
                    "evidence": {
                        "search_queries": ["Working set raw conclusion"],
                        "read_refs": ["docs/architect/decisions.md"],
                        "source_refs": [
                            {
                                "type": "session_artifact",
                                "path": ".memory/session/missing-session.json",
                                "excerpt": excerpt,
                            }
                        ],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-missing-session-source-ref.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "WORKING_SET_VERBATIM_FORBIDDEN"

    def test_non_session_source_ref_with_working_set_in_filename_is_not_treated_as_working_set(self, initialized_project, tmp_path):
        excerpt = "## 决策\n\n- 合法的长期结论\n"
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": "valid-decision.md"},
                    "payload": {"doc_markdown": excerpt},
                    "index": {"topic": "valid-decision", "summary": "valid save"},
                    "evidence": {
                        "search_queries": ["合法的长期结论"],
                        "read_refs": ["docs/architect/decisions.md"],
                        "source_refs": [
                            {
                                "type": "note",
                                "path": "notes/working-set-retrospective.md",
                                "excerpt": excerpt,
                            }
                        ],
                    },
                }
            ],
        }
        request_file = tmp_path / "save-non-session-working-set-name.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 0
        assert result["code"] == "SUCCESS"
        content = (initialized_project / ".memory" / "docs" / "architect" / "valid-decision.md").read_text(encoding="utf-8")
        assert "合法的长期结论" in content

    def test_execute_save_uses_project_root_for_relative_request_ref(self, initialized_project, monkeypatch, tmp_path):
        request = {
            "version": "1",
            "task": "update outdated rule",
            "entries": [
                {
                    "id": "update-1",
                    "action": "update",
                    "reason": "old rule outdated",
                    "target": {"bucket": "pm", "file": "decisions.md"},
                    "payload": {
                        "doc_markdown": "## 产品结论\n\n- 新规则\n",
                        "supersedes": "旧规则的结论已经过时",
                    },
                    "evidence": {
                        "search_queries": ["旧规则"],
                        "read_refs": ["docs/pm/decisions.md", "docs/qa/strategy.md"],
                    },
                }
            ],
        }
        request_ref = Path(".memory/session/save-update-direct.json")
        write_json(initialized_project / request_ref, request)
        monkeypatch.chdir(tmp_path)

        import lib.memory_save as memory_save

        data, code, _, _ = memory_save.execute_save(request, initialized_project, request_file=request_ref)

        assert code == "SUCCESS"
        trace = data["trace"]
        trace_payload = json.loads((initialized_project / trace["trace_file"]).read_text(encoding="utf-8"))
        assert trace_payload["request_ref"] == ".memory/session/save-update-direct.json"

    def test_source_refs_must_be_list_when_provided(self, initialized_project, tmp_path):
        request = {
            "version": "1",
            "entries": [
                {
                    "id": "create-1",
                    "action": "create",
                    "reason": "stable architecture decision",
                    "target": {"bucket": "architect", "file": "bad-source-refs.md"},
                    "payload": {"doc_markdown": "## 决策\n\n- 合法内容\n"},
                    "evidence": {
                        "search_queries": ["合法内容"],
                        "read_refs": ["docs/architect/decisions.md"],
                        "source_refs": "not-a-list",
                    },
                }
            ],
        }
        request_file = tmp_path / "save-invalid-source-refs.json"
        write_json(request_file, request)

        result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "INVALID_SAVE_REQUEST"
