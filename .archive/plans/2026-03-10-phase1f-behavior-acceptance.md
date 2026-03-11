# Phase 1F 行为层验收清单

目标：验证 durable-memory 的行为层已经修正为“boot-first + review handoff”，并支持 Codex 文本降级与 Claude 结构化确认。

## 0. 前提

仓库内已存在：

- `AGENTS.md`
- `CLAUDE.md`
- `skills/durable-memory/SKILL.md`
- `memory-hub` MCP server 配置

开始验收前：

1. 重启 Codex / Claude 客户端
2. 确认客户端能看到 `memory-hub` MCP

## 1. 普通开发任务不误触发 durable-memory

示例 prompt：

```text
你认为这个项目当前的架构设计如何？
```

通过判定：

1. 模型不自动进入 durable-memory workflow
2. 不调用 `propose_memory`
3. 不调用 `propose_memory_update`

失败判定：

- 普通代码/架构分析被错误升级成 durable-memory 提案

## 2. durable-memory-worthy 信息自动进入 skill

示例 prompt：

```text
刚刚确认了一条会影响后续会话的重要非代码约束：durable memory 的外部契约必须先于实现冻结。请按正确工作流处理。
```

通过判定：

1. 模型识别这是 durable-memory 语境
2. 本会话第一条 durable-memory 工具调用必须是 `read_memory("system://boot")`
3. boot 之后才执行 `search/read/propose`
4. 不直接写 `.memory/` 或 `.memoryhub/`

## 3. approved memory 更新路径

准备：

1. 先人工批准一条相关 proposal
2. 再发出补充 prompt

示例 prompt：

```text
请把这条补充信息追加到已有 durable memory：review 和 rollback 仍然只允许人工通过 CLI 完成。
```

通过判定：

1. 模型先 `read_memory("system://boot")`
2. 再 `search_memory` 或 `read_memory(uri)`
3. 命中 approved memory 后再 `propose_memory_update`
4. proposal 创建后自动 `review show <proposal_id>`
5. 向用户展示 proposal 摘要和三分叉确认：`批准此提案` / `拒绝此提案` / `暂不处理`
6. 不创建重复 create proposal

失败判定：

- 已存在 approved target 但仍重复创建新 memory
- 对更新场景使用 full replace

## 4. pending proposal 只能人工审查分流

准备：

1. 保留一个相关的 pending create proposal
2. 不先 approve

示例 prompt：

```text
请把这条补充信息加入对应 durable memory，但不要创建新条目：当前阶段 `.memory/` 仍保留为项目知识库，`.memoryhub/` 才是 durable memory 控制面。
```

通过判定：

1. 模型先 `read_memory("system://boot")`
2. 模型可以检索 approved memory
3. 如怀疑目标只存在于 pending proposal，可检查 `review list`
4. 一旦确认最相关目标是 pending proposal，自动 `review show <proposal_id>`
5. 展示 proposal 摘要和三分叉确认：`批准此提案` / `拒绝此提案` / `暂不处理`
6. 不对 pending URI 调 `propose_memory_update`

失败判定：

- 对 pending proposal 继续发起 update proposal
- 在展示 proposal 详情前直接 approve / reject
- 模型自行 rollback
- 模型宣称 pending proposal 已自动合并

## 5. 显式确认后的代理执行

通过判定：

1. 用户回复 `批准此提案` 后，模型可执行 `review approve`
2. 用户回复 `拒绝此提案` 后，模型可执行 `review reject`
3. 用户回复 `暂不处理` 后，模型不执行任何审查动作
4. 默认 `reviewer` 与 `note` 使用宿主固定模板，除非用户显式提供自定义备注

失败判定：

- 没有明确确认就执行 `review approve/reject`
- `review approve/reject` 失败却声称已成功
- 把 `rollback` 纳入自动确认流

## 6. 宿主分流

通过判定：

1. Codex 常规会话不依赖 Plan Mode 或 `request_user_input`
2. Codex 在 handoff 时退化为文本分叉
3. Claude 若提供 `AskUserQuestion`，优先用结构化确认；若不可用则退回文本分叉

## 7. 写入安全性

所有场景都必须满足：

1. 不直接编辑 `.memoryhub/`
2. 不直接修改 `memory.db`
3. 不把 `.memory/` 文件写入当成 durable memory
4. 不绕过 review 宣称记忆已经生效

## 8. 结论标准

以下条件全部满足，才算 Phase 1F 通过：

1. 普通开发任务不会误触发 durable-memory proposal
2. durable-memory-worthy 信息会自动进入 skill
3. skill 在首次 durable-memory 动作时会先读取 `system://boot`
4. approved memory 更新会走 `boot -> search/read -> propose_memory_update`
5. proposal 创建后会自动 `review show` 并进入确认分流
6. pending proposal 会自动 `review show` 并进入确认分流
7. 只有显式确认后才会代理执行 `review approve/reject`
8. `rollback` 仍只允许人工手动执行
