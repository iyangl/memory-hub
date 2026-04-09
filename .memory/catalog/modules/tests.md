# tests

> 基于 18 个跟踪文件生成的模块导航；先看 `tests/__init__.py`、`tests/test_brief.py` 定位回归入口，再回到对应实现模块。

## 何时阅读

当任务涉及回归范围、测试入口或需要确认行为覆盖时阅读；先看 `tests/__init__.py`、`tests/test_brief.py`，再回到对应实现模块。

## 推荐入口
- `tests/__init__.py`
- `tests/test_brief.py`
- `tests/test_catalog.py`

## 推荐阅读顺序
- `tests/__init__.py`
- `tests/test_brief.py`
- `tests/test_catalog.py`
- `tests/test_envelope.py`
- `tests/test_execution_contract.py`

## 隐含约束
- tests 用于定位行为与回归入口，确认测试后仍需回到实现模块。
- 先从 `tests/__init__.py`、`tests/test_brief.py` 确认阅读起点，再决定是否继续下钻。

## 主要风险
- 测试文件 `tests/__init__.py`、`tests/test_brief.py` 只说明验证切口，仍需回到被测实现。
- 入口文件 `tests/__init__.py` 可能只负责装配或导出，真实规则在 下游实现文件。

## 验证重点
- 确认测试入口 `tests/__init__.py`、`tests/test_brief.py` 是否覆盖当前任务涉及的行为与回归范围。

## 代表文件
- `tests/__init__.py` — 测试锚点
- `tests/test_brief.py` — 测试锚点
- `tests/test_catalog.py` — 测试锚点
- `tests/test_envelope.py` — 测试锚点
- `tests/test_execution_contract.py` — 测试锚点
- `tests/test_inbox.py` — 测试锚点
- `tests/test_memory_flow.py` — 测试锚点
- `tests/test_memory_index.py` — 测试锚点
- `tests/test_memory_init.py` — 测试锚点
- `tests/test_memory_list_search.py` — 测试锚点
- `tests/test_memory_read.py` — 测试锚点
- `tests/test_memory_save.py` — 测试锚点
- `tests/test_modules_check.py` — 测试锚点
- `tests/test_paths.py` — 测试锚点
- `tests/test_recall_planner.py` — 测试锚点

## 关联记忆
- `docs/architect/decisions.md`
- `docs/qa/strategy.md`

<!-- generator_version: 2 -->
<!-- structure_hash: 274c0cd2 -->
