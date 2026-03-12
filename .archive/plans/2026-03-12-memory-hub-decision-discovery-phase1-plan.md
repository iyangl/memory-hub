# Memory Hub Decision Discovery Lane Phase 1 开发计划

日期：2026-03-12
状态：计划中

## 1. Summary

Decision Discovery Lane Phase 1 的目标是：在当前 v2 已完成的统一记忆系统之上，新增一层“候选发现”能力，用来发现可能值得沉淀的知识点，但不直接写入 active docs 或 approved durable memory。

这阶段只做：

- 从工作区变更、现有 docs/default 规则、当前 recall 上下文中发现候选
- 输出结构化 candidate 列表
- 给出解释、证据和建议路由
- 保持与现有 unified write lane、docs review、durable review 解耦

这阶段不做：

- 自动 apply candidate
- 自动 approve docs review / durable proposal
- 黑盒大模型归纳任意高层意图
- 默认接入 `project-memory` 主 workflow

一句话说：

- Phase 1 先做“发现候选”，不做“自动生效”

## 2. Scope

### In Scope

1. 读取当前工作区代码变更
2. 读取相关 docs / durable recall 上下文
3. 识别 3 类高价值信号：
   - 默认规则被打破
   - 新例外规则出现
   - docs 与实现发生偏离
4. 生成结构化 discovery candidate
5. 提供本地 CLI 入口查看候选
6. 为后续接入 unified write lane 预留映射 helper

### Out of Scope

1. 不直接写 `.memory/docs/*`
2. 不直接写 approved durable state
3. 不新增新的 review 状态机
4. 不接入远程语义服务
5. 不分析 commit 历史、PR 历史或 issue 平台
6. 不在 Phase 1 中直接挂进默认 `project-memory` 主流程

## 3. Discovery Model

### Core Principle

discovery lane 只做三件事：

1. 发现候选
2. 解释为什么值得记
3. 告诉系统建议写入哪条 lane

它永远不做：

1. 直接生效
2. 直接改 docs
3. 直接创建 approved durable memory

### Signal Types

Phase 1 固定只抓 3 类信号：

#### 3.1 默认规则被打破

模式：

- 现有 docs / durable 中存在默认规则 A
- 新代码实现出现与 A 不一致的稳定行为 B

例子：

- docs 记录默认网络请求使用 https
- 新模块明确引入 ws

输出目标：

- `new-rule` 或 `exception-rule` candidate

#### 3.2 新例外规则出现

模式：

- 全局默认规则仍然成立
- 但某类模块、场景或目录出现新例外

例子：

- 默认都走统一请求封装
- 实时双向通信模块允许直接使用 ws transport

输出目标：

- 说明“例外条件”，不是单纯重复代码事实

#### 3.3 docs 与实现发生偏离

模式：

- docs 仍描述旧规则
- 实现已经稳定按新规则运行

输出目标：

- 偏向 `docs-only` 或 `dual-write` 的 update candidate

## 4. Inputs

Phase 1 的输入固定为四类：

1. 工作区变更
   - `git diff --name-only`
   - `git diff`
2. 现有项目记忆
   - `read_memory(...)`
   - `search_memory(..., scope=docs|all)`
   - `system://boot`
3. 可选会话摘要
   - 用户显式提供的本轮会话总结
4. 可选范围限制
   - 指定目录
   - 指定模块
   - 指定 docs domain

Phase 1 不读取：

- commit 历史
- PR 评论
- issue 数据
- 远程仓库信息

## 5. Output Contract

Phase 1 输出为 `discovery candidate` 列表。

每条 candidate 固定字段：

- `candidate_id`
- `signal_kind`
- `candidate_type`
- `title`
- `summary`
- `reason`
- `suggested_route`
- `target_ref`
- `evidence`
- `confidence`

字段约束：

- `signal_kind`
  - `default-rule-broken`
  - `exception-rule`
  - `docs-drift`
- `candidate_type`
  - `new-rule`
  - `exception-rule`
  - `docs-drift`
- `suggested_route`
  - `docs-only`
  - `durable-only`
  - `dual-write`
- `target_ref`
  - 若命中已有 docs / durable 目标则返回
  - 未命中则为 `null`
- `evidence`
  - 至少包含：
    - 相关 docs / durable ref
    - 变更文件路径
    - 简短证据摘要
- `confidence`
  - `high`
  - `medium`
  - `low`

## 6. Module Plan

### 6.1 `lib/decision_discovery.py`

职责：

- discovery 主入口
- 汇总上下文和 detector 输出
- 去重、排序、裁剪

建议接口：

```python
discover_decisions(
    project_root,
    *,
    diff_text,
    changed_files,
    summary=None,
    limit=5,
)
```

### 6.2 `lib/discovery_context.py`

职责：

- 读取相关 docs / durable recall
- 为 detectors 组装最小上下文
- 基于 changed files 推测相关 doc refs

### 6.3 `lib/discovery_signals.py`

职责：

- 默认规则突破 detector
- 新例外规则 detector
- docs drift detector

说明：

- detector 输出 signal，不直接输出写入动作

### 6.4 `lib/discovery_cli.py`

职责：

- 暴露本地 CLI 入口
- 返回结构化 JSON envelope

建议命令：

```bash
memory-hub discover [--summary-file <path>] [--project-root <path>] [--limit 5]
```

## 7. Integration Strategy

Phase 1 不新增新的 write lane 或 review lane。

接线策略：

1. discovery 只产出 candidate
2. 用户确认后，再映射到：
   - `capture_memory(...)`
   - `update_memory(...)`
3. 之后继续走现有：
   - docs change review
   - durable review

因此：

- discovery lane 在 unified write lane 之前
- review 仍完全复用现有系统

## 8. Trigger Strategy

Phase 1 只支持 3 种触发：

1. 用户显式要求
   - 例如“帮我看这次改动里有没有值得沉淀的知识”
2. task-end summary
   - 由 `memory-admin` 引导执行 discovery
3. review 前检查
   - 在准备沉淀某条规则前，先看是否存在更高层候选

Phase 1 不做：

- 每次保存文件自动运行
- 每次代码改动自动运行

## 9. UX / Presentation

Phase 1 的交互目标是“少打断、强解释”。

输出形式：

1. 先给总数
   - 例如：发现 2 条可能值得沉淀的候选
2. 每条候选给出：
   - 为什么值得记
   - 证据来自哪里
   - 建议进入哪条 lane
   - 命中的目标 ref 是什么

如果用户没有明确要求继续：

- 只展示候选
- 不自动进入 unified write lane

## 10. Implementation Order

建议按下面顺序实现：

### Step 1：只读 discovery 底座

- 新增 `decision_discovery.py`
- 新增 `discovery_context.py`
- 打通 diff + docs / recall 上下文读取

### Step 2：实现三个 detector

- 默认规则被打破
- 新例外规则出现
- docs drift

### Step 3：新增 CLI 入口

- `memory-hub discover`
- 先只输出 candidate

### Step 4：排序、去重、裁剪

- 按 `confidence` 和 `signal_kind` 排序
- 按 `target_ref + title` 去重

### Step 5：预留与 unified write lane 的映射 helper

- 先只在代码层提供 helper
- 不在 Phase 1 默认接入 `project-memory`

原因：

- 先验证 discovery 质量
- 避免把噪音直接引入主 workflow

## 11. Test Plan

Phase 1 至少补 4 组测试。

### 11.1 默认规则被打破

场景：

- docs 中有默认规则
- diff 中出现与默认规则冲突的稳定新实现

预期：

- 生成 `new-rule` 或 `exception-rule` candidate

### 11.2 新例外规则

场景：

- 默认规则仍成立
- 某目录/模块出现稳定例外

预期：

- candidate 指出“例外条件”
- 不只是重复代码事实

### 11.3 docs drift

场景：

- docs 仍描述旧规则
- 代码体现新规则

预期：

- 生成偏向 `docs-only` 或 `dual-write` 的 candidate

### 11.4 噪音控制

场景：

- 普通重构
- 重命名
- 无语义变化的格式调整

预期：

- 不生成 candidate
- 或仅生成低置信度、可解释 candidate

## 12. Acceptance Criteria

Phase 1 可以定义为完成，当且仅当：

1. `memory-hub discover` 能稳定返回结构化 candidate 列表
2. 三类高价值信号至少各有 1 条稳定测试通过
3. 普通重构不会大面积误报
4. 每条 candidate 都能说明：
   - 为什么值得记
   - 证据来自哪里
   - 建议进哪条 lane
5. discovery 本身不会直接改 docs 或 durable active state

## 13. Assumptions

- Phase 1 以本地规则发现为主，不引入远程模型服务。
- Phase 1 先通过 CLI 验证 discovery 质量，不直接绑进默认主 workflow。
- 若 discovery 质量不够稳，优先继续收紧信号和证据模型，而不是放宽自动写入。
