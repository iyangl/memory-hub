# Memory Hub v1 MVP Handoff

日期：2026-03-10
目的：归档这轮方案收敛过程，便于后续继续设计和实现时快速接手。

## 1. 当前问题为什么会发生

本轮分析的结论很明确：当前项目的问题不是单点 bug，而是设计层错位。

### 1.1 没有 authoritative 写入口

设计文档里提到 `memory.write`，但真实 CLI 并没有这个命令，只有 `index`。

结果是：

- agent 先直接改 `.memory/` 文件
- 再调用 `memory-hub index`

这导致：

- 无法强约束 agent
- 无法保证跨文件一致性
- 无法保证原子性
- 无法做真正的 review / rollback

### 1.2 文档、skill、实现已经漂移

仓库里多个地方仍在教 agent 使用不存在或不一致的接口：

- `REDESIGN.md` 仍以 `memory.write` 为核心
- `skills/memory-init/SKILL.md` 仍示例 `memory-hub write`
- `CLAUDE.md` 与 `skills/memory-index/SKILL.md` 又允许直接编辑 `.memory/`

这会让 agent 在工具失败后直接绕开系统。

### 1.3 init 天然产出浅层知识

当前 `init` 只是创建 `.memory/` 骨架，不会真正生成高价值 durable memory。

更重要的是，即使未来把 init 做得更强，它也不可能自动产出太多“代码读不出来”的知识，因为：

- 代码能推导的是结构、依赖、约定、实现
- durable memory 真正有价值的部分是决策、约束、历史、隐性前提、偏好
- 这些内容天然更依赖人工确认或会话沉淀

结论：不能再把 init 当成 durable memory 的主来源。

## 2. 四个 memory 工具的拆解结论

本轮对比对象：

- 当前 `Memory Hub`
- `Nocturne Memory`
- `OpenClaw Memory Fusion`
- `Memory Palace`

### 2.1 Memory Hub

优点：

- 目标定义是对的：只存代码读不到的知识
- 强调按需读取，不做全量 preload

短板：

- 没有 authoritative 写入口
- 没有 guard
- 没有 review 队列
- 没有 rollback 机制

### 2.2 Nocturne Memory

最值得借鉴的点：

- MCP 工具是正式写入口
- patch/append 更新，不鼓励 full replace
- snapshot / rollback 是系统能力
- `system://boot` 这类 system URI 很适合作为“先读什么”的硬约束

不必照搬的点：

- v1 不必直接引入 Node / Edge / Path 级别的复杂图抽象

### 2.3 OpenClaw Memory Fusion

最值得借鉴的点：

- 不依赖模型在线时“自觉写记忆”
- 将在线工作流和离线沉淀拆开
- 只保留高信号内容，主动避免递归污染

不必照搬的点：

- 当前阶段不需要 cron / ETL / QMD 这套运维流水线

### 2.4 Memory Palace

最值得借鉴的点：

- 写入前 `write_guard`
- fail-closed
- patch-only 更新
- write lane / review / rollback 闭环
- system URI + intent-aware retrieval 的控制面思路

不必照搬的点：

- v1 不需要 embedding、reranker、UI、maintenance 全家桶

## 3. 最终收敛出的设计原则

这轮讨论后，锁定了下面几条原则：

1. durable memory 必须有 authoritative 写入口
2. durable memory 不允许 agent 直接写文件
3. 写入要先 proposal，再 review，再 approve
4. v1 先解决“对不对、稳不稳”，不解决“高级不高级”
5. durable memory 只保留四类高价值信息：
   - `identity`
   - `decision`
   - `constraint`
   - `preference`
6. durable memory 必须明确说明：
   - 为什么代码里读不出来
   - 为什么这条信息可信

## 4. 已锁定的 v1 方案

### 4.1 技术路线

- `Hybrid`
- SQLite 作为 durable truth source
- 本地 stdio MCP 作为 agent 操作面
- CLI 作为人类 review / rollback 操作面
- Markdown 不再作为 durable memory 主写入面

### 4.2 写入模型

agent 只能做两类 durable 写动作：

- `propose_memory`
- `propose_memory_update`

两者都只产生 proposal，不直接改 active memory。

### 4.3 审查模型

关键 durable memory 统一走 CLI proposal queue：

- `review list`
- `review show`
- `review approve`
- `review reject`

### 4.4 更新模型

v1 坚持 patch/append，不提供 full replace。

原因：

- 降低误改整条记忆的风险
- 更适合 review
- 更容易生成版本链

### 4.5 读取模型

- 首次 memory 操作前先读 `system://boot`
- `system://boot` 只包含 approved 的 `identity / constraint`
- `decision / preference` 按需搜索或定向读取

## 5. 暂时不做的事情

为了把 v1 范围压住，以下内容明确不做：

- 自动会话提炼
- 语义检索 / 混合检索
- web review 面板
- 图结构
- alias / path cascade
- 自动迁移旧 `.memory/`
- 多用户并发
- 远程服务部署

## 6. 为什么不继续沿用旧 `.memory/` 方案

原因不是 markdown 本身不好，而是它在当前项目里的角色过重：

- 既是 agent 的直接写目标
- 又是 durable truth source
- 还承担索引同步

这三个职责绑在一起后，任何一步失败都会让状态变得不可信。

因此 v1 的调整不是“抛弃可读文本”，而是把 durable truth source 迁到 SQLite，把 markdown 降级为未来的导出 / 审阅材料。

## 7. 后续实现建议顺序

建议按这个顺序推进：

1. 新建 `.memoryhub/` 和 SQLite schema
2. 完成 `approved_memories / memory_versions / memory_proposals`
3. 实现 `review` 与 `rollback` CLI
4. 实现最小 stdio MCP server
5. 接入 `read/search/propose/update`
6. 增加最小 write guard
7. 重写 `CLAUDE.md`
8. 重写 `skills/*`
9. 补测试

不要反过来先改 skill 文案，因为没有 authoritative 后端时，skill 约束仍然是软的。

## 8. 后续实现时要重点验证的点

### 8.1 原子性

- `approve` 失败时不能留下半更新状态
- `rollback` 不能破坏版本链

### 8.2 guard 质量

- 完全重复要判成 `NOOP`
- 高重合要判成 `UPDATE_TARGET`
- 新内容才能进入 `PENDING_REVIEW`

### 8.3 行为约束

- agent 侧不能再看到“直接写 `.memory/`”的路径
- 任何 durable 写入都必须经过 proposal

## 9. 风险与注意事项

### 9.1 风险

- 如果 MCP 工具契约设计得太底层，agent 还是会难用
- 如果 proposal 字段太少，review 时会缺上下文
- 如果 review 全部手工且缺少筛选，后续会变成运维负担

### 9.2 当前推荐的处理方式

- v1 工具参数宁可偏显式，也不要过度抽象
- proposal 必须携带 `why_not_in_code` 和 `source_reason`
- 先把 review 队列做出来，再看是否需要加优先级或批处理

## 10. 本轮产出物

本轮已经归档两类文档：

- 方案基线：`.archive/plans/2026-03-10-memory-hub-v1-mvp-plan.md`
- 交接记录：`.archive/handoffs/2026-03-10-memory-hub-v1-mvp-handoff.md`

后续如果开始实现，建议继续在 `.archive/handoffs/` 下追加：

- 实施前 checklist
- 阶段性变更摘要
- 失败尝试与回退说明

这样可以把设计演化链保留下来，避免以后重复走这轮已经排除掉的弯路。
