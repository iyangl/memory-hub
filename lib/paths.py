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
DOCS_DIR = "docs"
STORE_DIR = "_store"
PROJECTIONS_DIR = "projections"
MANIFEST_FILE = "manifest.json"
MEMORY_DB_FILE = "memory.db"
BOOT_PROJECTION_FILE = "boot.json"
SEARCH_PROJECTION_FILE = "search.json"


def memory_root(project_root: Path | None = None) -> Path:
    """Return the .memory/ directory path."""
    root = project_root or Path.cwd()
    return root / ".memory"


def docs_root(project_root: Path | None = None) -> Path:
    """Return the .memory/docs/ directory path."""
    return memory_root(project_root) / DOCS_DIR


def bucket_path(bucket: str, project_root: Path | None = None) -> Path:
    """Return path to a bucket directory. Does not validate existence."""
    return docs_root(project_root) / bucket


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


def manifest_path(project_root: Path | None = None) -> Path:
    """Return path to .memory/manifest.json."""
    return memory_root(project_root) / MANIFEST_FILE


def store_root(project_root: Path | None = None) -> Path:
    """Return the .memory/_store/ directory path."""
    return memory_root(project_root) / STORE_DIR


def store_db_path(project_root: Path | None = None) -> Path:
    """Return path to .memory/_store/memory.db."""
    return store_root(project_root) / MEMORY_DB_FILE


def projections_root(project_root: Path | None = None) -> Path:
    """Return path to .memory/_store/projections/."""
    return store_root(project_root) / PROJECTIONS_DIR


def boot_projection_path(project_root: Path | None = None) -> Path:
    """Return path to the boot projection JSON file."""
    return projections_root(project_root) / BOOT_PROJECTION_FILE


def search_projection_path(project_root: Path | None = None) -> Path:
    """Return path to the search projection JSON file."""
    return projections_root(project_root) / SEARCH_PROJECTION_FILE


def docs_file_ref(bucket: str, filename: str) -> str:
    """Build a catalog ref for a docs-lane file."""
    return f"{DOCS_DIR}/{bucket}/{filename}"


def parse_docs_file_ref(file_ref: str) -> tuple[str, str] | None:
    """Parse docs/<bucket>/<file>.md refs into bucket and filename."""
    parts = file_ref.split("/")
    if len(parts) != 3 or parts[0] != DOCS_DIR or parts[1] not in BUCKETS:
        return None
    return parts[1], parts[2]


def validate_bucket(bucket: str) -> str | None:
    """Return error code if bucket is invalid, None if valid."""
    if bucket not in BUCKETS:
        return "INVALID_BUCKET"
    return None


def is_base_file(bucket: str, filename: str) -> bool:
    """Check if a file is a protected base file."""
    return filename in BASE_FILES.get(bucket, [])
