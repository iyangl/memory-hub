# Risk Backlog

说明:
- 仅记录 `Medium/Low` 风险，`High` 不进入 backlog，必须当轮修复。
- 每项需包含: 影响、触发条件、计划修复窗口、测试补充。

## Open

### R-M-001 Pull Token Budget 分配仍较粗糙
- Level: `Medium`
- 影响: `memory_context_brief + catalog_brief` 在复杂项目上可能挤占任务 token。
- 触发条件: 大仓库 + 长 prompt + 多角色注入。
- 修复窗口: `Hardening` 后第一轮优化迭代。
- 计划: 引入分段预算策略（memory/catalog 软硬上限）。
- 测试补充: 构造超长上下文用例，验证截断优先级。

### R-L-001 Catalog 评分启发式可解释性有限
- Level: `Low`
- 影响: brief 排名可能偏向文件名命中，不总是最优。
- 触发条件: 命名不规范项目或多语言混合仓。
- 修复窗口: 命中率评估后按需优化。
- 计划: 增加结构信号（调用关系、目录层级权重）。
- 测试补充: 多项目样本对比排名稳定性。

## Resolved

### R-H-Workspace-Push
- Level: `High`
- 状态: `Resolved`
- 修复: `session_sync_push` 增加 workspace 绑定校验，拒绝跨 workspace 写入。
- 证据: `tests/test_review_fixes.py::WorkspaceIsolationTest.test_session_sync_push_rejects_workspace_mismatch`

### R-H-ContextStamp-Contract
- Level: `High`
- 状态: `Resolved`
- 修复: `session.sync.push` schema 与运行时兼容策略统一（支持 legacy string）。
- 证据: `tests/test_push_validation.py::PushValidationTests.test_context_stamp_schema_matches_runtime_legacy_support`
