# Project Brief

## architect

### decisions.md
## v3 架构决策 — 2026-03-16 ~ 2026-03-18
### 决策 v3-1：从规则驱动转向 Skill 驱动

### tech-stack.md
## 技术栈
- 语言：Python 3.10+
- 运行时依赖：无（纯标准库）
- 开发依赖：pytest >= 7.0（仅测试）

## dev

### conventions.md
## 目录结构
- `lib/` — 核心 Python 模块（envelope、paths、9 个命令实现 + brief 生成）
- `tests/` — 单元测试（pytest，每个 `lib/` 模块对应一个测试文件）
- `.claude/commands/memory-hub/` — 三个 slash command 模板（init/recall/save）

## pm

### decisions.md
## v3 产品决策 — 2026-03-16 ~ 2026-03-18
### 结论 v3-1：Skill-Driven 架构替代规则驱动

## qa

### memory-相关逻辑变更必须补自动化测试和自测记录.md
# Memory 相关逻辑变更必须补自动化测试和自测记录
凡是修改 memory 相关逻辑，必须同时补齐对应的自动化测试，并留下可复现的自测记录。没有测试和自测记录的 memory 逻辑改动，不能视为完成。

### strategy.md
# 测试策略与质量约束
- 使用 pytest 进行单元测试
- 每个 lib/ 模块对应一个测试文件
