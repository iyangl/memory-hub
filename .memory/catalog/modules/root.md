# root

> 基于 1 个跟踪文件生成的模块导航；先看 `pyproject.toml` 定位入口与配置。

## 何时阅读

当任务涉及项目入口、运行方式、全局配置或无法确定模块归属时阅读；先看 `pyproject.toml`。

## 推荐入口
- `pyproject.toml`

## 推荐阅读顺序
- `pyproject.toml`

## 隐含约束
- 先从 `pyproject.toml` 确认阅读起点，再决定是否继续下钻。
- 涉及依赖、构建或发布边界时，补读 `pyproject.toml`。
- root 只提供全局入口与全局配置线索，不能替代具体业务模块。

## 主要风险
- root 入口容易让人误以为已经掌握业务细节，实际仍需下钻具体模块。
- 清单文件 `pyproject.toml` 能说明依赖与边界，但不能代替运行时逻辑。

## 验证重点
- 确认 `pyproject.toml` 声明的边界或入口没有与改动范围失配。
- 确认改动后需要补测或回归的关键路径。

## 代表文件
- `pyproject.toml` — 依赖/构建清单

## 关联记忆
- `docs/architect/decisions.md`
- `docs/dev/conventions.md`

<!-- generator_version: 2 -->
<!-- structure_hash: 50c86b7e -->
