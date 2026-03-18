"""Context loading for decision discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any

from lib.durable_errors import DurableMemoryError
from lib.project_memory_projection import refresh_boot_projection, refresh_search_projection


@dataclass(slots=True)
class DiscoveryContext:
    """Minimal read-only context for discovery detectors."""

    project_root: Path
    changed_files: list[str]
    diff_text: str
    summary: str
    docs_entries: list[dict[str, Any]]
    durable_entries: list[dict[str, Any]]
    boot_items: list[dict[str, Any]]


def build_discovery_context(project_root: Path, *, summary: str = "") -> DiscoveryContext:
    """Build discovery context from git diff and current memory projections."""
    changed_files = _collect_changed_files(project_root)
    diff_text = _collect_diff_text(project_root, changed_files)
    search_projection = refresh_search_projection(project_root)
    boot_projection = refresh_boot_projection(project_root)
    entries = list(search_projection.get("entries", []))
    return DiscoveryContext(
        project_root=project_root,
        changed_files=changed_files,
        diff_text=diff_text,
        summary=summary.strip(),
        docs_entries=[entry for entry in entries if entry.get("lane") == "docs"],
        durable_entries=[entry for entry in entries if entry.get("lane") == "durable"],
        boot_items=list(boot_projection.get("items", [])),
    )


def _collect_changed_files(project_root: Path) -> list[str]:
    tracked = _run_git(
        project_root,
        "diff",
        "--name-only",
        "--relative",
        "HEAD",
        "--",
    ).splitlines()
    staged = _run_git(
        project_root,
        "diff",
        "--name-only",
        "--cached",
        "--relative",
        "HEAD",
        "--",
    ).splitlines()
    untracked = _run_git(
        project_root,
        "ls-files",
        "--others",
        "--exclude-standard",
    ).splitlines()
    return sorted({path.strip() for path in tracked + staged + untracked if path.strip()})


def _collect_diff_text(project_root: Path, changed_files: list[str]) -> str:
    tracked = _run_git(
        project_root,
        "diff",
        "--no-ext-diff",
        "--relative",
        "HEAD",
        "--",
    )
    staged = _run_git(
        project_root,
        "diff",
        "--cached",
        "--no-ext-diff",
        "--relative",
        "HEAD",
        "--",
    )
    tracked_paths = set(
        _run_git(project_root, "ls-files").splitlines()
        + _run_git(project_root, "diff", "--name-only", "--relative", "HEAD", "--").splitlines()
        + _run_git(project_root, "diff", "--name-only", "--cached", "--relative", "HEAD", "--").splitlines()
    )
    synthetic = [_synthetic_untracked_patch(project_root, path) for path in changed_files if path not in tracked_paths]
    return "\n".join(part for part in [tracked, staged, *synthetic] if part.strip())


def _synthetic_untracked_patch(project_root: Path, relative_path: str) -> str:
    file_path = project_root / relative_path
    if not file_path.exists() or not file_path.is_file():
        return ""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"diff --git a/{relative_path} b/{relative_path}\nBinary files differ\n"
    lines = content.splitlines()
    body = "\n".join(f"+{line}" for line in lines)
    header = [
        f"diff --git a/{relative_path} b/{relative_path}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{relative_path}",
        f"@@ -0,0 +1,{max(len(lines), 1)} @@",
    ]
    return "\n".join(header + ([body] if body else ["+"]))


def _run_git(project_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise DurableMemoryError(
            "DISCOVERY_GIT_UNAVAILABLE",
            "git is required for decision discovery.",
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        message = "Decision discovery requires a git repository with a readable diff."
        raise DurableMemoryError(
            "DISCOVERY_GIT_FAILED",
            message,
            details={"stderr": stderr},
        ) from exc
    return result.stdout
