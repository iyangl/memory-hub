"""Tests for memory.save"""

import json
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
        assert result["data"]["rebuild"]["brief"] is False

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

    def test_create_requires_index_and_writes_doc(self, initialized_project, tmp_path):
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
        assert result["data"]["rebuild"]["brief"] is True

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
        content = (initialized_project / ".memory" / "docs" / "pm" / "decisions.md").read_text(encoding="utf-8")
        assert "- 新规则" in content
        assert "- 旧规则" not in content
        topics = (initialized_project / ".memory" / "catalog" / "topics.md").read_text(encoding="utf-8")
        assert "docs/pm/decisions.md — 产品结论：新规则" in topics

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
                    "index": {"topic": "working-set", "summary": "bad save"},
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

    def test_working_set_session_excerpt_cannot_be_written_verbatim_without_source_refs(self, initialized_project, tmp_path):
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
                    "index": {"topic": "working-set", "summary": "bad save"},
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
        assert code == 1
        assert result["code"] == "WORKING_SET_VERBATIM_FORBIDDEN"

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
                    "index": {"topic": "working-set", "summary": "bad save"},
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
