"""scan-modules — Discover code modules in a project.

Usage: memory-hub scan-modules [--project-root <path>]
Outputs JSON: {"project_type": "...", "modules": [{name, summary: "", files: [{path, description: ""}]}]}
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from lib import envelope

# Directories to always skip during filesystem traversal
SKIP_DIRS = frozenset({
    ".git", ".svn", ".hg", ".memory",
    "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", "target",
    ".idea", ".vscode", ".DS_Store",
    "vendor", "Pods", ".gradle",
})

# Container directories that hold sub-modules
CONTAINER_DIRS = frozenset({
    "packages", "apps", "modules", "crates",
    "services", "plugins", "extensions", "workspaces",
})

# Project type markers: filename -> project_type
MARKER_FILES = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "package.json": "node",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java-maven",
    "build.gradle": "java-gradle",
    "build.gradle.kts": "kotlin-gradle",
    "Gemfile": "ruby",
    "mix.exs": "elixir",
    "pubspec.yaml": "flutter",
    "CMakeLists.txt": "cmake",
    "Makefile": "make",
}

# Notable files to prioritize in module file lists
NOTABLE_PATTERNS = {
    "__init__.py", "__main__.py",
    "main.py", "main.go", "main.rs", "main.ts", "main.js",
    "index.ts", "index.js", "index.tsx", "index.jsx",
    "app.py", "app.ts", "app.js",
    "mod.rs", "lib.rs",
    "Cargo.toml", "package.json", "pyproject.toml", "go.mod",
    "Makefile", "Dockerfile",
    "setup.py", "setup.cfg",
}

# Source file extensions
SOURCE_EXTS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt", ".kts",
    ".rb", ".ex", ".exs", ".dart",
    ".c", ".cpp", ".h", ".hpp",
    ".swift", ".m",
    ".vue", ".svelte",
    ".toml", ".yaml", ".yml", ".json",
})

MAX_FILES_PER_MODULE = 15


def _detect_project_type(root: Path) -> str:
    for marker, ptype in MARKER_FILES.items():
        if (root / marker).exists():
            return ptype
    return "unknown"


def _get_tracked_files(root: Path) -> set[str] | None:
    """Get git-tracked files. Returns None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        return {f for f in result.stdout.splitlines() if f}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _list_source_files(
    directory: Path, root: Path, tracked: set[str] | None,
) -> list[str]:
    """List source files in a directory, relative to project root."""
    files = []
    if not directory.is_dir():
        return files

    for item in sorted(directory.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir() and item.name in SKIP_DIRS:
            continue

        if item.is_file():
            rel = str(item.relative_to(root))
            if tracked is not None and rel not in tracked:
                continue
            if item.suffix in SOURCE_EXTS or item.name in NOTABLE_PATTERNS:
                files.append(rel)
        elif item.is_dir():
            files.extend(_list_source_files(item, root, tracked))

    return files


def _pick_notable_files(
    files: list[str], module_prefix: str = "",
) -> list[str]:
    """Pick notable files with per-subdirectory representation.

    Strategy: each direct subdirectory gets at least 1 representative
    (NOTABLE_PATTERNS preferred), remaining budget fills from top.
    """
    if not files:
        return []

    # Group files by their direct subdirectory (relative to module)
    subdir_groups: dict[str, list[str]] = {}
    for f in files:
        rel = f[len(module_prefix):] if module_prefix and f.startswith(module_prefix) else f
        parts = Path(rel).parts
        key = parts[0] if len(parts) > 1 else ""
        subdir_groups.setdefault(key, []).append(f)

    selected: list[str] = []
    selected_set: set[str] = set()

    # Phase 1: one representative per subdirectory
    for _subdir, group in sorted(subdir_groups.items()):
        if len(selected) >= MAX_FILES_PER_MODULE:
            break
        notable = [f for f in group if Path(f).name in NOTABLE_PATTERNS]
        pick = notable[0] if notable else group[0]
        if pick not in selected_set:
            selected.append(pick)
            selected_set.add(pick)

    # Phase 2: fill remaining budget with notable files first
    budget = MAX_FILES_PER_MODULE - len(selected)
    if budget > 0:
        remaining_notable = [
            f for f in files
            if f not in selected_set and Path(f).name in NOTABLE_PATTERNS
        ]
        for f in remaining_notable[:budget]:
            selected.append(f)
            selected_set.add(f)
            budget -= 1

    # Phase 3: fill rest
    if budget > 0:
        rest = [f for f in files if f not in selected_set]
        for f in rest[:budget]:
            selected.append(f)
            selected_set.add(f)

    return selected


def _build_dir_tree(
    files: list[str], module_prefix: str, max_depth: int = 2,
) -> str:
    """Build a compact directory tree string with file counts per subdir."""
    tree: dict[str, int] = {}
    for f in files:
        rel = f[len(module_prefix):] if module_prefix and f.startswith(module_prefix) else f
        parts = Path(rel).parts
        # Count in each ancestor directory up to max_depth
        for depth in range(1, min(len(parts), max_depth + 1)):
            dir_path = "/".join(parts[:depth])
            tree.setdefault(dir_path, 0)
        # Count file in its immediate parent
        if len(parts) > 1:
            parent = "/".join(parts[:-1])
            # Only count at leaf-most tracked dir
            leaf_depth = min(len(parts) - 1, max_depth)
            leaf = "/".join(parts[:leaf_depth])
            tree[leaf] = tree.get(leaf, 0) + 1
        else:
            tree[""] = tree.get("", 0) + 1

    # Build output lines with indentation
    lines = []
    root_count = tree.pop("", 0)
    for dir_path in sorted(tree):
        depth = dir_path.count("/")
        name = dir_path.split("/")[-1]
        indent = "  " * depth
        count = tree[dir_path]
        lines.append(f"{indent}{name}/ ({count} files)")

    return "\n".join(lines)


def _is_module_dir(directory: Path, root: Path, tracked: set[str] | None) -> bool:
    """Check if a directory contains source files."""
    if not directory.is_dir():
        return False
    for item in directory.iterdir():
        if item.is_file():
            rel = str(item.relative_to(root))
            if tracked is not None and rel not in tracked:
                continue
            if item.suffix in SOURCE_EXTS or item.name in NOTABLE_PATTERNS:
                return True
    return False


def _discover_modules(root: Path) -> list[dict]:
    """Scan project root and discover code modules."""
    tracked = _get_tracked_files(root)
    modules = []
    seen_dirs: set[Path] = set()

    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith(".") or item.name in SKIP_DIRS:
            continue

        if item.name.lower() in CONTAINER_DIRS:
            # Container dir: each subdirectory is a module
            for sub in sorted(item.iterdir()):
                if not sub.is_dir() or sub.name.startswith("."):
                    continue
                if sub.name in SKIP_DIRS:
                    continue
                if not _is_module_dir(sub, root, tracked):
                    continue
                files = _list_source_files(sub, root, tracked)
                if files:
                    prefix = f"{item.name}/{sub.name}/"
                    seen_dirs.add(sub)
                    modules.append({
                        "name": f"{item.name}/{sub.name}",
                        "summary": "",
                        "total_files": len(files),
                        "dir_tree": _build_dir_tree(files, prefix),
                        "files": [
                            {"path": f, "description": ""}
                            for f in _pick_notable_files(files, prefix)
                        ],
                    })
        else:
            if not _is_module_dir(item, root, tracked):
                continue
            files = _list_source_files(item, root, tracked)
            if files:
                prefix = f"{item.name}/"
                seen_dirs.add(item)
                modules.append({
                    "name": item.name,
                    "summary": "",
                    "total_files": len(files),
                    "dir_tree": _build_dir_tree(files, prefix),
                    "files": [
                        {"path": f, "description": ""}
                        for f in _pick_notable_files(files, prefix)
                    ],
                })

    # Collect root-level source files as a "root" module
    root_files = []
    for item in sorted(root.iterdir()):
        if item.is_file():
            rel = str(item.relative_to(root))
            if tracked is not None and rel not in tracked:
                continue
            if item.suffix in SOURCE_EXTS or item.name in NOTABLE_PATTERNS:
                root_files.append(rel)

    if root_files:
        modules.insert(0, {
            "name": "root",
            "summary": "",
            "total_files": len(root_files),
            "dir_tree": "",
            "files": [
                {"path": f, "description": ""}
                for f in _pick_notable_files(root_files)
            ],
        })

    return modules


def scan(project_root: Path | None = None) -> dict:
    """Run module scan and return results dict."""
    root = project_root or Path.cwd()
    if not root.is_dir():
        return {"project_type": "unknown", "modules": []}

    project_type = _detect_project_type(root)
    modules = _discover_modules(root)

    return {
        "project_type": project_type,
        "modules": modules,
    }


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub scan-modules")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    result = scan(project_root)

    envelope.ok(result)
