# tests

> 单元测试：核心模块与 durable memory Phase 1A~Phase 2F 契约测试

- tests/durable_test_support.py — durable memory 测试数据、DB 辅助函数与 CLI 运行助手
- tests/test_catalog.py — catalog read/update/repair 测试
- tests/test_durable_cli.py — review/rollback CLI 与 docs review 契约测试
- tests/test_durable_proposals.py — proposal、write guard 与 approved search 测试
- tests/test_durable_review.py — approve、reject、rollback 事务测试
- tests/test_durable_schema.py — schema bootstrap、Phase 2C~2E 列扩展与 boot memory 顺序测试
- tests/test_envelope.py — JSON envelope 测试
- tests/test_mcp_server.py — MCP initialize/tools/list/tools/call、review surface 与 hybrid recall 契约测试
- tests/test_memory_index.py — index 命令测试
- tests/test_memory_init.py — init 命令测试
- tests/test_memory_list_search.py — list/search 命令测试
- tests/test_memory_read.py — read 命令测试
- tests/test_paths.py — 路径工具测试
- tests/test_session_extract.py — Phase 2F 会话提炼候选、route 分类与 unified write 落地测试
