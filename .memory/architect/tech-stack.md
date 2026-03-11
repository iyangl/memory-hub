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

- 无服务进程、无数据库、无协议层——纯文件读写
- 所有命令返回统一 JSON envelope（ok/fail），退出码 0/1/2
- 内容通过 stdin 传入（避免命令行转义和长度限制）
- 单用户场景，不引入并发控制
