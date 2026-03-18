## 技术栈

- 语言：Python 3.10+
- 运行时依赖：无（纯标准库）
- 开发依赖：pytest >= 7.0（仅测试）
- 构建系统：setuptools >= 68.0
- 包管理：pyproject.toml（PEP 621）

## CLI 入口

- 安装后入口：`memory-hub`（pyproject.toml `[project.scripts]` 注册）
- 开发模式入口：`python3 -m lib.cli`
- 分发器模式：`lib/cli.py` 按命令名动态 import 对应模块，避免启动时加载全部模块

## 关键设计约束

- 无服务进程、无外部数据库服务、无远程协议层
- 项目级本地存储：纯文件（`.memory/docs/` + `.memory/catalog/` + `.memory/BRIEF.md`）
- 所有 CLI 命令返回统一 JSON envelope（ok/fail），退出码 0/1/2
- 单用户场景，不引入并发控制

## 存储架构（v3）

- `docs/` 是唯一正本，所有项目知识在这里
- `BRIEF.md` 是 docs 的派生摘要，由 `memory-hub brief` 机械拼接生成
- `catalog/` 是派生索引，由 CLI 命令维护
- `inbox/` 是 Layer 2 临时写入区，不跟踪 git
