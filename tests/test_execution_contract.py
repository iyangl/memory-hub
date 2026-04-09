"""Tests for lib.execution_contract."""

import hashlib
import json
from pathlib import Path

import pytest

from lib.execution_contract import EXECUTION_CONTRACT_VERSION, WORKING_SET_VERSION, build_execution_contract
from lib.session_working_set import DURABLE_CANDIDATE_PLACEHOLDER, build_working_set


@pytest.fixture
def working_set_payload(tmp_path):
    memory = tmp_path / ".memory"
    (memory / "session").mkdir(parents=True)
    working_set = {
        "version": WORKING_SET_VERSION,
        "task": "重构 checkout 优惠券规则",
        "source_plan": ".memory/session/recall-plan.json",
        "summary": "任务涉及业务规则与主模块入口 需要先确认优惠链路",
        "items": [
            {
                "kind": "decision",
                "title": "pm/decisions.md",
                "summary": "优惠券规则会影响后续动作。",
                "bullets": ["规则一", "规则二"],
                "sources": [{"type": "doc", "path": "/repo/.memory/docs/pm/decisions.md"}],
                "selected_because": "业务规则",
                "decision_points": ["优惠券规则会影响后续动作。"],
                "constraints": [],
                "risks": [],
                "verification_focus": [],
            },
            {
                "kind": "navigation",
                "title": "checkout",
                "summary": "当任务涉及结算时阅读。",
                "bullets": ["约束: 先确认优惠规则。", "验证: 回归价格计算。"],
                "sources": [{"type": "module", "path": "/repo/.memory/catalog/modules/checkout.md"}],
                "selected_because": "主模块",
                "decision_points": [],
                "constraints": ["先确认优惠规则。"],
                "risks": ["金额错误。"],
                "verification_focus": ["回归价格计算。"],
            },
            {
                "kind": "navigation",
                "title": "pricing",
                "summary": "当任务涉及价格计算时阅读。",
                "bullets": ["验证: 核对边界条件。"],
                "sources": [{"type": "module", "path": "/repo/.memory/catalog/modules/pricing.md"}],
                "selected_because": "价格链路",
                "decision_points": [],
                "constraints": [],
                "risks": [],
                "verification_focus": ["核对边界条件。"],
            },
            {
                "kind": "navigation",
                "title": "checkout-duplicate",
                "summary": "当任务涉及结算时阅读。",
                "bullets": ["验证: 回归价格计算。"],
                "sources": [{"type": "module", "path": "/repo/.memory/catalog/modules/checkout.md"}],
                "selected_because": "重复来源",
                "decision_points": [],
                "constraints": [],
                "risks": [],
                "verification_focus": ["回归价格计算。"],
            },
        ],
        "priority_reads": [
            {"type": "doc", "path": "/repo/.memory/docs/pm/decisions.md", "reason": "业务规则"},
            {"type": "module", "path": "/repo/.memory/catalog/modules/checkout.md", "reason": "主模块入口"},
        ],
        "evidence_gaps": ["尚未确认 promotion 是否参与"],
        "primary_evidence_gap": "尚未确认 promotion 是否参与",
        "decision_points": ["优惠券规则会影响后续动作。"],
        "constraints": ["先确认优惠规则。"],
        "risks": ["金额错误。"],
        "verification_focus": ["回归价格计算。", "核对边界条件。"],
        "durable_candidates": ["checkout：验证: 回归价格计算。"],
    }
    path = memory / "session" / "working-set.json"
    path.write_text(json.dumps(working_set, ensure_ascii=False, indent=2), encoding="utf-8")
    return tmp_path, path, working_set



def test_build_execution_contract_from_working_set(working_set_payload):
    _, path, working_set = working_set_payload
    result = build_execution_contract(working_set, str(path))

    assert result["version"] == EXECUTION_CONTRACT_VERSION
    assert result["task"] == working_set["task"]
    assert result["source_working_set"] == str(path)
    assert result["source_plan"] == ".memory/session/recall-plan.json"
    assert result["goal"] == working_set["task"]
    assert result["goal"] != working_set["summary"]
    assert result["primary_evidence_gap"] == "尚未确认 promotion 是否参与"
    assert result["required_evidence"] == ["尚未确认 promotion 是否参与"]
    assert result["success_criteria"] == ["解决 尚未确认 promotion 是否参与"]
    assert result["decision_points"] == ["优惠券规则会影响后续动作。"]
    assert result["constraints"] == ["先确认优惠规则。"]
    assert result["risks"] == ["金额错误。"]
    assert result["verification_focus"] == ["回归价格计算。", "核对边界条件。"]
    assert result["durable_candidates"] == ["checkout：验证: 回归价格计算。"]



def test_known_context_uses_item_summaries_only_and_dedupes(working_set_payload):
    _, path, working_set = working_set_payload
    result = build_execution_contract(working_set, str(path))

    assert result["known_context"] == [
        "优惠券规则会影响后续动作。",
        "当任务涉及结算时阅读。",
        "当任务涉及价格计算时阅读。",
    ]


def test_contract_preserves_explicit_facets_from_working_set(working_set_payload):
    _, path, working_set = working_set_payload
    working_set["decision_points"] = ["优惠券规则会影响后续动作。", "优惠券规则会影响后续动作。"]
    working_set["constraints"] = ["先确认优惠规则。"]
    working_set["risks"] = ["金额错误。"]
    working_set["verification_focus"] = ["回归价格计算。", "回归价格计算。"]

    result = build_execution_contract(working_set, str(path))

    assert result["decision_points"] == ["优惠券规则会影响后续动作。"]
    assert result["constraints"] == ["先确认优惠规则。"]
    assert result["risks"] == ["金额错误。"]
    assert result["verification_focus"] == ["回归价格计算。"]



def test_allowed_sources_dedupes_priority_reads_and_item_sources(working_set_payload):
    _, path, working_set = working_set_payload
    result = build_execution_contract(working_set, str(path))

    assert result["allowed_sources"] == [
        {"type": "doc", "path": "/repo/.memory/docs/pm/decisions.md", "reason": "业务规则"},
        {"type": "module", "path": "/repo/.memory/catalog/modules/checkout.md", "reason": "主模块入口"},
        {"type": "module", "path": "/repo/.memory/catalog/modules/pricing.md", "reason": "价格链路"},
    ]



def test_success_criteria_and_required_evidence_are_empty_without_primary_gap(working_set_payload):
    _, path, working_set = working_set_payload
    working_set["primary_evidence_gap"] = None
    working_set["verification_focus"] = ["回归价格计算。"]

    result = build_execution_contract(working_set, str(path))

    assert result["success_criteria"] == []
    assert result["required_evidence"] == []
    assert result["verification_focus"] == ["回归价格计算。"]



def test_run_writes_output_file_when_out_is_provided(working_set_payload):
    project_root, path, _ = working_set_payload
    out_file = project_root / ".memory" / "session" / "execution-contract.json"

    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run([
                "--working-set-file", str(path),
                "--project-root", str(project_root),
                "--out", str(out_file),
            ])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 0
    assert payload["data"]["output_file"] == str(out_file)
    written = json.loads(out_file.read_text(encoding="utf-8"))
    assert written["task"] == "重构 checkout 优惠券规则"
    assert written["source_working_set"] == str(path)



def test_run_uses_default_session_output_file(working_set_payload):
    project_root, path, _ = working_set_payload

    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run([
                "--working-set-file", str(path),
                "--project-root", str(project_root),
            ])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 0
    output_file = payload["data"]["output_file"]
    assert output_file.endswith("/checkout-execution-contract.json")
    assert json.loads((project_root / ".memory" / "session" / "checkout-execution-contract.json").read_text(encoding="utf-8"))["task"] == "重构 checkout 优惠券规则"



def test_run_uses_hashed_default_output_file_for_non_ascii_task(tmp_path):
    working_set = {
        "version": WORKING_SET_VERSION,
        "task": "纯中文任务",
        "source_plan": ".memory/session/recall-plan.json",
        "summary": "目标摘要",
        "items": [],
        "priority_reads": [],
        "evidence_gaps": [],
        "primary_evidence_gap": None,
        "decision_points": [],
        "constraints": [],
        "risks": [],
        "verification_focus": [],
        "durable_candidates": [],
    }
    path = tmp_path / "working-set.json"
    path.write_text(json.dumps(working_set, ensure_ascii=False), encoding="utf-8")

    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run([
                "--working-set-file", str(path),
                "--project-root", str(tmp_path),
            ])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 0
    task_hash = hashlib.sha1("纯中文任务".encode("utf-8")).hexdigest()[:8]
    assert payload["data"]["output_file"].endswith(f"/execution-contract-{task_hash}-execution-contract.json")



def test_build_execution_contract_filters_placeholder_durable_candidates(working_set_payload):
    _, path, working_set = working_set_payload
    working_set["durable_candidates"] = [
        DURABLE_CANDIDATE_PLACEHOLDER,
        "checkout：验证: 回归价格计算。",
    ]

    result = build_execution_contract(working_set, str(path))

    assert result["durable_candidates"] == ["checkout：验证: 回归价格计算。"]



def test_build_execution_contract_accepts_legacy_v1_working_set(tmp_path):
    working_set = {
        "version": "1",
        "task": "兼容旧 working-set",
        "source_plan": ".memory/session/recall-plan.json",
        "summary": "旧版 payload",
        "items": [],
        "priority_reads": [],
        "primary_evidence_gap": None,
        "verification_focus": [],
        "durable_candidates": [],
    }

    result = build_execution_contract(working_set, str(tmp_path / "legacy-working-set.json"))

    assert result["version"] == EXECUTION_CONTRACT_VERSION
    assert result["task"] == "兼容旧 working-set"
    assert result["decision_points"] == []
    assert result["constraints"] == []
    assert result["risks"] == []



def test_build_execution_contract_limits_facets_for_external_v2_working_set(tmp_path):
    working_set = {
        "version": WORKING_SET_VERSION,
        "task": "外部 payload facet 上限",
        "source_plan": ".memory/session/recall-plan.json",
        "summary": "测试 facet 去重与限长",
        "items": [],
        "priority_reads": [],
        "primary_evidence_gap": None,
        "decision_points": ["决策1", "决策2", "决策3", "决策4", "决策5", "决策2"],
        "constraints": ["约束1", "约束2", "约束3", "约束4", "约束5", "约束1"],
        "risks": ["风险1", "风险2", "风险3", "风险4", "风险5", "风险3"],
        "verification_focus": ["验证1", "验证2", "验证3", "验证4", "验证5", "验证2"],
        "durable_candidates": [
            "候选1",
            "候选2",
            "候选3",
            "候选4",
            "候选5",
            "候选2",
            DURABLE_CANDIDATE_PLACEHOLDER,
        ],
    }

    result = build_execution_contract(working_set, str(tmp_path / "external-v2-working-set.json"))

    assert result["decision_points"] == ["决策1", "决策2", "决策3", "决策4"]
    assert result["constraints"] == ["约束1", "约束2", "约束3", "约束4"]
    assert result["risks"] == ["风险1", "风险2", "风险3", "风险4"]
    assert result["verification_focus"] == ["验证1", "验证2", "验证3", "验证4"]
    assert result["durable_candidates"] == ["候选1", "候选2", "候选3", "候选4"]



def test_build_execution_contract_accepts_direct_build_working_set(tmp_path):
    memory = tmp_path / ".memory"
    (memory / "docs" / "pm").mkdir(parents=True)
    (memory / "catalog" / "modules").mkdir(parents=True)
    (memory / "docs" / "pm" / "decisions.md").write_text(
        "## 规则\n\n- 先计算折扣再做上限校验\n",
        encoding="utf-8",
    )
    (memory / "catalog" / "modules" / "checkout.md").write_text(
        "# checkout\n\n## 何时阅读\n\n当任务涉及结算时阅读。\n\n## 推荐入口\n- `packages/checkout/index.ts`\n\n## 隐含约束\n- 先确认优惠规则。\n",
        encoding="utf-8",
    )

    working_set = build_working_set(
        {
            "task": "直接构建 contract",
            "recall_level": "deep",
            "recommended_docs": [
                {"bucket": "pm", "file": "decisions.md", "reason": "业务规则", "priority": 1},
            ],
            "recommended_modules": [
                {"name": "checkout", "reason": "主模块", "priority": 2, "entry_points": ["packages/checkout/index.ts"]},
            ],
            "evidence_gaps": [],
            "why_these": ["验证默认 source_plan"],
        },
        tmp_path,
    )

    result = build_execution_contract(working_set, str(Path(tmp_path) / ".memory" / "session" / "working-set.json"))

    assert result["source_plan"] == "<direct-build>"
    assert result["task"] == "直接构建 contract"
    assert result["decision_points"] == ["先计算折扣再做上限校验"]
    assert result["constraints"] == ["先确认优惠规则。"]


def test_run_fails_when_working_set_file_is_missing(tmp_path):
    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run(["--working-set-file", str(tmp_path / "missing.json")])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 1
    assert payload["code"] == "FILE_NOT_FOUND"



def test_run_fails_when_working_set_json_is_invalid(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not-json}", encoding="utf-8")

    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run(["--working-set-file", str(path)])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 1
    assert payload["code"] == "INVALID_JSON"



def test_run_fails_when_working_set_is_missing_required_fields(tmp_path):
    path = tmp_path / "bad-working-set.json"
    path.write_text(json.dumps({"task": "bad"}, ensure_ascii=False), encoding="utf-8")

    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run(["--working-set-file", str(path)])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 1
    assert payload["code"] == "INVALID_WORKING_SET"
    assert payload["details"]["missing_fields"]



def test_run_fails_when_priority_read_reason_has_invalid_type(tmp_path):
    path = tmp_path / "bad-working-set.json"
    path.write_text(
        json.dumps(
            {
                "version": WORKING_SET_VERSION,
                "task": "bad",
                "source_plan": ".memory/session/recall-plan.json",
                "summary": "summary",
                "items": [],
                "priority_reads": [{"type": "doc", "path": "/repo/doc.md", "reason": 123}],
                "primary_evidence_gap": None,
                "decision_points": [],
                "constraints": [],
                "risks": [],
                "verification_focus": [],
                "durable_candidates": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run(["--working-set-file", str(path)])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 1
    assert payload["code"] == "INVALID_WORKING_SET"
    assert payload["details"]["field"] == "priority_reads[0].reason"



def test_run_fails_when_required_string_fields_are_blank(tmp_path):
    path = tmp_path / "blank-working-set.json"
    path.write_text(
        json.dumps(
            {
                "version": WORKING_SET_VERSION,
                "task": "   ",
                "source_plan": "   ",
                "summary": "   ",
                "items": [],
                "priority_reads": [],
                "primary_evidence_gap": None,
                "decision_points": [],
                "constraints": [],
                "risks": [],
                "verification_focus": [],
                "durable_candidates": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    from io import StringIO
    import sys
    import lib.execution_contract as execution_contract

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            execution_contract.run(["--working-set-file", str(path)])
        payload = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdout = old_stdout

    assert exc_info.value.code == 1
    assert payload["code"] == "INVALID_WORKING_SET"
    assert payload["details"]["field"] == "task"
