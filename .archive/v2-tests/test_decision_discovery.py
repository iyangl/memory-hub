"""Tests for decision discovery lane phase 1."""

from __future__ import annotations

from pathlib import Path
import subprocess

from tests.durable_test_support import run_cli_command


def _init_project(project_root: Path) -> None:
    result, code = run_cli_command(["init", "--project-root", str(project_root)])
    assert code == 0, result


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(project_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit_baseline(project_root: Path) -> None:
    _git(project_root, "init")
    _git(project_root, "config", "user.name", "Tester")
    _git(project_root, "config", "user.email", "tester@example.com")
    _git(project_root, "add", "-f", ".")
    _git(project_root, "commit", "-m", "baseline")


def test_discover_detects_default_rule_broken(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _init_project(project_root)
    _write(
        project_root / ".memory" / "docs" / "architect" / "decisions.md",
        "# 架构决策\n\n默认网络请求使用 https。\n",
    )
    _commit_baseline(project_root)
    _write(
        project_root / "modules" / "module_chat" / "lib" / "network.dart",
        'const endpoint = "ws://chat.example.com";\n',
    )

    result, code = run_cli_command(["discover", "--project-root", str(project_root)])

    assert code == 0
    assert result["code"] == "DISCOVERY_OK"
    assert result["data"]["candidate_count"] == 1
    item = result["data"]["items"][0]
    assert item["signal_kind"] == "default-rule-broken"
    assert item["candidate_type"] == "new-rule"
    assert item["target_ref"] == "doc://architect/decisions"


def test_discover_detects_exception_rule(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _init_project(project_root)
    _write(
        project_root / ".memory" / "docs" / "architect" / "decisions.md",
        "# 架构决策\n\n默认网络请求使用 https。\n",
    )
    _commit_baseline(project_root)
    _write(
        project_root / "modules" / "realtime" / "lib" / "socket_client.dart",
        'const transport = "ws://stream.example.com";\n',
    )

    result, code = run_cli_command(["discover", "--project-root", str(project_root)])

    assert code == 0
    assert result["data"]["candidate_count"] == 1
    item = result["data"]["items"][0]
    assert item["signal_kind"] == "exception-rule"
    assert item["candidate_type"] == "exception-rule"
    assert item["target_ref"] == "doc://architect/decisions"


def test_discover_detects_docs_drift_from_summary(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _init_project(project_root)
    _write(
        project_root / ".memory" / "docs" / "architect" / "decisions.md",
        "# 架构决策\n\n统一写入仍使用 legacy pipeline。\n",
    )
    _commit_baseline(project_root)
    _write(
        project_root / "lib" / "writer.py",
        'WRITE_MODE = "unified write lane"\n',
    )
    summary_file = tmp_path / "summary.txt"
    summary_file.write_text("统一写入现在必须走 unified write lane。", encoding="utf-8")

    result, code = run_cli_command(
        [
            "discover",
            "--project-root",
            str(project_root),
            "--summary-file",
            str(summary_file),
        ]
    )

    assert code == 0
    assert result["data"]["candidate_count"] == 1
    item = result["data"]["items"][0]
    assert item["signal_kind"] == "docs-drift"
    assert item["candidate_type"] == "docs-drift"
    assert item["target_ref"] == "doc://architect/decisions"


def test_discover_ignores_noise_only_changes(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _init_project(project_root)
    _write(project_root / "lib" / "value.py", "value = 1\n")
    _commit_baseline(project_root)
    _write(project_root / "lib" / "value.py", "value = 2\n")

    result, code = run_cli_command(["discover", "--project-root", str(project_root)])

    assert code == 0
    assert result["data"]["candidate_count"] == 0
    assert result["data"]["items"] == []
