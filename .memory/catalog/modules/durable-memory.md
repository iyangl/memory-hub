# durable-memory

> Phase 1F durable memory：SQLite、CLI 审查面、最小 MCP server、workflow skill 与 review handoff 行为层

- skills/durable-memory/SKILL.md — durable-memory workflow 入口：语境判断、boot-first、review show handoff 与确认分流
- .archive/plans/2026-03-10-phase1f-behavior-acceptance.md — Phase 1F 会话级行为验收清单
- .archive/handoffs/2026-03-10-phase1f-durable-memory-behavior-handoff.md — Phase 1F 收尾交接：Codex 路径基本通过、MVP 可视为完成
- lib/durable_db.py — SQLite schema bootstrap、连接与事务工具
- lib/durable_errors.py — durable memory 领域错误类型
- lib/durable_guard.py — 最小 write guard：NOOP、UPDATE_TARGET、PENDING_REVIEW
- lib/durable_mcp_tools.py — durable memory MCP tool handlers
- lib/durable_proposal_utils.py — proposal 插入与 patch/append 物化助手
- lib/durable_repo.py — approved memory 查询与 create/update proposal 仓储接口
- lib/durable_review.py — approve、reject、rollback 事务服务
- lib/durable_store.py — 共享查询、版本写入与 approved upsert 助手
- lib/durable_uri.py — durable memory URI、type 与 slug 规则
- lib/mcp_server.py — 最小 stdio JSON-RPC MCP server
- lib/review_cli.py — review list/show/approve/reject CLI
- lib/rollback_cli.py — rollback CLI
