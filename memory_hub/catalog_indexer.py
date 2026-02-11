from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

SUPPORTED_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".dart"}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    ".dart_tool",
    ".venv",
    "venv",
    "__pycache__",
}
MAX_FILE_BYTES = 1_000_000

_IMPORT_FROM_RE = re.compile(r"import\s+[^;\n]*?from\s+['\"]([^'\"]+)['\"]")
_IMPORT_SIDE_RE = re.compile(r"import\s+['\"]([^'\"]+)['\"]")
_REQUIRE_RE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")


def infer_language(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".dart": "dart",
    }
    return mapping.get(suffix, "text")


def iter_source_files(workspace_root: Path) -> Iterable[Path]:
    root = workspace_root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _hash_file_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_imports_python(text: str) -> List[Dict[str, Any]]:
    imports: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "to_module": alias.name,
                        "confidence": 1.0,
                        "source_type": "ast",
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(
                    {
                        "to_module": node.module,
                        "confidence": 1.0,
                        "source_type": "ast",
                    }
                )
    return imports


def _extract_imports_inferred(text: str) -> List[Dict[str, Any]]:
    matches = []
    for pattern in (_IMPORT_FROM_RE, _IMPORT_SIDE_RE, _REQUIRE_RE):
        matches.extend(pattern.findall(text))

    unique_modules = sorted({str(module).strip() for module in matches if str(module).strip()})
    return [
        {
            "to_module": module,
            "confidence": 0.5,
            "source_type": "inferred",
        }
        for module in unique_modules
    ]


def extract_imports(language: str, text: str) -> List[Dict[str, Any]]:
    if language == "python":
        imports = _extract_imports_python(text)
        if imports:
            return imports
    return _extract_imports_inferred(text)


def build_catalog_snapshot(
    workspace_root: Path,
    files_hint: Sequence[str] | None = None,
) -> Dict[str, Any]:
    root = workspace_root.resolve()
    # files_hint is accepted for future incremental refresh; minimal implementation does full scan.
    _ = files_hint

    files: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    for file_path in iter_source_files(root):
        rel = file_path.relative_to(root).as_posix()
        text = _read_text(file_path)
        language = infer_language(file_path)
        imports = extract_imports(language, text)

        files.append(
            {
                "file_path": rel,
                "file_hash": _hash_file_bytes(file_path),
                "language": language,
                "import_count": len(imports),
            }
        )

        for item in imports:
            edges.append(
                {
                    "from_file": rel,
                    "to_module": item["to_module"],
                    "edge_type": "import",
                    "confidence": float(item["confidence"]),
                    "source_type": item["source_type"],
                }
            )

    return {
        "workspace_root": root,
        "files": files,
        "edges": edges,
        "full_rebuild": True,
    }
