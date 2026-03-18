# Memory Hub — Topics Index

## 代码模块
- core — 基础设施与仓库级行为接线：CLI 分发、JSON envelope、路径管理、规则入口、MCP/自测启动
- memory — 知识管理命令：init/read/list/search/index
- catalog — 索引管理命令：read/update/repair
- durable-memory — v2 主线 + decision discovery Phase 1：统一 read/search/capture/update/show review、本地 hybrid recall、boot/search projections、session-extract 与 discover 候选发现
- tests — 单元测试：核心模块与 durable memory Phase 1A~Phase 2F 契约测试
## 知识文件
### tech-stack
- docs/architect/tech-stack.md — 技术栈、关键依赖、使用方式与限制
### conventions
- docs/dev/conventions.md — 目录命名规则、模块组织方式、代码约定
### pm-decisions
- docs/pm/decisions.md — MVP 收口结论、默认使用路径与 post-MVP backlog
### architect-decisions
- docs/architect/decisions.md — 设计决策日志（write→index 重构）
### qa-strategy
- docs/qa/strategy.md — 测试策略与质量约束
### memory-相关逻辑变更必须补自动化测试和自测记录
- docs/qa/memory-相关逻辑变更必须补自动化测试和自测记录.md — 补充项目开发约束，确保后续所有 memory 相关改动都有自动化验证与人工自测痕迹。
