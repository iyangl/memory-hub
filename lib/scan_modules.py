"""scan-modules — Discover code modules in a project.

Usage: memory-hub scan-modules [--project-root <path>]
Outputs JSON with recall-first navigation fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import locale
import subprocess
from pathlib import Path

from lib import envelope
from lib.utils import atomic_write

SKIP_DIRS = frozenset({
    ".git", ".svn", ".hg", ".memory",
    "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", "target",
    ".idea", ".vscode", ".DS_Store",
    "vendor", "Pods", ".gradle",
})

CONTAINER_DIRS = frozenset({
    "packages", "apps", "modules", "crates",
    "services", "plugins", "extensions", "workspaces",
})

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
MAX_ENTRY_POINTS = 3
MAX_READ_ORDER = 5


def _format_path_examples(paths: list[str], limit: int = 2) -> str:
    examples = [f"`{path}`" for path in paths[:limit] if path]
    return "、".join(examples)


def _detect_project_type(root: Path) -> str:
    for marker, ptype in MARKER_FILES.items():
        if (root / marker).exists():
            return ptype
    return "unknown"


def _get_tracked_files(root: Path, include_untracked: bool = False) -> set[str] | None:
    encoding = locale.getpreferredencoding(False) or "utf-8"
    command = ["git", "-c", "core.quotePath=false", "ls-files", "-z"]
    if include_untracked:
        command.extend(["--others", "--exclude-standard", "--cached"])
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        output = result.stdout.decode(encoding, errors="replace")
        return {f for f in output.split("\x00") if f}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _list_source_files(directory: Path, root: Path, tracked: set[str] | None) -> list[str]:
    files = []
    if not directory.is_dir():
        return files

    for item in sorted(directory.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir() and item.name in SKIP_DIRS:
            continue

        if item.is_file():
            rel = item.relative_to(root).as_posix()
            if tracked is not None and rel not in tracked:
                continue
            if item.suffix in SOURCE_EXTS or item.name in NOTABLE_PATTERNS:
                files.append(rel)
        elif item.is_dir():
            files.extend(_list_source_files(item, root, tracked))

    return files


def _pick_notable_files(files: list[str], module_prefix: str = "") -> list[str]:
    if not files:
        return []

    subdir_groups: dict[str, list[str]] = {}
    for f in files:
        rel = f[len(module_prefix):] if module_prefix and f.startswith(module_prefix) else f
        parts = Path(rel).parts
        key = parts[0] if len(parts) > 1 else ""
        subdir_groups.setdefault(key, []).append(f)

    selected: list[str] = []
    selected_set: set[str] = set()

    for _subdir, group in sorted(subdir_groups.items()):
        if len(selected) >= MAX_FILES_PER_MODULE:
            break
        notable = [f for f in group if Path(f).name in NOTABLE_PATTERNS]
        pick = notable[0] if notable else group[0]
        if pick not in selected_set:
            selected.append(pick)
            selected_set.add(pick)

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

    if budget > 0:
        rest = [f for f in files if f not in selected_set]
        for f in rest[:budget]:
            selected.append(f)
            selected_set.add(f)

    return selected


def _build_dir_tree(files: list[str], module_prefix: str, max_depth: int = 2) -> str:
    tree: dict[str, int] = {}
    for f in files:
        rel = f[len(module_prefix):] if module_prefix and f.startswith(module_prefix) else f
        parts = Path(rel).parts
        for depth in range(1, min(len(parts), max_depth + 1)):
            dir_path = "/".join(parts[:depth])
            tree.setdefault(dir_path, 0)
        if len(parts) > 1:
            leaf_depth = min(len(parts) - 1, max_depth)
            leaf = "/".join(parts[:leaf_depth])
            tree[leaf] = tree.get(leaf, 0) + 1
        else:
            tree[""] = tree.get("", 0) + 1

    lines = []
    tree.pop("", 0)
    for dir_path in sorted(tree):
        depth = dir_path.count("/")
        name = dir_path.split("/")[-1]
        indent = "  " * depth
        count = tree[dir_path]
        lines.append(f"{indent}{name}/ ({count} files)")

    return "\n".join(lines)


def _is_module_dir(directory: Path, root: Path, tracked: set[str] | None) -> bool:
    if not directory.is_dir():
        return False
    for item in directory.iterdir():
        if item.is_file():
            rel = item.relative_to(root).as_posix()
            if tracked is not None and rel not in tracked:
                continue
            if item.suffix in SOURCE_EXTS or item.name in NOTABLE_PATTERNS:
                return True
    return False


def _guess_entry_points(files: list[str]) -> list[str]:
    preferred = []
    for path in files:
        name = Path(path).name
        if name in NOTABLE_PATTERNS:
            preferred.append(path)
    ordered = preferred + [p for p in files if p not in preferred]
    return ordered[:MAX_ENTRY_POINTS]


def _guess_read_when(name: str, entry_points: list[str], files: list[str]) -> str:
    example = _format_path_examples(entry_points or files, limit=2)
    if name == "root":
        return f"当任务涉及项目入口、全局配置或无法确定模块归属时阅读；先看 {example or '根目录代表文件'}。"
    if "/tests" in name or name.endswith("tests") or name == "tests":
        return f"当任务涉及验证策略、回归范围或测试入口时阅读；先看 {example or '测试文件'}。"
    return f"当任务涉及 {name} 的职责、边界或入口时阅读；优先从 {example or '代表文件'} 开始。"


def _guess_read_order(entry_points: list[str], notable_files: list[str]) -> list[str]:
    ordered = []
    for path in entry_points + notable_files:
        if path not in ordered:
            ordered.append(path)
    return ordered[:MAX_READ_ORDER]


def _guess_constraints(name: str, files: list[str], entry_points: list[str]) -> list[str]:
    constraints = []
    entry_example = _format_path_examples(entry_points, limit=2)
    if entry_example:
        constraints.append(f"先从 {entry_example} 定位模块边界，再决定是否继续下钻。")
    if any(Path(f).name in {"package.json", "pyproject.toml", "go.mod", "Cargo.toml"} for f in files):
        manifest_files = [f for f in files if Path(f).name in {"package.json", "pyproject.toml", "go.mod", "Cargo.toml"}]
        constraints.append(f"若要判断职责或依赖，先读清单文件 {_format_path_examples(manifest_files, limit=2)}。")
    if name == "root":
        constraints.append("root 只提供全局入口与配置线索，不能替代具体业务模块。")
    if not constraints:
        constraints.append("先从代表文件确认职责，再决定是否扩大阅读范围。")
    return constraints


def _guess_risks(name: str, files: list[str], entry_points: list[str]) -> list[str]:
    risks = []
    if name == "root":
        risks.append("root 入口容易让人误以为已经掌握业务细节，实际仍需下钻具体模块。")
    test_files = [f for f in files if "test" in Path(f).name.lower()]
    if test_files:
        risks.append(f"测试文件 {_format_path_examples(test_files, limit=2)} 只反映验证方式，不等于真实运行入口。")
    if entry_points and any(Path(path).name.startswith("index.") or Path(path).name.startswith("main.") for path in entry_points):
        risks.append(f"入口文件 {_format_path_examples(entry_points, limit=2)} 可能只负责分发，业务规则在下游文件。")
    if not risks:
        risks.append(f"若只根据目录名 {name} 理解模块，容易忽略真实入口与隐含约束。")
    return risks


def _guess_verification_focus(name: str, entry_points: list[str], files: list[str]) -> list[str]:
    if name == "tests":
        return [f"确认测试入口 {_format_path_examples(entry_points or files, limit=2) or '测试文件'} 覆盖的行为与当前任务相关。"]
    focuses = []
    if entry_points:
        focuses.append(f"确认入口文件 {_format_path_examples(entry_points, limit=2)} 是否足以定位改动边界。")
    focuses.append("确认改动后需要补测或回归的关键路径。")
    return focuses


def _guess_related_memory(name: str) -> list[str]:
    refs = ["docs/architect/decisions.md"]
    if name == "tests":
        refs.append("docs/qa/strategy.md")
    else:
        refs.append("docs/dev/conventions.md")
    return refs


def _compute_structure_hash(files: list[str]) -> str:
    """SHA-256 prefix (8 hex chars) of the sorted file list."""
    joined = "\n".join(sorted(files))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


def _build_module(name: str, files: list[str], prefix: str) -> dict:
    notable_files = _pick_notable_files(files, prefix)
    entry_points = _guess_entry_points(notable_files)
    summary = f"基于 {len(files)} 个跟踪文件生成的模块导航，代表文件：{_format_path_examples(notable_files, limit=2) or '无'}。"
    return {
        "name": name,
        "summary": summary,
        "total_files": len(files),
        "structure_hash": _compute_structure_hash(files),
        "dir_tree": _build_dir_tree(files, prefix),
        "files": [{"path": f, "description": ""} for f in notable_files],
        "read_when": _guess_read_when(name, entry_points, notable_files),
        "entry_points": entry_points,
        "read_order": _guess_read_order(entry_points, notable_files),
        "implicit_constraints": _guess_constraints(name, files, entry_points),
        "known_risks": _guess_risks(name, files, entry_points),
        "verification_focus": _guess_verification_focus(name, entry_points, files),
        "related_memory": _guess_related_memory(name),
    }


def _discover_modules(root: Path, include_untracked: bool = False) -> list[dict]:
    tracked = _get_tracked_files(root, include_untracked=include_untracked)
    modules = []

    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith(".") or item.name in SKIP_DIRS:
            continue

        if item.name.lower() in CONTAINER_DIRS:
            for sub in sorted(item.iterdir()):
                if not sub.is_dir() or sub.name.startswith(".") or sub.name in SKIP_DIRS:
                    continue
                if not _is_module_dir(sub, root, tracked):
                    continue
                files = _list_source_files(sub, root, tracked)
                if files:
                    modules.append(_build_module(f"{item.name}/{sub.name}", files, f"{item.name}/{sub.name}/"))
        else:
            if not _is_module_dir(item, root, tracked):
                continue
            files = _list_source_files(item, root, tracked)
            if files:
                modules.append(_build_module(item.name, files, f"{item.name}/"))

    root_files = []
    for item in sorted(root.iterdir()):
        if item.is_file():
            rel = item.relative_to(root).as_posix()
            if tracked is not None and rel not in tracked:
                continue
            if item.suffix in SOURCE_EXTS or item.name in NOTABLE_PATTERNS:
                root_files.append(rel)

    if root_files:
        modules.insert(0, _build_module("root", root_files, ""))

    return modules


def scan(project_root: Path | None = None, include_untracked: bool = False) -> dict:
    root = project_root or Path.cwd()
    if not root.is_dir():
        return {"project_type": "unknown", "modules": []}

    return {
        "project_type": _detect_project_type(root),
        "modules": _discover_modules(root, include_untracked=include_untracked),
    }


def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="memory-hub scan-modules")
    parser.add_argument("--project-root", help="Project root directory", default=None)
    parser.add_argument("--out", help="Optional output file for scan JSON")
    parsed = parser.parse_args(args)

    project_root = Path(parsed.project_root) if parsed.project_root else None
    result = scan(project_root)
    if parsed.out:
        atomic_write(Path(parsed.out), json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        payload = dict(result)
        payload["output_file"] = str(Path(parsed.out))
        envelope.ok(payload)
    envelope.ok(result)
