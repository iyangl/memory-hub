# memory-hub continuity / resume 设计草案（draft）

> 日期：2026-04-02
> 状态：draft
> 用途：Git 跟踪的设计草案 / 跨电脑 handoff 落点

这份草案基于对 livebase 的参考阅读，目标不是把 memory-hub 改造成另一个产品，而是在现有 recall-first / save correctness core 之上，补齐“工作连续性（continuity）/ 续跑（resume）”这一层。

## 一句话目标

把 memory-hub 从“能定位和保存知识”扩展为“能围绕未解证据缺口恢复工作”的本地 continuity engine。

## 当前基础（已存在）

memory-hub 已经具备这条链路的关键底座：

- recall 先做 plan，再决定读什么：`lib/recall_planner.py:556`
- deep recall 会生成压缩后的 working set：`lib/session_working_set.py:277`
- durable save 有严格 evidence guard，且禁止 working set 原样回写：`lib/memory_save.py:353`、`lib/memory_save.py:215`
- save 完成后自动重建 brief 与 catalog：`lib/memory_save.py:689`

因此，不建议推翻现有 memory 语义；更合适的方向是在其上增加 continuity 语义层。

## 要解决的问题

当前系统擅长回答：

- 该读哪些 docs / module cards？
- 哪些结论可以 durable save？
- 怎样避免把 session 内容污染长期 docs？

但还没有把下面这些对象正式产品化：

- 当前卡在哪个 evidence gap
- 下一步最小动作是什么
- 执行前的边界是什么
- 执行后哪些验证结果应留下，哪些只该作为 residue

结果是：recall 很强，save 很强，但“从 recall 到 act 再到 save”的中段还偏隐式。

## 核心设计原则

### 1. memory 是底座，continuity 是价值输出

- `.memory/docs/` 仍然是 durable knowledge 的唯一正本
- recall-first 与 save correctness core 保持不变
- 新设计只增加 session / workflow 语义，不削弱现有约束

### 2. 从“读什么”升级到“补哪个 gap”

recall 的目标不只是定位相关资料，而是明确：

- 当前主 evidence gap 是什么
- 为什么它阻塞任务推进
- 应该通过哪类证据来解决
- 解决后下一步最小动作是什么

### 3. working set 不只是摘要，而是 resume pack

deep recall 产物应该被重新定位为“最小可信恢复包”，面向继续执行，而不是面向回忆历史。

### 4. 执行前要有 contract，执行后要有 verification ledger

- contract：限制行动边界，降低 agent 自由发挥导致的偏航
- ledger：记录验证结果、未决歧义和 residue，服务下一次恢复

## 建议新增的 3 个会话级对象

### A. resume-pack

定位：由 deep recall 产出的最小恢复包。

建议关系：

- 可先复用现有 `working-set` 产物语义
- 先不必立刻新增命令，可把 `working-set` 视为 v1 resume-pack
- 后续若独立命令更清晰，可新增 `memory-hub resume-pack`

建议字段（Phase 1 定稿）：

- `task`
- `task_kind`
- `primary_evidence_gap`
- `verification_focus`
- `priority_reads`
- `durable_candidates`
- `source_plan`

说明：
- `primary_evidence_gap` 由 planner 直出，working-set 只透传
- `verification_focus` 只从压缩后的 `items[*].bullets` 中投影，不引入第二套抽取逻辑
- `durable_candidates` 保留为 save hint，不承担下一步执行指令
- `why_now`、`next_minimal_action`、顶层 `constraints` 不进入 Phase 1

建议约束：

- 必须短、小、可执行
- 偏向未决 gap / 下一步 / 边界 / 验证，而不是罗列背景
- 仍禁止原样回写 durable docs

### B. execution-contract

定位：在 recall 之后、执行之前生成的边界描述。

建议命令：

- `memory-hub contract --resume-file <path> [--out <file>]`

建议字段：

- `task`
- `goal`
- `confirmed_facts`
- `primary_evidence_gap`
- `allowed_sources`
- `disallowed_behaviors`
- `success_criteria`
- `required_evidence`
- `writeback_expectation`

建议作用：

- 给 agent / host 一个 machine-readable 的执行边界
- 把“不能猜来源、要带 evidence、不要把 working set 原样写回”等现有规则前置
- 降低 recall 完成后直接进入实现时的偏航风险

### C. verification-ledger

定位：执行后、save 前的结构化回写账本。

建议命令：

- `memory-hub writeback --contract <path> --out <file>`

建议字段：

- `task`
- `actions_taken`
- `checks_run`
- `findings`
- `resolved_gaps`
- `remaining_ambiguities`
- `residue`
- `durable_save_candidates`
- `source_refs`

建议作用：

- 区分“已经验证过的事实”和“只是工作中看到的片段”
- 为 `/memory-hub:save` 提供更高质量输入
- 为下次 resume 提供更短的入口

## 对现有产物的映射

### 现状 → 建议命名/角色

- `recall-plan` → 保持不变，负责判定 recall 深度与推荐来源
- `working-set` → 语义升级为 `resume-pack(v1)`
- `save-request` → 保持 durable save 输入角色不变
- `save-trace` → 仍是 save 阶段 trace artifact，不承担 continuity 主流程

### session 目录建议分层

建议未来把 `.memory/session/` 内产物按职责理解为：

- `recall-plan`：恢复判定
- `resume-pack`：恢复输入包
- `execution-contract`：执行边界
- `verification-ledger`：执行验证账本
- `save-request`：durable save 申请
- `save-trace/*`：save traceability artifact

不要求立刻调整物理目录；先统一语义即可。

## 建议的最小工作流

### v1（最小落地）

1. `recall-plan`
2. `working-set`（视为 resume-pack）
3. 人或 agent 执行任务
4. `save-request`
5. `save`

在这个版本里，先只做两件事：

- 给 `working-set` 增加 `primary_evidence_gap` / `verification_focus`
- 在 slash command 或 host 侧，把 `working-set` 解释为 resume-pack

### v1.5（补齐 contract）

1. `recall-plan`
2. `resume-pack`
3. `execution-contract`
4. act
5. `save-request`
6. `save`

这个版本的重点是把执行边界显式化。

### v2（补齐 ledger）

1. `recall-plan`
2. `resume-pack`
3. `execution-contract`
4. act
5. `verification-ledger`
6. `save-request`
7. `save`

这个版本里，resume / verify / save 会形成完整闭环。

## 为什么这个方案适合 memory-hub

### 1. 与现有架构一致

它沿用现有硬边界：

- docs 仍是唯一正本
- session artifact 仍不可直接当 durable docs
- save 仍由 correctness core 严格把关

### 2. 能增强 agent 集成

现有系统已经很适合 host / slash command 驱动；新增 contract 后，可以更自然支持：

- Claude Code / Codex / MCP host
- 多宿主共享同一套执行边界
- 机器可读的 resume / contract / writeback 资产

### 3. 能把 recall 与 save 之间的“中段”补齐

目前 memory-hub 的两端很强：

- recall-before-guess
- guarded durable save

新增 continuity 对象后，中间链路会更完整：

- 为什么现在读这些
- 当前 gap 是什么
- 接下来应该做什么
- 做完后留下什么证据

## 非目标

这份草案明确不建议在近期引入：

- 向量检索或 heavy RAG
- 多设备同步
- 长会话全文存档
- 把 memory-hub 做成通用 agent platform
- 为 continuity 新增过重的对象图或复杂状态机

## 建议的落地顺序

### Phase 1

只改语义，不改主流程：

- 把 `working-set` 定义为 `resume-pack(v1)`
- 为其新增 `primary_evidence_gap`、`verification_focus`
- 保留 `durable_candidates`
- 不做 `next_minimal_action` 与顶层 `constraints`
- 更新相关命令模板与宿主提示词

### Phase 2

增加 `execution-contract` 命令与 JSON 产物。

### Phase 3

增加 `verification-ledger` 命令与 JSON 产物，并研究是否能为 `/memory-hub:save` 提供结构化输入草稿。

## 开放问题

- `execution-contract` 是否只作为 session artifact，还是也允许 host 直接内联消费？
- `verification-ledger` 与 `save-request` 的边界应该多近：是前置账本，还是可直接半自动生成 save-request？
- 是否需要新增 `resume` 命令，还是继续由 `working-set` / slash command 承担？

## 当前建议结论

最稳妥的方向不是“重做 memory-hub”，而是：

- 保留现有 recall-first + durable save core
- 用 `resume-pack / execution-contract / verification-ledger` 这三个 session 级对象，补齐 continuity 主线
- Phase 1 已按最小范围落地：`primary_evidence_gap` 由 planner 直出，`verification_focus` 从压缩后的 items 投影，`durable_candidates` 保持不变
- 先把 continuity 做成 session artifact 语义，再决定是否升级为独立 CLI 命令

这条路最贴近现状，改动最小，也最容易逐步验证价值。
