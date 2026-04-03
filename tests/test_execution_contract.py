"""Tests for lib.execution_contract."""

import hashlib
import json

import pytest

from lib.execution_contract import build_execution_contract
from lib.session_working_set import DURABLE_CANDIDATE_PLACEHOLDER


@pytest.fixture
def working_set_payload(tmp_path):
    memory = tmp_path / ".memory"
    (memory / "session").mkdir(parents=True)
    working_set = {
        "version": "1",
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
            },
            {
                "kind": "navigation",
                "title": "checkout",
                "summary": "当任务涉及结算时阅读。",
                "bullets": ["约束: 先确认优惠规则。", "验证: 回归价格计算。"],
                "sources": [{"type": "module", "path": "/repo/.memory/catalog/modules/checkout.md"}],
                "selected_because": "主模块",
            },
            {
                "kind": "navigation",
                "title": "pricing",
                "summary": "当任务涉及价格计算时阅读。",
                "bullets": ["验证: 核对边界条件。"],
                "sources": [{"type": "module", "path": "/repo/.memory/catalog/modules/pricing.md"}],
                "selected_because": "价格链路",
            },
            {
                "kind": "navigation",
                "title": "checkout-duplicate",
                "summary": "当任务涉及结算时阅读。",
                "bullets": ["验证: 回归价格计算。"],
                "sources": [{"type": "module", "path": "/repo/.memory/catalog/modules/checkout.md"}],
                "selected_because": "重复来源",
            },
        ],
        "priority_reads": [
            {"type": "doc", "path": "/repo/.memory/docs/pm/decisions.md", "reason": "业务规则"},
            {"type": "module", "path": "/repo/.memory/catalog/modules/checkout.md", "reason": "主模块入口"},
        ],
        "evidence_gaps": ["尚未确认 promotion 是否参与"],
        "primary_evidence_gap": "尚未确认 promotion 是否参与",
        "verification_focus": ["回归价格计算。", "核对边界条件。"],
        "durable_candidates": ["checkout：验证: 回归价格计算。"],
    }
    path = memory / "session" / "working-set.json"
    path.write_text(json.dumps(working_set, ensure_ascii=False, indent=2), encoding="utf-8")
    return tmp_path, path, working_set



def test_build_execution_contract_from_working_set(working_set_payload):
    _, path, working_set = working_set_payload
    result = build_execution_contract(working_set, str(path))

    assert result["version"] == "1"
    assert result["task"] == working_set["task"]
    assert result["source_working_set"] == str(path)
    assert result["source_plan"] == ".memory/session/recall-plan.json"
    assert result["goal"] == working_set["task"]
    assert result["goal"] != working_set["summary"]
    assert result["primary_evidence_gap"] == "尚未确认 promotion 是否参与"
    assert result["required_evidence"] == ["尚未确认 promotion 是否参与"]
    assert result["success_criteria"] == ["解决 尚未确认 promotion 是否参与"]
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
        "version": "1",
        "task": "纯中文任务",
        "source_plan": ".memory/session/recall-plan.json",
        "summary": "目标摘要",
        "items": [],
        "priority_reads": [],
        "evidence_gaps": [],
        "primary_evidence_gap": None,
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
                "version": "1",
                "task": "bad",
                "source_plan": ".memory/session/recall-plan.json",
                "summary": "summary",
                "items": [],
                "priority_reads": [{"type": "doc", "path": "/repo/doc.md", "reason": 123}],
                "primary_evidence_gap": None,
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
                "version": "1",
                "task": "   ",
                "source_plan": "   ",
                "summary": "   ",
                "items": [],
                "priority_reads": [],
                "primary_evidence_gap": None,
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
