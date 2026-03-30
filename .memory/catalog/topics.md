# Memory Hub — Topics Index

## 代码模块
- root；当任务涉及项目入口、全局配置或无法确定模块归属时阅读；先看 `pyproject.toml`。；入口: `pyproject.toml`
- lib；当任务涉及 lib 的职责、边界或入口时阅读；优先从 `lib/__init__.py`、`lib/brief.py` 开始。；入口: `lib/__init__.py`, `lib/brief.py`
- tests；当任务涉及验证策略、回归范围或测试入口时阅读；先看 `tests/__init__.py`、`tests/test_brief.py`。；入口: `tests/__init__.py`, `tests/test_brief.py`
## 知识文件
### tech-stack
- docs/architect/tech-stack.md — 关键设计约束：无服务进程、无远程协议层、无外部数据库，所有状态都落在项目目录。
### conventions
- docs/dev/conventions.md — 命名约定：文件名：`snake_case`（如 `memory_read.py`、`catalog_repair.py`）
### pm-decisions
- docs/pm/decisions.md — Recall-first 产品结论：recall 的目标是先定位再读取，而不是把所有 docs 一次性读完。
### architect-decisions
- docs/architect/decisions.md — Recall-first 架构决策：`.memory/docs/` 是唯一正本；`BRIEF.md`、`catalog/`、`session/` 都是派生产物。
### qa-strategy
- docs/qa/strategy.md — # 测试策略与质量约束
### memory-相关逻辑变更必须补自动化测试和自测记录
- docs/qa/memory-相关逻辑变更必须补自动化测试和自测记录.md — # Memory 相关逻辑变更必须补自动化测试和自测记录
### caching
- docs/architect/caching.md — 决策：使用本地文件缓存
