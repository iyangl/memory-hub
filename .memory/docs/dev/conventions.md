## 目录结构

- `bin/` — CLI 入口脚本（`bin/memory-hub`，设置 sys.path 后调用 `lib.cli.main`）
- `lib/` — 核心 Python 模块（envelope、paths、8 个命令实现）
- `tests/` — 单元测试（pytest，每个 `lib/` 模块对应一个测试文件）
- `skills/` — AI Skill 提示词（8 个原子 Skill，每个一个 `SKILL.md`）
- `.memory/` — 统一项目记忆根目录（`docs/`、`catalog/`、`_store/`）

## 命名约定

- 文件名：`snake_case`（如 `memory_read.py`、`catalog_repair.py`）
- CLI 命令名：`kebab-case`（如 `catalog-read`、`catalog-update`）
- Skill 目录名：`kebab-case`（如 `project-memory/`、`memory-admin/`）
- 函数名：`snake_case`
- 常量：`UPPER_SNAKE_CASE`

## 模块组织

- 每个 CLI 命令对应 `lib/` 下一个独立模块，导出 `run(args)` 函数
- `cli.py` 作为分发器，通过 `COMMANDS` 字典映射命令名到模块路径
- `envelope.py` 提供 `ok()`/`fail()`/`system_error()` 三个统一输出函数
- `paths.py` 集中管理 `.memory/docs`、`.memory/catalog`、`.memory/_store` 路径常量与桶名验证
