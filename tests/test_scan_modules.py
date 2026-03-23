"""Tests for scan-modules command."""

import json
import pytest
from pathlib import Path

from lib.scan_modules import (
    scan, _detect_project_type, _discover_modules,
    _pick_notable_files, _build_dir_tree,
)


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
def deep_module_project(tmp_path):
    """Project with multiple subdirectories in a module."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'deep'\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("# entry")
    for subdir in ["common", "component", "network", "store"]:
        d = src / subdir
        d.mkdir()
        (d / "__init__.py").write_text("")
        (d / "core.py").write_text(f"# {subdir} core")
    # Add nested subdir
    ctrl = src / "component" / "control"
    ctrl.mkdir()
    (ctrl / "widget.py").write_text("# widget")
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


class TestPickNotableFiles:
    def test_subdirectory_representation(self):
        """Each subdirectory should get at least one representative."""
        files = [
            "mod/common/a.py",
            "mod/common/b.py",
            "mod/network/client.py",
            "mod/network/server.py",
            "mod/store/db.py",
        ]
        result = _pick_notable_files(files, "mod/")
        # Each subdir should have at least one file
        subdirs_in_result = {Path(f[len("mod/"):]).parts[0] for f in result}
        assert "common" in subdirs_in_result
        assert "network" in subdirs_in_result
        assert "store" in subdirs_in_result

    def test_notable_patterns_preferred(self):
        """Notable files should be preferred as subdir representatives."""
        files = [
            "mod/lib/other.py",
            "mod/lib/__init__.py",
            "mod/lib/core.py",
        ]
        result = _pick_notable_files(files, "mod/")
        # __init__.py should be picked as the lib/ representative
        assert "mod/lib/__init__.py" in result

    def test_respects_max_limit(self):
        """Should not exceed MAX_FILES_PER_MODULE."""
        files = [f"mod/sub{i}/file.py" for i in range(20)]
        result = _pick_notable_files(files, "mod/")
        assert len(result) <= 15

    def test_empty_files(self):
        assert _pick_notable_files([], "mod/") == []

    def test_root_level_files(self):
        """Files without subdirectory should be handled."""
        files = ["mod/main.py", "mod/utils.py"]
        result = _pick_notable_files(files, "mod/")
        assert len(result) == 2


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

    def test_nested_tree(self):
        files = [
            "src/component/control/widget.py",
            "src/component/view.py",
            "src/store/db.py",
        ]
        tree = _build_dir_tree(files, "src/")
        assert "component/" in tree
        assert "store/" in tree

    def test_empty_files(self):
        assert _build_dir_tree([], "src/") == ""

    def test_max_depth(self):
        files = [
            "src/a/b/c/d/deep.py",
        ]
        tree = _build_dir_tree(files, "src/", max_depth=2)
        lines = tree.strip().split("\n")
        # Should only show 2 levels
        max_indent = max(len(line) - len(line.lstrip()) for line in lines)
        assert max_indent <= 2  # 1 level of indent = 2 spaces


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
        assert "lib/__init__.py" in file_paths

    def test_total_files_field(self, python_project):
        """Each module should have total_files count."""
        modules = _discover_modules(python_project)
        for mod in modules:
            assert "total_files" in mod
            assert isinstance(mod["total_files"], int)
            assert mod["total_files"] >= len(mod["files"])

    def test_dir_tree_field(self, python_project):
        """Each module should have dir_tree string."""
        modules = _discover_modules(python_project)
        for mod in modules:
            assert "dir_tree" in mod
            assert isinstance(mod["dir_tree"], str)

    def test_deep_module_subdirectory_coverage(self, deep_module_project):
        """Subdirectories in a deep module should be covered in files."""
        modules = _discover_modules(deep_module_project)
        src_mod = next(m for m in modules if m["name"] == "src")
        file_paths = [f["path"] for f in src_mod["files"]]
        # Each subdirectory should have at least one file
        subdirs_present = set()
        for p in file_paths:
            parts = Path(p).parts
            if len(parts) > 1:
                subdirs_present.add(parts[1])
        for subdir in ["common", "component", "network", "store"]:
            assert subdir in subdirs_present, f"{subdir} not represented in files"

    def test_deep_module_dir_tree_not_empty(self, deep_module_project):
        """Deep module should have non-empty dir_tree."""
        modules = _discover_modules(deep_module_project)
        src_mod = next(m for m in modules if m["name"] == "src")
        assert src_mod["dir_tree"] != ""
        assert "common/" in src_mod["dir_tree"]


class TestScan:
    def test_returns_project_type(self, python_project):
        result = scan(python_project)
        assert result["project_type"] == "python"
        assert isinstance(result["modules"], list)

    def test_nonexistent_dir(self, tmp_path):
        result = scan(tmp_path / "nope")
        assert result["project_type"] == "unknown"
        assert result["modules"] == []
