# Memory Hub 显式记忆重构方案（修订版）

## 背景

当前 Memory Hub 的主要复杂度不在 durable memory 本身，而在 recall 包装链：

- `lib/cli.py` 暴露了 `brief / scan-modules / recall-plan / working-set / execution-contract / modules-check / catalog-*` 等完整链路。
- `/memory-hub:recall` 默认串联 `brief -> modules-check -> recall-plan -> search/catalog-read/read -> working-set -> execution-contract`。
- `memory_save.py` 还耦合了 working-set 防原样写回、`BRIEF.md` 重建、`catalog-repair`。

这导致 recall 成本高、上下文膨胀明显，偏离“简单 memory 工具”的目标。

## 新产品边界

Memory Hub 只做一件事：

**记录和找回用户在使用过程中明确产生的决策与有用信息。**

### 保留能力

- durable memory 写入
- `search / read / list` 轻量 recall
- `inbox` 暂存候选信息
- save 时的基本正确性校验：
  - 非 `noop` 需要 evidence
  - 修改已有 doc 前必须先读目标 doc
- 可选 session trace 审计

### 不再承担

- AI 主导的项目初始化知识生成
- 模块扫描 / 模块卡片 / 模块时效检查
- recall 深度规划
- working-set / execution-contract 会话打包
- `BRIEF.md` / `catalog/` 作为默认 recall 前置依赖

## 关键修订决策

### 1. Search 的召回质量由 docs 自身保证，不由 topics 保证

这里需要澄清一个事实：`lib/memory_search.py` 当前直接遍历 `.memory/docs/**/*.md`，并不依赖 `topics.md` 做召回。

因此收缩后：

- `search` 继续作为主路径，没有产品级倒退
- 新建 durable doc 的可发现性，改由 **doc 自身必须可检索** 来保证
- 具体要求：`create` 的 `payload.doc_markdown` 必须包含清晰 heading，且正文首段/首条要能表达主题

结论：
- **不再把 `topics.md` 视为 search 的 correctness 前提**
- `topics.md` 退化为 legacy 辅助索引，而不是主索引

### 2. `create` 不再强依赖 `index.topic / index.summary`

由于 search 主路径直接扫 `.memory/docs/`，所以 `create` 可以不再强制要求 `index`。

新规则：
- `create`：`index` 变为 **可选**
- 若提供 `index.topic / index.summary`，则继续更新 legacy `topics.md`
- 若不提供，`save` 仍应成功，只要 doc 内容本身满足可检索要求

这意味着：
- `register_doc()` 从“核心写入步骤”降为“legacy compatibility step”
- `memory_save.py:_validate_index()` 需要放宽

### 3. `merge` 保留兼容，但退出推荐动作集

当前 `merge` 与 `update` 的底层代码路径几乎相同，只是 `update` 多了 `supersedes` 语义。

修订后：
- 推荐动作集缩减为：`noop / create / append / update`
- `merge` 仅为 **兼容旧请求格式的 legacy alias**
- 文档与新的 slash workflow 不再推荐用户生成 `merge`
- 后续若确认无外部依赖，再物理删除 `merge`

### 4. `init` 必须彻底去掉派生产物耦合

`lib/memory_init.py` 当前在初始化末尾调用：
- `repair()`
- `generate_brief()`

这与“仅最小骨架”目标冲突。

修订后 `init` 语义：
- 只创建最小目录和必要基础路径
- 不生成 `BRIEF.md`
- 不触发 `catalog-repair`
- 不生成 `topics.md` / module cards
- 不要求 AI 在 init 阶段补齐高价值 docs

更激进的后续版本可直接去掉 `init`，让第一次 `save` 自然创建缺失路径。

### 5. Phase 1 必须同步改 `CLAUDE.md` 与 `AGENTS.md`

否则行为规则会继续要求：
- 先读 `BRIEF.md`
- 再跑 `recall-plan`
- 再跑 `working-set`

这会与新的产品边界冲突。

修订后：
- `CLAUDE.md` 和 `AGENTS.md` 进入 Phase 1 范围
- 两者都要改成“显式记忆存取”叙事
- 不再把 `BRIEF.md` / `catalog/` / `working-set` 当成默认前置

## 模块处理建议

### 保留为核心

- `lib/memory_save.py`
- `lib/memory_search.py`
- `lib/memory_read.py`
- `lib/memory_list.py`
- `lib/inbox_list.py`
- `lib/inbox_clean.py`
- `lib/paths.py`
- `lib/cli.py`

### 降级为兼容层

- `lib/memory_init.py`
- `lib/brief.py`
- `lib/memory_index.py`
- `lib/catalog_read.py`
- `lib/catalog_repair.py`

### 退出核心，后续删除

- `lib/recall_planner.py`
- `lib/session_working_set.py`
- `lib/execution_contract.py`
- `lib/scan_modules.py`
- `lib/modules_check.py`
- `lib/catalog_update.py`

## 分阶段实施

## Phase 1：先改入口与规则，立即止损

目标：先让默认工作流变轻，并让行为文档与新边界一致。

涉及文件：
- `.claude/commands/memory-hub/recall.md`
- `.claude/commands/memory-hub/init.md`
- `.claude/commands/memory-hub/save.md`
- `CLAUDE.md`
- `AGENTS.md`
- `lib/cli.py`
- `tests/test_memory_flow.py`

动作：
- recall 默认改成 `search -> read`
- init 文案改成“仅最小骨架”或“不推荐”
- save 文档口径改成“显式记忆写入”，去掉 recall-first 叙事
- `CLAUDE.md` / `AGENTS.md` 去掉 `BRIEF -> recall-plan -> working-set` 主路径要求
- 暂不删除旧实现，只是不再走默认路径

回滚点：
- 仅恢复 slash workflow 和行为文档，不动内核

## Phase 2：解耦 save 与 init

目标：把 save 从 recall-first 派生链中拆出来，并让 init 真正最小化。

涉及文件：
- `lib/memory_save.py`
- `lib/memory_init.py`
- `lib/paths.py`
- `tests/test_memory_save.py`
- `tests/test_memory_flow.py`
- `tests/test_memory_init.py`
- `tests/test_memory_index.py`
- `tests/test_catalog.py`

动作：
- 去掉 save 成功后的自动 `generate_brief()`
- 去掉 save 成功后的自动 `catalog_repair()`
- 将 working-set 检查降为：仅显式引用 legacy session artifact 时启用
- `create` 不再强依赖 `index.topic/index.summary`
- 若 `index` 存在，则继续维护 legacy topics
- 把 `merge` 改成仅兼容保留，不再作为推荐动作
- `memory_init.py` 去掉 `repair()` 与 `generate_brief()` 调用
- init 只建最小目录与必要路径

回滚点：
- 若历史仓库仍需要 touched-doc 索引，可恢复“提供 index 时更新 topics”，但不恢复 brief/catalog 自动重建

## Phase 3：清理 legacy 深链

目标：把 recall-first 深链正式废弃。

涉及文件：
- `lib/recall_planner.py`
- `lib/session_working_set.py`
- `lib/execution_contract.py`
- `lib/scan_modules.py`
- `lib/modules_check.py`
- `lib/catalog_update.py`
- `tests/test_recall_planner.py`
- `tests/test_session_working_set.py`
- `tests/test_execution_contract.py`
- `tests/test_scan_modules.py`
- `tests/test_modules_check.py`

动作：
- 先保留 deprecated shell
- 明确输出 replacement 提示
- 确认无人依赖后再物理删除实现

回滚点：
- Phase 3 前均可继续保留 deprecated shell，延迟物理删除

## 测试策略

### 保留并强化的核心测试

- `tests/test_memory_save.py`
- `tests/test_memory_read.py`
- `tests/test_memory_list_search.py`
- `tests/test_memory_flow.py`
- `tests/test_memory_init.py`
- `tests/test_paths.py`
- `tests/test_inbox.py`

### Phase 1 需要改的测试

- `tests/test_memory_flow.py`
  - 从 recall-first 链路，改成显式主路径：`init -> save -> search -> read`
  - 不再断言 `working-set` / `execution-contract` 产物

### Phase 2 需要改的测试

- `tests/test_memory_save.py`
  - 去掉对 `rebuild.brief` 的断言
  - 去掉 save 后必须触发 `catalog_repair` 的断言
  - 增加 `create` 不带 `index` 也能成功的测试
  - 增加“提供 `index` 时仍能更新 legacy topics”的兼容测试
  - 将 `merge` 调整为 legacy compatibility 测试，而非推荐主路径测试

- `tests/test_memory_init.py`
  - 改成断言 init 不再生成 `BRIEF.md`
  - 改成断言 init 不再触发 `repair` / `brief`

### Phase 3 处理的测试

以下测试在 Phase 3 进入 deprecated / 删除路径：
- `tests/test_recall_planner.py`
- `tests/test_session_working_set.py`
- `tests/test_execution_contract.py`
- `tests/test_scan_modules.py`
- `tests/test_modules_check.py`

### 新的回归标准

显式记忆模式的主回归标准：

1. 能在空项目中初始化最小骨架
2. 能直接 `save` durable knowledge
3. `search` 能从 `.memory/docs/**/*.md` 找回内容
4. `read` 能精确读取 durable doc
5. 不依赖 `BRIEF.md` / `catalog/` / `session` 即可完成主流程

## 兼容策略

推荐：**渐进废弃**

- `search / read / list / save / inbox-*` 保持主路径
- `init` 保留壳，但仅最小骨架
- `brief / index / catalog-*` 保留 legacy 能力，不再自动触发
- `recall-plan / working-set / execution-contract / scan-modules / modules-check / catalog-update` 先保留 deprecated shell，再删除

## 风险

1. 旧测试强绑定 recall-first 语义，会先红一批。
2. 若外部已有脚本依赖 `recall-plan` JSON，需要先保留兼容壳。
3. 去掉 `BRIEF.md` / `catalog/` 自动维护后，旧仓库的“导航感”会下降，但这是有意收缩职责。
4. 若新建 doc 内容写得过于贫弱，会影响直接 `search` 的召回；因此必须把“doc 自身可检索”作为新的写入约束。

## 推荐结论

**接受这次收缩。**

不要继续优化 recall-first 深链了，而是明确把 Memory Hub 改成“显式记忆存取工具”。

一句话口径：

> Memory Hub 不再负责“帮 AI 理解整个项目”，只负责“把用户明确产生的决策和有用信息记下来，并在需要时用 search/read 找回来”。
