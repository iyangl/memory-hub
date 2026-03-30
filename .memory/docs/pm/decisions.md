# Memory Hub 产品结论

## Recall-first 产品结论

- recall 的目标是先定位再读取，而不是把所有 docs 一次性读完。
- `light` 只读取少量最相关 docs / module cards；`deep` 才构建压缩后的 `working-set`。
- 当 planner 返回 `search_first = true` 时，必须先搜索，再依据回填结果决定最终来源与 recall 深度。
- `noop` 是合法结果，不需要为了保存而保存。

## Durable save 口径

- 每条候选知识都必须显式判定为 `noop | create | append | merge | update`。
- 能 `merge` 或 `append` 就不要 `create`；`update` 只用于明确替换已过时的长期结论。
- 非 `noop` 保存必须先 search 并读取目标 doc；working set 只能提炼，不能原样写回。
- `create` 需要补 `index`；`append` 只新增独立 section；`merge / update` 由上层提供完整合并后的 doc。

## 初始化与使用范围

- `/memory-hub:init` 只在 `.memory/` 不存在时使用；已有记忆时应转用 `/memory-hub:recall`、`brief` 或 `catalog-repair`。
- `.memory/inbox/` 只是 Layer 2 暂存区；是否进入长期 docs，由 `/memory-hub:save` 和 save core 决定。
