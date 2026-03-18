# Project Brief

## architect

### decisions.md
# 设计决策日志
### 决策 1 — 2026-02-26
背景：`memory-hub write` 通过 stdin/heredoc 传入内容，AI agent 调用时频繁出错（isatty 检测失败、heredoc 格式化错误、shell 转义问题）。`catalog-update` 同样依赖 stdin 传 JSON。

### tech-stack.md
## 技术栈
- 语言：Python 3.10+
- 运行时依赖：无（纯标准库）
- 开发依赖：pytest >= 7.0（仅测试）

## dev

### conventions.md
## 目录结构
- `bin/` — CLI 入口脚本（`bin/memory-hub`，设置 sys.path 后调用 `lib.cli.main`）
- `lib/` — 核心 Python 模块（envelope、paths、8 个命令实现）
- `tests/` — 单元测试（pytest，每个 `lib/` 模块对应一个测试文件）

### 记忆相关写入必须经过统一写入口.md
# 记忆相关写入必须经过统一写入口
所有记忆相关写入都必须经过统一写入口处理，不能直接修改 docs lane 或 durable store。

## pm

### decisions.md
# 需求结论与产品决策
### 结论 1 — 2026-03-11
背景：Phase 1F 完成后，Codex 路径的真实会话验收已基本符合预期；Claude 路径暂时搁置，不再阻塞当前版本收口。

## qa

### memory-相关逻辑变更必须补自动化测试和自测记录.md
# Memory 相关逻辑变更必须补自动化测试和自测记录
凡是修改 memory 相关逻辑，必须同时补齐对应的自动化测试，并留下可复现的自测记录。没有测试和自测记录的 memory 逻辑改动，不能视为完成。

### qa-strategy.md
# QA Strategy
所有 memory 相关改动都必须补回归测试。
新增一条规则：memory 相关改动必须运行 pytest -q。

### strategy.md
# 测试策略与质量约束
- 使用 pytest 进行单元测试
- 每个 lib/ 模块对应一个测试文件
