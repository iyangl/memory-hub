"""recall-plan — deprecated legacy command.

Usage: memory-hub recall-plan --task <task> [--project-root <path>] [--out <file>]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lib import envelope, paths
from lib.memory_search import search_docs
from lib.utils import atomic_write, fail_legacy_command

TASK_KIND_PATTERNS = (
    ("decide", ("方案", "决策", "改进", "重构", "设计", "风险", "取舍")),
    ("validate", ("测试", "验证", "回归", "assert", "test", "qa")),
    ("locate", ("哪里", "在哪", "find", "locate", "搜索", "定位")),
    ("understand", ("理解", "了解", "阅读", "看懂", "how", "为什么", "implementation")),
)
HIGH_RISK_PATTERNS = ("跨模块", "重构", "架构", "风险", "迁移", "验证", "回归")
SEARCH_FIRST_HINTS = (
    "别名", "别称", "原名", "旧称", "曾用名", "又叫", "也叫",
    "历史术语", "旧术语", "历史叫法", "旧叫法", "老叫法",
)
MATCH_STOPWORDS = frozenset({
    "任务", "模块", "文件", "入口", "逻辑", "功能", "对象", "来源", "代码", "项目",
    "方案", "决策", "改进", "重构", "设计", "风险", "取舍", "测试", "验证", "回归",
    "搜索", "定位", "理解", "了解", "阅读", "看懂", "where", "find", "locate",
    "implementation", "how", "为什么", "并", "和", "与", "及", "以及", "然后", "再", "的",
    *SEARCH_FIRST_HINTS,
})
MATCH_SPLIT_TERMS = tuple(
    sorted({
        *HIGH_RISK_PATTERNS,
        *SEARCH_FIRST_HINTS,
        *(keyword for _, keywords in TASK_KIND_PATTERNS for keyword in keywords),
        "并", "和", "与", "及", "以及", "然后", "再", "的",
    }, key=len, reverse=True)
)
MODULE_SECTION_HEADINGS = frozenset({"何时阅读", "推荐入口", "推荐阅读顺序", "隐含约束", "主要风险", "验证重点", "代表文件", "关联记忆"})



def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")



def _infer_task_kind(task: str) -> str:
    lower = task.lower()
    for kind, keywords in TASK_KIND_PATTERNS:
        if any(keyword.lower() in lower for keyword in keywords):
            return kind
    return "understand"



def _task_tokens(task: str) -> set[str]:
    chunks = re.findall(r"[A-Za-z0-9_\-/\.]+|[\u4e00-\u9fff]+", task.lower())
    tokens: set[str] = set()
    for chunk in chunks:
        parts = [chunk]
        if re.search(r"[\u4e00-\u9fff]", chunk) and MATCH_SPLIT_TERMS:
            parts = [chunk]
            for term in MATCH_SPLIT_TERMS:
                next_parts = []
                for part in parts:
                    next_parts.extend(re.split(re.escape(term), part))
                parts = next_parts
        for part in parts:
            token = part.strip()
            if len(token) < 2 or token in MATCH_STOPWORDS:
                continue
            tokens.add(token)
    return tokens



def _is_code_identifier_token(token: str) -> bool:
    if len(token) < 3:
        return False
    if token.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md")):
        return True
    if any(marker in token for marker in ("_", "/", ".")):
        return True
    return False



def _semantic_task_tokens(task: str) -> set[str]:
    return {token for token in _task_tokens(task) if not _is_code_identifier_token(token)}



def _identifier_task_tokens(task: str) -> set[str]:
    return {token for token in _task_tokens(task) if _is_code_identifier_token(token)}



def _token_match_score(tokens: set[str], text: str) -> int:
    if not tokens:
        return 0
    text_lower = text.lower()
    return sum(1 for token in tokens if token in text_lower)



def _match_breakdown(task: str, text: str) -> tuple[int, int]:
    return _token_match_score(_semantic_task_tokens(task), text), _token_match_score(_identifier_task_tokens(task), text)



def _match_score(task: str, text: str) -> int:
    semantic_score, identifier_score = _match_breakdown(task, text)
    return semantic_score * 2 + identifier_score



def _bucket_boost(task_kind: str, bucket: str) -> int:
    if task_kind == "decide":
        return 2 if bucket in {"architect", "pm"} else 0
    if task_kind == "validate":
        return 2 if bucket == "qa" else (1 if bucket == "pm" else 0)
    return 0



def _parse_brief_entries(project_root: Path | None) -> list[dict]:
    content = _read_text(paths.brief_path(project_root))
    entries = []
    current_bucket: str | None = None
    current_file: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_file, current_lines
        if current_bucket and current_file:
            summary = "\n".join(line for line in current_lines if line.strip()).strip()
            entries.append({
                "bucket": current_bucket,
                "file": current_file,
                "summary": summary,
            })
        current_file = None
        current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") and stripped[3:].strip() in paths.BUCKETS:
            flush()
            current_bucket = stripped[3:].strip()
            continue
        if stripped.startswith("### ") and current_bucket:
            flush()
            current_file = stripped[4:].strip()
            continue
        if current_file:
            current_lines.append(stripped)

    flush()
    return entries



def _parse_topics_module_line(line: str) -> dict | None:
    body = line[2:].strip()
    parts = [part.strip() for part in re.split(r"[；;]", body) if part.strip()]
    if not parts:
        return None
    return {
        "name": parts[0],
        "summary": parts[1] if len(parts) > 1 else "",
        "entry_points": re.findall(r"`([^`]+)`", body),
    }



def _parse_topics_knowledge_line(line: str, topic: str | None) -> dict | None:
    match = re.match(r"^-\s+(\S+?)\s+—\s+(.+)$", line.strip())
    if not match:
        return None
    file_ref = match.group(1)
    parsed = paths.parse_docs_file_ref(file_ref)
    if parsed is None:
        return None
    bucket, filename = parsed
    return {
        "topic": topic or "",
        "bucket": bucket,
        "file": filename,
        "summary": match.group(2).strip(),
    }



def _parse_topics(project_root: Path | None) -> tuple[list[dict], list[dict]]:
    content = _read_text(paths.topics_path(project_root))
    module_entries: list[dict] = []
    knowledge_entries: list[dict] = []
    section: str | None = None
    current_topic: str | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## 代码模块":
            section = "modules"
            current_topic = None
            continue
        if stripped == "## 知识文件":
            section = "knowledge"
            current_topic = None
            continue
        if stripped.startswith("## "):
            section = None
            current_topic = None
            continue
        if section == "modules" and stripped.startswith("- "):
            entry = _parse_topics_module_line(stripped)
            if entry:
                module_entries.append(entry)
            continue
        if section == "knowledge" and stripped.startswith("### "):
            current_topic = stripped[4:].strip()
            continue
        if section == "knowledge" and stripped.startswith("- "):
            entry = _parse_topics_knowledge_line(stripped, current_topic)
            if entry:
                knowledge_entries.append(entry)

    return module_entries, knowledge_entries



def _source_oriented_gap() -> str:
    return "当前任务主要依赖源码实现上下文，durable docs 无法稳定回答。"



def _has_strong_durable_signal(task: str, doc_matches: list[dict], module_matches: list[dict]) -> bool:
    semantic_tokens = _semantic_task_tokens(task)
    locator_text = _initial_locator_text(doc_matches, module_matches)
    if semantic_tokens and _token_match_score(semantic_tokens, locator_text) > 0:
        return True
    if any("BRIEF 命中" in item["reason"] or "topics 命中" in item["reason"] for item in doc_matches):
        return True
    return any(
        "topics 命中" in item["reason"] or "module card 命中" in item["reason"] or item.get("entry_points")
        for item in module_matches
    )



def _is_source_oriented_task(task: str, task_kind: str, doc_matches: list[dict], module_matches: list[dict]) -> bool:
    if task_kind not in {"understand", "locate"}:
        return False
    if any(keyword in task for keyword in SEARCH_FIRST_HINTS):
        return False
    if not _identifier_task_tokens(task):
        return False
    return not _has_strong_durable_signal(task, doc_matches, module_matches)



def _extract_module_name(module_card: str) -> str:
    first_line = module_card.splitlines()[0].strip()
    return first_line[2:].strip() if first_line.startswith("# ") else ""



def _extract_module_section_lines(module_card: str, heading: str) -> list[str]:
    lines = module_card.splitlines()
    current: str | None = None
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped[3:].strip()
            continue
        if current != heading or not stripped:
            continue
        if stripped.startswith("- `") and "`" in stripped[2:]:
            collected.append(stripped.split("`")[1])
        else:
            collected.append(stripped.lstrip("- ").strip())
    return collected



def _collect_module_cards(project_root: Path | None) -> list[dict]:
    modules_dir = paths.modules_path(project_root)
    if not modules_dir.exists():
        return []

    cards = []
    for file in sorted(modules_dir.glob("*.md")):
        content = _read_text(file)
        name = _extract_module_name(content) or file.stem
        cards.append({
            "name": name,
            "path": file,
            "read_when": " ".join(_extract_module_section_lines(content, "何时阅读")[:2]).strip(),
            "entry_points": _extract_module_section_lines(content, "推荐入口")[:3],
            "constraints": _extract_module_section_lines(content, "隐含约束")[:3],
            "risks": _extract_module_section_lines(content, "主要风险")[:3],
            "verification": _extract_module_section_lines(content, "验证重点")[:3],
        })
    return cards



def _collect_doc_matches(task: str, task_kind: str, project_root: Path | None) -> list[dict]:
    brief_entries = _parse_brief_entries(project_root)
    _, knowledge_entries = _parse_topics(project_root)
    candidates: dict[tuple[str, str], dict] = {}

    for entry in brief_entries:
        searchable = f"{entry['bucket']} {entry['file']} {entry['summary']}"
        semantic_score, identifier_score = _match_breakdown(task, searchable)
        if semantic_score <= 0 and (task_kind in {"understand", "locate"} or identifier_score <= 0):
            continue
        score = semantic_score * 2 + identifier_score
        key = (entry["bucket"], entry["file"])
        candidate = candidates.setdefault(key, {
            "bucket": entry["bucket"],
            "file": entry["file"],
            "score": 0,
            "reasons": [],
        })
        candidate["score"] += score + _bucket_boost(task_kind, entry["bucket"])
        candidate["reasons"].append(f"BRIEF 命中：{entry['summary'][:60] or entry['file']}")

    for entry in knowledge_entries:
        searchable = f"{entry['topic']} {entry['summary']} {entry['file']} {entry['bucket']}"
        semantic_score, identifier_score = _match_breakdown(task, searchable)
        if semantic_score <= 0 and (task_kind in {"understand", "locate"} or identifier_score <= 0):
            continue
        score = semantic_score * 2 + identifier_score
        key = (entry["bucket"], entry["file"])
        candidate = candidates.setdefault(key, {
            "bucket": entry["bucket"],
            "file": entry["file"],
            "score": 0,
            "reasons": [],
        })
        candidate["score"] += score + _bucket_boost(task_kind, entry["bucket"])
        candidate["reasons"].append(f"topics 命中：{entry['summary'][:60]}")

    results = sorted(candidates.values(), key=lambda item: (-item["score"], item["bucket"], item["file"]))[:5]
    for idx, item in enumerate(results, start=1):
        item["priority"] = idx
        item["reason"] = "；".join(dict.fromkeys(item["reasons"]))
        item.pop("reasons", None)
        item.pop("score", None)
    return results



def _collect_module_matches(task: str, task_kind: str, project_root: Path | None) -> list[dict]:
    topic_modules, _ = _parse_topics(project_root)
    module_cards = _collect_module_cards(project_root)
    candidates: dict[str, dict] = {}

    for entry in topic_modules:
        searchable = f"{entry['name']} {entry['summary']} {' '.join(entry['entry_points'])}"
        semantic_score, identifier_score = _match_breakdown(task, searchable)
        if semantic_score <= 0 and (task_kind in {"understand", "locate"} or identifier_score <= 0):
            continue
        score = semantic_score * 2 + identifier_score
        candidate = candidates.setdefault(entry["name"], {
            "name": entry["name"],
            "score": 0,
            "reasons": [],
            "entry_points": list(entry["entry_points"]),
        })
        candidate["score"] += score
        candidate["reasons"].append(f"topics 命中：{entry['summary'] or entry['name']}")

    for card in module_cards:
        searchable = " ".join([
            card["name"],
            card["read_when"],
            " ".join(card["entry_points"]),
            " ".join(card["constraints"]),
            " ".join(card["risks"]),
            " ".join(card["verification"]),
        ])
        semantic_score, identifier_score = _match_breakdown(task, searchable)
        if semantic_score <= 0 and (task_kind in {"understand", "locate"} or identifier_score <= 0):
            continue
        score = semantic_score * 2 + identifier_score
        candidate = candidates.setdefault(card["name"], {
            "name": card["name"],
            "score": 0,
            "reasons": [],
            "entry_points": [],
        })
        boost = 1 if task_kind == "decide" and (card["constraints"] or card["risks"]) else 0
        boost += 1 if task_kind == "validate" and card["verification"] else 0
        candidate["score"] += score + boost
        candidate["entry_points"] = candidate["entry_points"] or list(card["entry_points"])
        reason = card["read_when"] or (card["risks"][0] if card["risks"] else "模块导航与任务关键词匹配")
        candidate["reasons"].append(f"module card 命中：{reason[:60]}")

    results = sorted(candidates.values(), key=lambda item: (-item["score"], item["name"]))[:5]
    for idx, item in enumerate(results, start=1):
        item["priority"] = idx
        item["reason"] = "；".join(dict.fromkeys(item["reasons"]))
        item["entry_points"] = item["entry_points"][:3]
        item.pop("reasons", None)
        item.pop("score", None)
    return results



def _initial_locator_text(doc_matches: list[dict], module_matches: list[dict]) -> str:
    parts: list[str] = []
    for item in doc_matches:
        parts.append(f"{item['bucket']} {item['file']} {item['reason']}")
    for item in module_matches:
        parts.append(f"{item['name']} {' '.join(item.get('entry_points', []))} {item['reason']}")
    return " ".join(parts).lower()



def _unmatched_task_tokens(task: str, doc_matches: list[dict], module_matches: list[dict]) -> list[str]:
    tokens = sorted(_task_tokens(task), key=len, reverse=True)
    if not tokens:
        return []

    locator_text = _initial_locator_text(doc_matches, module_matches)
    return [token for token in tokens if token not in locator_text]



def _looks_like_specific_object_token(token: str) -> bool:
    if len(token) < 4:
        return False
    return bool(re.fullmatch(r"[a-z][a-z0-9_-]*", token) or re.search(r"[0-9_/.-]", token))



def _has_search_first_hint(task: str) -> bool:
    return any(hint in task for hint in SEARCH_FIRST_HINTS)



def _should_search_first(task: str, task_kind: str, doc_matches: list[dict], module_matches: list[dict]) -> bool:
    total_sources = len(doc_matches) + len(module_matches)
    if total_sources == 0:
        return True

    unresolved_tokens = _unmatched_task_tokens(task, doc_matches, module_matches)
    unresolved_specific_tokens = [token for token in unresolved_tokens if _looks_like_specific_object_token(token)]
    if unresolved_specific_tokens:
        return True

    if _has_search_first_hint(task) and unresolved_tokens:
        return True

    if task_kind in {"decide", "validate"} and total_sources <= 1:
        return True

    return False



def _build_search_queries(task: str) -> list[str]:
    tokens = sorted(_task_tokens(task), key=len, reverse=True)
    queries: list[str] = []

    for token in tokens[:4]:
        if token not in queries:
            queries.append(token[:80])

    if tokens:
        compact = " ".join(tokens[:6]).strip()
        if compact and compact not in queries:
            queries.append(compact[:80])
    else:
        compact = " ".join(re.findall(r"[A-Za-z0-9_\-/\u4e00-\u9fff]+", task))
        if compact:
            queries.append(compact[:80])

    if task not in queries:
        queries.append(task)
    return queries



def _search_stage(task: str, project_root: Path | None) -> tuple[list[str], list[dict], list[dict]]:
    queries = _build_search_queries(task)
    doc_candidates: dict[tuple[str, str], dict] = {}
    module_candidates: dict[str, dict] = {}

    for query in queries:
        for match in search_docs(query, project_root):
            parsed = paths.parse_docs_file_ref(match["file"])
            if parsed is None:
                continue
            bucket, filename = parsed
            key = (bucket, filename)
            candidate = doc_candidates.setdefault(key, {
                "bucket": bucket,
                "file": filename,
                "score": 0,
                "reasons": [],
            })
            candidate["score"] += 1
            line = match.get("line_content", "").strip()
            reason = f"search 命中：{query}"
            if line:
                reason = f"{reason} → {line[:60]}"
            candidate["reasons"].append(reason)

            stem = Path(filename).stem
            if stem and stem in _task_tokens(task):
                module_candidate = module_candidates.setdefault(stem, {
                    "name": stem,
                    "score": 0,
                    "reasons": [],
                    "entry_points": [],
                })
                module_candidate["score"] += 1
                module_candidate["reasons"].append(f"search 命中：{match['file']}")

    docs = sorted(doc_candidates.values(), key=lambda item: (-item["score"], item["bucket"], item["file"]))[:5]
    for idx, item in enumerate(docs, start=1):
        item["priority"] = idx
        item["reason"] = "；".join(dict.fromkeys(item["reasons"]))
        item.pop("reasons", None)
        item.pop("score", None)

    modules = sorted(module_candidates.values(), key=lambda item: (-item["score"], item["name"]))[:5]
    for idx, item in enumerate(modules, start=1):
        item["priority"] = idx
        item["reason"] = "；".join(dict.fromkeys(item["reasons"]))
        item.pop("reasons", None)
        item.pop("score", None)

    return queries, docs, modules



def _merge_doc_matches(primary: list[dict], secondary: list[dict], task_kind: str) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    order = 0
    for source in (primary, secondary):
        for item in source:
            key = (item["bucket"], item["file"])
            if key not in merged:
                order += 1
                merged[key] = {
                    "bucket": item["bucket"],
                    "file": item["file"],
                    "score": max(6 - int(item.get("priority", 5)), 1) + _bucket_boost(task_kind, item["bucket"]),
                    "reasons": [item["reason"]],
                    "order": order,
                }
                continue
            merged[key]["score"] += max(6 - int(item.get("priority", 5)), 1) + _bucket_boost(task_kind, item["bucket"])
            merged[key]["reasons"].append(item["reason"])

    results = sorted(merged.values(), key=lambda item: (-item["score"], item["order"], item["bucket"], item["file"]))[:5]
    for idx, item in enumerate(results, start=1):
        item["priority"] = idx
        item["reason"] = "；".join(dict.fromkeys(item["reasons"]))
        item.pop("reasons", None)
        item.pop("score", None)
        item.pop("order", None)
    return results



def _merge_module_matches(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order = 0
    for source in (primary, secondary):
        for item in source:
            key = item["name"]
            if key not in merged:
                order += 1
                merged[key] = {
                    "name": item["name"],
                    "score": max(6 - int(item.get("priority", 5)), 1),
                    "reasons": [item["reason"]],
                    "entry_points": list(item.get("entry_points", [])),
                    "order": order,
                }
                continue
            merged[key]["score"] += max(6 - int(item.get("priority", 5)), 1)
            merged[key]["reasons"].append(item["reason"])
            if not merged[key]["entry_points"]:
                merged[key]["entry_points"] = list(item.get("entry_points", []))

    results = sorted(merged.values(), key=lambda item: (-item["score"], item["order"], item["name"]))[:5]
    for idx, item in enumerate(results, start=1):
        item["priority"] = idx
        item["reason"] = "；".join(dict.fromkeys(item["reasons"]))
        item["entry_points"] = item["entry_points"][:3]
        item.pop("reasons", None)
        item.pop("score", None)
        item.pop("order", None)
    return results



def _decide_recall_level(task: str, task_kind: str, search_first: bool, source_oriented: bool, doc_matches: list[dict], module_matches: list[dict]) -> str:
    if source_oriented:
        return "skip"

    high_risk = any(keyword in task for keyword in HIGH_RISK_PATTERNS) or task_kind in {"decide", "validate"}
    source_count = len(doc_matches) + len(module_matches)

    if task_kind == "locate":
        return "skip" if search_first else "light"
    if high_risk and (source_count >= 2 or search_first):
        return "deep"
    if task_kind == "understand" and source_count >= 3:
        return "deep"
    return "light"



def plan_recall(task: str, project_root: Path | None = None) -> dict:
    brief_file = paths.brief_path(project_root)
    topics_file = paths.topics_path(project_root)
    modules_dir = paths.modules_path(project_root)

    missing = []
    if not brief_file.exists():
        missing.append(str(brief_file))
    if not topics_file.exists():
        missing.append(str(topics_file))
    if not modules_dir.exists():
        missing.append(str(modules_dir))
    if missing:
        envelope.fail("RECALL_CONTEXT_MISSING", "Recall planning context is incomplete.", details={"missing": missing})

    task_kind = _infer_task_kind(task)
    initial_doc_matches = _collect_doc_matches(task, task_kind, project_root)
    initial_module_matches = _collect_module_matches(task, task_kind, project_root)
    initial_unresolved_tokens = _unmatched_task_tokens(task, initial_doc_matches, initial_module_matches)

    search_first = _should_search_first(task, task_kind, initial_doc_matches, initial_module_matches)
    search_queries: list[str] = []
    search_hits = {"docs": [], "modules": []}
    search_stage_completed = False

    if search_first:
        search_queries, searched_docs, searched_modules = _search_stage(task, project_root)
        search_stage_completed = True
        doc_matches = _merge_doc_matches(initial_doc_matches, searched_docs, task_kind)
        module_matches = _merge_module_matches(initial_module_matches, searched_modules)
        search_hits = {
            "docs": [
                {
                    "bucket": item["bucket"],
                    "file": item["file"],
                    "priority": item["priority"],
                    "reason": item["reason"],
                }
                for item in searched_docs
            ],
            "modules": [
                {
                    "name": item["name"],
                    "priority": item["priority"],
                    "reason": item["reason"],
                    "entry_points": item["entry_points"],
                }
                for item in searched_modules
            ],
        }
    else:
        doc_matches = initial_doc_matches
        module_matches = initial_module_matches

    unresolved_tokens = _unmatched_task_tokens(task, doc_matches, module_matches)
    source_oriented = _is_source_oriented_task(task, task_kind, doc_matches, module_matches)

    total_sources = len(doc_matches) + len(module_matches)
    ambiguity = "low"
    if source_oriented:
        ambiguity = "high"
    elif search_first and total_sources == 0:
        ambiguity = "high"
    elif initial_unresolved_tokens or total_sources <= 2:
        ambiguity = "medium"
    recall_level = _decide_recall_level(
        task,
        task_kind,
        search_first and total_sources == 0,
        source_oriented,
        doc_matches,
        module_matches,
    )

    if source_oriented:
        doc_matches = []
        module_matches = []

    why_these = []
    if source_oriented:
        why_these.append("当前任务更适合直接阅读源码实现，durable recall 只能提供弱相关背景。")
    if doc_matches and any("BRIEF 命中" in item["reason"] for item in doc_matches):
        why_these.append("BRIEF 提供了与当前任务最相关的 durable docs 线索。")
    if doc_matches and any("topics 命中" in item["reason"] for item in doc_matches):
        why_these.append("topics.md 已把 durable docs 按话题归类，可先定位再阅读。")
    if doc_matches and any("search 命中" in item["reason"] for item in doc_matches):
        why_these.append("search-first 已完成搜索回填，并把命中的 docs 纳入最终推荐来源。")
    if module_matches:
        why_these.append("module cards 提供入口、约束、风险和验证重点，可降低误读概率。")
    if search_stage_completed and not total_sources:
        why_these.append("当前 BRIEF / topics / module cards 仍无法稳定定位目标对象，搜索后也未形成足够来源。")
    elif search_stage_completed:
        why_these.append("当前任务先经过搜索补充证据，再决定最终 recall 深度与推荐来源。")
    if not why_these:
        why_these.append("先读取最相关的 BRIEF / topics / module cards，再决定 recall 深度。")

    evidence_gaps = []
    if source_oriented:
        evidence_gaps.append(_source_oriented_gap())
    if search_stage_completed and not total_sources:
        evidence_gaps.append("当前无法仅凭 BRIEF、topics、module cards 与搜索结果稳定定位目标对象。")
    if not source_oriented and not doc_matches:
        evidence_gaps.append("尚未找到明确的 durable docs 命中。")
    if not source_oriented and not module_matches:
        evidence_gaps.append("尚未找到明确的 module card 命中。")
    evidence_gaps = list(dict.fromkeys(evidence_gaps))
    primary_evidence_gap = evidence_gaps[0] if evidence_gaps else None

    return {
        "version": "1",
        "task": task,
        "recall_level": recall_level,
        "task_kind": task_kind,
        "ambiguity": ambiguity,
        "search_first": search_first,
        "search_stage_completed": search_stage_completed,
        "search_queries": search_queries,
        "search_hits": search_hits,
        "recommended_docs": [
            {
                "bucket": item["bucket"],
                "file": item["file"],
                "priority": item["priority"],
                "reason": item["reason"],
            }
            for item in doc_matches
        ],
        "recommended_modules": [
            {
                "name": item["name"],
                "priority": item["priority"],
                "reason": item["reason"],
                "entry_points": item["entry_points"],
            }
            for item in module_matches
        ],
        "why_these": why_these,
        "evidence_gaps": evidence_gaps,
        "primary_evidence_gap": primary_evidence_gap,
    }



def run(args: list[str]) -> None:
    fail_legacy_command(
        "recall-plan",
        [
            "memory-hub search <query>",
            "memory-hub read <bucket> <file>",
        ],
        reason="Explicit-memory workflow no longer uses planner-based deep recall.",
    )
