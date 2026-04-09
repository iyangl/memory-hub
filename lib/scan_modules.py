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

RUNTIME_ENTRY_FILES = frozenset({
    "__main__.py",
    "main.py", "main.go", "main.rs", "main.ts", "main.js",
    "index.ts", "index.js", "index.tsx", "index.jsx",
    "app.py", "app.ts", "app.js",
})
BOUNDARY_FILES = frozenset({"__init__.py", "mod.rs", "lib.rs"})
DISPATCHER_FILES = RUNTIME_ENTRY_FILES | BOUNDARY_FILES
CANONICAL_TEST_DIR_NAMES = frozenset({"test", "tests", "__tests__"})
AMBIGUOUS_TEST_DIR_NAMES = frozenset({"spec", "specs"})
TEST_DIR_NAMES = CANONICAL_TEST_DIR_NAMES | AMBIGUOUS_TEST_DIR_NAMES
TEST_FILE_MARKERS = (".test.", ".spec.", "_test.", "_spec.")
MAX_FILES_PER_MODULE = 15
MAX_ENTRY_POINTS = 3
MAX_READ_ORDER = 5
MODULE_CARD_GENERATOR_VERSION = "2"


def _format_path_examples(paths: list[str], limit: int = 2) -> str:
    examples = [f"`{path}`" for path in paths[:limit] if path]
    return "、".join(examples)


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


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


def _is_manifest_file(path: str) -> bool:
    return Path(path).name in MARKER_FILES


def _is_test_file(path: str) -> bool:
    lower_path = path.lower()
    parts = {part.lower() for part in Path(path).parts}
    name = Path(path).name.lower()
    return (
        bool(parts & CANONICAL_TEST_DIR_NAMES)
        or (bool(parts & AMBIGUOUS_TEST_DIR_NAMES) and any(marker in lower_path for marker in TEST_FILE_MARKERS))
        or name.startswith("test_")
        or any(marker in lower_path for marker in TEST_FILE_MARKERS)
    )


def _is_dispatcher_file(path: str) -> bool:
    return Path(path).name in DISPATCHER_FILES


def _is_runtime_entry_file(path: str) -> bool:
    return Path(path).name in RUNTIME_ENTRY_FILES


def _module_is_test_like(name: str, files: list[str]) -> bool:
    parts = {part.lower() for part in Path(name).parts}
    if bool(parts & CANONICAL_TEST_DIR_NAMES) or name.endswith("tests"):
        return True
    if bool(parts & AMBIGUOUS_TEST_DIR_NAMES):
        return any(_is_test_file(path) for path in files)
    return False


def _manifest_files(files: list[str]) -> list[str]:
    return [path for path in files if _is_manifest_file(path)]


def _test_files(files: list[str]) -> list[str]:
    return [path for path in files if _is_test_file(path)]


def _downstream_files(files: list[str], entry_points: list[str]) -> list[str]:
    return [
        path
        for path in files
        if path not in entry_points and not _is_manifest_file(path) and not _is_test_file(path)
    ]


def _guess_entry_points(files: list[str]) -> list[str]:
    def rank(path: str) -> tuple[int, str]:
        if _is_runtime_entry_file(path) and not _is_test_file(path):
            return (0, path)
        if Path(path).name in BOUNDARY_FILES and not _is_test_file(path):
            return (1, path)
        if not _is_dispatcher_file(path) and not _is_manifest_file(path) and not _is_test_file(path):
            return (2, path)
        if _is_manifest_file(path):
            return (3, path)
        return (4, path)

    ordered = sorted(_unique_strings(files), key=rank)
    return ordered[:MAX_ENTRY_POINTS]


def _guess_summary(name: str, files: list[str], entry_points: list[str], notable_files: list[str]) -> str:
    entry_example = _format_path_examples(entry_points or notable_files or files, limit=2)
    manifest_example = _format_path_examples(_manifest_files(files), limit=1)
    test_example = _format_path_examples(_test_files(files), limit=2)
    downstream_example = _format_path_examples(_downstream_files(notable_files, entry_points), limit=2)

    if name == "root":
        if entry_example and manifest_example and manifest_example not in entry_example:
            detail = f"先看 {entry_example} 定位入口，再结合 {manifest_example} 确认全局配置。"
        else:
            detail = f"先看 {entry_example or manifest_example or '根目录代表文件'} 定位入口与配置。"
    elif _module_is_test_like(name, files):
        detail = f"先看 {test_example or entry_example or '测试文件'} 定位回归入口，再回到对应实现模块。"
    elif entry_example and downstream_example and downstream_example not in entry_example:
        detail = f"先看 {entry_example}，再下钻 {downstream_example}。"
    elif entry_example and manifest_example and manifest_example not in entry_example:
        detail = f"先看 {entry_example}，必要时补读 {manifest_example}。"
    else:
        detail = f"先看 {entry_example or '代表文件'}。"
    return f"基于 {len(files)} 个跟踪文件生成的模块导航；{detail}"


def _guess_read_when(name: str, entry_points: list[str], files: list[str]) -> str:
    entry_example = _format_path_examples(entry_points or files, limit=2)
    manifest_example = _format_path_examples(_manifest_files(files), limit=1)
    test_example = _format_path_examples(_test_files(files), limit=2)
    downstream_example = _format_path_examples(_downstream_files(files, entry_points), limit=2)

    if name == "root":
        if entry_example and manifest_example and manifest_example not in entry_example:
            return f"当任务涉及项目入口、运行方式、全局配置或无法确定模块归属时阅读；先看 {entry_example}，必要时补读 {manifest_example}。"
        return f"当任务涉及项目入口、运行方式、全局配置或无法确定模块归属时阅读；先看 {entry_example or manifest_example or '根目录代表文件'}。"
    if _module_is_test_like(name, files):
        return f"当任务涉及回归范围、测试入口或需要确认行为覆盖时阅读；先看 {test_example or entry_example or '测试文件'}，再回到对应实现模块。"
    if entry_example and downstream_example and downstream_example not in entry_example:
        return f"当任务涉及 {name} 的职责、入口或调用链时阅读；先看 {entry_example}，再继续 {downstream_example}。"
    if entry_example and manifest_example and manifest_example not in entry_example:
        return f"当任务涉及 {name} 的入口、依赖边界或构建形态时阅读；先看 {entry_example}，必要时补读 {manifest_example}。"
    return f"当任务涉及 {name} 的职责、边界或入口时阅读；优先从 {entry_example or '代表文件'} 开始。"


def _guess_read_order(entry_points: list[str], notable_files: list[str]) -> list[str]:
    ordered = []
    for path in entry_points + _downstream_files(notable_files, entry_points) + _manifest_files(notable_files) + _test_files(notable_files) + notable_files:
        if path not in ordered:
            ordered.append(path)
    return ordered[:MAX_READ_ORDER]


def _guess_constraints(name: str, files: list[str], entry_points: list[str]) -> list[str]:
    constraints = []
    entry_example = _format_path_examples(entry_points, limit=2)
    dispatcher_example = _format_path_examples([path for path in entry_points if _is_dispatcher_file(path)], limit=2)
    downstream_example = _format_path_examples(_downstream_files(files, entry_points), limit=2)
    manifest_example = _format_path_examples(_manifest_files(files), limit=2)

    if _module_is_test_like(name, files):
        constraints.append("tests 用于定位行为与回归入口，确认测试后仍需回到实现模块。")
    if dispatcher_example and downstream_example:
        constraints.append(f"先用 {dispatcher_example} 确认入口或装配方式，再继续下钻 {downstream_example}。")
    elif entry_example:
        constraints.append(f"先从 {entry_example} 确认阅读起点，再决定是否继续下钻。")
    if manifest_example:
        constraints.append(f"涉及依赖、构建或发布边界时，补读 {manifest_example}。")
    if name == "root":
        constraints.append("root 只提供全局入口与全局配置线索，不能替代具体业务模块。")
    return _unique_strings(constraints)[:3] or ["先从代表文件确认职责，再决定是否扩大阅读范围。"]


def _guess_risks(name: str, files: list[str], entry_points: list[str]) -> list[str]:
    risks = []
    test_example = _format_path_examples(_test_files(files), limit=2)
    dispatcher_example = _format_path_examples([path for path in entry_points if _is_dispatcher_file(path)], limit=2)
    downstream_example = _format_path_examples(_downstream_files(files, entry_points), limit=2)
    manifest_example = _format_path_examples(_manifest_files(files), limit=2)

    if name == "root":
        risks.append("root 入口容易让人误以为已经掌握业务细节，实际仍需下钻具体模块。")
    if _module_is_test_like(name, files):
        risks.append(f"测试文件 {test_example or '测试文件'} 只说明验证切口，仍需回到被测实现。")
    elif test_example:
        risks.append(f"测试锚点 {test_example} 只反映验证方式，不等于真实运行入口。")
    if dispatcher_example:
        risks.append(f"入口文件 {dispatcher_example} 可能只负责装配或导出，真实规则在 {downstream_example or '下游实现文件'}。")
    if manifest_example:
        risks.append(f"清单文件 {manifest_example} 能说明依赖与边界，但不能代替运行时逻辑。")
    return _unique_strings(risks)[:3] or [f"若只根据目录名 {name} 理解模块，容易忽略真实入口与隐含约束。"]


def _guess_verification_focus(name: str, entry_points: list[str], files: list[str]) -> list[str]:
    focuses = []
    test_example = _format_path_examples(_test_files(files), limit=2)
    manifest_example = _format_path_examples(_manifest_files(files), limit=1)

    if _module_is_test_like(name, files):
        focuses.append(f"确认测试入口 {test_example or '测试文件'} 是否覆盖当前任务涉及的行为与回归范围。")
        return _unique_strings(focuses)[:2]
    if test_example:
        focuses.append(f"对照测试锚点 {test_example}，确认当前改动仍被回归覆盖。")
    if manifest_example:
        focuses.append(f"确认 {manifest_example} 声明的边界或入口没有与改动范围失配。")
    focuses.append("确认改动后需要补测或回归的关键路径。")
    return _unique_strings(focuses)[:3]


def _guess_related_memory(name: str, files: list[str]) -> list[str]:
    refs = ["docs/architect/decisions.md"]
    if _module_is_test_like(name, files):
        refs.append("docs/qa/strategy.md")
    else:
        refs.append("docs/dev/conventions.md")
    return refs


def _compute_structure_hash(files: list[str]) -> str:
    """SHA-256 prefix (8 hex chars) of the sorted file list."""
    joined = "\n".join(sorted(files))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


def _describe_file(path: str, entry_points: list[str]) -> str:
    name = Path(path).name
    if _is_manifest_file(path):
        return "依赖/构建清单"
    if _is_test_file(path):
        return "测试锚点"
    if path in entry_points and name == "__init__.py":
        return "模块边界入口"
    if path in entry_points and _is_dispatcher_file(path):
        return "入口/装配层"
    if path in entry_points:
        return "优先阅读入口"
    return "代表实现文件"


def _build_module(name: str, files: list[str], prefix: str) -> dict:
    notable_files = _pick_notable_files(files, prefix)
    entry_points = _guess_entry_points(notable_files)
    summary = _guess_summary(name, files, entry_points, notable_files)
    return {
        "name": name,
        "summary": summary,
        "total_files": len(files),
        "generator_version": MODULE_CARD_GENERATOR_VERSION,
        "structure_hash": _compute_structure_hash(files),
        "dir_tree": _build_dir_tree(files, prefix),
        "files": [{"path": path, "description": _describe_file(path, entry_points)} for path in notable_files],
        "read_when": _guess_read_when(name, entry_points, files),
        "entry_points": entry_points,
        "read_order": _guess_read_order(entry_points, notable_files),
        "implicit_constraints": _guess_constraints(name, files, entry_points),
        "known_risks": _guess_risks(name, files, entry_points),
        "verification_focus": _guess_verification_focus(name, entry_points, files),
        "related_memory": _guess_related_memory(name, files),
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
        return
    envelope.ok(result)
