# Memory Hub Phase 2E Plan

日期：2026-03-11  
状态：已实现

## 1. 目标

Phase 2E 的目标是先把统一项目记忆系统的 recall 做稳，再进入自动会话提炼：

- `system://boot` 不再依赖运行时临时拼装，而是切到 `_store/projections/boot.json`
- `search_memory(scope=all)` 升级为本地 hybrid recall
- 结果必须可解释，并在 hybrid 被显式关闭时给出降级标记

## 2. 实现范围

本阶段新增了两个投影视图：

- `.memory/_store/projections/boot.json`
- `.memory/_store/projections/search.json`

以及一套本地 hybrid search 逻辑：

- docs 文本匹配
- durable 结构化匹配
- 基于 token overlap 的轻量 semantic score

## 3. 当前语义

### boot projection

- `read_memory(system://boot)` 改为读取 `boot.json`
- projection 内容仍然只包含 approved 的 `identity / constraint`
- projection 中保留 `storage_lane` 与 `doc_ref`

### search projection

- `search_memory(scope=docs|durable|all)` 都基于 `search.json`
- 每条结果包含：
  - `ref`
  - `lane`
  - `source_kind`
  - `score`
  - `lexical_score`
  - `semantic_score`
  - `snippet`

### 显式降级

若通过环境变量关闭 hybrid recall：

```bash
MEMORY_HUB_DISABLE_HYBRID_SEARCH=1
```

则 `search_memory` 返回：

- `search_kind = lexical`
- `degraded = true`
- `degrade_reasons = ["hybrid_search_disabled"]`

## 4. 刷新时机

projection 会在这些状态变更后刷新：

- durable proposal approve
- durable rollback
- docs review approve

若 projection 文件缺失，读取或搜索时会自动重建。

## 5. 边界

- 不引入远程搜索服务
- 不引入 embedding / 向量数据库
- dual-write 仍然不在 DB 中长期双存全文
- hybrid recall 只是 Phase 2E 的本地高质量 recall，不等于最终形态的完整语义检索平台
