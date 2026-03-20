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


def _pick_notable_files(files: list[str]) -> list[str]:
    """Pick notable files first, then fill up to MAX_FILES_PER_MODULE."""
    notable = [f for f in files if Path(f).name in NOTABLE_PATTERNS]
    rest = [f for f in files if f not in notable]
    result = notable + rest
    return result[:MAX_FILES_PER_MODULE]


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
                    seen_dirs.add(sub)
                    modules.append({
                        "name": f"{item.name}/{sub.name}",
                        "summary": "",
                        "files": [{"path": f, "description": ""} for f in _pick_notable_files(files)],
                    })
        else:
            if not _is_module_dir(item, root, tracked):
                continue
            files = _list_source_files(item, root, tracked)
            if files:
                seen_dirs.add(item)
                modules.append({
                    "name": item.name,
                    "summary": "",
                    "files": [{"path": f, "description": ""} for f in _pick_notable_files(files)],
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
            "files": [{"path": f, "description": ""} for f in _pick_notable_files(root_files)],
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
