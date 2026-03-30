# tests

> 基于 11 个跟踪文件生成的模块导航，代表文件：`tests/__init__.py`、`tests/test_brief.py`。

## 何时阅读

当任务涉及验证策略、回归范围或测试入口时阅读；先看 `tests/__init__.py`、`tests/test_brief.py`。

## 推荐入口
- `tests/__init__.py`
- `tests/test_brief.py`
- `tests/test_catalog.py`

## 推荐阅读顺序
- `tests/__init__.py`
- `tests/test_brief.py`
- `tests/test_catalog.py`
- `tests/test_envelope.py`
- `tests/test_memory_index.py`

## 隐含约束
- 先从 `tests/__init__.py`、`tests/test_brief.py` 定位模块边界，再决定是否继续下钻。

## 主要风险
- 测试文件 `tests/test_brief.py`、`tests/test_catalog.py` 只反映验证方式，不等于真实运行入口。

## 验证重点
- 确认测试入口 `tests/__init__.py`、`tests/test_brief.py` 覆盖的行为与当前任务相关。

## 代表文件
- `tests/__init__.py`
- `tests/test_brief.py`
- `tests/test_catalog.py`
- `tests/test_envelope.py`
- `tests/test_memory_index.py`
- `tests/test_memory_init.py`
- `tests/test_memory_list_search.py`
- `tests/test_memory_read.py`
- `tests/test_paths.py`
- `tests/test_scan_modules.py`
- `tests/test_utils.py`

## 关联记忆
- `docs/architect/decisions.md`
- `docs/qa/strategy.md`
