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
- LLM 通过本地 stdio MCP server 调 durable memory tools

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

1. 会话开始或首次触发 durable memory 时，先调 `read_memory("system://boot")`
2. 需要检索已有长期记忆时，调 `search_memory`
3. 发现新长期信息时，调 `propose_memory`
4. 发现应更新已有长期记忆时，调 `propose_memory_update`
5. 人类用 CLI `review approve/reject`
6. 必要时用 CLI `rollback`

禁止事项：

- 直接修改 `.memoryhub/`
- 直接改 SQLite
- 用 `.memory/` 文件型命令代替 durable memory proposal

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
