# Recall-First 审查报告

> 日期：2026-03-29
> 范围：设计是否背离初衷、代码是否符合设计、实现质量审查
> 依据：人工审查 + Codex reviewer 交叉审查（Gemini reviewer 本次因本地运行环境异常未返回有效结果）

---

## 1. 结论摘要

整体结论：**没有完全背离初衷，但已经出现明显漂移。**

当前状态更准确的描述是：

- recall-first 的外壳已经落地
- 主链已经能跑通
- 关键 correctness core 只落了一半
- 因此不能判定为“实现已经严格符合设计契约”

一句话总结：**方向正确，主链成型，契约未闭环。**

---

## 2. 审查基线

本次审查对照以下文档与实现：

### 设计基线
- `.claude/plan/recall-first-redesign-plan.md`
- `.claude/plan/recall-first-contract.md`
- `.claude/plan/recall-first-implementation-checklist.md`

### 关键实现
- `lib/recall_planner.py`
- `lib/session_working_set.py`
- `lib/scan_modules.py`
- `lib/catalog_update.py`
- `lib/brief.py`
- `lib/memory_init.py`
- `lib/cli.py`

### 命令模板
- `.claude/commands/memory-hub/init.md`
- `.claude/commands/memory-hub/recall.md`
- `.claude/commands/memory-hub/save.md`

### 派生产物
- `.memory/BRIEF.md`
- `.memory/catalog/topics.md`
- `.memory/catalog/modules/*.md`

---

## 3. 已对齐设计的部分

以下内容已经明显朝 recall-first 方向对齐：

### 3.1 recall-first 主结构已落地
- `recall-plan` 已存在并进入 CLI 分发链
- `working-set` 已存在并进入 CLI 分发链
- `.memory/session/` 已落地为会话级派生产物目录

### 3.2 module card 已从结构摘要转向导航卡
当前 `catalog_update` 输出的 module card 已包含：
- 何时阅读
- 推荐入口
- 推荐阅读顺序
- 隐含约束
- 主要风险
- 验证重点
- 代表文件
- 关联记忆

这与设计中的“模块阅读导航”方向一致。

### 3.3 command 模板已围绕 recall-first 重写
- `init` 已转向导航产物生成
- `recall` 已引入 `recall-plan` / `working-set`
- `save` 已写出 `noop / create / append / merge / update` 的契约语义

### 3.4 docs / brief / catalog / session 的边界更清晰
当前仓库已经比旧 v3 阶段更清楚地区分：
- docs：唯一正本
- BRIEF：boot summary
- catalog：导航派生产物
- session：会话级派生产物

---

## 4. 关键偏差与设计漂移

## Critical 1：`/save` 仍停留在模板层，不是代码级 correctness core

这是当前最大偏差。

### 设计要求
设计与 contract 明确要求：
- `noop / create / append / merge / update`
- 非 `noop` 前必须先 `search`
- 非 `noop` 前必须先 `read`
- working set 不可原样落长期 docs
- save 逻辑应由核心实现保证，而不是只靠宿主模板

### 当前实现现状
- `lib/cli.py` 中没有 `save` 核心命令实现
- 这些规则目前只存在于 `.claude/commands/memory-hub/save.md`

### 风险
这意味着：
- correctness 仍依赖命令模板执行者是否遵守流程
- `Read Before Write` 没有代码强约束
- `noop/create/append/merge/update` 没有统一可测试实现
- “Host Adapter 不是 Correctness Core” 这一原则尚未真正落地

### 结论
这是最核心的 contract 未闭环点。

---

## Critical 2：`recall-plan` 没有真正把 BRIEF / topics 作为 planner 输入

### 设计要求
设计要求 `recall-plan` 输入应包括：
- BRIEF
- topics
- module cards

### 当前实现现状
`lib/recall_planner.py` 当前对 BRIEF / topics / modules 做的是：
- 存在性检查
- 真正匹配仍主要依赖 docs 全文和 module card 全文的关键词命中

### 问题
这导致：
- `BRIEF.md` 和 `topics.md` 更像 guard，而不是 planner 的真实输入
- planner 没有真正走“boot summary -> 定位 -> 再决定 recall 深度”的协议

### 结论
这与 contract 中的 Bootstrap Recall Protocol 存在明显偏差。

---

## Critical 3：`search_first` 与 recall 深度判定顺序不符合协议

### 设计协议
设计规定的顺序是：
1. 读 BRIEF
2. 若对象不明确，先 search
3. 再判定 `skip | light | deep`
4. deep 时构建 working set

### 当前实现现状
在 `lib/recall_planner.py` 中：
- 当 `search_first = true` 时
- 直接把 `recall_level` 固定为 `light`

### 问题
这等于把：
- “先搜索，再决定深度”
实现成了：
- “需要搜索时默认 light”

### 结论
这是协议顺序层面的偏差，不只是算法细节问题。

---

## Warning 1：`working-set` 更像来源拼接，而不是任务级压缩上下文

### 设计要求
working set 应具备：
- 压缩
- 去重
- 限长
- 偏向决策 / 约束 / 风险 / 验证
- 保留 sources / evidence gaps / selected_because

### 当前实现现状
`lib/session_working_set.py` 目前主要行为是：
- 按推荐顺序读取 doc / module
- 生成 items
- 保留 sources / evidence gaps
- 汇总一个 summary

### 问题
缺少：
- 去重
- 预算控制
- 风险 / 约束 / 验证重点的结构化压缩
- module item 只抽取入口点，未把 `主要风险 / 隐含约束 / 验证重点` 带入结果

### 结论
working set 已存在，但还不够“任务可直接消费”。

---

## Warning 2：`scan-modules` 导航语义仍偏模板句

### 设计要求
init / scan 产物应尽量基于实际读代码得到：
- 导航
- 隐含约束
- 风险
- 验证重点

### 当前实现现状
`lib/scan_modules.py` 中这些字段主要来自通用规则函数：
- `_guess_read_when`
- `_guess_constraints`
- `_guess_risks`
- `_guess_verification_focus`

### 问题
当前 module cards 虽然形式正确，但很多内容仍是泛化模板，而不是证据驱动的项目特异性结论。

### 结论
导航卡已经成型，但语义质量还未完全达到设计期待。

---

## Warning 3：`BRIEF.md` 仍受旧 v3 叙事污染

### 设计要求
BRIEF 应是 recall-first base brief / boot summary，优先抽取高价值决策、约束、风险、验证重点。

### 当前实现现状
`lib/brief.py` 已经开始做优先抽取，不再是纯首段拼接。
但当前 `.memory/BRIEF.md` 仍然把旧 v3 决策与历史叙事放在靠前位置。

### 结论
问题不完全是 brief 生成算法，而是 Phase 0 中要求更新的 docs 决策语义尚未完全重写成 recall-first 叙事。

---

## Warning 4：`init` 模板与 CLI 实际行为仍有语义分叉

### 当前表现
模板写的是：
- `.memory/` 已存在时，转增量更新模式

但 `lib/memory_init.py` 的真实行为是：
- 已存在则直接返回 `ALREADY_INITIALIZED`

### 影响
这会导致：
- 用户心智与 CLI 行为不一致
- 模板工作流和直接调用 CLI 的语义不完全对齐

---

## Warning 5：端到端测试绕开了关键 contract 路径

### 当前表现
- `tests/test_memory_flow.py` 手工构造 `modules.json`，没有真的执行 `scan-modules`
- 测试里会在 planner 没给 deep 时手工改为 deep
- `tests/test_recall_planner.py` 对高风险任务的断言较宽松

### 影响
测试证明了链路可运行，但没有严格证明：
- planner 决策顺序正确
- deep recall 触发正确
- search-before-guess 被真实执行

### 结论
测试数量足够，但 contract-critical 覆盖还不够硬。

---

## 5. 代码实现质量评价

### 优点
- 模块拆分清楚
- 结构简洁
- CLI 扩展方式统一
- 输出 envelope 风格一致
- Windows 实际运行链路中的解码 / out-file 问题已补强

### 不足
- planner 语义仍偏关键词启发式
- working set 压缩力度不足
- save correctness 缺位
- 模板与核心实现的职责分界尚未最终收口

---

## 6. 最值得先修的 3 个点

### P1：实现代码级 `/save` core
需要下沉到代码：
- `noop / create / append / merge / update`
- mandatory search
- mandatory read
- durable write decision
- BRIEF / catalog 重建

这是从“模板式 recall-first”走向“契约式 recall-first”的关键一步。

### P2：重构 `recall_planner` 的输入和决策顺序
目标：
- 真正消费 `BRIEF.md`
- 真正消费 `topics.md`
- 把“定位目标”和“决定 recall 深度”拆成两步
- `search_first` 不再直接导向 `light`

### P3：收紧 `working-set` 与端到端测试
目标：
- 增加去重 / 限长 /压缩
- 把风险 / 约束 / 验证重点带进 module items
- 让真实链路测试不再靠手改 planner 输出兜底

---

## 7. 最终判断

如果问题是：

> recall-first 是否已经成功落地？

回答是：

**已经落地了 60%~70%，但关键 contract enforcement 还没闭环。**

更准确地说：
- 方向正确
- 主链已成型
- 外壳已经像 recall-first
- 但 `/save` 和 planner 协议仍是当前最大的设计漂移点

---

## 8. 后续建议

建议按以下顺序继续：

1. 先补 `/save` core
2. 再重构 `recall_planner`
3. 再增强 `working-set`
4. 最后收紧 E2E 测试与派生产物质量门

---

## 9. 附注

### 外部审查情况
- Codex reviewer：已完成并纳入结论
- Gemini reviewer：本次因本地 CLI 运行环境异常失败，未形成有效结论

### 当前结论可信度
- 对“是否完全符合设计契约”的结论：高
- 对“是否存在严重安全漏洞”的结论：低相关，本次重点不是安全面
- 对“下一步修复优先级”的结论：高
