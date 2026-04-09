"""Tests for lib.recall_planner."""

import pytest

from lib.recall_planner import plan_recall


@pytest.fixture
def project(tmp_path):
    memory = tmp_path / ".memory"
    (memory / "docs" / "architect").mkdir(parents=True)
    (memory / "docs" / "pm").mkdir(parents=True)
    (memory / "docs" / "qa").mkdir(parents=True)
    (memory / "docs" / "dev").mkdir(parents=True)
    (memory / "catalog" / "modules").mkdir(parents=True)

    (memory / "BRIEF.md").write_text(
        "# Project Brief\n\n## architect\n\n### decisions.md\n## 决策\nUse recall-first\n\n## pm\n\n### decisions.md\n## 规则\nCheckout coupon rules\n\n## qa\n\n### strategy.md\n## 验证策略\n金额链路要回归\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n- checkout；当任务涉及结算、优惠券或金额链路时阅读。；入口: `packages/checkout/index.ts`\n\n## 知识文件\n### pm-decisions\n- docs/pm/decisions.md — Checkout coupon rules and business constraints\n### architect-decisions\n- docs/architect/decisions.md — recall-first architecture decisions\n### qa-strategy\n- docs/qa/strategy.md — checkout validation strategy\n",
        encoding="utf-8",
    )
    (memory / "docs" / "architect" / "decisions.md").write_text("## 决策\n\nUse recall-first", encoding="utf-8")
    (memory / "docs" / "pm" / "decisions.md").write_text("## 规则\n\nCheckout coupon rules", encoding="utf-8")
    (memory / "docs" / "qa" / "strategy.md").write_text("## 验证策略\n\n金额链路要回归", encoding="utf-8")
    (memory / "docs" / "dev" / "conventions.md").write_text("## 约定\n\n测试先行", encoding="utf-8")
    (memory / "catalog" / "modules" / "checkout.md").write_text(
        "# checkout\n\n## 何时阅读\n\n当任务涉及结算、优惠券或金额链路时阅读。\n\n## 推荐入口\n- `packages/checkout/index.ts`\n\n## 推荐阅读顺序\n- `packages/checkout/index.ts`\n\n## 隐含约束\n- 先确认业务规则\n\n## 主要风险\n- 金额错误\n\n## 验证重点\n- 回归价格计算\n",
        encoding="utf-8",
    )
    return tmp_path


def test_decide_task_uses_brief_topics_and_module_cards(project):
    result = plan_recall("重构 checkout 优惠券规则并验证风险", project)
    assert result["task_kind"] == "decide"
    assert result["search_first"] is False
    assert result["recall_level"] == "deep"
    assert result["recommended_docs"]
    assert result["recommended_modules"]
    assert any("BRIEF 命中" in item["reason"] or "topics 命中" in item["reason"] for item in result["recommended_docs"])
    assert any("module card 命中" in item["reason"] for item in result["recommended_modules"])
    assert result["why_these"]
    assert result["primary_evidence_gap"] is None


def test_validate_task_prefers_qa_and_can_be_deep(project):
    result = plan_recall("验证 checkout 金额回归测试", project)
    assert result["task_kind"] == "validate"
    assert result["recall_level"] == "deep"
    assert result["recommended_docs"][0]["bucket"] == "qa"


def test_search_first_when_no_match_does_not_force_light(project):
    result = plan_recall("完全陌生的术语 xyzabc 需要验证风险", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert result["ambiguity"] == "high"
    assert result["search_queries"]
    assert result["search_hits"] == {"docs": [], "modules": []}
    assert result["recall_level"] == "deep"
    assert result["primary_evidence_gap"] == result["evidence_gaps"][0]
    assert result["primary_evidence_gap"] == "当前无法仅凭 BRIEF、topics、module cards 与搜索结果稳定定位目标对象。"


def test_search_first_feeds_search_hits_back_into_final_sources(project):
    memory = project / ".memory" / "docs"
    (memory / "architect" / "decisions.md").write_text("## 决策\n\nshadowtoken77 architecture note", encoding="utf-8")
    (memory / "qa" / "strategy.md").write_text("## 验证策略\n\nshadowtoken77 regression focus", encoding="utf-8")

    result = plan_recall("shadowtoken77 需要验证风险", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert result["search_queries"]
    assert result["search_hits"]["docs"]
    assert len(result["recommended_docs"]) >= 2
    assert any("search 命中" in item["reason"] for item in result["recommended_docs"])
    assert result["ambiguity"] in {"medium", "low"}
    assert result["recall_level"] == "deep"


def test_search_first_when_only_weak_single_match_exists(project):
    memory = project / ".memory" / "docs"
    (memory / "architect" / "decisions.md").write_text("## 决策\n\nshadowtoken77 architecture note", encoding="utf-8")
    (memory / "qa" / "strategy.md").write_text("## 验证策略\n\nshadowtoken77 regression focus", encoding="utf-8")

    result = plan_recall("checkout 别名 shadowtoken77 的验证风险", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert result["search_queries"]
    assert result["search_hits"]["docs"]
    assert any("shadowtoken77" in item["reason"] for item in result["search_hits"]["docs"])
    assert result["recommended_modules"]
    assert result["ambiguity"] == "medium"
    assert result["recall_level"] == "deep"


def test_search_first_when_task_mentions_chinese_historical_term(project):
    memory = project / ".memory" / "docs"
    (memory / "architect" / "decisions.md").write_text("## 决策\n\n影子令牌 是 checkout 的历史术语", encoding="utf-8")
    (memory / "qa" / "strategy.md").write_text("## 验证策略\n\n影子令牌 金额回归", encoding="utf-8")

    result = plan_recall("checkout 历史术语 影子令牌 的验证风险", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert result["search_queries"]
    assert result["search_hits"]["docs"]
    assert any("影子令牌" in item["reason"] for item in result["search_hits"]["docs"])
    assert result["recommended_modules"]
    assert result["ambiguity"] == "medium"
    assert result["recall_level"] == "deep"


def test_locate_task_can_skip_when_target_is_unclear(project):
    result = plan_recall("定位陌生对象 xyzabc 在哪里", project)
    assert result["task_kind"] == "locate"
    assert result["search_first"] is True
    assert result["recall_level"] == "skip"


def test_more_specific_module_card_ranks_ahead_of_generic_card(tmp_path):
    memory = tmp_path / ".memory"
    (memory / "docs" / "pm").mkdir(parents=True)
    (memory / "docs" / "qa").mkdir(parents=True)
    (memory / "docs" / "architect").mkdir(parents=True)
    (memory / "catalog" / "modules").mkdir(parents=True)

    (memory / "BRIEF.md").write_text(
        "# Project Brief\n\n## pm\n\n### decisions.md\n## 规则\nCheckout coupon rules\n\n## qa\n\n### strategy.md\n## 验证策略\n金额链路要回归\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n- checkout；当任务涉及结算时阅读。；入口: `packages/checkout/index.ts`\n- pricing；当任务涉及价格时阅读。；入口: `packages/pricing/index.ts`\n\n## 知识文件\n### pm-decisions\n- docs/pm/decisions.md — Checkout coupon rules\n### qa-strategy\n- docs/qa/strategy.md — checkout validation strategy\n",
        encoding="utf-8",
    )
    (memory / "docs" / "pm" / "decisions.md").write_text("## 规则\n\nCheckout coupon rules", encoding="utf-8")
    (memory / "docs" / "qa" / "strategy.md").write_text("## 验证策略\n\n金额链路要回归", encoding="utf-8")
    (memory / "catalog" / "modules" / "checkout.md").write_text(
        "# checkout\n\n## 何时阅读\n\n当任务涉及结算、优惠券或金额链路时阅读。\n\n## 推荐入口\n- `packages/checkout/index.ts`\n\n## 隐含约束\n- 先确认优惠规则\n\n## 主要风险\n- 金额错误\n\n## 验证重点\n- 回归价格计算\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "modules" / "pricing.md").write_text(
        "# pricing\n\n## 何时阅读\n\n当任务涉及模块职责时阅读。\n\n## 推荐入口\n- `packages/pricing/index.ts`\n\n## 隐含约束\n- 先确认入口\n\n## 主要风险\n- 容易误读\n\n## 验证重点\n- 确认边界\n",
        encoding="utf-8",
    )

    result = plan_recall("重构 checkout 优惠券规则并验证风险", tmp_path)
    assert result["recommended_modules"][0]["name"] == "checkout"


def test_source_oriented_fix_task_skips_durable_recall_when_only_code_identifier_matches(project):
    memory = project / ".memory"
    (memory / "BRIEF.md").write_text(
        "# Project Brief\n\n## dev\n\n### conventions.md\n## 命名约定\n文件名：`snake_case`（如 `catalog_repair.py`、`memory_search.py`）\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n\n## 知识文件\n### conventions\n- docs/dev/conventions.md — 命名约定：文件名：`snake_case`（如 `catalog_repair.py`、`memory_search.py`）\n",
        encoding="utf-8",
    )
    (memory / "docs" / "dev" / "conventions.md").write_text(
        "## 命名约定\n\n文件名：`snake_case`（如 `catalog_repair.py`、`memory_search.py`）\n",
        encoding="utf-8",
    )

    result = plan_recall("修复 catalog_repair 摘要误刷新", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert result["search_hits"]["docs"]
    assert any(item["bucket"] == "dev" and item["file"] == "conventions.md" for item in result["search_hits"]["docs"])
    assert result["recommended_docs"] == []
    assert result["recall_level"] == "skip"
    assert result["primary_evidence_gap"] == "当前任务主要依赖源码实现上下文，durable docs 无法稳定回答。"


def test_source_oriented_understand_task_does_not_run_durable_search(project):
    result = plan_recall("理解 recall_planner search-first 命中策略", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert result["search_hits"] == {"docs": [], "modules": []}
    assert result["recommended_docs"] == []
    assert result["recommended_modules"] == []
    assert result["recall_level"] == "skip"
    assert result["primary_evidence_gap"] == "当前任务主要依赖源码实现上下文，durable docs 无法稳定回答。"



def test_source_oriented_task_keeps_search_hit_docs_before_final_skip(project):
    docs_root = project / ".memory" / "docs"
    catalog_root = project / ".memory" / "catalog"
    (docs_root / "architect" / "decisions.md").write_text(
        "## 决策\n\n系统术语中将 foo_bar 记作 traceability-token。\n",
        encoding="utf-8",
    )
    (catalog_root / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n\n## 知识文件\n",
        encoding="utf-8",
    )

    result = plan_recall("理解 foo_bar traceability-token", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert result["search_hits"]["docs"]
    assert any(item["bucket"] == "architect" and item["file"] == "decisions.md" for item in result["recommended_docs"])
    assert result["recall_level"] == "light"
    assert result["primary_evidence_gap"] == "尚未找到明确的 module card 命中。"



def test_mixed_understand_task_keeps_durable_matches_when_semantic_context_exists(project):
    result = plan_recall("理解 recall_planner 的 recall-first 架构决策", project)
    assert result["search_first"] is True
    assert result["search_stage_completed"] is True
    assert any(item["bucket"] == "architect" and item["file"] == "decisions.md" for item in result["recommended_docs"])
    assert result["recall_level"] == "light"
    assert result["primary_evidence_gap"] == "尚未找到明确的 module card 命中。"


def test_validate_task_keeps_durable_doc_matches_for_save_traceability(project):
    memory = project / ".memory"
    (memory / "BRIEF.md").write_text(
        "# Project Brief\n\n## architect\n\n### decisions.md\n## Update supersedes traceability\n`update` 的 supersedes 追溯信息属于 session artifact。\n\n## pm\n\n### decisions.md\n## Durable save 口径\n`update` 只用于明确替换已过时的长期结论。\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n\n## 知识文件\n### architect-decisions\n- docs/architect/decisions.md — Update supersedes traceability：`update` 的 supersedes 追溯信息属于 session artifact。\n### pm-decisions\n- docs/pm/decisions.md — Durable save 口径：`update` 只用于明确替换已过时的长期结论。\n",
        encoding="utf-8",
    )
    (memory / "docs" / "architect" / "decisions.md").write_text(
        "## Update supersedes traceability\n\n- `update` 的 supersedes 追溯信息属于 session artifact。\n",
        encoding="utf-8",
    )
    (memory / "docs" / "pm" / "decisions.md").write_text(
        "## Durable save 口径\n\n- `update` 只用于明确替换已过时的长期结论。\n",
        encoding="utf-8",
    )

    result = plan_recall("验证 save update supersedes traceability", project)
    assert result["recall_level"] == "deep"
    assert result["recommended_docs"][0]["bucket"] == "architect"
    assert result["recommended_docs"][0]["file"] == "decisions.md"
    assert any(item["bucket"] == "pm" and item["file"] == "decisions.md" for item in result["recommended_docs"])


def test_understand_task_keeps_durable_kebab_case_term(project):
    memory = project / ".memory"
    (memory / "BRIEF.md").write_text(
        "# Project Brief\n\n## architect\n\n### decisions.md\n## 决策\nrecall-first 是核心架构原则\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n\n## 知识文件\n### architect-decisions\n- docs/architect/decisions.md — Recall-first 架构决策：recall-first 是核心架构原则。\n",
        encoding="utf-8",
    )
    (memory / "docs" / "architect" / "decisions.md").write_text(
        "## 决策\n\n- recall-first 是核心架构原则\n",
        encoding="utf-8",
    )

    result = plan_recall("理解 recall-first", project)
    assert result["search_first"] is False
    assert result["recommended_docs"]
    assert result["recommended_docs"][0]["bucket"] == "architect"
    assert result["recall_level"] == "light"
    assert result["primary_evidence_gap"] == "尚未找到明确的 module card 命中。"


def test_alias_hint_keeps_durable_match_for_code_like_historical_term(project):
    memory = project / ".memory"
    (memory / "BRIEF.md").write_text("# Project Brief\n", encoding="utf-8")
    (memory / "catalog" / "topics.md").write_text(
        "# Topics\n\n## 代码模块\n\n## 知识文件\n### architect-decisions\n- docs/architect/decisions.md — save-trace 是旧 trace artifact 术语。\n",
        encoding="utf-8",
    )
    (memory / "docs" / "architect" / "decisions.md").write_text(
        "## 历史术语\n\n- save-trace 是旧 trace artifact 术语\n",
        encoding="utf-8",
    )

    result = plan_recall("定位 save-trace 历史术语 在哪里", project)
    assert result["search_first"] is False
    assert result["search_stage_completed"] is False
    assert any(item["bucket"] == "architect" and item["file"] == "decisions.md" for item in result["recommended_docs"])
    assert result["recall_level"] == "light"
