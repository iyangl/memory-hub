# Codex CLI 集成

## 方式一：通过命令添加 MCP 服务器
使用 `codex mcp add` 可以写入配置，并在 Codex CLI 中启用该服务器。

示例：
```bash
codex mcp add memory-hub -- python -m daemon
```

说明：
1. 如果你的环境只支持 `python3`，请将命令里的 `python` 改为 `python3`。
2. Codex CLI 会读取 `~/.codex/config.toml` 和项目内 `.codex/config.toml`。

## 方式二：直接编辑项目配置
项目内已提供 `.codex/config.toml`，内容如下：

```toml
[mcp_servers.memory-hub]
command = "python"
args = ["-m", "daemon"]
```

如果你的环境只支持 `python3`，请把 `command` 改为 `python3`。
