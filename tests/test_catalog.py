"""Tests for catalog.read, catalog.update, catalog.repair"""

import json
import pytest
from io import StringIO
import sys

from lib import paths
from lib.scan_modules import MODULE_CARD_GENERATOR_VERSION


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


class TestCatalogRead:
    def test_read_topics(self, initialized_project):
        result, code = run_cmd("lib.catalog_read", ["topics", "--project-root", str(initialized_project)])
        assert code == 0
        assert "代码模块" in result["data"]["content"]

    def test_catalog_read_sanitizes_module_name(self, initialized_project):
        module_file = initialized_project / ".memory" / "catalog" / "modules" / "packages-web.md"
        module_file.write_text("# packages/web\n", encoding="utf-8")
        result, code = run_cmd("lib.catalog_read", ["packages/web", "--project-root", str(initialized_project)])
        assert code == 0
        assert "packages/web" in result["data"]["content"]


class TestCatalogUpdate:
    def test_catalog_update_is_deprecated(self, initialized_project):
        modules_json = json.dumps({
            "modules": [{"name": "core", "files": []}]
        })
        json_file = initialized_project / "modules.json"
        json_file.write_text(modules_json, encoding="utf-8")

        result, code = run_cmd("lib.catalog_update", ["--file", str(json_file), "--project-root", str(initialized_project)])
        assert code == 1
        assert result["code"] == "LEGACY_COMMAND_DEPRECATED"
        assert result["details"]["command"] == "catalog-update"
        assert result["details"]["replacement_commands"]


class TestCatalogRepair:
    def test_detects_missing_registration(self, initialized_project):
        result, code = run_cmd("lib.catalog_repair", ["--project-root", str(initialized_project)])
        assert code == 0
        missing = [a for a in result["data"]["ai_actions"] if a["type"] == "missing_registration"]
        assert len(missing) > 0

    def test_refreshes_stale_registered_summary(self, initialized_project):
        pm_doc = initialized_project / ".memory" / "docs" / "pm" / "decisions.md"
        pm_doc.write_text(
            "## Checkout 优惠券规则\n\n- 先计算折扣再做上限校验\n\n## 风险\n\n- 金额链路容易失真\n",
            encoding="utf-8",
        )
        topics = initialized_project / ".memory" / "catalog" / "topics.md"
        topics.write_text(
            "# Topics\n\n## 代码模块\n\n## 知识文件\n### pm-decisions\n- docs/pm/decisions.md — 旧摘要\n",
            encoding="utf-8",
        )

        result, code = run_cmd("lib.catalog_repair", ["--project-root", str(initialized_project)])
        assert code == 0
        refreshed = [item for item in result["data"]["fixed"] if item["type"] == "stale_summary_refreshed"]
        assert len(refreshed) == 1
        assert refreshed[0]["file_ref"] == "docs/pm/decisions.md"

        updated_topics = topics.read_text(encoding="utf-8")
        assert "docs/pm/decisions.md — Checkout 优惠券规则：先计算折扣再做上限校验；风险：金额链路容易失真" in updated_topics

    def test_keeps_valid_action_aware_summary(self, initialized_project):
        pm_doc = initialized_project / ".memory" / "docs" / "pm" / "decisions.md"
        pm_doc.write_text("## 规则\n\n- 旧规则\n\n## Checkout 优惠券规则\n\n- 先计算折扣再做上限校验\n", encoding="utf-8")
        topics = initialized_project / ".memory" / "catalog" / "topics.md"
        topics.write_text(
            "# Topics\n\n## 代码模块\n\n## 知识文件\n### pm-decisions\n- docs/pm/decisions.md — Checkout 优惠券规则：先计算折扣再做上限校验\n",
            encoding="utf-8",
        )

        result, code = run_cmd("lib.catalog_repair", ["--project-root", str(initialized_project)])
        assert code == 0
        refreshed = [item for item in result["data"]["fixed"] if item["type"] == "stale_summary_refreshed"]
        assert refreshed == []

        updated_topics = topics.read_text(encoding="utf-8")
        assert "docs/pm/decisions.md — Checkout 优惠券规则：先计算折扣再做上限校验" in updated_topics

    def test_refreshes_title_only_summary_to_richer_canonical_summary(self, initialized_project):
        pm_doc = initialized_project / ".memory" / "docs" / "pm" / "decisions.md"
        pm_doc.write_text(
            "# 缓存策略\n\n## 决策\n\n- 使用本地文件缓存\n\n## 风险\n\n- 金额链路容易失真\n",
            encoding="utf-8",
        )
        topics = initialized_project / ".memory" / "catalog" / "topics.md"
        topics.write_text(
            "# Topics\n\n## 代码模块\n\n## 知识文件\n### pm-decisions\n- docs/pm/decisions.md — 缓存策略\n",
            encoding="utf-8",
        )

        result, code = run_cmd("lib.catalog_repair", ["--project-root", str(initialized_project)])
        assert code == 0
        refreshed = [item for item in result["data"]["fixed"] if item["type"] == "stale_summary_refreshed"]
        assert len(refreshed) == 1
        assert refreshed[0]["old_summary"] == "缓存策略"
        assert refreshed[0]["new_summary"] == "决策：使用本地文件缓存；风险：金额链路容易失真"

        updated_topics = topics.read_text(encoding="utf-8")
        assert "docs/pm/decisions.md — 决策：使用本地文件缓存；风险：金额链路容易失真" in updated_topics
