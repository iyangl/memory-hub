# Memory Hub v3 Redesign Handoff

日期：2026-03-16
目的：归档 v2 → v3 架构转向的决策过程、核心结论和下一步计划。

## 1. 转向决策

截至 2026-03-16，Memory Hub 决定从 v2 的"规则驱动"架构转向 v3 的"Skill 驱动"架构。

触发这个决策的核心讨论链条：

1. v2 主线（Phase 2A-2F）已全部完成，下一阶段原计划是 decision discovery lane 和 end-of-task probe
2. 重新审视时发现：**LLM 大概率无法可靠遵守复杂规则**，而 v2 的大量复杂度正是在"控制 LLM 怎么用记忆系统"
3. Claude Code 有 hooks 可以强制执行，但 Codex 没有，两个平台无法用同一套方案
4. 随着上下文窗口越来越大（200k-1M），LLM 不需要每次都通过 MCP 查询记忆，可以直接在上下文中"拥有"这些知识
5. 参考 ccg-workflow 的设计后确认：**用固定 workflow 模板替代复杂规则**是更可靠的方案
6. 最终结论：放权给 LLM，只在两个节点（会话开始/结束）通过用户显式调用 skill 执行确定性 workflow

## 2. v2 → v3 变化总结

### 2.1 删除的

| 组件 | v2 | v3 |
|------|----|----|
| MCP server (7 tools) | 核心依赖 | 移除 |
| durable store (SQLite) | 核心存储 | 移除 |
| proposal/review 状态机 | 核心流程 | 移除 |
| CLAUDE.md 流程规则 (300+ 行) | 核心控制 | 大幅精简或移除 |
| 三路由 (docs-only/durable-only/dual-write) | 核心路由 | 移除，统一为 docs |
| boot-first 纪律 | 硬约束 | 不需要 |
| write guard | 硬约束 | 不需要 |
| session-extract | Phase 2F 交付 | 被 /save 替代 |
| discovery lane | Phase 1 已实现 | 归档，后续可能复用思路 |
| ~25 个 Python 模块 | 活跃代码 | 归档 |

### 2.2 保留的

| 组件 | 说明 |
|------|------|
| `.memory/docs/` | 项目知识主文档（唯一正本），原样保留 |
| `.memory/catalog/` | 派生索引文件，原样保留 |
| docs 内容 | architect/, dev/, pm/, qa/ 下的已有知识全部保留 |
| ~10 个基础 Python 模块 | paths, envelope, catalog_read/repair, memory_read/search/init, cli, utils |

### 2.3 新增的

| 组件 | 说明 |
|------|------|
| `.memory/BRIEF.md` | docs 的派生摘要，/recall 的主数据源，可从 docs 重建 |
| `/init` command | 固定 workflow：扫描项目 → 生成初始 docs → 构建 catalog → 生成 BRIEF.md |
| `/recall` command | 固定 workflow：读 BRIEF.md → 注入上下文（BRIEF 缺失时退化为读 docs） |
| `/save` command | 固定 workflow：提炼知识 → 去重检查 → 写入 docs → 重建 BRIEF.md → 修 catalog |

## 3. 已冻结的新设计前提

1. 这仍然是项目级系统
2. docs/ 是唯一正本；BRIEF.md 和 catalog/ 都是派生产物，可从 docs 重建
3. 用户通过显式 slash command 控制记忆的加载和保存
4. 工作过程中信任 LLM 的上下文能力，不干预
5. LLM 可以在工作中自主保存知识（Layer 2），但不强依赖
6. 不使用 MCP，所有操作通过 skill workflow 模板 + 原生工具完成
7. 跨平台一致：Claude Code 和 Codex 使用相同的 skill 模板

## 4. 存储一致性模型

v2 的核心复杂度来自 docs 和 durable store 的双正本一致性问题。

v3 通过"单一正本 + 派生视图"彻底消除这个问题：

```
docs/      = 唯一正本（所有知识在这里）
BRIEF.md   = 派生摘要（从 docs 生成，brief-repair 可重建）
catalog/   = 派生索引（从 docs 生成，catalog-repair 可重建）
```

BRIEF.md 不包含 docs 中没有的信息。如果 BRIEF.md 与 docs 不一致，以 docs 为准，重建 BRIEF.md 即可。

## 5. 知识判断框架

v3 把"什么值得保存"简化为：

**后悔测试**（借鉴 Nocturne）：这次会话结束后，如果没记下来会后悔吗？
- 决策结论、项目约束、架构选型理由、踩过的坑

**反面排除**：
- 代码本身能表达的、临时调试过程、未形成结论的讨论、通用知识

**分类**：只需判断放 architect / dev / pm / qa 哪个目录

**去重**（借鉴 Memory Palace）：写入前搜索已有 docs，判断新增 vs 更新

**Disclosure 标签**（借鉴 Nocturne）：每条知识附"何时需要"的场景描述

## 5. 当前仓库基线

### 5.1 关键参考文件

- 重构方案：`.archive/plans/2026-03-16-memory-hub-v3-skill-driven-redesign.md`
- v2 完成态：`.archive/handoffs/2026-03-11-memory-hub-v2-completion-handoff.md`
- v2 roadmap：`.archive/plans/2026-03-11-memory-hub-v2-roadmap.md`
- 参考项目：`.refrence/`（ccg-workflow, openclaw-memory-fusion, Memory-Palace, nocturne_memory）
- 已有项目知识：`.memory/docs/` 全部内容

### 5.2 参考项目借鉴清单

| 来源 | 借鉴 | 应用 |
|------|------|------|
| CCG-Workflow | 固定 workflow 模板 | 三个 command 都是确定性脚本 |
| CCG-Workflow | 用户显式调用 | 不依赖 LLM 自觉 |
| OpenClaw | MEMORY.md 热缓存 | BRIEF.md 派生摘要 |
| OpenClaw | 写入时提炼结论 | /save 的核心动作 |
| Nocturne | 后悔测试 | /save 核心判断标准 |
| Nocturne | Disclosure 字段 | 每条知识附适用场景标签 |
| Nocturne | 优先级分层 | /recall 按优先级渐进加载 |
| Memory Palace | Write Guard 去重 | /save 写入前搜索，判断新增 vs 更新 |
| Memory Palace | Compact 紧凑化 | BRIEF.md 是 docs 的紧凑视图 |

### 5.3 测试基线

当前 95 个测试中，与 durable/review/MCP 相关的测试在 v3 中将被移除或归档。
保留的基础模块测试（catalog, memory read/search/init）应继续通过。

## 6. 下一步计划

按优先级：

### P0：设计三个 workflow 模板

1. `/recall` — 读 BRIEF.md 注入上下文（BRIEF 缺失时退化读 docs）
2. `/save` — 后悔测试 → 去重检查 → 写 docs → 重建 BRIEF.md → 修 catalog
3. `/init` — 扫描项目 → 生成初始 docs → 构建 catalog → 生成 BRIEF.md

### P1：实施精简

1. 归档不再需要的模块到 `.archive/`
2. 精简 CLAUDE.md（从 300 行降到最小）
3. 移除 MCP 配置（`.mcp.json`）
4. 更新 README.md

### P2：验证

1. 在 Claude Code 中测试三个 command 的完整流程
2. 在 Codex 中测试相同流程
3. 真实项目使用观察

## 7. 当前不再继续的方向

以下 v2 后续候选项不再作为独立方向推进：

- decision discovery lane — 理念可能复用到 /save 的判断框架中，但不再作为独立 lane
- end-of-task probe — 被 /save 的显式调用替代
- 新项目 bootstrap — 被 /init 替代
- Claude 增强交互 — 不再需要，新架构不依赖 LLM 规则遵从

## 8. 设计哲学转变

| | v2 | v3 |
|---|---|---|
| 核心假设 | LLM 需要被规则约束 | LLM 可以被信任 |
| 控制方式 | 规则 + MCP + review 状态机 | 固定 workflow 模板 + 用户显式调用 |
| 复杂度来源 | 控制 LLM 行为 | workflow 模板设计 |
| 失败模式 | LLM 不遵守规则 → 行为不可预期 | LLM 不自主 save → /save 兜底 |
| 跨平台 | 依赖 hooks（CC）或规则（Codex） | 统一 skill 模板 |
