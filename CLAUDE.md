# Memory Hub — AI 行为指引

本仓库当前包含两套 memory surface，必须区分使用：

1. `.memory/`
   - 项目知识文件
   - 通过 `read/list/search/index/catalog-*` 维护
2. `.memoryhub/`
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
| `durable-memory` | durable memory v1：MCP tools + CLI review 工作流 |

## `.memory/` 项目知识工作流

适用场景：

- 记录本仓库自身的设计决策、约束、约定
- 维护 `topics.md` 与 `catalog/modules/*`

读：

1. `scoped_change` / `feature_work` 前先 `catalog-read topics`
2. 再 `memory.read` 相关知识文件
3. catalog 不够时用 `memory.search`

写：

1. AI 直接编辑 `.memory/<bucket>/<file>`
2. 再运行 `memory-hub index ...`
3. 若代码模块索引变更，运行 `memory-hub catalog-update --file ...`
4. 任务结束前执行 `memory-hub catalog-repair`

## Durable Memory v1 工作流

适用场景：

- 供 LLM 会话长期复用的高价值信息
- 不应再通过 `.memory/` 文件直写
- 普通代码审查或一次性讨论不默认进入此工作流

规则：

1. 一旦识别到 durable-memory 语境，立即进入 `durable-memory` skill
2. 一旦进入 durable-memory workflow，本会话第一条 durable-memory 工具调用必须是 `read_memory("system://boot")`
3. 由 skill 决定是否检索现有 memory、创建 proposal 或更新 proposal
4. proposal 创建成功后，skill 必须自动执行 `review show <proposal_id>`，展示摘要和 diff，再进入确认分流
5. 如果最相关目标是 pending proposal，skill 必须先 `review show <proposal_id>`，再进入人工审查分流
6. 宿主若提供结构化确认工具则优先使用；否则退化为固定文本分叉：`批准此提案` / `拒绝此提案` / `暂不处理`
7. 只有在展示 proposal 详情后且用户明确选择 `批准此提案` 或 `拒绝此提案` 时，LLM 才可代理执行对应的 CLI 审查命令
8. durable memory 只接受 `identity / decision / constraint / preference`
9. 禁止直接写 `.memoryhub/`、SQLite、导出文件
10. 禁止 LLM 自行 rollback durable memory
11. 禁止对 pending proposal 继续 update、amend、merge、reopen

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

- 不要直接编辑 `.memoryhub/`
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
