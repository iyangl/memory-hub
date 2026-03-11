# Memory Hub Phase 2D Plan

日期：2026-03-11  
状态：已实现

## 1. 目标

Phase 2D 的目标是把 Phase 2C 里“docs 变更只返回 inline preview”的临时状态，升级为统一的持久 review surface，并保持：

- `docs lane` 是正文主文档
- `durable-only` 继续走 durable proposal / review / rollback
- `review show` / `show_memory_review` 能同时展示 durable review 与 docs change review
- `review approve/reject` 继续作为 CLI 权威审查入口

## 2. 实现范围

本阶段新增和调整了这些能力：

1. 新增 `docs_change_reviews` 持久表，存放 docs 轻审查队列
2. docs-only / dual-write 不再在统一写入口里直接落盘，而是先创建 pending docs review
3. `show_memory_review(proposal_id|ref)` 同时支持：
   - durable review
   - docs change review
4. `memory-hub review list/show/approve/reject` 同时支持：
   - `proposal_id`
   - `doc://...`
   - durable URI
5. dual-write 的 docs review 可以关联一个 durable proposal；批准 docs review 时会同步批准关联 durable proposal

## 3. 数据模型

`docs_change_reviews`

- `review_id`
- `status`
- `doc_ref`
- `title`
- `before_content`
- `after_content`
- `reason`
- `linked_proposal_id`
- `created_at`
- `created_by`
- `reviewed_at`
- `reviewed_by`
- `review_note`

约束：

- 同一个 `doc_ref` 同时只允许一条 pending docs review

## 4. 行为语义

### docs-only

- `capture_memory(kind=docs)` 创建 pending docs review
- `update_memory(ref=doc://..., ...)` 创建 pending docs review
- 审批前不写 docs 文件
- `review approve doc://...` 后才应用文档并修复 catalog

### durable-only

- 继续沿用 durable proposal / review / rollback
- `show_memory_review` 与 `review show` 走 durable review 视图

### dual-write

- docs 变更先进入 pending docs review
- 同时创建一个关联 durable proposal
- `review approve doc://...` 时：
  - 应用 docs 文件
  - 修复 catalog
  - 同步批准关联 durable proposal

## 5. 边界

- `rollback` 仍然只适用于 durable-only
- docs review 不复用 durable proposal 状态机
- docs review 的批准流程包含文件系统写入与 DB 审查状态更新，跨介质不保证单事务；若发生失败，必须显式报错，不做 silent fallback

## 6. 关键文件

- `lib/docs_memory.py`
- `lib/docs_review.py`
- `lib/project_review.py`
- `lib/project_memory_write.py`
- `lib/review_cli.py`
- `lib/durable_mcp_tools.py`
- `lib/durable_db.py`

## 7. 验收

- docs review 可持久展示和审批
- `show_memory_review` 同时支持 durable/docs 两类 review
- `review list/show/approve/reject` 同时支持 `proposal_id|ref`
- `dual-write` 的 docs review 批准后会同步批准关联 durable proposal
- 现有 durable-only 自测与回归不退化
