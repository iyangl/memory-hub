# Project Brief



> Recall-first base brief: 只保留会影响后续动作的高价值上下文。

## architect

### caching.md
## 决策
使用本地文件缓存

### decisions.md
## Recall-first 架构决策
`.memory/docs/` 是唯一正本；`BRIEF.md`、`catalog/`、`session/` 都是派生产物。
recall 必须先执行 `recall-plan`，再按 `skip | light | deep` 决定读取范围。
当 `search_first = true` 时，必须先搜索，再把搜索命中回填为最终推荐来源，然后再决定 recall 深度。

### tech-stack.md
## 关键设计约束
无服务进程、无远程协议层、无外部数据库，所有状态都落在项目目录。
所有 CLI 命令返回统一 JSON envelope（ok/fail），退出码保持 0/1/2。
durable knowledge 只保存在 `.memory/docs/`，其余目录均视为派生产物或会话产物。

## dev

### conventions.md
## 命名约定
文件名：`snake_case`（如 `memory_read.py`、`catalog_repair.py`）
CLI 命令名：`kebab-case`（如 `catalog-read`、`catalog-update`）
函数名：`snake_case`

## pm

### decisions.md
## Recall-first 产品结论
recall 的目标是先定位再读取，而不是把所有 docs 一次性读完。
`light` 只读取少量最相关 docs / module cards；`deep` 才构建压缩后的 `working-set`。
当 planner 返回 `search_first = true` 时，必须先搜索，再依据回填结果决定最终来源与 recall 深度。

## qa

### memory-相关逻辑变更必须补自动化测试和自测记录.md
# Memory 相关逻辑变更必须补自动化测试和自测记录
凡是修改 memory 相关逻辑，必须同时补齐对应的自动化测试，并留下可复现的自测记录。没有测试和自测记录的 memory 逻辑改动，不能视为完成。

### strategy.md
# 测试策略与质量约束
使用 pytest 进行单元测试
每个 lib/ 模块对应一个测试文件
