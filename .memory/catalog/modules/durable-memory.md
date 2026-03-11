# durable-memory

> Phase 2F 自动会话提炼：project-memory 主 skill、统一 read/search/capture/update/show review、本地 hybrid recall、boot/search projections 与 session-extract 落 unified write lane

- skills/project-memory/SKILL.md — 统一项目记忆主入口：docs/catalog/durable/review 读取、检索、统一写入与会话提炼 handoff
- skills/project-memory/SKILL.md — 内部 durable branch：boot-first、proposal/update/review handoff、pending review split 与确认分流
- skills/memory-admin/SKILL.md — 维护入口：repair / diagnose / session-extract
- .archive/plans/2026-03-10-phase1f-behavior-acceptance.md — Phase 1F 会话级行为验收清单
- .archive/handoffs/2026-03-10-phase1f-durable-memory-behavior-handoff.md — Phase 1F 收尾交接：Codex 路径基本通过、MVP 可视为完成
- .archive/plans/2026-03-11-memory-hub-v2-design-draft.md — v2 统一项目记忆面设计草案（docs 主文档、DB 最小控制面）
- .archive/plans/2026-03-11-memory-hub-v2-roadmap.md — v2 roadmap：Phase 2A~2F
- .archive/plans/2026-03-11-memory-hub-phase2c-plan.md — Phase 2C 实施方案：统一写入入口与 catalog 内化
- .archive/plans/2026-03-11-memory-hub-phase2d-plan.md — Phase 2D 实施方案：统一 review surface 与 docs 持久轻审查
- .archive/plans/2026-03-11-memory-hub-phase2e-plan.md — Phase 2E 实施方案：boot/search 投影视图与本地 hybrid recall
- .archive/plans/2026-03-11-memory-hub-phase2f-plan.md — Phase 2F 实施方案：本地会话提炼、候选路由与 unified write lane 落地
- lib/durable_db.py — SQLite schema bootstrap、连接与事务工具（store 位于 `.memory/_store/memory.db`）
- lib/durable_errors.py — durable memory 领域错误类型
- lib/durable_guard.py — 最小 write guard：NOOP、UPDATE_TARGET、PENDING_REVIEW
- lib/durable_mcp_tools.py — 统一 read/search/capture/update/review view 与 durable proposal 兼容层的 MCP tool handlers
- lib/durable_proposal_utils.py — proposal 插入与 patch/append 物化助手
- lib/project_memory_view.py — 统一 read/search 数据视图：docs、catalog、durable
- lib/project_memory_projection.py — Phase 2E recall 投影与 hybrid search：boot/search projection、本地 lexical+semantic 评分
- lib/project_memory_write.py — 统一写入路由：docs-only、durable-only、dual-write 与 pending review handoff
- lib/session_extract.py — Phase 2F 本地会话提炼服务：候选提取、route 分类、混合检索定位与 unified write 落地
- lib/session_extract_cli.py — session-extract CLI：读取 transcript，生成 docs/durable/dual-write 候选并提交 review
- lib/docs_memory.py — docs lane 共享助手：slug、render、summary、catalog 注册
- lib/docs_review.py — docs change review 持久化、应用与拒绝服务
- lib/project_review.py — 统一 review 视图与 approve/reject 分发：durable review + docs change review
- lib/durable_repo.py — approved memory 查询与 create/update proposal 仓储接口
- lib/durable_review.py — approve、reject、rollback 事务服务
- lib/durable_store.py — 共享查询、版本写入与 approved upsert 助手
- lib/durable_uri.py — durable memory URI、type 与 slug 规则
- lib/mcp_server.py — 最小 stdio JSON-RPC MCP server（统一 read/search/capture/update/review 入口）
- lib/review_cli.py — review list/show/approve/reject CLI
- lib/rollback_cli.py — rollback CLI
