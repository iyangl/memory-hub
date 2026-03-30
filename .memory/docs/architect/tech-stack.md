# Memory Hub 技术栈与运行约束

## 技术栈

- 语言：Python 3.10+
- 运行时依赖：无（纯标准库）
- 开发依赖：pytest（自动化测试）
- 构建系统：setuptools + `pyproject.toml`

## CLI 入口

- 安装后入口：`memory-hub`
- Windows 开发模式入口：`py -3 -m lib.cli`
- `lib/cli.py` 按命令名动态分发到各子模块，保持命令实现独立。

## 关键设计约束

- 无服务进程、无远程协议层、无外部数据库，所有状态都落在项目目录。
- 所有 CLI 命令返回统一 JSON envelope（ok/fail），退出码保持 0/1/2。
- durable knowledge 只保存在 `.memory/docs/`，其余目录均视为派生产物或会话产物。

## 存储架构

- `docs/` 是唯一正本。
- `BRIEF.md` 由 `brief` 根据高价值 section 自动提炼。
- `catalog/` 由 `scan-modules`、`catalog-update`、`catalog-repair` 维护。
- `session/` 只保存 recall-plan、working-set、save-request 等任务级文件，不能替代长期 docs。
