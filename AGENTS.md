# Memory Hub — Codex 使用规则

## 规则优先级

当规则冲突时，按以下顺序：

1. **Skill 规则**（最高优先级）
   - `skills/project-memory/SKILL.md`
   - `skills/memory-admin/SKILL.md`

2. **项目规则**（本文件）
   - `AGENTS.md`

3. **全局规则**（最低优先级）
   - Codex 全局配置

项目规则覆盖全局规则，Skill 规则覆盖项目规则。

## 宿主前提

本仓库只暴露两个 memory workflow 入口：

- `project-memory`
- `memory-admin`

如果当前 Codex 会话看不到它们，视为配置问题并停止。不要设计 fallback。

## 统一记忆模型

- `.memory/docs/` 是项目知识主文档
- `.memory/catalog/` 是 docs 索引
- `.memory/_store/memory.db` 是 durable 最小控制面

不要把 docs lane 和 durable store 当成同一件事。

docs lane 用于：

- 仓库设计决策
- 项目约束与约定
- catalog 与模块索引维护

durable lane 只用于：

- 跨会话有价值
- 不能稳定从代码恢复
- 适合表示为 `identity` / `decision` / `constraint` / `preference`

## MCP 约束

记忆相关 MCP 只认：

- server: `memory-hub`
- tools:
  - `read_memory`
  - `search_memory`
  - `capture_memory`
  - `update_memory`
  - `show_memory_review`

统一 ref 只认：

- `system://boot`
- `doc://<bucket>/<name>`
- `catalog://topics`
- `catalog://modules/<name>`
- durable URI，例如 `constraint://...`

不要：

- 使用 `read_mcp_resource`
- 把 `doc://...` / `catalog://...` / `system://...` 当成 MCP resources
- 虚构名为 `memory` 的 server
- 把 `propose_memory(...)` / `propose_memory_update(...)` 当成默认入口

## 入口路由

### 任务语义到入口的映射

**用户问题包含以下特征时，使用 `memory-admin`**：

任务语义：
- "有没有新规则" / "形成了什么规则" / "规则变化"
- "例外规则" / "特殊情况" / "打破了什么规则"
- "文档偏离实现" / "文档与代码不一致" / "docs drift"
- "这次改动的规则/约束/决策"

执行：
- `python3 -m lib.cli discover` — 发现规则候选
- `python3 -m lib.cli session-extract --file <path>` — 提取会话记忆
- `python3 -m lib.cli catalog-repair` — 修复索引一致性

**用户问题包含以下特征时，使用 `project-memory`**：

任务语义：
- "这个文件/模块做什么" / "功能如何实现"
- "设计决策是什么" / "为什么这样设计"
- "如何使用" / "调用关系"
- 需要写入新的项目知识

执行：
- 读取 `catalog://topics` 定位上下文
- 读取相关 `doc://...`
- 必要时 `search_memory(scope=docs|all)`
- 写入通过 `capture_memory` / `update_memory`

### 入口职责

使用 `project-memory`：

- 普通仓库分析
- 设计与功能开发
- 判断知识应进入 docs lane 还是 durable lane
- 查看 review 摘要
- 一旦任务进入 durable-memory 语境，也继续由它进入内部 durable branch

使用 `memory-admin`：

- `catalog-repair` — 修复索引
- `discover` — 发现规则候选
- `session-extract` — 提取会话
- manifest / store / projection 诊断

不要绕过这两个入口自行拼 memory 操作。

## 读取规则

普通仓库知识读取顺序：

1. `read_memory(ref="catalog://topics")`
2. `read_memory(ref="doc://...")`
3. 若 docs 上下文不够，再 `search_memory(query, scope="docs|all", ...)`

普通仓库知识问题不要默认进入 durable 写入流程。

## 写入规则

统一写入口：

- `capture_memory(kind=auto|docs|durable, ...)`
- `update_memory(ref, mode="patch|append", ...)`

路由语义：

- `docs-only` -> docs change review
- `durable-only` -> durable proposal / review
- `dual-write` -> docs change review + linked durable summary proposal

review 展示必须使用：

- `show_memory_review(proposal_id|ref)`

如果它不可用，视为 Codex 或 MCP 配置问题并停止。

## Durable Branch

只有在任务明确进入"跨会话、高价值、代码读不出来的信息"时，才进入 durable branch。

允许类型仅限：

- `identity`
- `decision`
- `constraint`
- `preference`

进入 durable branch 前必须判断：

1. 这条信息会影响未来会话吗
2. 这条信息不能稳定从代码读出来吗
3. 能否清楚说明 `why_not_in_code`
4. 能否清楚说明 `source_reason`

任一条件不满足，就不要进入 durable 写入。

本会话第一次进入 durable branch 时，第一条 durable 工具调用必须是：

- `read_memory(ref="system://boot")`

在 boot 之前，不要调用：

- `read_memory(ref=<non-system>)`
- `search_memory(..., scope="durable", ...)`
- `capture_memory(...)`
- `update_memory(...)`
- `propose_memory(...)`
- `propose_memory_update(...)`

durable 写入规则：

- 已知目标 URI -> `read_memory(ref=uri)`
- 未知目标 URI -> `search_memory(query, scope="durable", ...)`
- 没有相关 approved memory -> `capture_memory(kind="durable", ...)`
- 已有相关 approved memory -> `update_memory(ref=uri, mode="patch|append", ...)`

不要：

- 直接写 `.memory/_store/`
- 直接改 `memory.db`
- full replace durable content

## Review 规则

对于 pending proposal 或 pending docs review：

1. 先 `show_memory_review(...)`
2. 展示摘要和 diff
3. 再进入固定确认分叉：
   - `批准此提案`
   - `拒绝此提案`
   - `暂不处理`

只有在 review 详情已展示，且用户明确选择 `批准此提案` 或 `拒绝此提案` 后，Codex 才可代理执行对应的 `review approve/reject`。

不要：

- 在未展示 review 详情前 approve / reject
- 对 pending proposal 继续 update
- amend / merge / reopen pending proposal
- 代理执行 `rollback`

## 维护规则

### discover 的预期行为

**输入**：
- git diff（当前工作区改动）
- 现有 memory context（docs + durable）

**输出**：
- candidate 列表（可能为空）
- 每个 candidate 包含：理由、相关文件、建议分类

**识别范围**：
- 代码中的新决策
- 明显的约束变化
- 文档与代码的不一致

**不识别**：
- 纯文档规则的变化（需要人工分析）
- 隐式的规则收紧
- 语义层面的规则演化

**discover 返回 0 候选时**：
- 不代表没有规则变化
- 可能需要人工补充分析
- 特别是文档规则的变化

### 其他维护规则

- `discover` 只返回 candidate，不直接写 active docs 或 approved durable state
- `session-extract` 只通过既有 write lane / review flow 产生候选，不直接生效

## 硬边界

不要：

- 直接编辑 `.memory/_store/`
- 直接改 `memory.db`
- 用 docs 文件写入代替 durable memory
- 绕过统一写入口直接改 `.memory/docs/*`

## 任务结束

- 若改动了 `.memory/` 或 catalog：执行 `python3 -m lib.cli catalog-repair`
- 若改动了 durable memory / MCP / review 契约：同步更新 `README.md`

## 任务执行自检

### 开始前

- [ ] 我识别了任务语义（规则发现 vs 代码理解 vs 维护）
- [ ] 我选择了正确的入口（project-memory vs memory-admin）
- [ ] 如果是 memory-admin 任务，我知道要用哪个工具

### 执行中

- [ ] 我按入口的 workflow 顺序执行
- [ ] 我没有绕过统一入口直接调用底层工具
- [ ] 如果是规则发现任务，我先执行了 discover

### 结束后

- [ ] 如果 discover 返回 0 候选，我补充了人工分析
- [ ] 如果改动了 memory，我执行了 catalog-repair
- [ ] 我没有违反硬边界（直接写 _store/ 等）
