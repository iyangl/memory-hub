# Memory Hub — Claude Code 使用规则

## 规则优先级

当规则冲突时，按以下顺序：

1. **Skill 规则**（最高优先级）
   - `skills/project-memory/SKILL.md`
   - `skills/memory-admin/SKILL.md`

2. **项目规则**（本文件）
   - `CLAUDE.md`

3. **全局规则**（最低优先级）
   - `~/.claude/CLAUDE.md`

项目规则覆盖全局规则，Skill 规则覆盖项目规则。

---

## 第一步：任务分类（每次任务必须先完成）

收到用户问题后，立即判断：

### A. 规则发现

用户问题包含以下特征？
- "有没有新规则" / "形成了什么规则" / "规则变化"
- "例外规则" / "特殊情况" / "打破了什么规则"
- "文档偏离实现" / "文档与代码不一致" / "docs drift"
- "这次改动的规则/约束/决策"

→ YES: 跳转到 [规则发现流程]

示例：
- ✅ "这次改动里有没有新规则" → 规则发现
- ✅ "文档和代码还一致吗" → 规则发现
- ❌ "这个文件做什么" → 不是规则发现

### B. 代码理解 / 功能开发

用户问题包含以下特征？
- "这个文件/模块做什么" / "功能如何实现"
- "设计决策是什么" / "为什么这样设计"
- "如何使用" / "调用关系"
- "帮我实现/开发/添加"
- 需要写入新的项目知识

→ YES: 跳转到 [知识装配流程]

示例：
- ✅ "durable store 的写入流程是什么" → 代码理解
- ✅ "帮我加一个新的 CLI 命令" → 功能开发
- ❌ "有没有例外规则" → 不是代码理解

### C. 维护诊断

用户问题包含以下特征？
- "修复索引" / "catalog repair"
- "提取会话" / "session extract"
- "检查一致性" / "诊断"

→ YES: 跳转到 [维护流程]

### D. 都不匹配

→ 跳转到 [知识装配流程]，作为通用起点

---

## [规则发现流程]

入口：`memory-admin`

### 检查点 1：上下文

我读了 catalog 吗？
- NO → 现在执行：`read_memory(ref="catalog://topics")`
- YES → 继续

我读了相关 docs 吗？
- NO → 根据 catalog 读取相关 `doc://...`
- YES → 继续

### 检查点 2：自动发现

我执行了 discover 吗？
- NO → 现在执行：`python3 -m lib.cli discover`
- YES → 继续

### 检查点 3：分析结果

discover 返回了候选吗？
- YES → 展示候选，等待用户决策
- NO → 补充人工分析

discover 返回 0 候选时，不代表没有规则变化。discover 不识别：
- 纯文档规则的变化
- 隐式的规则收紧
- 语义层面的规则演化

必须人工补充分析，特别关注文档规则变化。

### 检查点 4：知识沉淀

如果发现了值得记录的规则：
- 纯项目规则 → 多数走 `docs-only`
- 跨会话高价值 → 可能走 `dual-write`
- 纯长期偏好/身份 → 才走 `durable-only`

通过统一写入口写入，不要直接改文件。

---

## [知识装配流程]

入口：`project-memory`

### 检查点 1：定位

我读了 catalog 吗？
- NO → 现在执行：`read_memory(ref="catalog://topics")`
- YES → 继续

### 检查点 2：知识

我读了相关 docs 吗？
- NO → 根据 catalog 中的索引，读取相关 `doc://...`
- YES → 继续

上下文足够吗？
- NO → 执行：`search_memory(query, scope="docs|all")`
- YES → 继续

### 检查点 3：执行

上下文装配完成，开始执行实际任务（代码分析、功能开发等）。

### 检查点 4：知识沉淀

任务产生了新知识吗？（新决策、新约束、新约定）
- NO → 结束
- YES → 判断应该记录在哪里，通过统一写入口写入

---

## [维护流程]

入口：`memory-admin`

根据任务直接执行：
- 修复索引 → `python3 -m lib.cli catalog-repair`
- 发现规则 → `python3 -m lib.cli discover`
- 提取会话 → `python3 -m lib.cli session-extract --file <path>`
- 诊断问题 → 直接检查 `.memory/` 下相关文件

---

## [Durable Branch]

只有在知识沉淀阶段判断为 durable 时才进入。不要主动进入。

### 进入前四个问题（任一为否，停止）

1. 这条信息会影响未来会话吗？
2. 这条信息不能稳定从代码读出来吗？
3. 能否清楚说明 `why_not_in_code`？
4. 能否清楚说明 `source_reason`？

允许类型仅限：`identity` / `decision` / `constraint` / `preference`

### 检查点 1：Boot

本会话第一次进入 durable branch 吗？
- YES → 现在执行：`read_memory(ref="system://boot")`
- NO（已 boot）→ 继续

在 boot 之前，禁止调用任何其他 durable 工具。

### 检查点 2：查找已有记忆

已知目标 URI？
- YES → `read_memory(ref=uri)`
- NO → `search_memory(query, scope="durable")`

### 检查点 3：写入路由

找到已有 approved memory？
- YES → `update_memory(ref=uri, mode="patch|append", ...)`
- NO → `capture_memory(kind="durable", ...)`

找到的是 pending proposal？
- → 停止写入，进入 [Review 流程]

---

## [Review 流程]

### 检查点 1：展示

我展示了 review 详情吗？
- NO → 现在执行：`show_memory_review(proposal_id|ref)`
- YES → 继续

如果 `show_memory_review` 不可用，视为宿主或 MCP 配置问题并停止。

### 检查点 2：展示内容

向用户展示摘要和 diff，然后给出固定确认分叉：
- `批准此提案`
- `拒绝此提案`
- `暂不处理`

### 检查点 3：执行

用户明确选择了吗？
- `批准此提案` → 执行：`python3 -m lib.cli review approve <id> --reviewer claude --note "..."`
- `拒绝此提案` → 执行：`python3 -m lib.cli review reject <id> --reviewer claude --note "..."`
- `暂不处理` → 停止，不执行任何审查动作
- 用户未选择 → 等待，不要自行决定

禁止：
- 在未展示 review 详情前 approve / reject
- 对 pending proposal 继续 update
- amend / merge / reopen pending proposal
- 代理执行 `rollback`

---

## 宿主前提

本仓库只暴露两个 memory workflow 入口：

- `project-memory`（主工作流）
- `memory-admin`（维护入口）

如果当前 Claude 会话看不到它们，视为配置问题并停止。不要设计 fallback。

## 统一记忆模型

- `.memory/docs/` — 项目知识主文档
- `.memory/catalog/` — docs 索引
- `.memory/_store/memory.db` — durable 最小控制面

不要把 docs lane 和 durable store 当成同一件事。

docs lane 用于：仓库设计决策、项目约束与约定、catalog 与模块索引维护

durable lane 只用于：跨会话有价值、不能稳定从代码恢复、适合表示为 `identity` / `decision` / `constraint` / `preference`

## MCP 约束

记忆相关 MCP 只认：

- server: `memory-hub`
- tools: `read_memory` / `search_memory` / `capture_memory` / `update_memory` / `show_memory_review`

统一 ref 只认：

- `system://boot`
- `doc://<bucket>/<name>`
- `catalog://topics`
- `catalog://modules/<name>`
- durable URI，例如 `constraint://...`

禁止：

- 使用 `read_mcp_resource`
- 把 `doc://...` / `catalog://...` / `system://...` 当成 MCP resources
- 虚构名为 `memory` 的 server
- 把 `propose_memory(...)` / `propose_memory_update(...)` 当成默认入口

## 写入规则

统一写入口：

- `capture_memory(kind=auto|docs|durable, ...)`
- `update_memory(ref, mode="patch|append", ...)`

路由语义：

- `docs-only` → docs change review
- `durable-only` → durable proposal / review
- `dual-write` → docs change review + linked durable summary proposal

## 硬边界

禁止：

- 直接编辑 `.memory/_store/`
- 直接改 `memory.db`
- 用 docs 文件写入代替 durable memory
- 绕过统一写入口直接改 `.memory/docs/*`

## 任务结束

- 若改动了 `.memory/` 或 catalog → 执行 `python3 -m lib.cli catalog-repair`
- 若改动了 durable memory / MCP / review 契约 → 同步更新 `README.md`
