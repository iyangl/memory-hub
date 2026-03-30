# root

> 基于 1 个跟踪文件生成的模块导航，代表文件：`pyproject.toml`。

## 何时阅读

当任务涉及项目入口、全局配置或无法确定模块归属时阅读；先看 `pyproject.toml`。

## 推荐入口
- `pyproject.toml`

## 推荐阅读顺序
- `pyproject.toml`

## 隐含约束
- 先从 `pyproject.toml` 定位模块边界，再决定是否继续下钻。
- 若要判断职责或依赖，先读清单文件 `pyproject.toml`。
- root 只提供全局入口与配置线索，不能替代具体业务模块。

## 主要风险
- root 入口容易让人误以为已经掌握业务细节，实际仍需下钻具体模块。

## 验证重点
- 确认入口文件 `pyproject.toml` 是否足以定位改动边界。
- 确认改动后需要补测或回归的关键路径。

## 代表文件
- `pyproject.toml`

## 关联记忆
- `docs/architect/decisions.md`
- `docs/dev/conventions.md`
