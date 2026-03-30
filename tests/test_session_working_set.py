"""Tests for lib.session_working_set."""

import pytest

from lib.session_working_set import build_working_set


@pytest.fixture
def project(tmp_path):
    memory = tmp_path / ".memory"
    (memory / "docs" / "pm").mkdir(parents=True)
    (memory / "docs" / "architect").mkdir(parents=True)
    (memory / "catalog" / "modules").mkdir(parents=True)
    (memory / "docs" / "pm" / "decisions.md").write_text(
        "## 规则\n\n优惠券规则会影响后续动作。\n\n## 范围\n\n只适用于 checkout。",
        encoding="utf-8",
    )
    (memory / "docs" / "architect" / "decisions.md").write_text(
        "## 决策\n\nUse recall-first.\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "modules" / "checkout.md").write_text(
        "# checkout\n\n## 何时阅读\n\n当任务涉及结算时阅读。\n\n## 推荐入口\n- `packages/checkout/index.ts`\n- `packages/checkout/rules.ts`\n\n## 隐含约束\n- 先确认优惠规则。\n- 不要跳过上限校验。\n\n## 主要风险\n- 金额错误。\n\n## 验证重点\n- 回归价格计算。\n",
        encoding="utf-8",
    )
    return tmp_path


def test_build_working_set_keeps_sources_and_structured_module_context(project):
    plan = {
        "task": "重构 checkout 优惠券规则",
        "recall_level": "deep",
        "recommended_docs": [
            {"bucket": "pm", "file": "decisions.md", "reason": "业务规则", "priority": 1},
            {"bucket": "architect", "file": "decisions.md", "reason": "架构决策", "priority": 2},
        ],
        "recommended_modules": [
            {"name": "checkout", "reason": "主模块", "priority": 1, "entry_points": ["packages/checkout/index.ts"]},
            {"name": "checkout", "reason": "金额链路风险", "priority": 2, "entry_points": ["packages/checkout/rules.ts"]},
        ],
        "evidence_gaps": ["尚未确认 promotion 是否参与", "尚未确认 promotion 是否参与"],
        "why_these": ["任务涉及业务规则与主模块入口"],
    }
    result = build_working_set(plan, project, "plan.json")
    assert result["items"]
    assert all(item["sources"] for item in result["items"])
    assert result["evidence_gaps"] == ["尚未确认 promotion 是否参与"]

    navigation = next(item for item in result["items"] if item["kind"] == "navigation")
    assert navigation["title"] == "checkout"
    assert any(bullet.startswith("约束: ") for bullet in navigation["bullets"])
    assert any(bullet.startswith("风险: ") for bullet in navigation["bullets"])
    assert any(bullet.startswith("验证: ") for bullet in navigation["bullets"])
    assert "主模块" in navigation["selected_because"]
    assert "金额链路风险" in navigation["selected_because"]

    module_reads = [item for item in result["priority_reads"] if item["type"] == "module"]
    assert len(module_reads) == 1
    assert result["durable_candidates"]


def test_working_set_applies_limits_and_dedupes(tmp_path):
    memory = tmp_path / ".memory"
    (memory / "docs" / "pm").mkdir(parents=True)
    (memory / "catalog" / "modules").mkdir(parents=True)

    recommended_docs = []
    for idx in range(1, 6):
        filename = f"rule-{idx}.md"
        (memory / "docs" / "pm" / filename).write_text(
            "## 规则\n\n- 规则一\n- 规则二\n- 规则三\n- 规则四\n- 规则五\n",
            encoding="utf-8",
        )
        recommended_docs.append({"bucket": "pm", "file": filename, "reason": f"规则 {idx}", "priority": idx})

    recommended_modules = []
    for idx in range(1, 5):
        name = f"module-{idx}"
        (memory / "catalog" / "modules" / f"{name}.md").write_text(
            f"# {name}\n\n## 何时阅读\n\n当任务涉及 {name} 时阅读。\n\n## 推荐入口\n- `{name}/index.ts`\n\n## 隐含约束\n- 约束 {idx}\n\n## 主要风险\n- 风险 {idx}\n\n## 验证重点\n- 验证 {idx}\n",
            encoding="utf-8",
        )
        recommended_modules.append({"name": name, "reason": f"模块 {idx}", "priority": idx, "entry_points": [f"{name}/index.ts"]})

    plan = {
        "task": "跨模块 recall",
        "recall_level": "deep",
        "recommended_docs": recommended_docs,
        "recommended_modules": recommended_modules,
        "evidence_gaps": ["gap-1", "gap-1", "gap-2", "gap-3", "gap-4", "gap-5", "gap-6"],
        "why_these": ["需要读取多份规则", "需要读取多个模块", "第三条不应进入 summary"],
    }

    result = build_working_set(plan, tmp_path, "plan.json")
    assert len(result["items"]) <= 6
    assert all(len(item["bullets"]) <= 4 for item in result["items"])
    assert sum(len(item["bullets"]) for item in result["items"]) <= 16
    assert len(result["priority_reads"]) <= 4
    assert result["evidence_gaps"] == ["gap-1", "gap-2", "gap-3", "gap-4", "gap-5"]
    assert len(result["durable_candidates"]) <= 3
    assert result["summary"] == "需要读取多份规则 需要读取多个模块"


def test_working_set_requires_deep(project):
    plan = {"task": "foo", "recall_level": "light"}
    with pytest.raises(SystemExit):
        build_working_set(plan, project, "plan.json")
