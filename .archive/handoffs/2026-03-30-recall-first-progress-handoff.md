# Recall-First Progress Handoff

日期：2026-03-30
目的：归档最近一轮 recall-first 主链收口、审查结论、已修 warning，以及下一步应继续处理的剩余问题。

## 1. 当前结论

截至 2026-03-30，Memory Hub 的 recall-first 主链已经进入“边界收口”阶段，不再是“只有设计、缺少 correctness core”的状态。

当前可以稳定成立的判断：

- `save` correctness core 已落在代码里，而不是只停留在 command 模板
- `.memory/docs/` 作为唯一正本、`BRIEF.md` / `catalog/` 作为派生产物的模型已经跑通
- `search-first` 已不再只在零命中时触发，中文历史术语 / 别名场景也已补上回归
- `working-set` 的定位仍然是任务级压缩上下文，不是长期知识正文
- 当前剩余的主要 warning 已缩小到：`update.supersedes` 仍然只有校验，没有进入长期可追溯产物

## 2. 最近完成的修改

### 2.1 修复 topics summary 的跨命令一致性

问题：

- `save` 会恢复 action-aware summary
- 但后续单独运行 `catalog-repair` 时，`catalog_repair` 只认 `summarize_doc()` 的 whole-doc summary
- 导致合法的 action-aware summary 被再次判成 stale 并改写

本轮修改：

- `lib/memory_index.py`
  - 新增 `_normalize_summary_text()`
  - 新增 `_extract_h1_title()`
  - 新增 `_extract_h2_sections()`
  - 新增 `summary_candidates_markdown()`
  - 新增 `summary_candidates_doc()`
- `lib/catalog_repair.py`
  - 从“只接受 `summarize_doc()` 单一摘要”改成“接受 `summary_candidates_doc()` 给出的合法摘要候选集合”
- 回归测试补到：
  - `tests/test_catalog.py`
  - `tests/test_memory_index.py`
  - `tests/test_memory_flow.py`

结果：

- `save -> catalog-repair` 不会再把合法 action-aware summary 错误回滚
- `topics.md` 的知识摘要在跨命令场景下保持稳定

### 2.2 收紧 search-first 的中文别名 / 历史术语边界

问题：

- 之前的 planner 对 ASCII slug、路径、编号风格 token 更敏感
- 对“中文别名 / 历史术语 / 旧叫法”这类任务表达，触发 `search_first` 不够硬
- 这与 recall-first 的 `Search Before Guess` 原则不完全对齐

本轮修改：

- `lib/recall_planner.py`
  - 新增 `SEARCH_FIRST_HINTS`
  - 新增 `_has_search_first_hint()`
  - 在 `_should_search_first()` 中增加：当 task 含别名/历史术语提示词，且仍有 unresolved tokens 时，强制进入 `search_first`
- 保持 `_looks_like_specific_object_token()` 的原有 ASCII / path / number 判定，不把所有中文词一概升级成“具体对象 token”，避免过度扩张
- 回归测试补到：
  - `tests/test_recall_planner.py`
  - `tests/test_memory_flow.py`

本轮锁住的代表用例：

- `checkout 别名 shadowtoken77 的验证风险`
- `checkout 历史术语 影子令牌 的验证风险`

结果：

- planner 在这类任务下会先 search，再把命中的 docs 回填到最终推荐来源
- recall-first 的“先定位，再决定读什么”在中文历史术语场景下也成立

## 3. 关键文件

本轮修改和后续继续开发时，优先看这些文件：

- `lib/memory_save.py`
- `lib/memory_index.py`
- `lib/catalog_repair.py`
- `lib/recall_planner.py`
- `tests/test_catalog.py`
- `tests/test_memory_index.py`
- `tests/test_memory_flow.py`
- `tests/test_recall_planner.py`
- `.claude/plan/recall-first-contract.md`
- `.claude/plan/recall-first-redesign-plan.md`
- `.claude/plan/recall-first-review-report.md`

## 4. 审查结论更新

最新一轮 final review 的稳定结论如下：

- recall-first 主链总体上已经对齐设计初衷
- 旧审查里关于“save core 缺位”的 critical 已不再成立
- 旧审查里关于“search-first 只在零命中触发”的 critical 也不再成立
- 当前问题不是“架构没落地”，而是“少数边界条件还要继续收口”

多模型审查情况：

- Codex reviewer：完成，可作为有效外部审查输入
- Gemini reviewer：本机环境失败，表现为 `@google/gemini-cli` / `@opentelemetry` 依赖下的 `SyntaxError`，属于本地 CLI / Node runtime 问题，不作为仓库代码 blocker

## 5. 当前验证状态

本轮最终确认的验证结果：

- `py -3 -m pytest E:/Development/Codes/memory-hub/tests/test_recall_planner.py -q`
  - 结果：`7 passed`
- `py -3 -m pytest E:/Development/Codes/memory-hub/tests/test_recall_planner.py E:/Development/Codes/memory-hub/tests/test_memory_flow.py -q`
  - 结果：`13 passed`
- `py -3 -m pytest -q`
  - 结果：`123 passed`

因此当前仓库状态可认为：

- topics summary consistency：已锁住回归
- Chinese alias / historical-term search-first：已锁住回归
- 全量测试：通过

## 6. 当前剩余问题

当前最值得继续收口的 warning 是：`update.supersedes` 只有校验，没有长期留痕。

更具体地说：

- 当前 save core 已能校验 `update.supersedes` 语义是否合理
- 但“谁 supersede 了谁、为什么被替换、后续怎么追”这部分还没有稳定进入长期可追溯产物
- 这意味着 update 行为的 correctness 已有一部分，但 traceability 还不完整

这是当前主线里最接近“下一刀就该补”的问题。

## 7. 下一步建议

建议按这个顺序继续：

1. 收口 `update.supersedes` 的留痕设计
   - 明确留痕应落在哪个产物里
   - 明确是 docs 正文、save 结果、还是派生索引承担追溯职责
2. 在 `lib/memory_save.py` 中补齐对应写入或派生逻辑
3. 补 update-action 的回归测试
   - 至少覆盖：有 `supersedes` 的 update 请求
   - 覆盖 save 后如何观察到 supersede 关系
4. 最后重新跑全量 pytest

## 8. 继续开发时的注意事项

继续这条主线时，保持这些边界不要漂移：

- 不直接手改 `.memory/docs/`，由 `/memory-hub:save` / `memory-hub save --file ...` 驱动长期写入
- 不直接手改 `.memory/catalog/`
- 不直接手改 `.memory/BRIEF.md`
- `working-set` 不能原样落回长期 docs
- `search_first` 不是兜底，而是 recall-first 协议的一部分
- 遇到“对象名 / 历史术语 / 别名不明确”的任务，优先保证 search-before-guess 成立

## 9. 恢复工作时的最小入口

如果后面要从这个 handoff 继续，最小恢复路径是：

1. 先看 `.claude/plan/recall-first-contract.md`
2. 再看 `.claude/plan/recall-first-review-report.md`
3. 然后看：
   - `lib/memory_save.py`
   - `lib/recall_planner.py`
   - `tests/test_memory_flow.py`
4. 接着从 `update.supersedes` 的 traceability 开始补

当前不需要重开的话题：

- `topics summary` 跨命令一致性
- 中文历史术语的 `search_first`

这两个 warning 目前都已有代码修复和测试锁定。
