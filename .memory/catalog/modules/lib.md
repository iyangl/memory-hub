# lib

> 基于 22 个跟踪文件生成的模块导航；先看 `lib/__init__.py`、`lib/brief.py`，再下钻 `lib/catalog_repair.py`、`lib/catalog_update.py`。

## 何时阅读

当任务涉及 lib 的职责、入口或调用链时阅读；先看 `lib/__init__.py`、`lib/brief.py`，再继续 `lib/catalog_repair.py`、`lib/catalog_update.py`。

## 推荐入口
- `lib/__init__.py`
- `lib/brief.py`
- `lib/catalog_read.py`

## 推荐阅读顺序
- `lib/__init__.py`
- `lib/brief.py`
- `lib/catalog_read.py`
- `lib/catalog_repair.py`
- `lib/catalog_update.py`

## 隐含约束
- 先用 `lib/__init__.py` 确认入口或装配方式，再继续下钻 `lib/catalog_repair.py`、`lib/catalog_update.py`。

## 主要风险
- 入口文件 `lib/__init__.py` 可能只负责装配或导出，真实规则在 `lib/catalog_repair.py`、`lib/catalog_update.py`。

## 验证重点
- 确认改动后需要补测或回归的关键路径。

## 代表文件
- `lib/__init__.py` — 模块边界入口
- `lib/brief.py` — 优先阅读入口
- `lib/catalog_read.py` — 优先阅读入口
- `lib/catalog_repair.py` — 代表实现文件
- `lib/catalog_update.py` — 代表实现文件
- `lib/cli.py` — 代表实现文件
- `lib/envelope.py` — 代表实现文件
- `lib/execution_contract.py` — 代表实现文件
- `lib/inbox_clean.py` — 代表实现文件
- `lib/inbox_list.py` — 代表实现文件
- `lib/memory_index.py` — 代表实现文件
- `lib/memory_init.py` — 代表实现文件
- `lib/memory_list.py` — 代表实现文件
- `lib/memory_read.py` — 代表实现文件
- `lib/memory_save.py` — 代表实现文件

## 关联记忆
- `docs/architect/decisions.md`
- `docs/dev/conventions.md`

<!-- generator_version: 2 -->
<!-- structure_hash: a5750035 -->
