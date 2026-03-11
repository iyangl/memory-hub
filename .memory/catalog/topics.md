# Memory Hub — Topics Index

## 代码模块
- core — 基础设施与仓库级行为接线：CLI 分发、JSON envelope、路径管理、规则入口、MCP/自测启动
- memory — 知识管理命令：init/read/list/search/index
- catalog — 索引管理命令：read/update/repair
- durable-memory — Phase 1F durable memory：SQLite、CLI 审查面、最小 MCP server、workflow skill 与 review handoff 行为层
- tests — 单元测试：核心模块与 durable memory Phase 1A/1B/1C 契约测试
## 知识文件
### tech-stack
- architect/tech-stack.md — 技术栈、关键依赖、使用方式与限制
### conventions
- dev/conventions.md — 目录命名规则、模块组织方式、代码约定
### pm-decisions
- pm/decisions.md — MVP 收口结论、默认使用路径与 post-MVP backlog
### architect-decisions
- architect/decisions.md — 设计决策日志（write→index 重构）
### qa-strategy
- qa/strategy.md — 测试策略与质量约束
