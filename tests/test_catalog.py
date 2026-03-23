"""Tests for catalog.read, catalog.update, catalog.repair"""

import json
import pytest
from pathlib import Path
from io import StringIO
import sys

from lib import paths
from lib.utils import atomic_write


@pytest.fixture
def initialized_project(tmp_path):
    root = tmp_path / ".memory"
    for bucket, files in paths.BASE_FILES.items():
        for f in files:
            fp = root / "docs" / bucket / f
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("", encoding="utf-8")
    catalog = root / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "modules").mkdir(exist_ok=True)
    (catalog / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n\n## 知识文件\n", encoding="utf-8"
    )
    return tmp_path


def run_cmd(module_name, args, stdin_content=None):
    import importlib
    old_stdout = sys.stdout
    old_stdin = sys.stdin
    sys.stdout = StringIO()
    if stdin_content is not None:
        sys.stdin = StringIO(stdin_content)
    try:
        mod = importlib.import_module(module_name)
        with pytest.raises(SystemExit) as exc_info:
            mod.run(args)
        return json.loads(sys.stdout.getvalue()), exc_info.value.code
    finally:
        sys.stdout = old_stdout
        sys.stdin = old_stdin


class TestCatalogRead:
    def test_read_topics(self, initialized_project):
        result, code = run_cmd("lib.catalog_read", ["topics", "--project-root", str(initialized_project)])
        assert code == 0
        assert "代码模块" in result["data"]["content"]

    def test_read_nonexistent_module(self, initialized_project):
        result, code = run_cmd("lib.catalog_read", ["nope", "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "CATALOG_NOT_FOUND"


class TestCatalogUpdate:
    def test_creates_module_files(self, initialized_project):
        modules_json = json.dumps({
            "modules": [
                {
                    "name": "core",
                    "summary": "核心模块",
                    "files": [
                        {"path": "lib/cli.py", "description": "CLI 入口"},
                        {"path": "lib/envelope.py", "description": "JSON envelope"},
                    ]
                }
            ]
        })
        # Write JSON to a temp file
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        assert "core" in result["data"]["modules_written"]
        # Check module file exists
        module_file = initialized_project / ".memory" / "catalog" / "modules" / "core.md"
        assert module_file.exists()
        content = module_file.read_text(encoding="utf-8")
        assert "lib/cli.py" in content

    def test_deletes_old_modules(self, initialized_project):
        # Create an old module file
        old = initialized_project / ".memory" / "catalog" / "modules" / "old.md"
        old.write_text("# old\n", encoding="utf-8")
        modules_json = json.dumps({"modules": [{"name": "new", "summary": "新模块", "files": []}]})
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        assert "old.md" in result["data"]["modules_deleted"]
        assert not old.exists()

    def test_new_format_with_all_sections(self, initialized_project):
        """Module with all optional fields should produce rich markdown."""
        modules_json = json.dumps({
            "modules": [{
                "name": "auth",
                "summary": "认证模块",
                "purpose": "处理用户登录、注册和会话管理。基于 JWT 实现无状态认证。",
                "key_abstractions": [
                    "AuthService — 认证核心逻辑",
                    "JwtHelper — Token 生成和验证",
                ],
                "internal_deps": [
                    "database — 用户数据存储",
                    "config — JWT 密钥配置",
                ],
                "dir_tree": "handlers/ (3 files)\nmodels/ (2 files)",
                "files": [
                    {"path": "auth/service.py", "description": "认证服务入口"},
                    {"path": "auth/jwt.py", "description": "JWT 工具"},
                ],
            }]
        })
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        module_file = initialized_project / ".memory" / "catalog" / "modules" / "auth.md"
        content = module_file.read_text(encoding="utf-8")
        assert "## 职责" in content
        assert "处理用户登录" in content
        assert "## 关键抽象" in content
        assert "AuthService" in content
        assert "## 内部依赖" in content
        assert "database" in content
        assert "## 目录结构" in content
        assert "handlers/" in content
        assert "## 代表文件" in content
        assert "`auth/service.py`" in content

    def test_new_format_graceful_degrade(self, initialized_project):
        """Module missing optional fields should still produce valid markdown."""
        modules_json = json.dumps({
            "modules": [{
                "name": "simple",
                "summary": "简单模块",
                "files": [{"path": "simple/main.py", "description": ""}],
            }]
        })
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        module_file = initialized_project / ".memory" / "catalog" / "modules" / "simple.md"
        content = module_file.read_text(encoding="utf-8")
        assert "# simple" in content
        assert "> 简单模块" in content
        assert "## 代表文件" in content
        # Optional sections should NOT appear
        assert "## 职责" not in content
        assert "## 关键抽象" not in content
        assert "## 内部依赖" not in content
        assert "## 目录结构" not in content


class TestCatalogRepair:
    def test_detects_dead_links(self, initialized_project):
        # Add a dead link to topics.md
        topics = initialized_project / ".memory" / "catalog" / "topics.md"
        topics.write_text(
            "# Topics\n\n## 知识文件\n### ghost\n- docs/pm/ghost.md — 不存在的文件\n",
            encoding="utf-8"
        )
        result, code = run_cmd("lib.catalog_repair", ["--project-root", str(initialized_project)])
        assert code == 0
        assert any(f["type"] == "dead_link_removed" for f in result["data"]["fixed"])

    def test_detects_legacy_docs_refs(self, initialized_project):
        topics = initialized_project / ".memory" / "catalog" / "topics.md"
        topics.write_text(
            "# Topics\n\n## 知识文件\n### legacy\n- pm/decisions.md — 旧路径\n",
            encoding="utf-8"
        )
        result, code = run_cmd("lib.catalog_repair", ["--project-root", str(initialized_project)])
        assert code == 0
        legacy = [a for a in result["data"]["ai_actions"] if a["type"] == "legacy_docs_ref"]
        assert len(legacy) == 1
        assert legacy[0]["suggested"] == "docs/pm/decisions.md"

    def test_detects_missing_registration(self, initialized_project):
        result, code = run_cmd("lib.catalog_repair", ["--project-root", str(initialized_project)])
        assert code == 0
        # Base files are not registered, should be in ai_actions
        missing = [a for a in result["data"]["ai_actions"] if a["type"] == "missing_registration"]
        assert len(missing) > 0


class TestCatalogUpdateValidation:
    def test_sanitizes_module_name(self, initialized_project):
        modules_json = json.dumps({
            "modules": [{"name": "My Module", "summary": "test", "files": []}]
        })
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        assert "my-module" in result["data"]["modules_written"]
        module_file = initialized_project / ".memory" / "catalog" / "modules" / "my-module.md"
        assert module_file.exists()

    def test_skips_invalid_module_missing_name(self, initialized_project):
        modules_json = json.dumps({
            "modules": [
                {"name": "", "summary": "empty name", "files": []},
                {"name": "valid", "summary": "ok", "files": []},
            ]
        })
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        assert "valid" in result["data"]["modules_written"]
        assert len(result["data"]["modules_skipped"]) == 1
        assert result["data"]["modules_skipped"][0]["reason"] == "missing or empty 'name'"

    def test_skips_invalid_files_field(self, initialized_project):
        modules_json = json.dumps({
            "modules": [{"name": "bad", "summary": "x", "files": "not-a-list"}]
        })
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        assert len(result["data"]["modules_skipped"]) == 1
        skipped_actions = [a for a in result["ai_actions"] if a["type"] == "invalid_module_skipped"]
        assert len(skipped_actions) == 1

    def test_mixed_valid_invalid_modules(self, initialized_project):
        modules_json = json.dumps({
            "modules": [
                {"name": "good", "summary": "works", "files": []},
                {"summary": "no name field", "files": []},
                {"name": "also-good", "summary": "fine", "files": [{"path": "a.py", "description": ""}]},
            ]
        })
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")
        result, code = run_cmd("lib.catalog_update",
                               ["--file", str(json_file),
                                "--project-root", str(initialized_project)])
        assert code == 0
        written = result["data"]["modules_written"]
        assert "good" in written
        assert "also-good" in written
        assert len(result["data"]["modules_skipped"]) == 1
