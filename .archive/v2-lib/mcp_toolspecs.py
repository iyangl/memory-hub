"""Tool specifications for the local MCP server."""

from __future__ import annotations

TOOLS = [
    {
        "name": "read_memory",
        "description": "Read system boot projection, docs, catalog, or an approved durable memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string"},
                "uri": {"type": "string"},
                "anchor": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_memory",
        "description": "Search docs lane, durable lane, or both with unified refs and local hybrid recall.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "scope": {"type": "string", "enum": ["docs", "durable", "all"]},
                "type": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_memory",
        "description": "Create a durable memory proposal instead of writing directly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "recall_when": {"type": "string"},
                "why_not_in_code": {"type": "string"},
                "source_reason": {"type": "string"},
            },
            "required": ["type", "title", "content", "recall_when", "why_not_in_code", "source_reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_memory_update",
        "description": "Create a patch/append update proposal for an approved durable memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "append": {"type": "string"},
                "recall_when": {"type": "string"},
                "why_not_in_code": {"type": "string"},
                "source_reason": {"type": "string"},
            },
            "required": ["uri", "source_reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "capture_memory",
        "description": "Unified write entry for docs-only, durable-only, or dual-write capture.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["auto", "docs", "durable"]},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "reason": {"type": "string"},
                "doc_domain": {"type": "string"},
                "memory_type": {"type": "string"},
                "recall_when": {"type": "string"},
                "why_not_in_code": {"type": "string"},
            },
            "required": ["kind", "title", "content", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_memory",
        "description": "Unified update entry for docs lane or durable lane.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string"},
                "mode": {"type": "string", "enum": ["patch", "append"]},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "append": {"type": "string"},
                "reason": {"type": "string"},
                "recall_when": {"type": "string"},
                "why_not_in_code": {"type": "string"},
            },
            "required": ["ref", "mode", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_memory_review",
        "description": "Load a structured review summary for a pending durable proposal or docs change review.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "integer", "minimum": 1},
                "ref": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]
