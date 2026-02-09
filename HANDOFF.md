# Memory Hub Handoff

更新时间：2026-02-09

## 1. 项目状态（当前接力点）
- 项目已按 greenfield 重建，旧实现已整体移除（保留 `.git` 历史）。
- 新架构已落地：`Python + SQLite + MCP`，本地优先、按 `project_id` 隔离。
- 双 skill 入口已定义（文档级）：
  - `skills/memory-pull/SKILL.md`
  - `skills/memory-push/SKILL.md`
- MCP 工具已实现：
  - `session.sync.pull`
  - `session.sync.push`
  - `session.sync.resolve_conflict`

## 2. 核心代码结构
- `memory_hub/server.py`：MCP JSON-RPC server、tools 注册与分发。
- `memory_hub/sync.py`：pull/push/冲突处理的编排逻辑。
- `memory_hub/store.py`：SQLite 数据访问与事务处理。
- `memory_hub/policy.py`：任务类型识别与角色注入策略。
- `memory_hub/schema.sql`：当前数据库 schema。
- `tests/test_policy.py`：策略单元测试。
- `tests/test_sync_flow.py`：同步流/冲突/隔离集成测试。

## 3. 已验证结果
已执行并通过：
```bash
python3 -m unittest discover -s tests -v
```
结果：6/6 通过。

已执行 MCP 冒烟：
- `initialize`
- `tools/list`
- `session.sync.push`
- `session.sync.pull`

## 4. 换电脑后快速启动（建议顺序）
1. 克隆仓库并进入目录。
2. 使用 Python 3.10+（建议 3.11/3.12）。
3. 运行测试确认环境：
```bash
python3 -m unittest discover -s tests -v
```
4. 启动 MCP server：
```bash
python3 -m memory_hub.server --root ~/.memory-hub
```
5. 验证 MCP 配置文件：
- `.mcp.json`
- `.codex/config.toml`

## 5. 当前行为约定
- 不再保留“每轮对话强制日志”规则。
- 只在会话边界进行同步：
  - 会话开始：`memory-pull <task prompt>`（先 pull 再执行任务）。
  - 会话结束：`memory-push`（无需新 prompt）。

## 6. 关键默认策略
- 固定角色：`pm | architect | dev | qa`。
- 任务自适应注入：
  - planning -> PM + Architect
  - design -> Architect + PM
  - implement -> Architect + Dev
  - test/review -> QA + Dev + Architect 摘要
- 冲突默认策略：`merge_note`。
- handoff TTL：72 小时。

## 7. 待完成事项（下一棒优先级）
P0
1. 将 skill 文档与实际客户端触发链路打通（确保 `memory-pull` 能包裹任务执行）。
2. 增加 `session.sync.resolve_conflict` 的更细粒度测试（多字段冲突矩阵）。
3. 增加错误码字典与用户可读错误映射（现在以异常文本为主）。

P1
1. 增加简易 CLI（仅用于本地调试 pull/push，不替代 skill 入口）。
2. 增加 `sync_audit` 查看工具（本地只读）。
3. 增加 schema migration 版本号机制。

P2
1. 对 `task_type=auto` 增加更多中英关键词和歧义回退策略。
2. 增加 token budget 的更精细裁剪策略（按角色配额）。

## 8. 已知风险
- `memory-pull/memory-push` 目前是“skill 规范 + MCP 实现”，还需要客户端侧真正按 skill 规范调用。
- 当前未提供单独发布版 CLI，仅依赖 MCP server。
- 目前无可视化 UI，排查依赖日志与测试。

## 9. 建议接力启动 Prompt（给下一台机器的 Codex）
```text
Read HANDOFF.md first.
Then run tests and verify MCP smoke calls for session.sync.pull/session.sync.push.
Next, implement client skill execution wiring so memory-pull runs pull before task execution and memory-push runs zero-prompt sync.
```
