# Claude Code 集成

## 方式一：通过命令添加 MCP 服务器
使用 `claude mcp add` 可以把 MCP 服务器写入配置。

示例：
```bash
claude mcp add --transport stdio --scope project memory-hub -- python -m daemon
```

说明：
1. 如果你的环境只支持 `python3`，请将命令里的 `python` 改为 `python3`。
2. 选项必须放在服务器名之前，`--` 后面才是实际执行的命令和参数。
3. 使用 `--scope project` 时会创建或更新项目根目录的 `.mcp.json`。

## 方式二：直接编辑项目配置
项目内已提供 `.mcp.json`，内容如下：

```json
{
  "mcpServers": {
    "memory-hub": {
      "command": "python",
      "args": ["-m", "daemon"]
    }
  }
}
```

如果你的环境只支持 `python3`，请把 `command` 改为 `python3`。
