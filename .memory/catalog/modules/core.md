# core

> 基础设施与仓库级行为接线：CLI 分发、JSON envelope、路径管理、规则入口、MCP/自测启动

- AGENTS.md — Codex 仓库级规则入口：语境识别、`project-memory` durable branch 触发与硬边界
- CLAUDE.md — Claude 仓库级行为指引：统一 `.memory/` 根目录、`project-memory` 主入口、统一写入与内部 durable branch
- README.md — 项目说明：`.memory/` 统一目录、lane 分层、`project-memory` / `memory-admin` / unified MCP 用法、session-extract 与自测方式
- .mcp.json — 项目级 MCP server 配置
- bin/memory-hub — memory-hub CLI 可执行入口
- bin/memory-hub-mcp — memory-hub MCP server 可执行入口
- bin/selftest-phase1c — Phase 1C 一键端到端自测脚本
- lib/cli.py — CLI 命令分发入口，包含 review/rollback/session-extract
- lib/envelope.py — 统一 JSON envelope 输出格式与退出码
- lib/paths.py — 路径常量、`.memory/docs` / `.memory/_store` / projections 计算与 bucket 校验
- skills/project-memory/SKILL.md — 统一项目记忆主入口 skill
- skills/memory-admin/SKILL.md — 项目记忆维护入口 skill，包含 session-extract
- lib/utils.py — 共享工具函数（atomic_write）
