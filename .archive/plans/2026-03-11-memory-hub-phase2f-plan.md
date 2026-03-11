# Memory Hub Phase 2F Plan

日期：2026-03-11  
状态：已实现

## 1. 目标

Phase 2F 的目标是把自动会话提炼接入统一项目记忆系统，同时保持这些边界不变：

- 不新增旁路状态机
- 不直接写 active docs
- 不绕过 durable review / docs review
- 不改变 v2 现有 5 个 MCP 主接口

## 2. 设计

本阶段采用本地 `session-extract` 入口：

```bash
memory-hub session-extract --file <session-transcript>
```

提炼器做三件事：

1. 从会话文本中提取候选
2. 用现有 hybrid recall 定位更新目标
3. 把候选送进既有 unified write lane

## 3. 候选类型

提炼器只产生三类候选：

- `docs-only`
- `durable-only`
- `dual-write`

其中：

- docs-only -> docs change review
- durable-only -> durable proposal / review
- dual-write -> docs change review + linked durable proposal

## 4. 提炼规则

支持两种输入方式：

### 显式标注

- `docs[qa|QA Strategy]: ...`
- `durable[preference|Chinese Replies]: ...`
- `dual[architect,constraint|Unified Write Lane]: ...`

显式标注优先，用于稳定测试与高确定性提炼。

### 启发式分类

未标注时使用本地规则：

- 偏好 / 身份关键词 -> durable-only
- 约束 / 决策关键词 -> dual-write
- QA / dev / pm 关键词 -> docs-only

## 5. 更新策略

提炼器不会盲目创建新条目。

- 对 docs-only / dual-write：
  - 优先用标题在 `scope=all` 中定位 docs ref
  - 命中后走 `update_memory(ref=doc://..., mode=append, ...)`
- 对 durable-only：
  - 优先在 durable lane 中定位 approved memory
  - 命中后走 `update_memory(ref=<durable-uri>, mode=append, ...)`
- 未命中时才走 `capture_memory(...)`

若 durable create 命中 `UPDATE_TARGET`：

- durable-only -> 自动转成 durable append update
- dual-write -> 读取 `doc_ref` 后转成 docs update

## 6. 验收

Phase 2F 的最小验收：

1. `session-extract` 能创建 docs review
2. `session-extract` 能创建 durable-only proposal
3. `session-extract` 能创建 dual-write docs review + linked durable proposal
4. 命中现有 docs 时，提炼器走 update，而不是重复 create
5. 空或无价值 transcript 不会产生候选
6. 全量回归与 `bin/selftest-phase1c` 继续通过
