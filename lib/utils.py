"""Shared utility functions for memory-hub."""

from __future__ import annotations

from pathlib import Path


def atomic_write(filepath: Path, content: str) -> None:
    """Write content atomically: write to .tmp then rename."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    if filepath.exists():
        filepath.unlink()
    tmp_path.rename(filepath)
