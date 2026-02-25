"""Path constants and validation for .memory/ structure."""

from __future__ import annotations

from pathlib import Path

# Valid bucket names
BUCKETS = ("pm", "architect", "dev", "qa")

# Base files that init creates and cannot be deleted/renamed
BASE_FILES: dict[str, list[str]] = {
    "pm": ["decisions.md"],
    "architect": ["tech-stack.md", "decisions.md"],
    "dev": ["conventions.md"],
    "qa": ["strategy.md"],
}

# Catalog paths
CATALOG_DIR = "catalog"
TOPICS_FILE = "topics.md"
MODULES_DIR = "modules"


def memory_root(project_root: Path | None = None) -> Path:
    """Return the .memory/ directory path."""
    root = project_root or Path.cwd()
    return root / ".memory"


def bucket_path(bucket: str, project_root: Path | None = None) -> Path:
    """Return path to a bucket directory. Does not validate existence."""
    return memory_root(project_root) / bucket


def file_path(bucket: str, filename: str, project_root: Path | None = None) -> Path:
    """Return path to a file within a bucket."""
    return bucket_path(bucket, project_root) / filename


def catalog_path(project_root: Path | None = None) -> Path:
    """Return path to catalog/ directory."""
    return memory_root(project_root) / CATALOG_DIR


def topics_path(project_root: Path | None = None) -> Path:
    """Return path to catalog/topics.md."""
    return catalog_path(project_root) / TOPICS_FILE


def modules_path(project_root: Path | None = None) -> Path:
    """Return path to catalog/modules/ directory."""
    return catalog_path(project_root) / MODULES_DIR


def module_file_path(module_name: str, project_root: Path | None = None) -> Path:
    """Return path to catalog/modules/<name>.md."""
    return modules_path(project_root) / f"{module_name}.md"


def validate_bucket(bucket: str) -> str | None:
    """Return error code if bucket is invalid, None if valid."""
    if bucket not in BUCKETS:
        return "INVALID_BUCKET"
    return None


def is_base_file(bucket: str, filename: str) -> bool:
    """Check if a file is a protected base file."""
    return filename in BASE_FILES.get(bucket, [])
