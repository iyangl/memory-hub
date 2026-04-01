---
description: '提炼并持久化本次会话中的项目知识'
---

# /memory-hub:save — 保存项目记忆

按 recall-first contract 提炼 durable knowledge，生成结构化 `save-request`，再调用代码级 `save` core 执行写入与重建。

## 上下文

- 用户补充说明：$ARGUMENTS

---

## 执行流程

### Step 1：收集候选知识

来源包括：
1. `.memory/inbox/*.md`
2. 当前会话中的决策、约束、风险、验证策略、业务口径
3. 当前任务的 working set（只作为提炼原料，不可原样写回）

### Step 2：后悔测试

对每条候选知识先问：

> 本次会话结束后，如果没记下来，未来继续此项目的人会不会后悔？

若答案是否：
- 直接判定为 `noop`
- 不进入长期 docs

### Step 3：Search Before Write / Read Before Write

对于每条非 `noop` 候选：

1. 先 search，确认现有 docs 是否已有相关结论：
```bash
py -3 -m lib.cli search "<关键词>"
```
2. 再 read 候选目标 doc 或对比 doc：
```bash
py -3 -m lib.cli read <bucket> <filename>
```
3. 再决定写入动作与归宿

硬约束：
- 非 `noop` 必须至少有 1 条 `search_queries`
- 非 `noop` 必须至少有 1 条 `read_refs`
- `append / merge / update` 必须把目标 doc 放进 `read_refs`
- 不允许在未读目标 doc 的情况下直接覆盖长期知识

### Step 4：显式判定动作

每条候选知识必须判定为以下之一：

- `noop`：没有新的长期知识
- `create`：没有合适归宿，需要新建 doc
- `append`：在现有 doc 中新增独立 section
- `merge`：并入已有结论，由上层提供完整合并后的 doc
- `update`：修改已过时结论，必须说明旧结论为何过时

默认优先级：
- 能 merge 就不 create
- 能 append 就不 create
- update 只用于明确替换旧结论

### Step 5：生成 `save-request.json`

把保存决策写入 `.memory/session/save-request.json`，形状如下：

```json
{
  "version": "1",
  "task": "<本次保存任务>",
  "entries": [
    {
      "id": "append-checkout-rule",
      "action": "append",
      "reason": "stable checkout business rule",
      "target": {"bucket": "pm", "file": "decisions.md"},
      "payload": {"section_markdown": "## Checkout 优惠券规则\n\n- 先计算折扣再做上限校验\n"},
      "evidence": {
        "search_queries": ["Checkout 优惠券规则"],
        "read_refs": ["docs/pm/decisions.md", "docs/architect/decisions.md"],
        "source_refs": []
      }
    }
  ]
}
```

补充约束：
- `create` 必须带 `index.topic` / `index.summary`
- `append` 的 `section_markdown` 必须包含新的 heading
- `update` 必须带 `payload.supersedes`
- `update` 成功后，save core 会尽力在 `.memory/session/save-trace/` 下写入当前这次 save 的单独 trace artifact；若 trace 持久化失败，不影响 durable docs 已生效的 save 结果
- `trace_file` 应返回仓库内相对路径，优先引用当前 save request 的 repo-relative 路径；若 request 文件不在仓库内，artifact 中的 `request_ref` 应退化为 basename 或 `null`
- 旧的 `.memory/session/save-trace.jsonl` 视为 legacy session artifact：新实现不读取、不迁移回放
- 若 `source_refs` 中引用了 working set excerpt，写入内容不能与 excerpt 原样相同，也不能整段嵌入

### Step 6：调用 `save` core

执行：

```bash
py -3 -m lib.cli save --file .memory/session/save-request.json
```

`save` core 会负责：
- 校验 request 形状与 action 语义
- 重放 evidence 校验
- 执行 durable docs 写入
- `create` 时注册 `topics.md`
- 非 `noop` 后自动重建 `BRIEF.md` 与 `catalog-repair`

### Step 7：读取结果并汇报

向用户报告：
- `create / append / merge / update / noop` 分别有哪些
- 新增/更新了哪些 durable docs
- 哪些候选被判定为 `noop`
- `BRIEF.md` 是否已重建
- 若失败，给出 `save` core 返回的错误码与原因

说明：
- inbox 清理不是当前 `save` core 的职责；如需要清理，请单独确认并处理

---

## 边界

- working set 不能原样写回 docs
- docs 是唯一正本
- BRIEF / catalog 都是派生产物
- `noop` 是合法成功结果，不强制“为了保存而保存”
- 不直接手工改 `.memory/docs/` 来绕过 `save` core
