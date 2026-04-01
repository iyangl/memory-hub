# Memory Hub 架构决策

## Recall-first 架构决策

- `.memory/docs/` 是唯一正本；`BRIEF.md`、`catalog/`、`session/` 都是派生产物。
- recall 必须先执行 `recall-plan`，再按 `skip | light | deep` 决定读取范围。
- 当 `search_first = true` 时，必须先搜索，再把搜索命中回填为最终推荐来源，然后再决定 recall 深度。
- deep recall 只通过压缩后的 `working-set` 组织任务上下文，working set 不能原样写回长期 docs。

## Host 与 correctness core 边界

- slash command、AGENTS 和宿主适配脚本只负责提醒、接线与提示，不承担核心正确性。
- `memory-hub save --file <save.json>` 是 durable save correctness core。
- 非 `noop` 保存必须带 search/read evidence；`append / merge / update` 必须先读取目标 doc；`update` 必须显式说明 `supersedes`。
- 保存成功后自动重建 `BRIEF.md` 并执行 `catalog-repair`。

## 初始化与派生产物约束

- `init` 只用于首次创建 `.memory/`；若目录已存在，CLI 必须返回 `ALREADY_INITIALIZED`。
- `brief` 负责从 docs 提取高价值 section 生成 boot summary，而不是手工维护摘要。
- `scan-modules --out ...` 生成裸模块 JSON；`catalog-update` 和 `catalog-repair` 负责维护 topics 与 module cards。

## Update supersedes traceability

- `update` 的 supersedes 追溯信息属于 session artifact，应写入 `.memory/session/save-trace/<artifact>.json`，而不是 durable docs 正文。
- trace 持久化是 best-effort：若写入失败，不影响 durable docs 已成功写入这一事实。
- `save` 返回值中的 `data.trace` 应显式包含 `update_supersedes`、`trace_file`、`warning`，且 `trace_file` 使用仓库内相对路径。
- 旧的 `.memory/session/save-trace.jsonl` 视为 legacy session artifact：新实现不读取、不迁移回放，可安全忽略或删除。
- 本设计只解决 trace artifact 的并发覆盖问题，不承诺整个 `save` 流程对 durable docs / rebuild 产物的全流程并发安全。
