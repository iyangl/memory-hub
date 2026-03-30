"""Path constants and validation for .memory/ structure."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

# Valid bucket names
BUCKETS = ("pm", "architect", "dev", "qa")

# Base files that init creates and cannot be deleted/renamed
BASE_FILES: dict[str, list[str]] = {
    "pm": ["decisions.md"],
    "architect": ["tech-stack.md", "decisions.md"],
    "dev": ["conventions.md"],
    "qa": ["strategy.md"],
}

# Catalog / memory paths
CATALOG_DIR = "catalog"
TOPICS_FILE = "topics.md"
MODULES_DIR = "modules"
DOCS_DIR = "docs"
MANIFEST_FILE = "manifest.json"
INBOX_DIR = "inbox"
SESSION_DIR = "session"
BRIEF_FILE = "BRIEF.md"


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


def inbox_root(project_root: Path | None = None) -> Path:
    """Return the .memory/inbox/ directory path."""
    return memory_root(project_root) / INBOX_DIR


def session_root(project_root: Path | None = None) -> Path:
    """Return the .memory/session/ directory path."""
    return memory_root(project_root) / SESSION_DIR


def session_file_path(slug: str, suffix: str = ".json", project_root: Path | None = None) -> Path:
    """Return path to .memory/session/<slug><suffix>."""
    return session_root(project_root) / f"{slug}{suffix}"


def brief_path(project_root: Path | None = None) -> Path:
    """Return path to .memory/BRIEF.md."""
    return memory_root(project_root) / BRIEF_FILE


def validate_docs_filename(filename: str) -> str | None:
    """Return error code if a docs filename is invalid, None if valid."""
    if not isinstance(filename, str):
        return "INVALID_DOCS_FILENAME"

    candidate = filename.strip()
    if not candidate:
        return "INVALID_DOCS_FILENAME"

    if candidate != Path(candidate).name:
        return "INVALID_DOCS_FILENAME"

    posix = PurePosixPath(candidate)
    windows = PureWindowsPath(candidate)
    if posix.is_absolute() or windows.is_absolute():
        return "INVALID_DOCS_FILENAME"

    if any(part == ".." for part in posix.parts) or any(part == ".." for part in windows.parts):
        return "INVALID_DOCS_FILENAME"

    if any(separator in candidate for separator in ("/", "\\")):
        return "INVALID_DOCS_FILENAME"

    return None


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
