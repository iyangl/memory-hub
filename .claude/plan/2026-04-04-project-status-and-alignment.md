# Memory Hub 当前进展与路线一致性评估

## 结论

当前项目整体路线与核心思想保持一致，而且比之前更聚焦。

现阶段更准确的定位是：**主架构已经对齐核心思想，现处于内容深化与 recall 质量增强阶段。**

也就是说：
- 方向不是主要问题
- 主循环已经成形
- 当前瓶颈主要在内容质量与 recall 命中质量，不在入口设计

---

## 当前核心思想

Memory Hub 的核心思想可以概括为：

1. **Memory Hub 不是代码摘要库**，而是代码阅读前的“决策性上下文前置层”
2. **不是所有任务都要先读记忆**，而是先判断任务，再决定 recall 深度
3. recall 应遵循 **先定位，再决定读什么**，而不是把所有资料一次性读完
4. 长期知识只沉淀高价值、低代码可见性、会改变后续动作的信息：
   - 决策
   - 约束
   - 风险
   - 验证重点
   - 业务口径
   - 模块阅读导航
5. session working set 只能作为任务级上下文，**不能原样回写 durable docs**

---

## 已完成事项

### 1. 主入口已经收敛

当前有效入口已经收敛到 `memory-hub` CLI 与 `.claude/commands/memory-hub/*.md` 这条主线。

现行命令面见：`lib/cli.py`

当前 CLI surface：
- `init`
- `read`
- `list`
- `search`
- `index`
- `catalog-read`
- `catalog-update`
- `catalog-repair`
- `brief`
- `scan-modules`
- `recall-plan`
- `working-set`
- `execution-contract`
- `save`
- `inbox-list`
- `inbox-clean`
- `modules-check`

这说明项目已经从“多入口并存”收敛到一条主路径。

### 2. recall-first 主循环已经落地

架构与产品层已经明确写入 recall-first 契约：

- `.memory/docs/architect/decisions.md`
- `.memory/docs/pm/decisions.md`

已明确的核心规则包括：
- `.memory/docs/` 是唯一正本
- recall 必须先执行 `recall-plan`
- 根据 `skip | light | deep` 决定读取范围
- 当 `search_first = true` 时，必须先搜索，再决定最终来源
- `noop` 是合法结果

### 3. recall-plan 已经进入实现层

`lib/recall_planner.py` 已经承担实际 recall 规划，而不是停留在 README 级别说明。

当前实现已经具备：
- 任务类型判断
- 高风险模式判断
- search-first 提示词判断
- 从 `BRIEF.md` / `topics.md` / module cards 中提取候选来源

这与“先定位，再决定读什么”的核心思想一致。

### 4. session working set 已经成形

`lib/session_working_set.py` 已经把任务级上下文层实现出来。

当前 working set 具备这些特征：
- 有压缩与限长机制
- 有 priority reads
- 会按 doc 类型优先提取“决策 / 验证 / 约束”类信息
- 会从 docs 与 module cards 中提炼任务相关信息
- 不再是简单的原文拼接

这说明项目已经具备 docs / catalog / BRIEF 之外的任务级上下文层。

### 5. save correctness core 已经比较稳

`lib/memory_save.py` 当前已经形成了较明确的 correctness boundary：

- 只允许 `noop / create / append / merge / update`
- 非 `noop` 写入需要 evidence
- 会检查 source refs
- 会扫描 session working set 来源
- 明确阻止把 working set 原样写回 durable docs
- 保存成功后会自动重建 `BRIEF.md` 并执行 `catalog-repair`

这与“长期知识必须是提炼结果，而不是 session 内容搬运”的原则保持一致。

### 6. init/save 边界已经对齐

活跃文档已经统一为：
- **只有初始化阶段**允许 `/memory-hub:init` 直接生成初始 docs
- 初始化之后，长期知识更新统一走 `/memory-hub:save`

已对齐文档包括：
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`
- `.claude/commands/memory-hub/init.md`

### 7. 活跃路径中的旧入口噪音已大幅清理

本轮清理已移除活跃路径里的旧残留：
- 旧 MCP 入口
- 旧 repo-local skill 残留
- 旧 review / rollback / selftest 入口
- 会误导当前协作方式的旧测试文档

当前旧引用仅保留在 `.archive/**` 历史材料中。

### 8. 工程状态健康可验证

当前验证状态：
- 已将全局 Python 切换到 Homebrew Python 3.14.3
- 全局 `pytest` 已可用
- 项目测试通过：`170 passed`

---

## 还未完全到位的部分

### 1. 内容层还不够“决策导向”

当前框架已经对了，但 recall 的最终质量仍然取决于：
- docs 里是否真正沉淀了决策、约束、风险、验证重点
- module cards 是否真正具备导航价值

也就是说，当前更大的差距在“记忆内容密度”，不是命令面。

### 2. module cards 还需要继续做深

目前 recall planner 和 working set 已经能够消费 module cards，但如果 module cards 本身仍然偏浅，那么 recall 效果也会受限。

理想的 module card 应该稳定回答：
- 什么时候该读这个模块
- 推荐从哪个入口开始看
- 阅读顺序是什么
- 隐含约束是什么
- 主要风险是什么
- 验证重点是什么

### 3. recall-plan 当前仍偏启发式

当前 `lib/recall_planner.py` 的规划逻辑仍然主要依赖：
- 关键词
- token 命中
- bucket boost
- 结构化索引解析

这在当前阶段足够可用，但距离“稳定命中真正需要前置决策性上下文的任务”还有提升空间。

### 4. init 的深度记忆闭环还没有完全打透

`/memory-hub:init` 的目标方向已经正确：
- 不是总结代码结构
- 而是沉淀高价值背景、约束、风险、验证重点与模块阅读导航

但从工程成熟度来看，它仍然比较依赖执行者质量，还没有达到“稳定自动产出高质量初始记忆”的程度。

### 5. recall 效果的验收标准还不够强

当前 save 的 correctness 已经相对清晰，但 recall 的效果验收仍然不够系统。

简单说：
- save 更像“写入正确性”已形成体系
- recall 更像“方向正确，但效果验证还不够制度化”

---

## 路线一致性判断

### 一致点 1：Memory Hub 不是代码摘要库

当前设计已经把 `.memory/docs/` 固定为唯一正本，而 `BRIEF.md`、`catalog/`、`session/` 明确是派生产物。这与“决策性上下文前置层”的定位是一致的。

### 一致点 2：不是所有任务都要先读记忆

当前产品口径与 recall planner 都明确支持按任务选择 `skip / light / deep`，而不是强制全量 recall。

### 一致点 3：真正重视的是决策、约束、风险、验证重点

`lib/session_working_set.py` 中对 docs 的提取优先级，已经明显倾向于：
- 决策
- 验证
- 约束

这与核心思想一致。

### 一致点 4：host 只负责接线，correctness core 在 CLI

当前架构决策中已经明确：
- slash command / AGENTS / host 负责提醒与接线
- correctness core 在 `memory-hub save --file <save.json>`

这避免了把系统正确性完全依赖在宿主提示词上。

---

## 当前总体判断

如果压缩成一句话：

**Memory Hub 现在已经从“清理旧世界”进入到“新世界主干已成形”的阶段。**

更具体地说：
- 架构方向：对
- 主命令面：对
- correctness 边界：对
- session 层设计：对
- 活跃路径清洁度：明显改善
- 当前主要差距：不是方向错误，而是内容质量和 recall 命中质量还要继续做深

因此当前判断不是“偏航”，而是：

**路线一致，而且比之前更一致了；下一阶段的重点不是换方向，而是沿现有方向继续补深度。**

---

## 按优先级的下一步建议

### P0：当前最应该做的

#### P0-1. 把 module cards 做成真正可用的阅读导航卡

优先补的不是数量，而是质量。重点补齐：
- 何时阅读
- 推荐入口
- 阅读顺序
- 隐含约束
- 主要风险
- 验证重点

原因：现有 recall-plan 和 working-set 已经具备消费这些信息的能力，现在最缺的是高质量导航内容。

#### P0-2. 对现有 durable docs 做一次“决策性内容密度”体检

核心检查标准：
- 如果只是代码事实复述，则不算高价值记忆
- 如果会改变后续阅读、修改、验证动作，则算高价值记忆

这一步会直接决定 recall 是否真正有价值。

#### P0-3. 给 recall 链路补任务效果验收

建议挑几类代表任务做场景化验收，例如：
- 理解某模块
- 修改跨模块逻辑
- 验证一条规则是否仍成立
- 决定是否 update 一条长期知识

关注点：
- recall-plan 给出的深度是否合理
- priority reads 是否像真正该先看的来源
- working set 是否暴露了关键约束 / 风险 / 验证重点

### P1：下一阶段增强

#### P1-1. 提升 recall-plan 的命中质量

在不推翻现有架构前提下，增强：
- 任务语义分类
- module/doc 匹配质量
- 高隐含约束任务识别能力
- 局部任务的 skip/light 判断准确率

#### P1-2. 强化 init 的高价值产出约束

让 init 产出的初始 docs 更显式回答：
- 为什么这条信息不是代码直接可见的
- 先看哪个入口最有效
- 哪个风险最容易误读
- 哪个验证点最容易被漏掉

#### P1-3. 为浅层 module cards / docs 增加质量检查机制

目标不是检查“有没有文件”，而是检查“内容是否真的有导航价值”。

### P2：后续优化

#### P2-1. 继续做 Claude Code-only 体验优化

如果最终完全收口到 Claude Code-only，可继续优化：
- command 文档
- hooks 提醒
- recall 触发体验
- 候选知识捕获体验

#### P2-2. 继续瘦身历史包袱

后续可继续整理：
- 历史计划文档标注
- 当前方案与历史方案分层
- 归档材料清晰化

但这不应优先于 recall 质量工作。

#### P2-3. 追加 recall 质量分析工具

包括更细的评分、体检、freshness/usefulness 检查等。这些是后续增强项，不是当前最紧迫事项。

---

## 行动建议（简版）

当前建议不是换方向，而是：

1. 沿现有 recall-first 主架构继续推进
2. 优先补强 module cards 与 durable docs 的“决策性内容密度”
3. 为 recall 链路建立更清晰的效果验收
4. 再在此基础上继续增强 planner 命中质量与 init 深度闭环

换句话说：

**主架构已经站稳，下一步重点是把“内容质量”与“命中质量”做深。**
