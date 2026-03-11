# core

> 基础设施与仓库级行为接线：CLI 分发、JSON envelope、路径管理、规则入口、MCP/自测启动

- AGENTS.md — Codex 仓库级规则入口：语境识别、durable-memory 触发与硬边界
- CLAUDE.md — Claude 仓库级行为指引：两套 memory surface 与 skill 触发规则
- README.md — 项目说明：两套存储面、行为层分层、CLI/MCP 用法与自测方式
- .mcp.json — 项目级 MCP server 配置
- bin/memory-hub — memory-hub CLI 可执行入口
- bin/memory-hub-mcp — memory-hub MCP server 可执行入口
- bin/selftest-phase1c — Phase 1C 一键端到端自测脚本
- lib/cli.py — CLI 命令分发入口
- lib/envelope.py — 统一 JSON envelope 输出格式与退出码
- lib/paths.py — 路径常量、.memory/.memoryhub 路径计算与 bucket 校验
- lib/utils.py — 共享工具函数（atomic_write）
