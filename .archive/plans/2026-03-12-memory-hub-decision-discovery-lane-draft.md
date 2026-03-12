# Memory Hub Decision Discovery Lane 设计草案

日期：2026-03-12
状态：草案
目标：作为 v2 主线完成后的下一阶段候选立项入口，补齐“系统能安全地记，但还不够可靠地发现该记什么”的缺口。

## 1. 背景

截至 Phase 2F，Memory Hub 已经具备：

- 统一目录与底座
- 统一读写入口
- docs change review 与 durable review
- 本地 hybrid recall
- `session-extract` 会话提炼

当前系统更强的是：

- `write control`
- `review control`
- `recall quality`

但当前仍然存在一个明显缺口：

- 系统只能较稳定地处理“已经在会话中被表达出来的知识”
- 还不能稳定发现“只隐含在代码修改、默认规则突破、局部例外规则里，但还没被人说出来的知识”

换句话说，当前已经有：

- `write lane`
- `review lane`
- `recall lane`

但还缺：

- `decision discovery lane`

## 2. 目标

Decision discovery lane 的目标不是自动写入知识，而是自动发现“可能值得沉淀的候选知识”。

成功标准：

1. 能从代码变更、现有 docs/default 规则、会话结论中发现高价值候选
2. 发现结果只进入 candidate / review 流，不直接生效
3. 优先抓“规则变化”，而不是抓普通代码事实
4. 尽量减少噪音，不把 memory 变成垃圾堆

一句话目标：

- 自动发现值得审查的知识候选，而不是自动写入最终知识

## 3. 非目标

本阶段明确不做：

1. 不自动批准 docs review 或 durable proposal
2. 不直接改 `.memory/docs/*` 或 active durable state
3. 不追求从任意代码 diff 中归纳一切高层设计意图
4. 不做黑盒、不可解释的大模型自动记忆系统
5. 不新增独立的第三套 review 状态机

## 4. 核心原则

Discovery lane 只做三件事：

1. 发现候选
2. 给出理由
3. 路由到现有 review surface

永远不做：

1. 直接生效
2. 直接写 active docs
3. 直接写 approved durable memory

因此，discovery lane 的正确位置是：

- 在 unified write lane 之前
- 在 docs review / durable review 之前
- 作为 candidate discovery 层存在

## 5. 重点要抓的信号

第一版只抓 5 类高价值信号。

### 5.1 默认规则被打破

模式：

- 现有 docs / durable 中存在默认规则 A
- 新代码实现出现了与 A 不一致的行为 B
- B 不是临时试验，而是稳定选择

例子：

- docs 记录默认网络请求使用 https
- 新模块明确引入 ws
- 这不是普通实现差异，而是默认规则的例外

### 5.2 新例外规则出现

模式：

- 不是全局规则改了
- 而是“某类模块除外”
- 这种信息未来极易漏记

例子：

- 默认都走统一请求封装
- 但实时双向通信模块允许直接使用 ws transport

### 5.3 docs 与实现发生偏离

模式：

- docs 仍描述旧规则
- 实际实现已经稳定按新规则运行
- 如果不更新 docs，下次 agent 会继续沿用旧知识

### 5.4 会影响未来决策的稳定结论

模式：

- 当前会话没有明确说“记下来”
- 但在实现、讨论、review 中已经形成稳定结论
- 这种结论会影响后续模块、接口、约束或审查标准

### 5.5 反复出现的局部模式

模式：

- 新约定在多个文件/模块中重复出现
- 说明它正在演化成项目级规则

## 6. 输出模型

Discovery lane 不直接输出正式 memory，而是输出 `discovery candidate`。

第一版 candidate 字段建议固定为：

- `candidate_type`
  - `docs-only`
  - `durable-only`
  - `dual-write`
- `title`
- `summary`
- `evidence`
- `reason`
- `target_ref?`
- `suggested_route`
- `confidence`
- `conflict_with_existing?`

其中：

- `evidence` 需要可解释，至少指向：
  - 相关 doc ref
  - 代码文件
  - 会话片段
- `reason` 必须说明“为什么这条候选值得被记”

## 7. 与现有系统的接入点

第一版尽量复用现有能力，不新增旁路。

### 7.1 读取面

复用：

- `read_memory(...)`
- `search_memory(...)`
- `system://boot`

用途：

- 获取现有默认规则
- 获取 docs / durable recall 上下文

### 7.2 写入面

发现后的结果不直接写入，而是转成现有写入入口：

- `capture_memory(...)`
- `update_memory(...)`

### 7.3 审查面

仍然复用：

- `show_memory_review(...)`
- docs change review
- durable review

也就是说，discovery lane 本质上是“candidate 生成器”，不是“新的写入系统”。

## 8. 建议的第一阶段实现

我建议第一阶段采用“低成本、高解释性”的规则发现，而不是黑盒语义代理。

### 8.1 输入

第一阶段输入建议只看：

- git diff / 工作区变更
- 相关 docs ref
- 当前 hybrid recall 结果
- 可选的会话摘要

### 8.2 发现方法

采用三步：

1. 抽取现有规则
   - 从 docs / durable recall 中拿当前默认规则与关键约束
2. 抽取新事实
   - 从 diff / 变更文件里抽协议、接口、约束、目录和实现模式变化
3. 对比并生成 candidate
   - 命中“规则突破 / 新例外 / docs 偏离”时生成候选

### 8.3 输出策略

第一阶段只做：

- 列出候选
- 说明理由
- 给出建议路由

不做：

- 自动 apply
- 自动 approve
- 自动合并 multiple candidates

## 9. 用户交互建议

不建议在每次小改动后都打断用户。

更合理的触发点：

1. task-end summary
2. review 前
3. 用户主动要求“整理这次变化里值得记的知识”

交互形式建议：

- 发现到 1~3 条候选时，展示摘要
- 每条候选给：
  - 为什么觉得值得记
  - 证据来自哪里
  - 建议进 docs / durable / dual-write 哪条 lane

## 10. 第一版验收标准

如果立项开发，第一版至少应通过这些场景：

1. 已有默认规则被代码稳定突破时，能生成 candidate
2. 发现“例外规则”时，优先建议 `docs-only` 或 `dual-write`
3. 不会因为普通代码重构生成大量噪音 candidate
4. candidate 具备可解释 evidence
5. candidate 最终仍走现有 docs review / durable review
6. 没有任何 candidate 会直接写 active docs 或 approved durable state

## 11. 当前建议

当前已经适合把 decision discovery lane 作为下一阶段正式立项。

原因：

- v2 已把写入控制、review 和 recall 立住
- 当前最大缺口已非常明确：`怎么更可靠地发现该记什么`
- 这条 lane 可以高度复用现有底座，不需要推翻当前系统

但建议按以下边界启动：

- 先做设计与候选发现
- 不直接做自动写入
- 先做规则突破 / 例外规则 / docs 偏离三类高价值场景
