# Memory Hub

项目知识库 + durable memory 控制面。

当前仓库同时包含两套能力：

1. `.memory/` 文件型项目知识库
2. `.memoryhub/` SQLite durable memory v1

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

## 两套存储面

### `.memory/`

项目知识文件与 catalog：

```text
.memory/
├── pm/
├── architect/
├── dev/
├── qa/
└── catalog/
```

用于记录项目级设计决策、约束、约定和目录索引。

v1 不计划移除 `.memory/`。它仍然是项目知识的主存储面。

### `.memoryhub/`

durable memory v1：

```text
.memoryhub/
└── memory.db
```

用于存储：

- `approved_memories`
- `memory_versions`
- `memory_proposals`
- `audit_events`

`.memoryhub/` 不替代 `.memory/` 的全部职责；它只负责 durable memory proposal/review/rollback。

## 行为层分层

durable-memory v1 的行为层分为四层：

1. `AGENTS.md` / `CLAUDE.md`
   - 只识别 durable-memory 语境与硬边界
2. `skills/durable-memory/SKILL.md`
   - 决定是否加载 boot memory、检索现有 memory、创建 proposal 或更新 proposal
3. MCP
   - 提供 `read/search/propose/update` 能力
4. CLI
   - 只做人类审查与回滚

当前约束：

- 普通代码/架构分析不默认进入 durable-memory workflow
- 跨会话、高价值、非代码信息才应进入 durable memory
- 如果最相关目标是 pending proposal，只能进入人工审查分流，不能继续 update
- 一旦进入 durable-memory workflow，本会话第一条 durable-memory 工具调用必须是 `read_memory("system://boot")`
- proposal 创建成功或命中 pending proposal 后，必须先 `review show <proposal_id>`，再进入确认分流

## 文件型知识命令

```bash
memory-hub init
memory-hub read <bucket> <file> [--anchor <heading>]
memory-hub list <bucket>
memory-hub search "<query>"
memory-hub index <bucket> <file> --topic <name> --summary "<desc>"
memory-hub catalog-read [topics|<module>]
memory-hub catalog-update --file <path-to-json>
memory-hub catalog-repair
```

这套命令仍然服务 `.memory/` 目录，不参与 durable memory v1 的写入审查。

## Durable Memory CLI

审查与回滚统一走 CLI：

```bash
memory-hub review list
memory-hub review show <proposal_id>
memory-hub review approve <proposal_id> [--reviewer <id>] [--note <text>]
memory-hub review reject <proposal_id> --note <text> [--reviewer <id>]
memory-hub rollback <uri> --to-version <version_id> --note <text> [--reviewer <id>]
```

## Durable Memory MCP

本地 stdio MCP server：

```bash
python3 -m lib.mcp_server
```

或：

```bash
memory-hub-mcp
```

当前暴露 4 个 tools：

- `read_memory`
- `search_memory`
- `propose_memory`
- `propose_memory_update`

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

### Durable Memory 推荐工作流

1. 规则层识别当前信息是否进入 durable-memory 语境
2. 一旦进入 durable-memory 语境，转入 `durable-memory` skill
3. 由 skill 在首次 durable-memory 动作时决定是否加载 `system://boot`
4. 由 skill 决定是检索 approved memory、创建 proposal，还是更新 approved memory
5. `proposal_id` 一旦产生或命中 pending proposal，skill 先自动执行 `review show <proposal_id>`，展示摘要和 diff
6. 若宿主支持结构化确认工具，则用三分叉确认；否则退化为文本分叉：`批准此提案` / `拒绝此提案` / `暂不处理`
7. 只有在展示 proposal 详情后且用户明确确认时，agent 才可代理执行 CLI `review approve/reject`
8. 必要时用 CLI `rollback`

禁止事项：

- 直接修改 `.memoryhub/`
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

会话级行为验收见：

- `.archive/plans/2026-03-10-phase1f-behavior-acceptance.md`

如果你在 Codex CLI 中调试 durable-memory skill，注意它读取的是全局
`~/.agents/skills/durable-memory/SKILL.md`。修改仓库内
`skills/durable-memory/SKILL.md` 后，需要同步复制到全局 skill 目录，并重启
Codex 会话。

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
