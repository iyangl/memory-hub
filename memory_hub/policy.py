from __future__ import annotations

from typing import Any, Dict, List, Literal, Sequence

RoleType = Literal["pm", "architect", "dev", "qa"]
TaskType = Literal["planning", "design", "implement", "test", "review", "auto"]

VALID_TASK_TYPES = {"planning", "design", "implement", "test", "review", "auto"}
VALID_ROLES = {"pm", "architect", "dev", "qa"}

_TASK_KEYWORDS = {
    "planning": [
        "plan",
        "planning",
        "roadmap",
        "milestone",
        "scope",
        "requirement",
        "需求",
        "规划",
        "里程碑",
    ],
    "design": [
        "design",
        "architecture",
        "schema",
        "interface",
        "api design",
        "架构",
        "设计",
        "方案",
        "接口",
    ],
    "implement": [
        "implement",
        "implementation",
        "code",
        "coding",
        "fix",
        "bugfix",
        "refactor",
        "write",
        "实现",
        "开发",
        "修复",
        "重构",
        "写代码",
    ],
    "test": [
        "test",
        "testing",
        "qa",
        "regression",
        "coverage",
        "验证",
        "测试",
        "回归",
    ],
    "review": [
        "review",
        "code review",
        "审查",
        "评审",
        "检查",
    ],
}


def resolve_task_type(task_prompt: str, requested_task_type: str | None) -> TaskType:
    requested = (requested_task_type or "auto").strip().lower()
    if requested in VALID_TASK_TYPES and requested != "auto":
        return requested  # type: ignore[return-value]

    text = (task_prompt or "").lower()
    for task_type, keywords in _TASK_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return task_type  # type: ignore[return-value]

    # Auto fallback should bias towards PM+Architect context.
    return "planning"


def roles_for_task(task_type: TaskType) -> List[RoleType]:
    mapping: Dict[str, List[RoleType]] = {
        "planning": ["pm", "architect"],
        "design": ["architect", "pm"],
        "implement": ["architect", "dev"],
        "test": ["qa", "dev", "architect"],
        "review": ["qa", "dev", "architect"],
        "auto": ["pm", "architect"],
    }
    return mapping.get(task_type, ["pm", "architect"])


def truncate_to_budget(text: str, max_tokens: int) -> str:
    max_chars = max(400, max_tokens * 4)
    if len(text) <= max_chars:
        return text
    suffix = "\n... (truncated)"
    return text[: max_chars - len(suffix)] + suffix


def build_context_brief(
    role_payloads: Sequence[Dict[str, Any]],
    open_loops_top: Sequence[Dict[str, Any]],
    handoff_latest: Dict[str, Any] | None,
    max_tokens: int,
) -> str:
    lines: List[str] = []
    lines.append("[Context Brief]")

    if role_payloads:
        lines.append("Roles:")
        for role_block in role_payloads:
            role = role_block.get("role", "unknown")
            items = role_block.get("items", [])
            lines.append(f"- {role}:")
            if not items:
                lines.append("  (no items)")
                continue
            for item in items[:6]:
                key = item.get("memory_key", "unknown_key")
                value = item.get("value")
                value_text = value if isinstance(value, str) else repr(value)
                lines.append(f"  - {key}: {value_text}")

    if open_loops_top:
        lines.append("Open Loops (Top):")
        for loop in open_loops_top[:3]:
            loop_id = loop.get("loop_id")
            title = loop.get("title", "")
            priority = loop.get("priority", "")
            lines.append(f"- [{priority}] {title} ({loop_id})")

    if handoff_latest:
        lines.append("Latest Handoff:")
        summary = handoff_latest.get("summary", {})
        summary_text = summary if isinstance(summary, str) else repr(summary)
        lines.append(f"- {summary_text}")

    return truncate_to_budget("\n".join(lines), max_tokens=max_tokens)


def normalize_role(role: str) -> RoleType:
    role_value = (role or "").strip().lower()
    if role_value not in VALID_ROLES:
        raise ValueError(f"invalid role: {role}")
    return role_value  # type: ignore[return-value]
