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
