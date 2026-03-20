"""Tests for scan-modules command."""

import json
import pytest
from pathlib import Path

from lib.scan_modules import scan, _detect_project_type, _discover_modules


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


@pytest.fixture
def empty_project(tmp_path):
    return tmp_path


class TestDetectProjectType:
    def test_python(self, python_project):
        assert _detect_project_type(python_project) == "python"

    def test_node(self, monorepo_project):
        assert _detect_project_type(monorepo_project) == "node"

    def test_unknown(self, empty_project):
        assert _detect_project_type(empty_project) == "unknown"


class TestDiscoverModules:
    def test_python_project(self, python_project):
        modules = _discover_modules(python_project)
        names = [m["name"] for m in modules]
        assert "lib" in names
        assert "tests" in names

    def test_root_files(self, python_project):
        modules = _discover_modules(python_project)
        root_mod = next((m for m in modules if m["name"] == "root"), None)
        assert root_mod is not None
        root_files = [f["path"] for f in root_mod["files"]]
        assert "main.py" in root_files

    def test_monorepo_container(self, monorepo_project):
        modules = _discover_modules(monorepo_project)
        names = [m["name"] for m in modules]
        assert "packages/web" in names
        assert "packages/api" in names

    def test_skips_hidden_dirs(self, python_project):
        hidden = python_project / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("# secret")
        modules = _discover_modules(python_project)
        names = [m["name"] for m in modules]
        assert ".hidden" not in names

    def test_skips_node_modules(self, python_project):
        nm = python_project / "node_modules"
        nm.mkdir()
        pkg = nm / "some-pkg"
        pkg.mkdir()
        (pkg / "index.js").write_text("// pkg")
        modules = _discover_modules(python_project)
        names = [m["name"] for m in modules]
        assert "node_modules" not in names

    def test_empty_project(self, empty_project):
        modules = _discover_modules(empty_project)
        assert modules == []

    def test_module_files_have_description_field(self, python_project):
        modules = _discover_modules(python_project)
        for mod in modules:
            assert mod["summary"] == ""
            for f in mod["files"]:
                assert "description" in f
                assert f["description"] == ""

    def test_notable_files_prioritized(self, python_project):
        """__init__.py should appear before other files."""
        modules = _discover_modules(python_project)
        lib_mod = next(m for m in modules if m["name"] == "lib")
        file_paths = [f["path"] for f in lib_mod["files"]]
        init_idx = file_paths.index("lib/__init__.py")
        assert init_idx == 0


class TestScan:
    def test_returns_project_type(self, python_project):
        result = scan(python_project)
        assert result["project_type"] == "python"
        assert isinstance(result["modules"], list)

    def test_nonexistent_dir(self, tmp_path):
        result = scan(tmp_path / "nope")
        assert result["project_type"] == "unknown"
        assert result["modules"] == []
