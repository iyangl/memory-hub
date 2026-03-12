"""Signal detectors for decision discovery."""

from __future__ import annotations

import re
from typing import Any

from lib.discovery_context import DiscoveryContext

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff\-]+")
RULE_MARKERS = ("默认", "必须", "禁止", "不允许", "只能", "决定", "约束", "default", "must", "never")
EXCEPTION_MARKERS = ("实时", "realtime", "websocket", "socket", "stream", "长连接", "channel", "订阅")
RULE_FILLERS = ("默认", "现在", "目前", "仍", "继续", "必须", "应该", "使用", "走", "采用", "允许", "统一")
ALTERNATIVE_GROUPS = (
    ("https", "http", "ws", "wss", "grpc", "tcp", "udp"),
    ("legacy pipeline", "unified write lane"),
)
CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1}


def detect_signals(context: DiscoveryContext) -> list[dict[str, Any]]:
    """Detect high-value discovery candidates from current context."""
    candidates = []
    candidates.extend(detect_default_rule_broken(context))
    candidates.extend(detect_exception_rules(context))
    candidates.extend(detect_docs_drift(context))
    return candidates


def detect_default_rule_broken(context: DiscoveryContext) -> list[dict[str, Any]]:
    """Detect likely violations of existing default rules."""
    combined = _combined_text(context)
    candidates: list[dict[str, Any]] = []
    if _has_exception_context(context):
        return candidates
    for entry in _knowledge_entries(context):
        if not _looks_like_default_rule(entry):
            continue
        conflict = _find_conflict(entry, combined)
        if conflict is None:
            continue
        old_term, new_term = conflict
        candidates.append(
            _candidate(
                signal_kind="default-rule-broken",
                candidate_type="new-rule",
                title=f"默认规则可能被打破：{old_term} -> {new_term}",
                summary=f"{entry['ref']} 当前把 {old_term} 视为默认规则，但工作区变更引入了 {new_term}。",
                reason="现有知识中存在默认规则，新变更出现了与默认规则不一致的实现。",
                suggested_route=_suggested_route(entry),
                target_ref=_target_ref(entry),
                evidence=_evidence(entry, context, old_term, new_term),
                confidence="high" if context.summary else "medium",
            )
        )
    return candidates


def detect_exception_rules(context: DiscoveryContext) -> list[dict[str, Any]]:
    """Detect scoped exception candidates instead of full rule replacements."""
    combined = _combined_text(context)
    candidates: list[dict[str, Any]] = []
    if not _has_exception_context(context):
        return candidates
    for entry in _knowledge_entries(context):
        if not _looks_like_default_rule(entry):
            continue
        conflict = _find_conflict(entry, combined)
        if conflict is None:
            continue
        old_term, new_term = conflict
        candidates.append(
            _candidate(
                signal_kind="exception-rule",
                candidate_type="exception-rule",
                title=f"可能出现新的例外规则：{old_term} -> {new_term}",
                summary=f"{entry['ref']} 保持默认 {old_term}，但当前变更看起来在受限场景中引入了 {new_term}。",
                reason="检测到默认规则仍存在，但当前变更更像一个带范围的例外，而不是全局替换。",
                suggested_route=_suggested_route(entry),
                target_ref=_target_ref(entry),
                evidence=_evidence(entry, context, old_term, new_term),
                confidence="high" if context.summary else "medium",
            )
        )
    return candidates


def detect_docs_drift(context: DiscoveryContext) -> list[dict[str, Any]]:
    """Detect likely drift between docs and the current implementation."""
    if not context.summary or not _looks_like_rule_text(context.summary):
        return []
    summary_tokens = _tokens(context.summary)
    best_entry = _best_doc_match(context.docs_entries, summary_tokens)
    if best_entry is None:
        return []
    entry_text = f"{best_entry['title']}\n{best_entry['content']}".lower()
    novelty = _novel_terms(context.summary.lower(), entry_text)
    if not novelty:
        return []
    return [
        _candidate(
            signal_kind="docs-drift",
            candidate_type="docs-drift",
            title=f"文档可能已经偏离实现：{best_entry['ref']}",
            summary=f"{best_entry['ref']} 似乎仍描述旧规则，而当前摘要/变更提示出现了新的规则表述：{', '.join(novelty[:2])}。",
            reason="当前会话摘要与代码变更共同指向新的规则描述，但目标文档尚未包含对应表述。",
            suggested_route="dual-write" if _has_related_durable_ref(context, best_entry["ref"]) else "docs-only",
            target_ref=best_entry["ref"],
            evidence={
                "refs": [best_entry["ref"]],
                "changed_files": context.changed_files[:5],
                "doc_excerpt": _excerpt(best_entry["content"], novelty[0]),
                "summary_excerpt": context.summary[:200],
            },
            confidence="high" if len(novelty) > 1 else "medium",
        )
    ]


def _combined_text(context: DiscoveryContext) -> str:
    return "\n".join(part for part in [context.diff_text, context.summary] if part.strip()).lower()


def _knowledge_entries(context: DiscoveryContext) -> list[dict[str, Any]]:
    return [*context.docs_entries, *context.durable_entries]


def _looks_like_default_rule(entry: dict[str, Any]) -> bool:
    text = f"{entry['title']}\n{entry['content']}".lower()
    return "默认" in text or "default" in text


def _find_conflict(entry: dict[str, Any], combined_text: str) -> tuple[str, str] | None:
    entry_text = f"{entry['title']}\n{entry['content']}".lower()
    for group in ALTERNATIVE_GROUPS:
        old_term = next((term for term in group if term in entry_text), None)
        if old_term is None:
            continue
        new_term = next((term for term in group if term != old_term and term in combined_text), None)
        if new_term is not None:
            return old_term, new_term
    return None


def _has_exception_context(context: DiscoveryContext) -> bool:
    haystack = "\n".join(context.changed_files + [context.diff_text, context.summary]).lower()
    return any(marker in haystack for marker in EXCEPTION_MARKERS)


def _best_doc_match(entries: list[dict[str, Any]], summary_tokens: list[str]) -> dict[str, Any] | None:
    best_entry = None
    best_score = 0
    summary_set = set(_rule_tokens(" ".join(summary_tokens)))
    for entry in entries:
        entry_tokens = set(_rule_tokens(f"{entry['title']}\n{entry['content']}"))
        overlap = len(summary_set & entry_tokens)
        if overlap > best_score:
            best_entry = entry
            best_score = overlap
    return best_entry if best_score >= 1 else None


def _looks_like_rule_text(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in RULE_MARKERS)


def _novel_terms(summary_text: str, entry_text: str) -> list[str]:
    found: list[str] = []
    for group in ALTERNATIVE_GROUPS:
        for term in group:
            if term in summary_text and term not in entry_text:
                found.append(term)
    if found:
        return found
    summary_tokens = [token for token in _tokens(summary_text) if len(token) >= 4]
    return [token for token in summary_tokens if token not in entry_text][:3]


def _has_related_durable_ref(context: DiscoveryContext, doc_ref: str) -> bool:
    return any(entry.get("doc_ref") == doc_ref for entry in context.durable_entries)


def _suggested_route(entry: dict[str, Any]) -> str:
    if entry.get("lane") == "docs":
        return "docs-only"
    if entry.get("doc_ref") or entry.get("type") in {"constraint", "decision"}:
        return "dual-write"
    return "durable-only"


def _target_ref(entry: dict[str, Any]) -> str:
    return str(entry.get("doc_ref") or entry["ref"])


def _evidence(
    entry: dict[str, Any],
    context: DiscoveryContext,
    old_term: str,
    new_term: str,
) -> dict[str, Any]:
    return {
        "refs": [str(entry.get("ref"))],
        "changed_files": context.changed_files[:5],
        "rule_excerpt": _excerpt(str(entry["content"]), old_term),
        "diff_excerpt": _excerpt(context.diff_text or context.summary, new_term),
    }


def _excerpt(text: str, term: str) -> str:
    lowered = text.lower()
    needle = term.lower()
    index = lowered.find(needle)
    if index == -1:
        return text[:200].strip()
    start = max(index - 60, 0)
    end = min(index + len(term) + 80, len(text))
    return text[start:end].strip()


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _rule_tokens(text: str) -> list[str]:
    normalized = text.lower()
    for filler in RULE_FILLERS:
        normalized = normalized.replace(filler, " ")
    return _tokens(normalized)


def _candidate(
    *,
    signal_kind: str,
    candidate_type: str,
    title: str,
    summary: str,
    reason: str,
    suggested_route: str,
    target_ref: str | None,
    evidence: dict[str, Any],
    confidence: str,
) -> dict[str, Any]:
    return {
        "candidate_id": f"{signal_kind}:{target_ref or title}",
        "signal_kind": signal_kind,
        "candidate_type": candidate_type,
        "title": title,
        "summary": summary,
        "reason": reason,
        "suggested_route": suggested_route,
        "target_ref": target_ref,
        "evidence": evidence,
        "confidence": confidence,
    }


def sort_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort candidates by confidence and deterministic tie-breakers."""
    return sorted(
        items,
        key=lambda item: (
            -CONFIDENCE_ORDER.get(str(item["confidence"]), 0),
            str(item["signal_kind"]),
            str(item["target_ref"] or ""),
            str(item["title"]),
        ),
    )
