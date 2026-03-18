"""URI helpers for durable memory."""

from __future__ import annotations

import re
from typing import Iterable

from lib.durable_errors import DurableMemoryError

MEMORY_TYPES = ("identity", "decision", "constraint", "preference")
SYSTEM_BOOT_URI = "system://boot"
TYPE_ORDER = {"identity": 0, "constraint": 1, "decision": 2, "preference": 3}
_URI_PATTERN = re.compile(r"^(identity|decision|constraint|preference)://([a-z0-9-]+)$")


def validate_memory_type(memory_type: str) -> str:
    """Validate durable memory type."""
    value = str(memory_type or "").strip().lower()
    if value not in MEMORY_TYPES:
        raise DurableMemoryError("INVALID_TYPE", f"Invalid durable memory type: {memory_type}")
    return value


def parse_memory_uri(uri: str) -> tuple[str, str]:
    """Parse a durable memory URI."""
    value = str(uri or "").strip()
    if value == SYSTEM_BOOT_URI:
        raise DurableMemoryError("INVALID_URI", "system://boot is not a writable durable memory URI")
    match = _URI_PATTERN.match(value)
    if not match:
        raise DurableMemoryError("INVALID_URI", f"Invalid durable memory URI: {uri}")
    return match.group(1), match.group(2)


def is_system_boot_uri(uri: str) -> bool:
    """Return whether the URI is system://boot."""
    return str(uri or "").strip() == SYSTEM_BOOT_URI


def make_memory_uri(memory_type: str, slug: str) -> str:
    """Build a durable memory URI."""
    return f"{validate_memory_type(memory_type)}://{slug}"


def slugify_title(title: str) -> str:
    """Convert a title to kebab-case slug."""
    lowered = re.sub(r"[^a-z0-9]+", "-", str(title or "").strip().lower())
    slug = lowered.strip("-")
    return slug or "item"


def reserve_memory_uri(memory_type: str, title: str, existing_uris: Iterable[str]) -> str:
    """Reserve a stable URI against existing approved and pending URIs."""
    base_slug = slugify_title(title)
    used = {str(item).strip() for item in existing_uris if str(item).strip()}
    candidate = make_memory_uri(memory_type, base_slug)
    if candidate not in used:
        return candidate

    suffix = 2
    while True:
        candidate = make_memory_uri(memory_type, f"{base_slug}-{suffix}")
        if candidate not in used:
            return candidate
        suffix += 1
