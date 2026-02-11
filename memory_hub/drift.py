from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List

from .catalog_indexer import SUPPORTED_SUFFIXES, iter_source_files


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_supported_relative_paths(workspace_root: Path) -> Iterable[Path]:
    root = workspace_root.resolve()
    for full_path in iter_source_files(root):
        if full_path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield full_path.relative_to(root)


def _filter_supported_paths(raw_paths: Iterable[str]) -> List[str]:
    normalized = []
    for raw in raw_paths:
        value = raw.strip()
        if not value:
            continue
        suffix = Path(value).suffix.lower()
        if suffix in SUPPORTED_SUFFIXES:
            normalized.append(value)
    return sorted(set(normalized))


def _run_git_command(workspace_root: Path, args: List[str]) -> List[str]:
    proc = subprocess.run(
        ["git", "-C", str(workspace_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.splitlines()


def _detect_with_git_diff(workspace_root: Path) -> Dict[str, object]:
    tracked_lines = _run_git_command(workspace_root, ["diff", "--name-only", "HEAD"])
    untracked_lines = _run_git_command(
        workspace_root,
        ["ls-files", "--others", "--exclude-standard"],
    )
    changed = _filter_supported_paths([*tracked_lines, *untracked_lines])

    return {
        "method": "git_diff",
        "changed_files": changed,
        "drift_score": 0.0,  # set by caller with denominator awareness
    }


def _detect_with_hash(
    workspace_root: Path,
    known_hashes: Dict[str, str],
) -> Dict[str, object]:
    root = workspace_root.resolve()
    current_hashes: Dict[str, str] = {}
    for rel_path in _iter_supported_relative_paths(root):
        path = root / rel_path
        try:
            current_hashes[rel_path.as_posix()] = _hash_file(path)
        except OSError:
            continue

    known_keys = set(known_hashes.keys())
    current_keys = set(current_hashes.keys())
    all_keys = known_keys | current_keys

    changed = []
    for key in sorted(all_keys):
        if known_hashes.get(key) != current_hashes.get(key):
            changed.append(key)

    denominator = max(len(all_keys), 1)
    score = len(changed) / denominator

    return {
        "method": "hash_compare",
        "changed_files": changed,
        "drift_score": score,
        "total_files": len(all_keys),
    }


def detect_drift(workspace_root: Path, known_hashes: Dict[str, str]) -> Dict[str, object]:
    root = workspace_root.resolve()

    try:
        git_result = _detect_with_git_diff(root)
        changed_files: List[str] = list(git_result["changed_files"])
        denominator = max(len(known_hashes), 1)
        drift_score = min(len(changed_files) / denominator, 1.0)
        return {
            "method": "git_diff",
            "changed_files": changed_files,
            "drift_score": drift_score,
            "total_files": len(known_hashes),
        }
    except Exception:
        return _detect_with_hash(root, known_hashes)
