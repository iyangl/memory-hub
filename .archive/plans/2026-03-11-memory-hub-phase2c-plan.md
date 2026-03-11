# Phase 2C 实施方案：统一写入入口与 catalog 内化

日期：2026-03-11  
状态：已实现第一版

## Summary

Phase 2C 的目标是把项目记忆的写路径收敛成一个统一入口，同时把 catalog 从显式用户心智降为内部自动维护实现。

本阶段第一版的固定边界：

- 新增统一 MCP 写入口：
  - `capture_memory(kind=auto|docs|durable, ...)`
  - `update_memory(ref, mode=patch|append, ...)`
- `docs-only` 与 `durable-only` 完整打通
- `dual-write` 采用：
  - docs 为主文档
  - durable 只保存摘要 proposal，并通过 `doc_ref` 建立关联
- docs 变更当前返回 inline preview，不引入持久 docs review surface
- full review surface uplift 继续留到 Phase 2D

## Route Rules

### docs-only

- `kind=docs`
- 或 `kind=auto` 且仅提供 `doc_domain`

行为：

- 写入 `.memory/docs/<bucket>/<file>.md`
- 自动确保 topics 注册
- 自动运行 `catalog-repair`
- 返回 docs change preview

### durable-only

- `kind=durable`
- 或 `kind=auto` 且仅提供 `memory_type`

行为：

- 继续走 durable proposal / review
- 保留现有 `propose_memory` / `propose_memory_update` 兼容接口

### dual-write

- `kind=auto` 且同时提供 `doc_domain` 与 `memory_type`

行为：

- docs 主文档先写入或更新
- durable lane 只创建或更新摘要 proposal
- 通过 `doc_ref` 关联 docs 与 durable

## Schema Changes

durable DB 增加最小元数据：

- `storage_lane`
  - `durable`
  - `dual`
- `doc_ref`

适用表：

- `memory_versions`
- `approved_memories`
- `memory_proposals`

目的：

- 标识 durable-only 与 dual-write
- 让 doc ref 可以反查已批准的 durable summary

## Current Limitations

- docs 轻审查暂时不是持久化 review surface，而是 inline preview
- dual-write 的 durable 部分当前存的是摘要，不是 docs 全文
- `update_memory(doc ref)` 只有在存在关联 durable summary 时才会同步创建 durable update proposal
- `memory-admin` 只先落 skill 入口，后续维护动作继续在 Phase 2D / 2E 丰富
