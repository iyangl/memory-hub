## 目录结构

- `lib/` — 核心 Python 模块（envelope、paths、9 个命令实现 + brief 生成）
- `tests/` — 单元测试（pytest，每个 `lib/` 模块对应一个测试文件）
- `.claude/commands/memory-hub/` — 三个 slash command 模板（init/recall/save）
- `.memory/` — 项目记忆根目录（docs/、catalog/、inbox/、BRIEF.md）
- `.archive/` — 归档的 v2 代码和数据

## 命名约定

- 文件名：`snake_case`（如 `memory_read.py`、`catalog_repair.py`）
- CLI 命令名：`kebab-case`（如 `catalog-read`、`catalog-update`）
- 函数名：`snake_case`
- 常量：`UPPER_SNAKE_CASE`

## 模块组织

- 每个 CLI 命令对应 `lib/` 下一个独立模块，导出 `run(args)` 函数
- `cli.py` 作为分发器，通过 `COMMANDS` 字典映射命令名到模块路径
- `envelope.py` 提供 `ok()`/`fail()`/`system_error()` 三个统一输出函数
- `paths.py` 集中管理 `.memory/docs`、`.memory/catalog`、`.memory/inbox`、`.memory/BRIEF.md` 路径常量与桶名验证
- `brief.py` 负责从 docs/ 机械拼接生成 BRIEF.md
