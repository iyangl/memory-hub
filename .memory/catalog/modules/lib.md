# lib

> 基于 22 个跟踪文件生成的模块导航，代表文件：`lib/__init__.py`、`lib/brief.py`。

## 何时阅读

当任务涉及 lib 的职责、边界或入口时阅读；优先从 `lib/__init__.py`、`lib/brief.py` 开始。

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
- 先从 `lib/__init__.py`、`lib/brief.py` 定位模块边界，再决定是否继续下钻。

## 主要风险
- 若只根据目录名 lib 理解模块，容易忽略真实入口与隐含约束。

## 验证重点
- 确认入口文件 `lib/__init__.py`、`lib/brief.py` 是否足以定位改动边界。
- 确认改动后需要补测或回归的关键路径。

## 代表文件
- `lib/__init__.py`
- `lib/brief.py`
- `lib/catalog_read.py`
- `lib/catalog_repair.py`
- `lib/catalog_update.py`
- `lib/cli.py`
- `lib/envelope.py`
- `lib/execution_contract.py`
- `lib/inbox_clean.py`
- `lib/inbox_list.py`
- `lib/memory_index.py`
- `lib/memory_init.py`
- `lib/memory_list.py`
- `lib/memory_read.py`
- `lib/memory_save.py`

## 关联记忆
- `docs/architect/decisions.md`
- `docs/dev/conventions.md`

<!-- structure_hash: a5750035 -->
