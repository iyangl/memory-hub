# Memory Hub End-of-Task Probe Design

日期：2026-03-11  
状态：草案

## 1. 背景

Phase 2F 已经提供 `session-extract`，可以把一段会话沉淀成 `docs-only`、`durable-only`、`dual-write` 三类候选，并复用现有 unified write lane 与 review surface。

当前缺口在于：

- `session-extract` 是显式维护动作，不是每次任务的默认收尾步骤
- agent 完成任务后，经常直接结束回复，没有再做一次“这次工作里有没有值得未来记住的内容”的检查
- 如果把这件事设计成新的可见 skill，会再次破坏 v2 已经收敛好的入口心智

因此，需要一个内部的 `end-of-task probe`：

- 由规则在任务结束前强制触发
- 允许返回 `NOOP`
- 不新增新的公开 skill / MCP 主入口
- 继续复用现有 write / review 边界

## 2. 设计结论

`end-of-task probe` 定义为：

- 一个内部工作流步骤，不是第三个可见 skill
- 触发时机是“任务准备结束、即将发送最终答复之前”，不是每一轮对话结束
- 只负责发现候选，不负责绕过 review 直接落盘
- 默认高阈值运行，优先返回 `NOOP`

它与现有能力的关系是：

- `project-memory` 仍然是日常项目记忆主入口
- `memory-admin` 仍然是显式维护入口
- `session-extract` 继续保留为手工 / 批量提炼工具
- `end-of-task probe` 只是把“本次任务是否值得沉淀”的检查，变成默认收尾动作

## 3. 目标

- 让 agent 在每次任务收尾时，默认做一次记忆价值检查
- 降低“用户没提醒就没有沉淀”的遗漏率
- 保持 `docs lane` 为正式项目知识主文档
- 保持 durable memory 的高门槛与 review discipline
- 不让用户学习新的产品入口

## 4. 非目标

- 不要求每次任务都产出候选
- 不自动 approve docs review 或 durable proposal
- 不把 probe 设计成新的 MCP tool
- 不在 casual chat、翻译、一次性问答后强制制造记忆
- 不取代 `session-extract` 的离线 / 批量会话提炼用途

## 5. 触发策略

probe 只在满足以下条件时触发：

- agent 正在结束一个 task-oriented 会话
- 本次任务涉及仓库阅读、代码修改、设计结论、规则澄清，或显式讨论“该记住什么”
- agent 即将发送最终答复

probe 默认不触发于：

- casual chat
- 单纯翻译 / 改写
- 与项目无关的一次性问答
- 明确被用户要求“不要记录 / 不要记住”的内容
- 中途放弃或未完成的任务

约束：

- 每个任务最多触发一次
- 若 probe 结果为 `NOOP`，不向用户额外暴露冗余流程
- 若 probe 创建了 review 目标，可以在最终答复中顺带说明，但不强制把最终答复变成审查会话

## 6. 固定自检问题

probe 执行时，agent 固定问自己三件事：

1. 本次任务新增了哪些未来会重复用到的项目知识，应该进入 docs？
2. 本次会话明确了哪些代码里不能稳定恢复的 decision / constraint / preference / identity，应该进入 durable？
3. 如果下一次在新会话里继续这项工作，缺少哪条信息会明显增加理解成本？

如果三个问题都得不到稳定答案，probe 必须返回 `NOOP`。

## 7. 输入上下文

probe 的最小输入应包含：

- 本次用户请求与最终完成范围
- 本次会话中 agent 的最终任务摘要
- 触达过的核心文件与改动 diff
- 已创建但尚未处理的 docs review / durable proposal
- 必要时的现有 memory 搜索结果

建议的上下文优先级：

1. 本次修改的文件与 diff
2. 本次任务总结
3. 最近几轮与结论有关的会话内容
4. 现有 docs / durable 命中结果

不要求 probe 依赖完整原始 transcript 文件。

## 8. 决策模型

probe 只允许四种输出：

- `NOOP`
- `docs-only`
- `durable-only`
- `dual-write`

推荐判断顺序：

1. 若信息完全可从代码、测试、现有 docs 稳定恢复，则 `NOOP`
2. 若信息属于正式项目知识，优先 `docs-only`
3. 若信息既需要成为正式项目文档，又需要更强的 recall / review handoff，则 `dual-write`
4. 只有当信息不适合进入 docs、但确实需要跨会话保存时，才使用 `durable-only`

默认偏置：

- 优先 `NOOP`
- 其次 `docs-only`
- 对 `durable-only` 采用最高门槛

## 9. Durable 门槛

probe 只有在以下条件同时满足时，才允许产生 `durable-only` 或带 durable 分支的 `dual-write`：

- 未来会在后续会话中再次重要
- 无法稳定从代码或正式 docs 中恢复
- 结论足够稳定，不是临时猜测
- 能明确写出 `why_not_in_code`
- 能落入四种 durable type 之一：
  - `identity`
  - `decision`
  - `constraint`
  - `preference`

典型 durable 候选：

- 用户或项目的稳定偏好
- 明确说清但不会写进代码的约束
- 会影响后续协作方式的决策

默认不应进入 durable 的内容：

- 纯实现细节
- 已写入代码或测试即可恢复的信息
- 临时排障过程
- 一次性无后续价值的上下文

## 10. 候选 Schema

probe 的内部候选建议统一为：

```json
{
  "route": "docs-only | durable-only | dual-write",
  "title": "short title",
  "summary": "one-paragraph summary",
  "content": "candidate body",
  "doc_bucket": "pm | architect | dev | qa | null",
  "memory_type": "identity | decision | constraint | preference | null",
  "why_not_in_code": "required for durable paths",
  "recall_when": "required for durable paths",
  "source_reason": "why this was learned in the current task",
  "related_files": ["path/a", "path/b"],
  "confidence": "high | medium"
}
```

约束：

- 每次 probe 最多提交 3 个候选
- `durable-only` / `dual-write` 必须填写 `memory_type`、`why_not_in_code`、`recall_when`
- `docs-only` 必须能明确归到一个 docs bucket

## 11. 执行流程

建议执行顺序：

1. 任务准备结束时触发 probe
2. 收集最小上下文并回答固定三问
3. 生成 0 到 3 个候选，或返回 `NOOP`
4. 对每个候选先做去重 / 命中判断
5. 若仅为 docs 候选，直接复用 `capture_memory` / `update_memory`
6. 若存在 durable 候选，且本会话尚未进入 durable branch，先执行 `read_memory(ref="system://boot")`
7. 对 durable / dual-write 候选复用现有 `capture_memory` / `update_memory` 与 write guard
8. 若结果进入 pending review，立即调用 `show_memory_review(...)`
9. 最终答复中只做简洁说明，不自动 approve / reject

## 12. 与现有能力的复用关系

probe 不应重新发明自己的存储或审查逻辑。

它应直接复用：

- `capture_memory(...)`
- `update_memory(...)`
- `show_memory_review(...)`
- docs review queue
- durable proposal / review queue
- 现有 `NOOP` / `UPDATE_TARGET` guard 语义

实现上优先共享 Phase 2F 的提炼与分类逻辑，而不是再做一套完全独立的 heuristics。

## 13. 规则集成建议

规则层只做两件事：

- 在 task-oriented 会话的最终答复前，强制执行一次 probe
- 明确 probe 允许 `NOOP`，且不得绕过 review

建议固定提示模板：

```text
Before final answer, run one end-of-task probe.
Ask:
1. What project knowledge from this task should future work see?
2. What stable non-code decision/constraint/preference emerged?
3. If nothing meets the threshold, return NOOP.
Prefer NOOP over low-value memory.
Prefer docs-only over durable-only when in doubt.
```

`project-memory` 仍然是主入口；probe 是其收尾步骤，不是独立入口。

## 14. 参考项目借鉴

本设计主要参考了三个方向，但只借用与当前 v2 边界一致的部分。

### 14.1 OpenClaw Memory Fusion

借鉴点：

- 不把“是否沉淀”交给模型自觉，而是做成系统级强制流程
- 输入必须先去噪，只保留高信号内容
- 要显式防止递归污染，例如把自己的通知、工具输出、维护回显重新喂回提炼器
- 可以接受后续分层治理，但不要求第一次实现就上完整 cron 体系

落到本设计中的对应做法：

- probe 在 task-oriented 会话结束前强制触发一次
- probe 只看任务摘要、diff、相关文件与必要的现有 memory 命中结果
- 明确排除 tool output、system banner、review 回显、agent 自己的通知文本
- 当前只先落单次 end-of-task probe；后续若需要，再追加低频 consolidation

不照搬的部分：

- 不直接引入 hourly / daily / weekly 三层调度作为 v2 当前实现前提
- 不把 transcript 文件扫描当成当前 probe 的唯一输入事实源

### 14.2 Memory Palace

借鉴点：

- “学习”动作适合做成内部服务，而不是新的公开入口
- 默认 `prepare-only`，先过 write guard，再决定是否执行
- 需要强约束元数据：`source`、`reason`、`session_id`
- 对 rejected / degraded / executed 都要保留审计线索
- 应为 trigger 行为准备稳定样本集

落到本设计中的对应做法：

- probe 定义为内部 workflow step，不新增公开 skill / MCP tool
- probe 默认只产出候选或 `NOOP`，不直接越过 review 落盘
- durable 候选必须提供 `source_reason`、`why_not_in_code`、`recall_when`
- probe 结果继续复用现有 `NOOP` / `UPDATE_TARGET` / pending review 语义
- 单独维护 trigger sample draft，用于回归验证噪音率与路由正确性

不照搬的部分：

- 不引入 Memory Palace 那套更重的 vitality / decay / observability 体系
- 不把 end-of-task probe 暴露成独立维护 API

### 14.3 Nocturne Memory

借鉴点：

- boot-first 必须是硬约束，而不是建议
- read-before-modify 的纪律必须写进规则
- “什么时候该想起这条记忆”需要显式字段，而不是隐含在正文里

落到本设计中的对应做法：

- probe 一旦要进入 durable path，首次 durable tool call 必须先 `read_memory(system://boot)`
- 若命中已有 durable 目标，必须先读 / 看 review，再决定 update
- durable 路径强制填写 `recall_when`，并把它写成尽量单一、具体的触发场景

不照搬的部分：

- 不采用“重要就立刻 create_memory”的即时直写模型
- 不引入 priority / alias / disclosure 全套图式结构作为当前 v2 前提

### 14.4 当前抽象

综合以上参考后，当前 probe 的产品抽象应是：

- 触发：像 OpenClaw 一样由系统强制触发，而不是靠模型自觉
- 守卫：像 Memory Palace 一样先过内部 guard / prepare，再决定是否进入写入面
- 召回：像 Nocturne 一样重视 boot-first 与显式 recall trigger

## 15. Trigger Sample Draft

probe 的触发与结果回归样本草案单独维护在：

- `.archive/plans/2026-03-11-memory-hub-end-of-task-probe-trigger-samples.md`

该样本集应覆盖三类情况：

- 应运行 probe，且产出 `docs-only` / `durable-only` / `dual-write` / `NOOP`
- 应跳过 probe
- 边界样本：允许存在条件性判断，但必须偏保守

## 16. 风险与控制

主要风险：

- 每次任务都跑 probe，可能增加 review 噪音
- LLM 可能把代码中可恢复的信息错误送入 durable
- 最终答复被记忆审查流程打断，影响交互流畅度

对应控制：

- 高阈值 + 默认 `NOOP`
- 候选数上限为 3
- durable 强制检查 `why_not_in_code`
- 默认只在最终答复中附带简洁说明，不自动进入长审查对话

## 17. 最小验收

最小验收标准：

1. 普通无新知识的代码修改任务，probe 返回 `NOOP`
2. 产生正式项目知识的任务，probe 能创建 docs review
3. 产生稳定非代码约束 / 偏好的任务，probe 能创建 durable proposal
4. 第一次进入 durable path 时，probe 仍遵守 boot-first
5. probe 不会直接写 active docs 或 approved durable state
6. 连续对同一任务重复执行 probe，不会重复制造等价候选

## 18. 后续实现建议

推荐分两步落地：

第一步：

- 先以规则 + skill workflow 形式落地
- 不新增 CLI / MCP surface
- 用真实会话观察噪音率与 `NOOP` 比例

第二步：

- 若规则版本证明有效，再把 probe 抽成共享内部服务
- 与 `session-extract` 共享候选分类、去重和 update-target 定位逻辑
- 必要时再补充维护入口用于诊断 probe 结果
