"""End-to-end memory flow tests for recall-first chain."""

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



def test_recall_first_flow(tmp_path):
    result, code = run_cmd("lib.memory_init", ["--project-root", str(tmp_path)])
    assert code == 0

    docs = tmp_path / ".memory" / "docs"
    (docs / "architect" / "decisions.md").write_text("## 决策\n\nUse recall-first", encoding="utf-8")
    (docs / "pm" / "decisions.md").write_text("## 规则\n\nCheckout coupon rules", encoding="utf-8")
    (docs / "qa" / "strategy.md").write_text("## 验证策略\n\n金额链路回归", encoding="utf-8")

    modules_json = {
        "modules": [{
            "name": "checkout",
            "summary": "结算模块",
            "read_when": "当任务涉及结算时阅读。",
            "entry_points": ["packages/checkout/index.ts"],
            "read_order": ["packages/checkout/index.ts"],
            "implicit_constraints": ["先确认优惠规则"],
            "known_risks": ["金额错误"],
            "verification_focus": ["回归价格计算"],
            "related_memory": ["docs/pm/decisions.md"],
            "files": [{"path": "packages/checkout/index.ts", "description": "入口"}],
        }]
    }
    modules_file = tmp_path / "modules.json"
    modules_file.write_text(json.dumps(modules_json, ensure_ascii=False), encoding="utf-8")

    result, code = run_cmd("lib.catalog_update", ["--file", str(modules_file), "--project-root", str(tmp_path)])
    assert code == 0

    result, code = run_cmd("lib.brief", ["--project-root", str(tmp_path)])
    assert code == 0

    result, code = run_cmd("lib.recall_planner", ["--task", "重构 checkout 优惠券规则并验证风险", "--project-root", str(tmp_path), "--out", str(tmp_path / "plan.json")])
    assert code == 0
    assert result["data"]["recommended_modules"]
    assert result["data"]["recommended_docs"]

    plan_path = tmp_path / "plan.json"
    planned = json.loads(plan_path.read_text(encoding="utf-8"))
    assert planned["recall_level"] == "deep"

    working_set_path = tmp_path / "working-set.json"
    result, code = run_cmd("lib.session_working_set", ["--plan-file", str(plan_path), "--project-root", str(tmp_path), "--out", str(working_set_path)])
    assert code == 0
    assert result["data"]["items"]
    assert result["data"]["output_file"] == str(working_set_path)

    navigation = next(item for item in result["data"]["items"] if item["kind"] == "navigation")
    assert any(bullet.startswith("约束: ") for bullet in navigation["bullets"])
    assert any(bullet.startswith("风险: ") for bullet in navigation["bullets"])
    assert any(bullet.startswith("验证: ") for bullet in navigation["bullets"])
    assert result["data"]["priority_reads"]

    contract_path = tmp_path / "execution-contract.json"
    result, code = run_cmd("lib.execution_contract", ["--working-set-file", str(working_set_path), "--project-root", str(tmp_path), "--out", str(contract_path)])
    assert code == 0
    assert result["data"]["output_file"] == str(contract_path)
    assert result["data"]["source_working_set"] == str(working_set_path)
    assert "known_context" in result["data"]
    assert "allowed_sources" in result["data"]



def test_search_first_flow_searches_then_builds_final_plan(tmp_path):
    result, code = run_cmd("lib.memory_init", ["--project-root", str(tmp_path)])
    assert code == 0

    docs = tmp_path / ".memory" / "docs"
    (docs / "architect" / "decisions.md").write_text("## 决策\n\nUse recall-first\n\n## 附录\n\nshadowtoken77 architecture note", encoding="utf-8")
    (docs / "pm" / "decisions.md").write_text("## 规则\n\nCheckout coupon rules", encoding="utf-8")
    (docs / "qa" / "strategy.md").write_text("## 验证策略\n\n金额链路回归\n\n## 附录\n\nshadowtoken77 regression focus", encoding="utf-8")

    modules_json = {
        "modules": [{
            "name": "checkout",
            "summary": "结算模块",
            "read_when": "当任务涉及结算时阅读。",
            "entry_points": ["packages/checkout/index.ts"],
            "read_order": ["packages/checkout/index.ts"],
            "implicit_constraints": ["先确认优惠规则"],
            "known_risks": ["金额错误"],
            "verification_focus": ["回归价格计算"],
            "related_memory": ["docs/pm/decisions.md"],
            "files": [{"path": "packages/checkout/index.ts", "description": "入口"}],
        }]
    }
    modules_file = tmp_path / "modules.json"
    modules_file.write_text(json.dumps(modules_json, ensure_ascii=False), encoding="utf-8")

    result, code = run_cmd("lib.catalog_update", ["--file", str(modules_file), "--project-root", str(tmp_path)])
    assert code == 0
    result, code = run_cmd("lib.brief", ["--project-root", str(tmp_path)])
    assert code == 0

    result, code = run_cmd("lib.recall_planner", ["--task", "shadowtoken77 需要验证风险", "--project-root", str(tmp_path), "--out", str(tmp_path / "search-plan.json")])
    assert code == 0
    planned = result["data"]
    assert planned["search_first"] is True
    assert planned["search_stage_completed"] is True
    assert planned["search_hits"]["docs"]
    assert len(planned["recommended_docs"]) >= 2
    assert any("search 命中" in item["reason"] for item in planned["recommended_docs"])
    assert planned["recall_level"] == "deep"

    plan_path = tmp_path / "search-plan.json"
    result, code = run_cmd("lib.session_working_set", ["--plan-file", str(plan_path), "--project-root", str(tmp_path)])
    assert code == 0
    assert result["data"]["items"]
    assert result["data"]["priority_reads"]



def test_recall_first_flow_with_real_scan_modules_chain(tmp_path):
    result, code = run_cmd("lib.memory_init", ["--project-root", str(tmp_path)])
    assert code == 0

    docs = tmp_path / ".memory" / "docs"
    (docs / "architect" / "decisions.md").write_text("## 决策\n\nUse recall-first", encoding="utf-8")
    (docs / "pm" / "decisions.md").write_text("## 规则\n\nCheckout coupon rules", encoding="utf-8")
    (docs / "qa" / "strategy.md").write_text("## 验证策略\n\n金额链路回归", encoding="utf-8")

    (tmp_path / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    checkout_dir = tmp_path / "packages" / "checkout"
    checkout_dir.mkdir(parents=True)
    (checkout_dir / "index.ts").write_text("export const checkout = true\n", encoding="utf-8")
    (checkout_dir / "rules.ts").write_text("export const couponRules = []\n", encoding="utf-8")

    scan_file = tmp_path / "scan.json"
    result, code = run_cmd("lib.scan_modules", ["--project-root", str(tmp_path), "--out", str(scan_file)])
    assert code == 0
    assert result["data"]["output_file"] == str(scan_file)

    result, code = run_cmd("lib.catalog_update", ["--file", str(scan_file), "--project-root", str(tmp_path)])
    assert code == 0
    assert "packages-checkout" in result["data"]["modules_written"]

    result, code = run_cmd("lib.brief", ["--project-root", str(tmp_path)])
    assert code == 0

    result, code = run_cmd("lib.recall_planner", ["--task", "重构 checkout 优惠券规则并验证风险", "--project-root", str(tmp_path), "--out", str(tmp_path / "scan-plan.json")])
    assert code == 0
    planned = result["data"]
    assert planned["recommended_docs"]
    assert any(item["name"] == "packages/checkout" for item in planned["recommended_modules"])

    plan_path = tmp_path / "scan-plan.json"
    result, code = run_cmd("lib.session_working_set", ["--plan-file", str(plan_path), "--project-root", str(tmp_path)])
    assert code == 0
    navigation = next(item for item in result["data"]["items"] if item["kind"] == "navigation")
    assert navigation["title"] == "packages/checkout"
    assert any(bullet.startswith("约束: ") for bullet in navigation["bullets"])
    assert any(bullet.startswith("风险: ") for bullet in navigation["bullets"])
    assert any(bullet.startswith("验证: ") for bullet in navigation["bullets"])



def test_search_first_flow_when_initial_hits_are_still_ambiguous(tmp_path):
    result, code = run_cmd("lib.memory_init", ["--project-root", str(tmp_path)])
    assert code == 0

    docs = tmp_path / ".memory" / "docs"
    (docs / "architect" / "decisions.md").write_text("## 决策\n\nUse recall-first\n\n## 附录\n\nshadowtoken77 architecture note", encoding="utf-8")
    (docs / "pm" / "decisions.md").write_text("## 规则\n\nCheckout coupon rules", encoding="utf-8")
    (docs / "qa" / "strategy.md").write_text("## 验证策略\n\n金额链路回归\n\n## 附录\n\nshadowtoken77 regression focus", encoding="utf-8")

    modules_json = {
        "modules": [{
            "name": "checkout",
            "summary": "结算模块",
            "read_when": "当任务涉及结算时阅读。",
            "entry_points": ["packages/checkout/index.ts"],
            "read_order": ["packages/checkout/index.ts"],
            "implicit_constraints": ["先确认优惠规则"],
            "known_risks": ["金额错误"],
            "verification_focus": ["回归价格计算"],
            "related_memory": ["docs/pm/decisions.md"],
            "files": [{"path": "packages/checkout/index.ts", "description": "入口"}],
        }]
    }
    modules_file = tmp_path / "modules.json"
    modules_file.write_text(json.dumps(modules_json, ensure_ascii=False), encoding="utf-8")

    result, code = run_cmd("lib.catalog_update", ["--file", str(modules_file), "--project-root", str(tmp_path)])
    assert code == 0
    result, code = run_cmd("lib.brief", ["--project-root", str(tmp_path)])
    assert code == 0

    result, code = run_cmd("lib.recall_planner", ["--task", "checkout 别名 shadowtoken77 的验证风险", "--project-root", str(tmp_path)])
    assert code == 0
    planned = result["data"]
    assert planned["search_first"] is True
    assert planned["search_stage_completed"] is True
    assert planned["search_hits"]["docs"]
    assert planned["recommended_modules"]
    assert planned["ambiguity"] == "medium"
    assert planned["recall_level"] == "deep"



def test_search_first_flow_when_task_uses_chinese_historical_term(tmp_path):
    result, code = run_cmd("lib.memory_init", ["--project-root", str(tmp_path)])
    assert code == 0

    docs = tmp_path / ".memory" / "docs"
    (docs / "architect" / "decisions.md").write_text("## 决策\n\nUse recall-first\n\n## 附录\n\n影子令牌 是 checkout 的历史术语", encoding="utf-8")
    (docs / "pm" / "decisions.md").write_text("## 规则\n\nCheckout coupon rules", encoding="utf-8")
    (docs / "qa" / "strategy.md").write_text("## 验证策略\n\n金额链路回归\n\n## 附录\n\n影子令牌 金额回归", encoding="utf-8")

    modules_json = {
        "modules": [{
            "name": "checkout",
            "summary": "结算模块",
            "read_when": "当任务涉及结算时阅读。",
            "entry_points": ["packages/checkout/index.ts"],
            "read_order": ["packages/checkout/index.ts"],
            "implicit_constraints": ["先确认优惠规则"],
            "known_risks": ["金额错误"],
            "verification_focus": ["回归价格计算"],
            "related_memory": ["docs/pm/decisions.md"],
            "files": [{"path": "packages/checkout/index.ts", "description": "入口"}],
        }]
    }
    modules_file = tmp_path / "modules.json"
    modules_file.write_text(json.dumps(modules_json, ensure_ascii=False), encoding="utf-8")

    result, code = run_cmd("lib.catalog_update", ["--file", str(modules_file), "--project-root", str(tmp_path)])
    assert code == 0
    result, code = run_cmd("lib.brief", ["--project-root", str(tmp_path)])
    assert code == 0

    result, code = run_cmd("lib.recall_planner", ["--task", "checkout 历史术语 影子令牌 的验证风险", "--project-root", str(tmp_path)])
    assert code == 0
    planned = result["data"]
    assert planned["search_first"] is True
    assert planned["search_stage_completed"] is True
    assert planned["search_hits"]["docs"]
    assert any("影子令牌" in item["reason"] for item in planned["search_hits"]["docs"])
    assert planned["recommended_modules"]
    assert planned["ambiguity"] == "medium"
    assert planned["recall_level"] == "deep"



def test_save_flow_updates_docs_and_brief(tmp_path):
    result, code = run_cmd("lib.memory_init", ["--project-root", str(tmp_path)])
    assert code == 0

    docs = tmp_path / ".memory" / "docs"
    (docs / "pm" / "decisions.md").write_text("## 规则\n\n- 旧规则\n", encoding="utf-8")
    (docs / "architect" / "decisions.md").write_text("## 决策\n\n- recall-first\n", encoding="utf-8")

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
            str(tmp_path),
        ],
    )
    assert code == 0

    save_request = {
        "version": "1",
        "task": "save checkout rules",
        "entries": [{
            "id": "append-pm-rule",
            "action": "append",
            "reason": "stable checkout business rule",
            "target": {"bucket": "pm", "file": "decisions.md"},
            "payload": {"section_markdown": "## Checkout 优惠券规则\n\n- 先计算折扣再做上限校验\n"},
            "evidence": {
                "search_queries": ["Checkout 优惠券 规则"],
                "read_refs": ["docs/pm/decisions.md", "docs/architect/decisions.md"],
            },
        }],
    }
    request_file = tmp_path / "save-request.json"
    request_file.write_text(json.dumps(save_request, ensure_ascii=False, indent=2), encoding="utf-8")

    result, code = run_cmd("lib.memory_save", ["--file", str(request_file), "--project-root", str(tmp_path)])
    assert code == 0
    assert result["code"] == "SUCCESS"
    assert result["data"]["rebuild"]["brief"] is True

    updated_doc = (docs / "pm" / "decisions.md").read_text(encoding="utf-8")
    assert "Checkout 优惠券规则" in updated_doc

    brief = (tmp_path / ".memory" / "BRIEF.md").read_text(encoding="utf-8")
    assert brief.startswith("# Project Brief")

    topics_path = tmp_path / ".memory" / "catalog" / "topics.md"
    topics = topics_path.read_text(encoding="utf-8")
    assert "docs/pm/decisions.md" in topics
    assert "Checkout 优惠券规则：先计算折扣再做上限校验" in topics

    repair_result, repair_code = run_cmd("lib.catalog_repair", ["--project-root", str(tmp_path)])
    assert repair_code == 0
    assert not any(item["type"] == "stale_summary_refreshed" for item in repair_result["data"]["fixed"])

    topics_after_repair = topics_path.read_text(encoding="utf-8")
    assert "Checkout 优惠券规则：先计算折扣再做上限校验" in topics_after_repair

    search_result, search_code = run_cmd("lib.memory_search", ["Checkout 优惠券规则", "--project-root", str(tmp_path)])
    assert search_code == 0
    assert search_result["data"]["total"] >= 1
