# Memory Hub Recall-First 重构计划

> 日期：2026-03-27
> 状态：规划完成，尚未实施
> 目标：将 Memory Hub 从“项目知识库 / skill-driven 工作流”进一步收敛为**代码阅读前的决策性上下文前置层**。

---

## Context

当前 v3 已完成“去 MCP / 去 durable / 三个 command 收口”，但主链仍围绕“BRIEF 机械预热 + 人工按需深入”，还没有真正落成新的产品定位：

- recall-first，而不是默认全量读
- 只沉淀会改变后续动作的高价值信息：决策、约束、风险、业务口径、验证策略、模块阅读导航
- init 产出“模块阅读导航 + 隐含约束 + 风险 + 验证重点”，而不是代码结构摘要
- 为中大型任务增加 session working set
- 主设计按 Claude Code 优先，hooks 只做轻量 recall / 候选捕获 / 提醒 / 质量门，不替代最终 save/init 深分析

本次规划同时发现：当前 `.memory/catalog/` 与 `BRIEF.md` 仍带有旧 schema / 旧叙事，测试也尚未覆盖真实链路与漂移检测。

补充说明：`v3-phase1-dev-plan.md` 属于旧 v3 线在开发尾声阶段的历史实施稿；当前执行以本计划为准。

---

## 总体策略

采用“**先冻结决策 → 再改 schema 和派生链路 → 再重写命令模板 → 最后补测试和重建派生产物**”的顺序推进。

推荐平台策略：**主设计立即按 Claude Code-only 收口，Codex 进入冻结兼容态**。

### 增补原则（受 Memory Palace 启发）

#### 原则 A：Bootstrap Recall Protocol
recall 不是“先读一点再看情况”，而是固定协议：

1. 先读 base brief
2. 若任务对象不明确，先 search/topics/modules 定位
3. 再判定 `skip | light | deep`
4. `deep` 时构建 session working set

#### 原则 B：Search Before Guess
当任务中的模块名、业务对象、历史术语、抽象概念不够明确时，先查 `topics.md`、module cards、相关 docs，再决定读什么；不允许仅凭 task 文本直接猜推荐来源。

#### 原则 C：Read Before Write
`/save` 在合并知识前，必须先读取目标 doc 或候选 doc，再决定是 append / merge / update；不允许在未读旧内容的情况下直接覆盖长期知识。

#### 原则 D：Guard Result Is First-Class
`/save` 的结果不只分“写入/不写入”，而是显式支持：
- `noop`
- `create`
- `append`
- `merge`
- `update`

#### 原则 E：Host Adapter 不是 Correctness Core
hooks、AGENTS 兼容说明、宿主适配脚本只负责提醒、接线和增强，不承担核心正确性。核心链路仍由 recall planner、working set、save merge 逻辑保证。

---

## Phase 0：冻结新定位与平台边界

### 需要修改的文件

1. `README.md`
2. `CLAUDE.md`
3. `AGENTS.md`
4. `.memory/docs/pm/decisions.md`
5. `.memory/docs/architect/decisions.md`
6. `.archive/plans/2026-03-16-memory-hub-v3-skill-driven-redesign.md`

### 修改目标

#### `README.md`
- 重写产品定位为“代码阅读前的决策性上下文前置层”
- 写明 recall-first 和 skip/light/deep recall 原则
- 明确 memory 存什么 / 不存什么
- 将 Codex 从主叙事降级；推荐写成：Claude Code 主支持，Codex 冻结兼容
- 明确 bootstrap recall protocol：先 base brief，必要时 search，再判定 recall 深度
- 明确 `/save` 可以合法返回 `noop`

#### `CLAUDE.md`
- 从“三个 command 说明”升级成“行为优先级文档”
- 强调：先判断要不要 recall，再按需读 docs，再执行，再 save
- 写入 recall 三档触发条件：局部性 / 隐含约束密度 / 决策风险
- hooks 只作为增强层，不作为 correctness 前提
- 明确写入 `search before guess`
- 明确写入 `read before write`

#### `AGENTS.md`
- 改成极简兼容说明，不再镜像 CLAUDE.md
- 明确本文件只负责兼容，不承担 correctness 规则

#### `.memory/docs/pm/decisions.md`
- 新增产品决策：决策性上下文前置层、recall-first、memory 价值边界、平台策略
- 新增：`noop` 为合法 save 结果
- 新增：working set 不等于长期记忆

#### `.memory/docs/architect/decisions.md`
- 新增架构决策：base brief、task-scoped recall planner、session working set、module navigation、hooks 边界
- 新增：bootstrap recall protocol
- 新增：search before guess / read before write

#### `.archive/plans/2026-03-16-memory-hub-v3-skill-driven-redesign.md`
- 降级为阶段性历史方案，顶部注明当前定位已演进

---

## Phase 1：重构核心 schema 与派生链路

### 可复用的现有能力

#### `lib/scan_modules.py`
复用：
- `_detect_project_type`
- `_get_tracked_files`
- `_list_source_files`
- `_pick_notable_files`
- `_build_dir_tree`
- `_discover_modules`

#### `lib/catalog_update.py`
复用：
- JSON -> markdown 管线
- topics 区段更新机制
- module 名称 sanitize
- 校验入口

#### 其他可复用
- `lib/utils.py`：原子写/命名工具
- `lib/memory_init.py`：布局创建与初始化 guard
- `lib/cli.py`：动态命令分发模式

### 需要改造/新增的文件

1. `lib/scan_modules.py`
2. `lib/catalog_update.py`
3. `lib/brief.py`
4. `lib/memory_init.py`
5. `lib/cli.py`
6. `lib/recall_planner.py`（新增）
7. `lib/session_working_set.py`（新增）
8. `lib/hook_bridge.py`（可选新增，若确认 CC-only）

### 具体改造方向

#### `lib/scan_modules.py`
- 将 module 输出从“结构脚手架”改成“导航脚手架”
- 保留：`name`、`dir_tree`、`total_files`、`files`
- 新增字段：
  - `read_when`
  - `entry_points`
  - `read_order`
  - `implicit_constraints`
  - `known_risks`
  - `verification_focus`
  - `related_memory`
- 可选增强字段：
  - `aliases`
  - `why_read_first`
- 弱化或删除：
  - `purpose`
  - `key_abstractions`
  - `internal_deps`

#### `lib/catalog_update.py`
- 重写 module markdown section
- 目标 section：
  - 何时阅读
  - 推荐阅读顺序
  - 隐含约束
  - 主要风险
  - 验证重点
  - 代表文件
  - 关联记忆
- `topics.md` 的代码模块区改成“导航入口索引”而不是静态模块摘要
- 允许旧 schema 输入降级兼容，但输出统一走新导航叙事

#### `lib/brief.py`
- 将 BRIEF 重定位为 **base brief / boot summary**
- 不再均匀拼接 docs 首段；优先抽取全局高价值决策/约束/风险
- 保留总行数控制，但输出要服务 recall-first，而不是“文档目录摘要”

#### `lib/memory_init.py`
- 升级 layout version
- 增加 `.memory/session/` 骨架
- init 完成后切换到新链路：scan navigation scaffold -> catalog update -> brief build

#### `lib/cli.py`
- 新增命令：
  - `recall-plan`
  - `working-set`

#### `lib/recall_planner.py`（新增）
- 输入：
  - 任务描述
  - base brief
  - `topics.md`
  - module cards
- 输出不只是 `skip | light | deep`，还应包含：
  - `recall_level`
  - `task_kind`
  - `ambiguity`
  - `search_first`
  - `recommended_docs`
  - `recommended_modules`
  - `why_these`
  - `evidence_gaps`

#### `lib/session_working_set.py`（新增）
- 把 deep recall 选中的内容压缩成当前任务 working set
- 只作为会话内派生层，不直接落入长期 docs
- 每条内容应尽量保留：
  - 来源路径
  - 被选中原因
  - 证据缺口

#### `lib/hook_bridge.py`（可选新增）
- 只做轻量 recall 提醒、候选捕获、Stop 前提醒、质量门触发
- 不承担 correctness

---

## Phase 2：重写命令模板

### 需要修改的文件

1. `.claude/commands/memory-hub/init.md`
2. `.claude/commands/memory-hub/recall.md`
3. `.claude/commands/memory-hub/save.md`

### 修改目标

#### `init.md`
- 不再以 tech-stack / conventions / architecture summary 为中心
- 核心产物改为：模块阅读导航、隐含约束、风险、验证重点
- 保留“实际读代码再生成知识”的要求

#### `recall.md`
- 先执行 `recall-plan` 判定 `skip/light/deep`
- `skip`：不读或只读极少量 base brief
- `light`：读 base brief + 少量相关 docs/module cards
- `deep`：构建 session working set，再注入上下文
- 若 `search_first = true`，先 search 再决定来源
- 推荐阅读时必须给出 `why_these`

#### `save.md`
- 保留“后悔测试 + 去重 + docs 为唯一正本”
- 新增 working set 的归档规则
- 新增 hooks 候选与最终 save 的边界说明
- 最后仍重建：BRIEF / topics / modules catalog
- 支持 `noop / create / append / merge / update`

---

## Phase 3：测试补齐与派生产物重建

### 需要修改/新增的测试文件

#### 修改
1. `tests/test_scan_modules.py`
2. `tests/test_catalog.py`
3. `tests/test_brief.py`
4. `tests/test_memory_init.py`
5. `tests/test_paths.py`

#### 新增
6. `tests/test_recall_planner.py`
7. `tests/test_session_working_set.py`
8. `tests/test_memory_flow.py`

### 测试目标

#### `tests/test_scan_modules.py`
- 覆盖新导航字段、入口文件识别、代表文件优先级、非 trivial 模块筛选

#### `tests/test_catalog.py`
- 覆盖新 module markdown section、topics 代码模块区的新叙事、旧 schema 输入处理、全量重建

#### `tests/test_brief.py`
- 覆盖决策/约束/风险优先提取、base brief 行数控制、禁止内容不进入 BRIEF

#### `tests/test_memory_init.py`
- 覆盖新 layout version、session 目录、init 后新派生链

#### `tests/test_recall_planner.py`
- 覆盖 `task_kind` 分类与 `search_first`
- 覆盖对象模糊时不盲猜模块

#### `tests/test_session_working_set.py`
- 覆盖 working set 压缩、去重、长度控制
- 覆盖来源路径保留与 evidence gap 保留

#### `tests/test_memory_flow.py`
- 跑真实主链：init -> scan-modules -> catalog-update -> brief -> recall-plan -> working-set

### 需要整体重建的派生产物
- `.memory/catalog/topics.md`
- `.memory/catalog/modules/*.md`
- `.memory/BRIEF.md`

---

## File-by-File Execution Order

1. `.memory/docs/pm/decisions.md`
2. `.memory/docs/architect/decisions.md`
3. `README.md`
4. `CLAUDE.md`
5. `AGENTS.md`
6. `lib/recall_planner.py`
7. `lib/session_working_set.py`
8. `lib/scan_modules.py`
9. `lib/catalog_update.py`
10. `lib/brief.py`
11. `lib/cli.py`
12. `lib/memory_init.py`
13. `.claude/commands/memory-hub/init.md`
14. `.claude/commands/memory-hub/recall.md`
15. `.claude/commands/memory-hub/save.md`
16. `tests/test_scan_modules.py`
17. `tests/test_catalog.py`
18. `tests/test_brief.py`
19. `tests/test_memory_init.py`
20. `tests/test_paths.py`
21. `tests/test_recall_planner.py`
22. `tests/test_session_working_set.py`
23. `tests/test_memory_flow.py`
24. 重建 `.memory/catalog/*` 与 `.memory/BRIEF.md`

---

## Platform Decision

推荐方案：**主设计立即按 Claude Code-only 收口，Codex 进入冻结兼容态**。

执行上落成三条规则：
1. 架构与流程按 Claude Code 能力设计
2. Codex 不再作为 correctness 约束源，只保留手工兼容说明
3. hooks 作为 Claude Code 增强层进入主设计，但不能成为 correctness 前提

### 明确不吸收的范围

本次只吸收 Memory Palace 的“协议与治理语义”，不吸收其重型产品复杂度。

明确不引入：
- SQLite durable store
- MCP-first 主架构
- Dashboard / Review / Rollback UI
- 完整 vitality score / decay 数值治理系统
- 多部署档位（A/B/C/D）带来的运维复杂度

---

## 本次增补的最小落地优先级

优先落地三件事：

1. `recall-plan` 增加：
   - `search_first`
   - `task_kind`
   - `why_these`
2. `/recall` 强制执行：
   - base brief
   - 若不明确先 search
   - 再做 skip/light/deep
3. `/save` 增加：
   - `noop`
   - `create`
   - `append`
   - `merge`
   - `update`

---

## Verification

### 单元验证
```bash
pytest -q tests/test_scan_modules.py tests/test_catalog.py tests/test_brief.py tests/test_memory_init.py tests/test_paths.py tests/test_recall_planner.py tests/test_session_working_set.py tests/test_memory_flow.py
```

### 真实链路验证
```bash
python3 -m lib.cli init
python3 -m lib.cli scan-modules
python3 -m lib.cli catalog-update ...
python3 -m lib.cli brief
python3 -m lib.cli recall-plan --task "<任务描述>"
python3 -m lib.cli working-set ...
```

### 人工验收
- 场景 A：局部小任务，应命中 `skip` 或 `light`
- 场景 B：对象模糊任务，应先 search 再 recall
- 场景 C：跨模块/高风险任务，应命中 `deep`，并生成可用的 session working set
- 场景 D：无新长期知识时，`/save` 应合法返回 `noop`
- 验证 `.memory/catalog/modules/*.md` 是否真正变成“阅读导航卡”
- 验证 BRIEF 是否是 base brief，而不是 bucket 首段拼盘
