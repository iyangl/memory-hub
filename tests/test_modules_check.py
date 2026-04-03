"""Tests for modules-check command."""

import json
import subprocess
import pytest
from io import StringIO
from pathlib import Path
import sys

from lib import paths
from lib.utils import sanitize_module_name


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


@pytest.fixture
def project_with_cards(tmp_path):
    """Create a project with source files and matching module cards."""
    # Source files
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "__init__.py").write_text("")
    (lib_dir / "core.py").write_text("# core")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")

    # Run scan to get the hash
    from lib.scan_modules import scan
    scan_result = scan(tmp_path)
    modules = scan_result["modules"]

    # Create module cards with correct hashes
    modules_dir = tmp_path / ".memory" / "catalog" / "modules"
    modules_dir.mkdir(parents=True)
    for mod in modules:
        name = sanitize_module_name(mod["name"])
        h = mod.get("structure_hash", "")
        card = f"# {mod['name']}\n\n> summary\n\n<!-- structure_hash: {h} -->\n"
        (modules_dir / f"{name}.md").write_text(card, encoding="utf-8")

    return tmp_path


class TestModulesCheck:
    def test_all_up_to_date(self, project_with_cards):
        result, code = run_cmd("lib.modules_check", [
            "--project-root", str(project_with_cards),
        ])
        assert code == 0
        data = result["data"]
        assert data["stale"] == []
        assert data["added"] == []
        assert data["removed"] == []
        assert len(data["up_to_date"]) > 0

    def test_detects_new_module(self, project_with_cards):
        # Add a new module directory
        new_dir = project_with_cards / "newmod"
        new_dir.mkdir()
        (new_dir / "main.py").write_text("# new")

        result, code = run_cmd("lib.modules_check", [
            "--project-root", str(project_with_cards),
        ])
        assert code == 0
        assert "newmod" in result["data"]["added"]

    def test_detects_removed_module(self, project_with_cards):
        # Add an extra card that has no corresponding source
        modules_dir = project_with_cards / ".memory" / "catalog" / "modules"
        (modules_dir / "ghost.md").write_text(
            "# ghost\n\n<!-- structure_hash: deadbeef -->\n",
            encoding="utf-8",
        )

        result, code = run_cmd("lib.modules_check", [
            "--project-root", str(project_with_cards),
        ])
        assert code == 0
        assert "ghost" in result["data"]["removed"]

    def test_detects_structure_change(self, project_with_cards):
        # Add a file to an existing module to change its hash
        lib_dir = project_with_cards / "lib"
        (lib_dir / "new_file.py").write_text("# new")

        result, code = run_cmd("lib.modules_check", [
            "--project-root", str(project_with_cards),
        ])
        assert code == 0
        assert "lib" in result["data"]["stale"]

    def test_no_cards_returns_all_added(self, tmp_path):
        # Project with source but no .memory/catalog/modules
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "main.py").write_text("# main")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")

        result, code = run_cmd("lib.modules_check", [
            "--project-root", str(tmp_path),
        ])
        assert code == 0
        assert len(result["data"]["added"]) > 0
        assert result["data"]["stale"] == []
        assert result["data"]["removed"] == []

    def test_detects_untracked_module_in_git_repo(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)

        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "core.py").write_text("# core")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
        subprocess.run(["git", "add", "pyproject.toml", "lib/core.py"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

        from lib.scan_modules import scan
        scan_result = scan(tmp_path)
        modules_dir = tmp_path / ".memory" / "catalog" / "modules"
        modules_dir.mkdir(parents=True)
        for mod in scan_result["modules"]:
            name = sanitize_module_name(mod["name"])
            h = mod.get("structure_hash", "")
            card = f"# {mod['name']}\n\n> summary\n\n<!-- structure_hash: {h} -->\n"
            (modules_dir / f"{name}.md").write_text(card, encoding="utf-8")

        new_dir = tmp_path / "newmod"
        new_dir.mkdir()
        (new_dir / "main.py").write_text("# new")

        result, code = run_cmd("lib.modules_check", [
            "--project-root", str(tmp_path),
        ])
        assert code == 0
        assert "newmod" in result["data"]["added"]

    def test_rejects_module_name_collisions(self, tmp_path, monkeypatch):
        from lib import modules_check

        monkeypatch.setattr(modules_check, "scan", lambda _root, include_untracked=True: {
            "modules": [
                {"name": "packages/web", "structure_hash": "11111111"},
                {"name": "packages-web", "structure_hash": "22222222"},
            ]
        })

        result, code = run_cmd("lib.modules_check", [
            "--project-root", str(tmp_path),
        ])
        assert code == 1
        assert result["code"] == "MODULE_NAME_COLLISION"
