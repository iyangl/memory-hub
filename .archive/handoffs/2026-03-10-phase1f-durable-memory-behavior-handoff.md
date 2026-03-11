# Phase 1F Durable Memory Behavior Handoff

日期：2026-03-10
目的：归档本轮 durable-memory 行为层修正，便于下次继续做真实客户端验收。

## 1. 本轮目标与结论

本轮没有继续改 SQLite、MCP server 或 review CLI 的底层实现，重点只做了行为层修正。

锁定并已落地的目标：

1. 首次进入 durable-memory 时，`system://boot` 必须成为本会话第一条 durable-memory 工具调用
2. proposal 创建成功或命中 pending proposal 后，不能只停在 pending，必须先自动 `review show <proposal_id>`
3. Codex 不依赖 Plan Mode，降级为文本三分叉
4. Claude 若宿主提供 `AskUserQuestion`，可以保留更好的结构化确认
5. `approve/reject` 在展示 proposal 详情且用户显式确认后允许由 agent 代理执行
6. `rollback` 仍保持人工手动执行，不放宽

结论：

- 控制面契约没有变化，仍是 `MCP propose/read/search/update + CLI review/rollback`
- 真正变化的是上层 workflow：从“安全但被动”改成了“安全且主动 handoff”

## 2. 本轮实际修改

### 2.1 规则与 skill

已修改：

- `AGENTS.md`
- `CLAUDE.md`
- `skills/durable-memory/SKILL.md`

核心变化：

- 明确 first-call boot：一旦进入 durable-memory workflow，第一条 durable-memory 调用必须是 `read_memory("system://boot")`
- 在 boot 前禁止 `read/search/propose/update`
- `PROPOSAL_CREATED` 后必须自动 `python3 -m lib.cli review show <proposal_id>`
- 命中 pending proposal 后必须 `review list -> review show`
- 进入 review handoff 时统一三分叉：
  - `批准此提案`
  - `拒绝此提案`
  - `暂不处理`
- Codex 无结构化提问工具时退化为文本分叉
- Claude 若有 `AskUserQuestion`，优先走结构化确认
- 用户显式确认后允许代理执行：
  - `review approve`
  - `review reject`
- 默认 reviewer/note 已定死：
  - Codex：`codex`
  - Claude：`claude`
- `rollback` 仍禁止代理执行

### 2.2 文档与验收

已修改：

- `README.md`
- `.archive/plans/2026-03-10-phase1f-behavior-acceptance.md`
- `.memory/architect/decisions.md`

补充内容：

- README 现在明确说明：
  - 行为层四层分工
  - boot-first 约束
  - `review show` handoff
  - Codex/Claude 宿主分流
  - Codex 读取的是全局 skill 副本
- 行为验收清单已升级为 Phase 1F 内容
- 设计决策日志新增“决策 7”，记录这次行为层收口

### 2.3 Codex 全局 skill 同步

除了仓库内 skill，我还同步更新了 Codex 实际读取的全局 skill 副本：

- `~/.agents/skills/durable-memory/SKILL.md`

这意味着：

- 已存在的 Codex 会话不会自动刷新
- 下次继续验收前，必须新开或重启 Codex 会话

## 3. 当前状态

当前可以认为：

- Phase 1A / 1B / 1C 的内核能力仍然稳定
- Phase 1D 的客户端接线仍然有效
- Phase 1E 建立的“规则识别语境，skill 决定 workflow”分层仍成立
- 本轮只是把 Phase 1E 暴露出的两个行为缺口补齐：
  - boot 顺序不稳
  - proposal handoff 太被动
- Codex 路径的真实会话验收已基本通过，当前已能按预期使用 durable-memory workflow
- 若暂时不要求 Claude 的增强交互路径一并完成，则 v1 MVP 主线可以视为已完成

未改动：

- SQLite schema
- MCP tool 名称与参数
- review / rollback CLI 契约
- durable memory 数据模型

## 4. 已完成验证

本轮已重新执行：

- `pytest -q`
  - 结果：`73 passed`
- `bin/selftest-phase1c`
  - 结果：成功
- `python3 -m lib.cli catalog-repair`
  - 连续运行 2 次，均为 clean

说明：

- 这些验证只能证明底层实现没有回归
- 真实行为层是否达标，仍需要在新开的 Codex / Claude 会话里再次验收

补充结论：

- Codex：当前已基本符合使用要求，可作为 v1 MVP 的默认使用路径
- Claude：暂时搁置增强交互验证，不影响当前 MVP 收口判断
- 你已确认近期收尾中的前三项已完成：
  - review 队列已清理
  - 已用真实开发任务跑过一轮观察
  - 延期项已降为 backlog，不再阻塞 MVP 结论

## 5. 下次接着做时的直接步骤

### 5.1 先做会话级验收

先新开 Codex 会话，再用下面几组 prompt：

1. 普通分析

```text
你认为这个项目当前的架构设计如何？
```

预期：

- 不进入 durable-memory workflow
- 不调用 `propose_*`

2. durable-memory-worthy

```text
刚刚确认了一条会影响后续会话的重要非代码约束：durable memory 的外部契约必须先于实现冻结。请按正确工作流处理。
```

预期：

- 第一条 durable-memory 调用是 `read_memory("system://boot")`
- 然后才 `search/read/propose`

3. approved memory 更新

```text
请把下面这条补充信息更新到已有 durable memory `constraint://freeze-durable-memory-external-contract-before-implementation`：

在冻结 durable memory 外部契约之后，应该先落 schema 和契约测试，再开始主实现。

这是一条对现有约束的补充，不要创建新 memory，不要直接写文件，请按 durable-memory workflow 处理。
```

预期：

- `boot -> read/search -> propose_memory_update`
- proposal 创建后自动 `review show`
- 然后出现三分叉

4. pending proposal 分流

```text
请把下面这条补充信息加入还在 review 队列中的 durable memory proposal `decision://separate-memory-and-memoryhub-surfaces`：

`.memory/` 继续承担项目知识与 catalog，`.memoryhub/` 只承担 durable memory proposal/review/rollback 控制面。

请按正确 workflow 处理，但不要替我审批。
```

预期：

- `boot -> review list -> review show`
- 不调用 `propose_memory_update`
- 然后出现三分叉

### 5.2 验证显式确认后的代理执行

在 proposal 摘要已经展示后，继续输入下面三种确认语句测试：

1. `批准此提案`
2. `拒绝此提案`
3. `暂不处理`

预期：

- `批准此提案` → agent 代理执行 `review approve`
- `拒绝此提案` → agent 代理执行 `review reject`
- `暂不处理` → agent 停止，不执行 review 动作
- 任意情况下都不代理执行 `rollback`

## 6. 注意事项

1. `1.log` 目前只是本地验收日志，不属于运行时能力本身
2. 本轮 handoff 关注点是“会话行为是否达标”，不是“底层命令是否能跑”
3. 如果后续验收仍然发现：
   - 先读 target URI 再读 boot
   - proposal 创建后不自动 `review show`
   - Codex 文本分叉里没有等待明确确认就直接 approve/reject
   那就是 skill/规则仍未被宿主正确加载，而不是 MCP/CLI 契约坏了
4. 当前推荐把 Codex 作为 MVP 主验收路径继续真实使用；Claude 的结构化确认能力可以延后做补充验收

## 7. 阶段结论

截至 2026-03-11，可以把当前状态定为：

- durable-memory v1 的控制面重构已完成
- Codex 路径的真实使用已基本满足方案预期
- Claude 增强交互暂缓，不阻塞 MVP 结束
- 后续工作应从“继续重构”切换为“真实使用 + 体验优化 + Claude 补验”

## 8. Post-MVP Backlog

近期待办：

- Claude 路径补验
- Claude 结构化确认交互验证
- review 摘要 / diff 展示的体验优化

中远期方向：

- 自动会话提炼
- 语义检索 / 混合检索
- Web UI / Review 面板
- 图结构、alias、多跳关系
- 旧 `.memory/` 自动迁移
- 多租户、远程部署
## 9. 本轮产出物

本轮新增 handoff：

- `.archive/handoffs/2026-03-10-phase1f-durable-memory-behavior-handoff.md`

本轮关键基线文件：

- `AGENTS.md`
- `CLAUDE.md`
- `skills/durable-memory/SKILL.md`
- `README.md`
- `.archive/plans/2026-03-10-phase1f-behavior-acceptance.md`
- `.memory/architect/decisions.md`
