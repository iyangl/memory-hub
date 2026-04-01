# Memory Hub Recall-First Contract

> 日期：2026-03-28
> 状态：Draft
> 作用：冻结 recall-first 主链的实现契约，作为进入编码前的唯一实现边界文档。
> 关系：`v3-phase1-dev-plan.md` 是历史实施稿；当前以 `recall-first-redesign-plan.md` 和本契约为准。

---

## 1. Purpose

本文件用于冻结以下三类实现边界：

1. `recall-plan` 的输入、输出与决策规则
2. `working-set` 的输入、输出与来源保留规则
3. `/save` 的 decision / guard 语义

目标不是设计完整产品，而是确保在实现 recall-first 主链时：

- 先固定协议，再写代码
- 各模块之间通过稳定 contract 协作
- 避免 `scan_modules` / `catalog_update` / `brief` / `recall` / `save` 彼此反复回改

---

## 2. Scope

### In Scope
- recall-first 主链协议
- `recall-plan` CLI contract
- `working-set` CLI contract
- `/save` decision contract
- `search before guess`
- `read before write`
- working set 与长期 docs 的边界
- 最小可验证输出格式

### Out of Scope
- SQLite durable store
- MCP-first 主架构
- Dashboard / Review / Rollback UI
- vitality score / decay 数值系统
- 多部署档位（A/B/C/D）
- 审计后台、可视化控制台、远程检索服务

---

## 3. Core Invariants

### 3.1 docs 是唯一正本
长期知识只存于 `.memory/docs/`。
以下都属于派生产物或会话产物：

- `.memory/BRIEF.md`
- `.memory/catalog/topics.md`
- `.memory/catalog/modules/*.md`
- `.memory/session/*`

### 3.2 Bootstrap Recall Protocol
recall 必须遵循固定顺序：

1. 读 base brief
2. 若任务对象不明确，先 search / index 定位
3. 再判定 `skip | light | deep`
4. `deep` 时构建 session working set

### 3.3 Search Before Guess
当模块、对象、业务术语、历史别名不明确时，必须先 search，不允许直接猜推荐来源。

### 3.4 Read Before Write
`/save` 的任何非 `noop` 写入动作，都必须先读取目标 doc 或候选 doc，再决定如何写入。

### 3.5 Working Set 只服务当前任务
working set 是会话级派生产物，不是长期记忆。
`/save` 不允许直接把 working set 原文写回 docs。

### 3.6 `noop` 是合法成功结果
没有新的长期知识要沉淀时，`/save` 可以返回 `noop`，这不构成失败。

### 3.7 Contract 优先于实现细节
实现可以调整内部算法，但不能破坏本文件定义的字段、动作语义、边界与不变量。

---

## 4. Terminology

### base brief
指 `.memory/BRIEF.md`。
它是 boot summary，不是文档目录摘要。

### topic index
指 `.memory/catalog/topics.md`。
它提供 docs 与 code modules 的导航入口。

### module card
指 `.memory/catalog/modules/*.md`。
它描述“什么时候读、先读什么、风险是什么、验证重点是什么”。

### durable knowledge
会影响未来动作、且不应仅存在于当前会话中的稳定结论。
例如：
- 决策
- 约束
- 风险
- 验证策略
- 业务口径

### session working set
当前任务的压缩上下文集合。
它保留来源、原因、证据缺口，但默认不进入长期 docs。

### evidence gap
当前 recall 或 working set 仍缺失、需要进一步阅读或验证的关键证据。

---

## 5. Recall-First Flow Contract

### 5.1 总体链路

```text
task
 -> read BRIEF
 -> recall-plan
 -> if search_first: search/index locate
 -> choose skip/light/deep
 -> if deep: working-set
 -> execute task
 -> save decision
```

### 5.2 三档 recall 的语义

#### `skip`
含义：
- 不需要额外 recall，或仅需要极少量 base brief 背景

#### `light`
含义：
- 读 base brief + 少量 docs / module cards 即可

#### `deep`
含义：
- 需要先做较完整 recall，再构建 session working set

---

## 6. `recall-plan` Contract

### 6.1 Command Role
`recall-plan` 的职责不是直接完成 recall，而是：

- 判断 recall 深度
- 判断任务类型
- 判断是否必须先 search
- 给出推荐来源
- 给出为什么推荐这些来源
- 明确当前证据缺口

### 6.2 Suggested CLI Shape

```bash
python3 -m lib.cli recall-plan --task "<任务描述>" [--project-root <path>] [--out <file>]
```

### 6.3 Output Schema

```json
{
  "version": "1",
  "task": "修复 checkout 优惠券校验逻辑",
  "recall_level": "deep",
  "task_kind": "decide",
  "ambiguity": "medium",
  "search_first": true,
  "search_queries": ["checkout coupon discount validation"],
  "recommended_docs": [],
  "recommended_modules": [],
  "why_these": [],
  "evidence_gaps": []
}
```

规则补充：
- 对象不明确时 `search_first = true`
- 不允许盲猜模块
- `locate` 不默认 deep
- `decide` / `validate` 优先读取决策、约束、风险、验证重点

---

## 7. `working-set` Contract

### 7.1 Command Role
`working-set` 负责：
- 接收 deep recall 计划
- 读取推荐来源
- 压缩成当前任务可直接使用的上下文
- 保留来源与被选入原因
- 保留当前证据缺口

### 7.2 Suggested CLI Shape

```bash
python3 -m lib.cli working-set --plan-file <recall-plan.json> [--project-root <path>] [--out <file>]
```

### 7.3 Output Schema

```json
{
  "version": "1",
  "task": "修复 checkout 优惠券校验逻辑",
  "source_plan": "C:/tmp/recall-plan.json",
  "summary": "本任务涉及业务规则、风险与验证重点。",
  "items": [],
  "priority_reads": [],
  "evidence_gaps": [],
  "durable_candidates": []
}
```

约束：
- 每个 item 至少有 1 个 source
- working set 不等于长期知识
- 不允许把猜测包装成稳定结论

---

## 8. `/save` Decision Contract

### 8.1 Allowed Actions
- `noop`
- `create`
- `append`
- `merge`
- `update`

### 8.2 Save Rules
- 非 `noop` 前必须先 search
- 非 `noop` 前必须先 read 目标 doc
- working set 不能原样落盘
- 默认优先 `merge`，其次 `append`，最后 `create`
- `update` 必须明确旧结论为什么过时
- `update` 的 supersedes 追溯信息应落在 `.memory/session/save-trace/<artifact>.json` 等会话产物，而不是污染 durable docs 正文
- 该 trace 属于 best-effort session artifact：持久化失败不会改变 durable docs 已成功写入这一事实
- 旧的 `.memory/session/save-trace.jsonl` 属于 legacy session artifact；新实现不读取、不迁移回放
- 本设计只解决 trace artifact 的并发覆盖问题，不承诺 `save` 对 durable docs / rebuild 产物的全流程并发安全

---

## 9. Derived Artifact Rebuild Contract

凡是 `/save` 完成了非 `noop` 的 durable 写入，至少重建：
1. `BRIEF.md`
2. `catalog-repair`

若模块导航变更，再重建 module catalog。

---

## 10. Acceptance Checklist

### `recall-plan`
- [ ] 有 `task_kind`
- [ ] 有 `search_first`
- [ ] 有 `why_these`
- [ ] 不会在对象模糊时直接猜模块

### `working-set`
- [ ] 每条 item 都有 source
- [ ] 保留 evidence gap
- [ ] 内容偏向决策/约束/风险/验证

### `/save`
- [ ] `noop / create / append / merge / update` 语义清晰
- [ ] 非 `noop` 前必有 search + read
- [ ] working set 不会原样写回 docs
