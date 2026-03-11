# Memory Hub — AI 行为指引

本仓库当前在 `.memory/` 下包含两条 lane，必须区分使用：

1. `.memory/`
   - 统一项目记忆根目录
2. `.memory/docs/`
   - 项目知识文件
   - 通过 `read/list/search/index/catalog-*` 维护
3. `.memory/_store/memory.db`
   - durable memory v1
   - 通过 `MCP propose/read/search + CLI review/rollback` 维护

## Skill 列表

| Skill | 说明 |
|-------|------|
| `memory.init` | 初始化 `.memory/` 并生成项目知识骨架 |
| `memory.read` | 精准读取 `.memory/` 知识文件 |
| `memory.list` | 列出 `.memory/` bucket 文件 |
| `memory.search` | 跨 bucket 全文检索 `.memory/` |
| `memory.index` | 注册 `.memory/` 知识文件到 topics.md |
| `catalog.read` | 读取轻量目录或模块索引 |
| `catalog.update` | 更新代码模块索引 |
| `catalog.repair` | 一致性检查与自愈 |
| `project-memory` | 统一项目记忆入口：读 docs/catalog/durable/review |
| `memory-admin` | 项目记忆维护入口：repair/diagnose/session-extract |

## `.memory/` 项目知识工作流

适用场景：

- 记录本仓库自身的设计决策、约束、约定
- 维护 `topics.md` 与 `catalog/modules/*`

读：

1. `scoped_change` / `feature_work` 前先进入 `project-memory`
2. 在宿主里调用 `memory-hub` MCP 的 `read_memory(ref="catalog://topics")`
3. 再通过同一个 `read_memory(...)` 读取相关 `doc://...`
4. docs 上下文不够时，用同一个 `memory-hub` MCP 调 `search_memory(..., scope=docs|all)`

不要把 `catalog://...` 或 `doc://...` 当成 MCP resource。
不要使用 `read_mcp_resource`，也不要假设存在名为 `memory` 的 MCP server。

写：

1. 宿主里统一通过 `memory-hub` MCP 的 `capture_memory(...)` 与 `update_memory(...)` 进入写入口
2. review 展示优先用同一个 `memory-hub` MCP 的 `show_memory_review(...)`
3. `propose_memory(...)` / `propose_memory_update(...)` 只作为兼容入口，不作为默认规则写法
4. `session-extract` 只通过 `memory-admin` 走 `memory-hub session-extract --file ...`
5. 若确实发生人工 docs 直写，再通过统一 write lane 或 review flow 补齐索引一致性
6. 任务结束前执行 `memory-hub catalog-repair`

## Durable Memory v1 工作流

适用场景：

- 供 LLM 会话长期复用的高价值信息
- 不应再通过 `.memory/` 文件直写
- 普通代码审查或一次性讨论不默认进入此工作流

规则：

1. 统一从 `project-memory` 进入记忆工作流
2. 上述统一动作都指 `memory-hub` 这个 MCP server 的对应 tools
3. 若任务进入 durable-memory 语境，由 `project-memory` 进入内部 durable branch
4. 一旦进入 durable-memory workflow，本会话第一条 durable-memory 工具调用必须是 `memory-hub.read_memory(ref="system://boot")`
5. `capture_memory(kind=auto|docs|durable)` 与 `update_memory(ref, mode=patch|append)` 是默认写入口
6. `docs-only` 变更进入持久 docs change review；批准后再应用 docs 与 catalog 变更
7. `durable-only` 变更继续走 proposal / review
8. `dual-write` 创建 docs change review，并关联 durable summary proposal；批准 docs review 时同步批准关联 durable proposal
9. review 目标进入 pending 状态后，skill 必须先调用 `memory-hub.show_memory_review(...)`，展示摘要和 diff，再进入确认分流；只有 MCP review 展示不可用时才退回 `review show <proposal_id|ref>`
10. 如果最相关目标是 pending proposal 或 pending docs review，skill 必须先 `show_memory_review(...)`，再进入人工审查分流
11. 宿主若提供结构化确认工具则优先使用；否则退化为固定文本分叉：`批准此提案` / `拒绝此提案` / `暂不处理`
12. 只有在展示 proposal 详情后且用户明确选择 `批准此提案` 或 `拒绝此提案` 时，LLM 才可代理执行对应的 CLI 审查命令
13. durable memory 只接受 `identity / decision / constraint / preference`
14. 禁止直接写 `.memory/_store/`、SQLite、导出文件
15. 禁止 LLM 自行 rollback durable memory
16. 禁止对 pending proposal 继续 update、amend、merge、reopen

### Durable Memory 价值门槛

只有满足下面两个条件的信息才应进入 durable memory：

1. `why_not_in_code`
   - 为什么这条信息不能通过读代码得到
2. `source_reason`
   - 这条信息来自哪里，为什么可信

若无法清晰回答，不应写入 durable memory。

### Durable Memory 类型约束

只允许四种类型：

- `identity`
- `decision`
- `constraint`
- `preference`

### Durable Memory 禁止事项

- 不要直接编辑 `.memory/_store/`
- 不要直接操作 `memory.db`
- 不要把 `.memory/` 文件写入当成 durable memory
- 不要在展示 proposal 详情和拿到明确确认前执行 `review approve/reject`
- 不要对 pending proposal 继续提交 update proposal
- 不要对 pending proposal 执行 amend、merge 或 reopen
- 不要用 full replace 更新 durable memory
- 不要代理执行 `rollback`

## 任务结束时

- 若本次改动了 `.memory/` 或 catalog：执行 `catalog.repair`
- 若本次改动了 durable memory 实现：至少跑相关 pytest
- 若本次改动影响 MCP/CLI 契约：同步更新 `README.md` 与相关 skill
