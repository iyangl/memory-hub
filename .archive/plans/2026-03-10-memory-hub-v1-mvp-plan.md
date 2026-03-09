# Memory Hub v1 MVP 重构方案

日期：2026-03-10
状态：可行，建议作为下一阶段正式基线

## 1. 目标

v1 只解决三个基础问题：

1. agent 不能绕过规范直接修改 durable memory。
2. durable memory 的写入、更新、回滚必须可控且原子。
3. durable memory 只沉淀代码里读不出来的高价值信息。

## 2. 非目标

以下能力明确延后到 v2 及以后：

- 自动会话提炼
- 语义检索 / 混合检索
- Web UI / Review 面板
- 图结构、alias、多跳关系
- 后台索引 worker
- 旧 `.memory/` 自动迁移
- 多租户、远程部署

## 3. 为什么这个方案可行

这个方案是刻意收窄后的 MVP，不追求一步到位做成 Memory Palace。

可行性依据：

- 当前最核心的问题不是“检索不够高级”，而是“没有 authoritative 写入口”。
- 只保留四类 durable memory，可以显著降低写入判断和 review 成本。
- SQLite + 本地 stdio MCP 的实现复杂度可控，足以支撑单仓库、单用户、显式写入的初始场景。
- proposal -> review -> approve 的队列模型，已经足够解决“直接改文件导致不可控”的问题。

## 4. 锁定前提

- 客户端：`Codex + Claude`
- durable memory 类型仅保留：`identity / decision / constraint / preference`
- 旧 `.memory/` 暂不兼容，不参与新系统读写
- v1 只允许显式写入，不做自动沉淀
- 关键 durable memory 统一走 CLI 审查队列
- SQLite 是 durable truth source
- Markdown 不再作为 durable memory 主写入面

## 5. 总体架构

### 5.1 核心分层

1. `MCP Server`
   - agent 唯一 durable memory 读写入口
   - 暴露 `read/search/propose/update` 四类工具

2. `SQLite Durable Store`
   - durable truth source
   - 存储已批准记忆、历史版本、待审提案

3. `CLI Review Surface`
   - 人类审批 durable memory proposal
   - 执行 approve / reject / rollback

4. `Skill / CLAUDE 规则`
   - 只负责编排和行为约束
   - 不再允许 agent 直接写 `.memory*`

### 5.2 存储目录

建议新增独立目录：

```text
.memoryhub/
├── memory.db
└── exports/        # 可选，后续导出 markdown 时使用；v1 可为空
```

## 6. 持久化模型

### 6.1 `approved_memories`

当前生效版本。

建议字段：

- `uri`
- `type`
- `title`
- `content`
- `recall_when`
- `why_not_in_code`
- `source_reason`
- `status`
- `current_version_id`
- `created_at`
- `updated_at`

### 6.2 `memory_versions`

历史版本与回滚基线。

建议字段：

- `id`
- `uri`
- `type`
- `title`
- `content`
- `recall_when`
- `why_not_in_code`
- `source_reason`
- `status`
- `supersedes_version_id`
- `created_at`
- `created_by`

### 6.3 `memory_proposals`

所有待审创建 / 更新请求。

建议字段：

- `id`
- `proposal_kind` (`create` / `update`)
- `target_uri`
- `type`
- `title`
- `content`
- `recall_when`
- `why_not_in_code`
- `source_reason`
- `patch_old_string`
- `patch_new_string`
- `append_content`
- `guard_decision`
- `guard_reason`
- `status` (`pending` / `approved` / `rejected`)
- `created_at`
- `reviewed_at`
- `review_note`

## 7. MCP 控制面

v1 固定为本地 stdio MCP server。

### 7.1 `read_memory(uri)`

职责：

- 读取 `system://boot`
- 读取普通 approved memory
- 不读取 pending / rejected proposal

约束：

- `system://boot` 默认只返回 approved 的 `identity` 与 `constraint`
- 返回内容要包含：正文、类型、最近版本、`recall_when`、最近审查状态

### 7.2 `search_memory(query, type?, scope_hint?)`

职责：

- 只检索 approved memory
- v1 使用关键词 / FTS 检索

排序建议：

- `type` 命中优先
- 文本命中度优先
- 最近更新时间次之

### 7.3 `propose_memory(type, title, content, recall_when, why_not_in_code, source_reason)`

职责：

- 创建 durable memory 提案
- 不直接写入 approved store

约束：

- 仅允许四种 `type`
- 缺少 `why_not_in_code` 或 `source_reason` 直接拒绝
- 空内容直接拒绝

### 7.4 `propose_memory_update(uri, old_string, new_string, append?, recall_when?, source_reason?)`

职责：

- 基于 patch 或 append 生成更新提案

约束：

- 禁止 full replace
- `old_string/new_string` 必须成对出现，或只允许合法 append
- `append=""` 直接拒绝
- 更新前建议先 `read_memory(uri)`

## 8. 写入守卫

v1 采用最小 write guard，只做规则 + 关键词/FTS，不接入 embedding 或 LLM。

### 8.1 拒绝条件

- `content` 为空
- 非法 `type`
- 缺少 `why_not_in_code`
- 缺少 `source_reason`

### 8.2 判定结果

- `NOOP`
  - 与现有 approved memory 等价或无新增价值
- `UPDATE_TARGET`
  - 与现有 approved memory 高重合，更像更新已有记忆
- `PENDING_REVIEW`
  - 通过 guard，进入 review 队列

### 8.3 设计原则

- guard 的职责是“挡掉明显错误”和“减少重复”
- guard 不负责替代人类审批
- v1 采用 fail-closed：guard 无法正常完成时，不继续写入

## 9. 审查与回滚

统一通过 CLI 进行：

```bash
memory-hub review list
memory-hub review show <proposal_id>
memory-hub review approve <proposal_id>
memory-hub review reject <proposal_id>
memory-hub rollback <uri> --to-version <id>
```

### 9.1 approve 的事务要求

`approve` 必须在单个 SQLite 事务里完成：

1. 写入新的 `memory_versions`
2. 更新 `approved_memories.current_version_id`
3. 更新 `approved_memories` 当前内容
4. 更新 `memory_proposals.status = approved`
5. 记录审计信息

任何一步失败，都不允许留下中间态。

### 9.2 reject 的语义

- 仅更新 proposal 状态
- 不修改 active memory

### 9.3 rollback 的语义

- 基于 `memory_versions` 恢复到指定版本
- rollback 后也要留下新版本记录，不直接抹历史

## 10. Durable Memory 的价值约束

v1 不允许“什么都记”。

每条 durable memory 都必须回答两个问题：

1. `why_not_in_code`
   - 为什么这条信息不能通过读代码得到
2. `source_reason`
   - 这条信息来自哪里，为什么可信

如果不能清晰回答，就不应进入 durable memory。

## 11. Skill / CLAUDE 侧的强约束

需要将现有规则切换到新模型：

1. 首次 memory 操作前先 `read_memory("system://boot")`
2. 读后再改
3. 不允许直接编辑 `.memory*` 路径
4. 发现长期信息时，只允许调用 `propose_*`
5. skill 不再教授“先写 markdown，再 index”的流程

## 12. 测试验收基线

### 12.1 写入约束

- agent 只能通过 MCP `propose_*` 修改 durable memory
- 非法参数组合必须失败
- 不存在的 full replace 路径必须被拒绝

### 12.2 write guard

- 完全重复内容返回 `NOOP`
- 高重合内容返回 `UPDATE_TARGET`
- 正常新内容返回 `PENDING_REVIEW`

### 12.3 原子性

- `approve` 成功后 active / version / proposal 状态一致
- `approve` 失败时不得残留中间态
- `reject` 不影响 active memory
- `rollback` 能恢复指定版本

### 12.4 读取侧

- `system://boot` 只包含 approved 的 `identity / constraint`
- `search_memory` 不返回 pending / rejected proposal
- `read_memory` 不返回 proposal 草稿

## 13. 实施顺序建议

建议按下面顺序落地，避免一次改太多：

### Phase 1

- 建立 `.memoryhub/` 与 SQLite schema
- 建立最小 repository / service 层
- 建立 `review` 与 `rollback` CLI

### Phase 2

- 引入本地 stdio MCP server
- 实现 `read/search/propose/update`
- 接通最小 write guard

### Phase 3

- 重写 `CLAUDE.md` 与 `skills/*`
- 移除“直接写文件再 index”的旧路径
- 增补测试

## 14. 结论

这个方案适合作为 v1。

它没有追求产品级 completeness，而是优先建立 durable memory 的最小控制面：

- 一个 authoritative 写入口
- 一个可审查的 proposal 队列
- 一套可回滚的版本链
- 一条明确的价值准入规则

只要这四件事先立住，后续再叠加自动提炼、语义检索、导出和 UI，系统就不会继续沿着当前 v0/v1 的错误方向演化。
