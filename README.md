# Memory Hub

项目知识库 + durable memory 控制面。

当前仓库包含一个统一根目录下的两条 lane：

1. `.memory/docs/` 项目知识文档 lane
2. `.memory/_store/memory.db` durable memory store lane

前者服务“项目知识读写与 catalog 索引”，后者服务“LLM 长期记忆的 propose/review/rollback 闭环”。

## 核心原则

- 只沉淀代码读不到的信息
- durable memory 不允许直写，必须经过 `propose -> review -> approve/reject`
- 审查与回滚走 CLI
- 规则只识别 durable-memory 语境，workflow 由 skill 编排，MCP 只是 skill 可调用的能力面

## 安装

### 前置条件

- Python 3.10+
- 运行时无第三方依赖

### 直接运行

```bash
python3 -m lib.cli <command> [args]
python3 -m lib.mcp_server
```

### pip 安装

```bash
pip install -e .

memory-hub <command> [args]
memory-hub-mcp
```

## 统一目录

### `.memory/`

统一项目记忆根目录：

```text
.memory/
├── manifest.json
├── docs/
│   ├── pm/
│   ├── architect/
│   ├── dev/
│   └── qa/
├── catalog/
│   ├── topics.md
│   └── modules/
└── _store/
    ├── memory.db
    └── projections/
        ├── boot.json
        └── search.json
```

其中：

- `docs/` 记录项目级设计决策、约束、约定和 QA 策略
- `catalog/` 维护知识索引
- `_store/memory.db` 存储 durable memory v1 的：
  `approved_memories`、`memory_versions`、`memory_proposals`、`audit_events`、`docs_change_reviews`
- `_store/projections/` 承担统一 recall 投影视图：`boot.json` 与 `search.json`

## 行为层分层

Phase 2F 起，项目记忆的行为层分为五层：

1. `AGENTS.md` / `CLAUDE.md`
   - 只识别记忆语境与硬边界
2. `skills/project-memory/SKILL.md`
   - 统一项目记忆主入口，决定读 docs / catalog / durable / review，并在内部处理 durable branch
3. `skills/memory-admin/SKILL.md`
   - repair / diagnose / session-extract 维护动作
4. MCP
   - 提供统一 `read/search/capture/update/show_review`
5. CLI
   - 只做人类审查与回滚

当前约束：

- 普通代码/架构分析不默认进入 durable-memory workflow
- 跨会话、高价值、非代码信息才应进入 durable memory
- 如果最相关目标是 pending proposal，只能进入人工审查分流，不能继续 update
- 一旦进入 durable-memory workflow，本会话第一条 durable-memory 工具调用必须是 `memory-hub.read_memory(ref="system://boot")`
- review 目标进入 pending 状态后，必须先 `memory-hub.show_memory_review(...)`；若该 MCP 展示不可用，应视为宿主或 MCP 配置问题并停止

## 文件型知识命令

```bash
memory-hub init
memory-hub read <bucket> <file> [--anchor <heading>]
memory-hub list <bucket>
memory-hub search "<query>"
memory-hub index <bucket> <file> --topic <name> --summary "<desc>"
memory-hub discover [--summary-file <path>] [--limit <n>]
memory-hub catalog-read [topics|<module>]
memory-hub catalog-update --file <path-to-json>
memory-hub catalog-repair
memory-hub session-extract --file <path-to-session-transcript>
```

这套命令仍然服务 `.memory/docs/` 与 `catalog/`，不参与 durable memory v1 的写入审查。

## Durable Memory CLI

审查与回滚统一走 CLI：

```bash
memory-hub review list
memory-hub review show <proposal_id|ref>
memory-hub review approve <proposal_id|ref> [--reviewer <id>] [--note <text>]
memory-hub review reject <proposal_id|ref> --note <text> [--reviewer <id>]
memory-hub rollback <uri> --to-version <version_id> --note <text> [--reviewer <id>]
```

## Project Memory MCP

本地 stdio MCP server：

```bash
python3 -m lib.mcp_server
```

或：

```bash
memory-hub-mcp
```

Phase 2F 后当前 MCP 仍暴露 7 个 tools：

- `read_memory`
- `search_memory`
- `propose_memory`
- `propose_memory_update`
- `capture_memory`
- `update_memory`
- `show_memory_review`

### 客户端配置示例

如果直接用源码目录运行，推荐这样配：

```json
{
  "mcpServers": {
    "memory-hub": {
      "command": "python3",
      "args": ["-m", "lib.mcp_server"],
      "cwd": "/absolute/path/to/memory-hub",
      "env": {
        "PYTHONPATH": "/absolute/path/to/memory-hub",
        "MEMORY_HUB_PROJECT_ROOT": "/absolute/path/to/target-project"
      }
    }
  }
}
```

如果已经 `pip install -e .`，也可以改成：

```json
{
  "mcpServers": {
    "memory-hub": {
      "command": "memory-hub-mcp",
      "env": {
        "MEMORY_HUB_PROJECT_ROOT": "/absolute/path/to/target-project"
      }
    }
  }
}
```

### 统一项目记忆推荐工作流

1. 统一从 `project-memory` 进入记忆工作流
2. 在 Codex/Claude 里，`read_memory`、`search_memory`、`capture_memory`、`update_memory`、`show_memory_review` 都指 `memory-hub` 这个 MCP server 的 tools；不要把 `doc://...` / `catalog://...` 当成 MCP resources，也不要使用 `read_mcp_resource`
3. 普通仓库知识读取优先走 `memory-hub.read_memory(ref="doc://...")`、`memory-hub.read_memory(ref="catalog://...")` 与 `memory-hub.search_memory(..., scope=docs|all)`；`scope=all` 默认使用本地 hybrid recall
4. 统一写入优先走 `memory-hub.capture_memory(kind=auto|docs|durable, ...)` 与 `memory-hub.update_memory(ref, mode=patch|append, ...)`
5. `propose_memory(...)` 与 `propose_memory_update(...)` 仅作为兼容入口保留，不是默认工作流
6. 若路由结果是 `docs-only`，系统创建持久 docs change review；批准后再应用 docs 与 catalog 变更
7. 若路由结果是 `durable-only`，系统继续走 durable proposal / review
8. 若路由结果是 `dual-write`，系统创建 docs change review，并关联 durable summary proposal；批准 docs review 时同步批准关联 durable proposal
9. review 目标一旦产生或命中 pending 状态，先用 `memory-hub.show_memory_review(...)` 展示摘要和 diff；若该 MCP 展示不可用，应视为宿主或 MCP 配置问题并停止，不再设计 fallback
10. 若宿主支持结构化确认工具，则用三分叉确认；否则退化为文本分叉：`批准此提案` / `拒绝此提案` / `暂不处理`
11. 只有在展示 proposal 详情后且用户明确确认时，agent 才可代理执行 CLI `review approve/reject`
12. 必要时用 CLI `rollback`
13. 需要把一次对话沉淀成候选时，通过 `memory-admin` 运行 `memory-hub session-extract --file <transcript>`；提炼出的 docs / durable / dual-write 候选仍然只会进入既有 unified write lane 与 review surface，不会直接写 active state
14. 需要判断“这次代码改动里有没有新的规则、例外规则或 docs drift 候选”时，通过 `memory-admin` 运行 `memory-hub discover [--summary-file <path>]`；该命令只返回候选，不会直接写 active docs 或 approved durable state

`search_memory` 当前返回的关键元数据包括：

- `search_kind`
- `lane`
- `source_kind`
- `score`
- `lexical_score`
- `semantic_score`

若通过环境变量显式关闭 hybrid recall：

```bash
MEMORY_HUB_DISABLE_HYBRID_SEARCH=1
```

系统会退化到 lexical search，并显式返回：

- `degraded: true`
- `degrade_reasons: ["hybrid_search_disabled"]`

禁止事项：

- 直接修改 `.memory/_store/`
- 直接改 SQLite
- 用 `.memory/` 文件型命令代替 durable memory proposal
- 对 pending proposal 继续发起 update proposal
- 在展示 proposal 详情和拿到明确确认前执行 `review approve/reject`
- 代理执行 `rollback`

## 自测

一键端到端自测：

```bash
bin/selftest-phase1c
```

保留测试数据目录：

```bash
bin/selftest-phase1c --keep-root
```

这个脚本会自动验证：

- MCP `initialize`
- `tools/list`
- `read_memory(system://boot)`
- `propose_memory`
- `review list/show/approve`
- `propose_memory_update`
- `rollback`
- 预期错误路径

Phase 2F 会话提炼冒烟可直接执行：

```bash
memory-hub session-extract --file ./session.txt
```

Decision discovery 冒烟可直接执行：

```bash
memory-hub discover
memory-hub discover --summary-file ./summary.txt
```

会话级行为验收见：

- `.archive/plans/2026-03-10-phase1f-behavior-acceptance.md`

如果你在 Codex CLI 中调试项目记忆 workflow，注意它读取的是全局
`~/.agents/skills/project-memory/SKILL.md` 与
`~/.agents/skills/memory-admin/SKILL.md`。修改仓库内 skill 后，需要同步复制到
全局 skill 目录，并重启 Codex 会话。

## 测试

```bash
pytest -q
```

## 退出码

CLI 退出码：

- `0` 成功
- `1` 业务错误
- `2` 系统错误

## 备注

`REDESIGN.md` 主要记录早期 `.memory/` 文件型工作流的重构背景。durable memory v1 的当前基线，以 `README.md`、`CLAUDE.md`、`.archive/plans/*contract*` 和 `.archive/plans/*mvp-plan*` 为准。

## 许可

MIT
