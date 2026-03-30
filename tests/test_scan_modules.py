"""Tests for scan-modules command."""

import json
import pytest
from io import StringIO
from pathlib import Path
import sys

from lib.scan_modules import (
    scan, _detect_project_type, _discover_modules,
    _pick_notable_files, _build_dir_tree,
)


def run_cmd(module, args):
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with pytest.raises(SystemExit) as exc_info:
            module.run(args)
        return json.loads(sys.stdout.getvalue()), exc_info.value.code
    finally:
        sys.stdout = old_stdout


@pytest.fixture
def python_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "__init__.py").write_text("")
    (lib_dir / "core.py").write_text("# core")
    (lib_dir / "utils.py").write_text("# utils")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_core.py").write_text("# test")
    (tmp_path / "main.py").write_text("# entry")
    return tmp_path


@pytest.fixture
def monorepo_project(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "mono"}')
    pkgs = tmp_path / "packages"
    pkgs.mkdir()
    for name in ["web", "api"]:
        pkg = pkgs / name
        pkg.mkdir()
        (pkg / "index.ts").write_text(f"// {name}")
        (pkg / "package.json").write_text(f'{{"name": "{name}"}}')
    return tmp_path


class TestDetectProjectType:
    def test_python(self, python_project):
        assert _detect_project_type(python_project) == "python"

    def test_node(self, monorepo_project):
        assert _detect_project_type(monorepo_project) == "node"


class TestPickNotableFiles:
    def test_subdirectory_representation(self):
        files = [
            "mod/common/a.py",
            "mod/common/b.py",
            "mod/network/client.py",
            "mod/network/server.py",
            "mod/store/db.py",
        ]
        result = _pick_notable_files(files, "mod/")
        subdirs_in_result = {Path(f[len("mod/"):]).parts[0] for f in result}
        assert {"common", "network", "store"}.issubset(subdirs_in_result)


class TestBuildDirTree:
    def test_basic_tree(self):
        files = [
            "src/common/a.py",
            "src/common/b.py",
            "src/network/client.py",
        ]
        tree = _build_dir_tree(files, "src/")
        assert "common/" in tree
        assert "network/" in tree


class TestDiscoverModules:
    def test_python_project(self, python_project):
        modules = _discover_modules(python_project)
        names = [m["name"] for m in modules]
        assert "lib" in names
        assert "tests" in names
        lib_mod = next(m for m in modules if m["name"] == "lib")
        assert "read_when" in lib_mod
        assert "entry_points" in lib_mod
        assert "read_order" in lib_mod
        assert "implicit_constraints" in lib_mod
        assert "known_risks" in lib_mod
        assert "verification_focus" in lib_mod
        assert "related_memory" in lib_mod
        assert lib_mod["summary"].startswith("基于 ")
        assert "`lib/__init__.py`" in lib_mod["summary"] or "`lib/core.py`" in lib_mod["summary"]
        assert any("`" in item for item in lib_mod["implicit_constraints"])
        assert any("入口文件" in item or "测试文件" in item or "目录名" in item for item in lib_mod["known_risks"])

    def test_root_files(self, python_project):
        modules = _discover_modules(python_project)
        root_mod = next((m for m in modules if m["name"] == "root"), None)
        assert root_mod is not None
        root_files = [f["path"] for f in root_mod["files"]]
        assert "main.py" in root_files
        assert root_mod["entry_points"]

    def test_monorepo_container(self, monorepo_project):
        modules = _discover_modules(monorepo_project)
        names = [m["name"] for m in modules]
        assert "packages/web" in names
        assert "packages/api" in names


class TestScan:
    def test_returns_project_type(self, python_project):
        result = scan(python_project)
        assert result["project_type"] == "python"
        assert isinstance(result["modules"], list)

    def test_cli_supports_out_file(self, python_project):
        from lib import scan_modules

        out_file = python_project / "scan.json"
        result, code = run_cmd(scan_modules, ["--project-root", str(python_project), "--out", str(out_file)])
        assert code == 0
        saved = json.loads(out_file.read_text(encoding="utf-8"))
        assert saved["project_type"] == "python"
        assert result["data"]["output_file"] == str(out_file)
