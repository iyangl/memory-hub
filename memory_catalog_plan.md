Memory Hub × Catalog 实施计划（从当前代码直接落地）
Summary
当前代码已有 session.sync.pull/push/resolve_conflict 与基础 SQLite 模型，可作为基线。
实施顺序按 P0-a -> P0-b -> P0-c -> P1，每阶段都可独立验收。
目标是先把“可用且可审计的双引擎闭环”做出来，再做漂移与体验优化。
当前基线与差距
已有：State Engine 主流程、冲突处理、基础审计、项目隔离。
缺失：迁移机制、push 强校验错误码、Catalog 最小实现、ConsistencyStamp 对象化、catalog_jobs 补偿、health.check、drift fallback。
风险点：context_stamp 仍是 vN 字符串，catalog 相关接口尚未落地。
Phase P0-a（Schema 校验 + 错误码 + 迁移框架）
新增 errors.py。
定义统一业务错误结构：error_code/message/details/retryable。
新增 validation.py。
实现 session.sync.push 输入 schema 校验。
校验字段：role_deltas/decisions_delta/open_loops/files_touched 类型与字段完整性。
新增 memory_hub/migrations/ 目录。
拆分现有 schema.sql 为 000_base.sql，新增 schema_migrations 表。
修改 store.py:init_db 为“启动自动迁移”。
修改 server.py 将业务错误映射为稳定 JSON-RPC 错误数据。
新增测试 test_push_validation.py 与 test_migrations.py。
Phase P0-b（Catalog 最小可用）
新增迁移 001_catalog_core.sql。
建表：catalog_meta/catalog_files/catalog_edges。
新增 catalog_indexer.py。
能力：扫描项目文件，抽取 import 依赖边。
置信度规则：AST 静态可证实 1.0，推测性依赖 0.5。
新增 catalog.py。
实现 catalog.brief.generate(project_id, task_prompt, task_type, token_budget)。
evidence 输出结构固定为 list[{file, reason}]。
brief 仅纳入 confidence >= 0.5 的边。
修改 server.py 注册 catalog.brief.generate。
新增测试 test_catalog_brief.py。
Phase P0-c（Consistency + Jobs + Health）
新增迁移 002_consistency_jobs.sql。
建表：catalog_jobs/drift_reports/consistency_links。
修改 sync.py:session_sync_push。
push 成功后同事务写入 catalog_jobs 与 consistency_links。
新增 catalog_worker.py。
实现 job 执行、失败重试、最大重试后 failed。
新增 catalog.health.check(project_id)。
返回 freshness、coverage、pending_jobs、drift_score、consistency_status。
修改 pull 返回 consistency_stamp 对象，不再使用 vN 字符串协议。
新增测试 test_consistency_and_jobs.py。
Phase P1（漂移检测 + Pull 智能复用 + Skill 编排）
新增 drift.py。
检测策略：优先 git diff，失败回退 hash 比对。
memory-pull 前先 catalog.health.check。
fresh 且版本未变时复用 brief 缓存。
stale/unknown 时降级注入并异步触发 catalog 刷新。
更新 SKILL.md 与 SKILL.md 为最终协议。
新增测试 test_drift_fallback.py 与 test_pull_cache_strategy.py。
Public APIs / Types（落地后）
session.sync.pull 返回 consistency_stamp 对象。
session.sync.push 返回 sync_id/memory_version/consistency_stamp/conflicts/status。
catalog.brief.generate 返回 catalog_brief/evidence/catalog_version/freshness。
catalog.health.check 返回标准健康结构。
catalog_edges.confidence 语义固定：0.0~1.0，阈值 0.5。
测试与验收
单测：policy、validation、migration、catalog brief、jobs、drift。
集成：pull -> generate -> task，push -> job -> health 的完整闭环。
回归：现有 test_sync_flow.py 全通过。
跨会话验收采样：至少 2 个项目、每项目 10 次切换。
命中率计算：正确携带(目标+约束+决策)/应携带总数。
通过门槛：总体 >=90%，单项目 >=85%。
实施顺序（提交粒度）
Commit 1：迁移框架 + P0-a 校验与错误码 + 测试。
Commit 2：Catalog 核心表 + indexer + brief.generate + 测试。
Commit 3：consistency/jobs/health + push 改造 + 测试。
Commit 4：drift fallback + pull 复用策略 + skill 文档 + 测试。
Assumptions / Defaults
仅本地 SQLite，按 project_id 严格隔离。
固定四角色，不开放自定义角色。
默认冲突策略 merge_note。
handoff TTL 72 小时，open_loops 不自动过期。
不启用逐轮对话强制日志，仅 pull/push 边界审计。

Hardening 执行更新（2026-02-11）
已完成：
1) 高风险修复：push 入口补齐 workspace 绑定校验，跨 workspace 写入将抛出 WORKSPACE_MISMATCH。
2) 协议一致性：session.sync.push 的 context_stamp 在 MCP schema 中与运行时保持一致（object|string|null）。
3) 契约测试补充：
   - test_session_sync_push_rejects_workspace_mismatch
   - test_context_stamp_schema_matches_runtime_legacy_support
4) 流程落地：
   - 新增 .github/pull_request_template.md（Hardening Gate）
   - 新增 risk_backlog.md（Medium/Low 统一收口）

下一步：
1) 跑全量测试 + 一轮 code review gate（仅 High 阻塞）。
2) 若无 High，进入“连续 2 轮无 High”计数。

Gate Review 轮次记录
- 轮次: Round 1（2026-02-11）
- 结果: 未发现新的 High 阻塞问题
- 验证: `python3 -m unittest discover -s tests -v` 全量通过（37/37）
- 计数: 连续无 High = 1/2
- 剩余: 再完成 1 轮 Gate Review（无 High）即可通过 Hardening 退出门槛中的该项要求

- 轮次: Round 2（2026-02-11）
- 结果: 未发现新的 High 阻塞问题
- 验证: `python3 -m unittest discover -s tests -v` 全量通过（37/37）
- 计数: 连续无 High = 2/2（已满足）
- 结论: Hardening Gate 中“连续两轮无 High”条件完成

验收脚本执行记录（2026-02-11）
- 目的: 验证跨会话命中率评估脚本链路可执行。
- 命令: `python3 scripts/evaluate_handoff_hit_rate.py --input /tmp/memory_hub_acceptance_smoke_20260211.jsonl`
- 结果: `pass=true`，`overall_hit_rate=1.0`（合成样本 smoke）。
- 说明: 该结果仅证明评估管道可用，不代表真实业务命中率；仍需使用真实人工标注样本做正式验收。

验收模板补充（2026-02-11）
- 新增文件: `samples/acceptance_template.jsonl`
- README 更新: 增加模板入口说明，便于快速开始标注。
- 校验: `python3 scripts/evaluate_handoff_hit_rate.py --input samples/acceptance_template.jsonl` 可执行（占位数据预期不通过）。
