# Memory Hub v3 Skill-Driven Redesign

日期：2026-03-16
状态：已确认方向，含参考项目借鉴与 BRIEF.md 设计

## 1. 重构动机

### 1.1 核心矛盾

v2 的大量复杂度花在了"控制 LLM 怎么用记忆系统"上：
- CLAUDE.md 300+ 行流程规则（任务分类、检查点、禁止清单）
- 7 个 MCP tool + 复杂路由（docs-only / durable-only / dual-write）
- review 状态机（durable proposal + docs change review）
- boot-first 纪律、write guard、catalog 维护规则

但 LLM 大概率无法可靠遵守这些规则。v2 completion handoff 已经承认：

> 允许存在少量"顺序不够理想但结果正确"的可接受偏差
> 不再建议为了让普通自然语言请求 100% 严格按固定顺序执行，而继续堆更重的全局规则

### 1.2 平台差异加剧问题

- Claude Code 有 hooks 机制，可以在关键节点强制执行操作
- Codex 没有 hooks，所有流程控制只能靠规则文本

继续用规则约束 LLM 的路线无法跨平台统一。

### 1.3 上下文窗口增长改变了前提

200k、1M 的上下文下：
- 项目知识可以直接作为上下文的一部分存在
- LLM 不需要每次都通过 MCP 工具"查询"记忆
- 真正需要工具调用的场景很少

## 2. 新架构：Skill-Driven

### 2.1 核心思路

从"用规则约束 LLM 行为"转向"用固定 workflow 模板驱动 LLM 执行"。

参考 ccg-workflow 的设计：
- 每个 slash command 是一个完整的 workflow 脚本
- LLM 不需要理解规则，只需要跟着模板步骤执行
- 用户显式控制流程切换
- 状态通过文件传递

### 2.2 三个 Command

```
/init    — 首次扫描项目，生成初始记忆
/recall  — 加载记忆到上下文
/save    — 提炼并持久化知识
```

### 2.3 运行模型

```
┌─────────────────────────────────────────────┐
│              会话 / 需求生命周期               │
│                                             │
│  ┌──────────┐                 ┌──────────┐  │
│  │ /recall  │    LLM 自由     │  /save   │  │
│  │ 显式调用  │ ──工作区间──▶   │ 显式调用  │  │
│  │ 固定流程  │   信任上下文    │ 固定流程  │  │
│  └──────────┘                 └──────────┘  │
│   读取+注入                     提炼+持久化   │
│   确定性workflow                确定性workflow │
└─────────────────────────────────────────────┘
```

### 2.4 三层信任模型

- Layer 1: `/recall` — 用户显式调用，100% 可靠
- Layer 2: LLM 自主 save — 最佳努力，遵守就赚到，不遵守不影响
- Layer 3: `/save` — 用户显式调用，100% 可靠

## 3. 存储设计

### 3.1 单一正本 + 两个派生视图

```
.memory/
  BRIEF.md      ← 派生摘要（/recall 的主要数据源）
  docs/         ← 唯一正本（所有知识在这里）
    architect/  ← 架构决策、技术选型
    dev/        ← 开发约定、编码规范
    pm/         ← 产品决策、需求结论
    qa/         ← 测试策略、质量约定
  catalog/      ← 派生索引（定位用）
    topics.md
    modules/
```

核心约束：**docs/ 是唯一正本，BRIEF.md 和 catalog/ 都是派生产物。**

- BRIEF.md 可以从 docs 重建（brief-repair）
- catalog 可以从 docs 重建（catalog-repair）
- 不存在"两个正本冲突"的可能

### 3.2 BRIEF.md 设计

BRIEF.md 是 `/recall` 的主要数据源，是 docs 的精简派生摘要。

设计约束：
- 所有信息必须也存在于 docs/ 中，BRIEF.md 不包含独有数据
- `/save` 先写 docs，再从 docs 重新生成 BRIEF.md
- BRIEF.md 丢失时 `/recall` 退化为直接读 docs，下次 `/save` 再生成
- 建议控制在 ~200 行以内

为什么需要 BRIEF.md 而不是每次直接读 docs：

1. **筛选质量更高** — 摘要在 `/save` 时生成（LLM 有完整任务上下文），比 `/recall` 时猜测哪些 docs 相关更准
2. **确定性** — 每次 `/recall` 读到一样的内容，不会因为 LLM 的选择差异产生不同结果
3. **Token 效率** — 500-1000 tokens vs 完整 docs 5000-10000 tokens
4. **优雅降级** — BRIEF.md 不存在时系统仍工作，只是 `/recall` 变慢

### 3.3 移除

- `.memory/_store/memory.db` — durable store 整套移除
- `.memory/_store/projections/` — boot/search 投影移除
- `.memory/manifest.json` — 简化后不需要

### 3.4 不再需要的概念

- durable-only / docs-only / dual-write 三路由
- durable proposal / review 状态机
- boot projection / search projection
- rollback 机制

## 4. MCP — 移除

MCP server 整个移除。原因：

- MCP tool 能做的（读/写/搜索文件），skill 模板通过 Read/Write/Edit/Bash 全能做
- MCP 的唯一"优势"是格式约束，但 skill 模板里写清楚格式示例效果相同
- 少维护一个 stdio server、少一套 tool schema、少一个运行时依赖

## 5. 代码保留与删除

### 5.1 保留（~10 模块）

| 模块 | 理由 |
|------|------|
| `paths.py` | 路径管理 |
| `envelope.py` | CLI 响应协议 |
| `catalog_read.py` | /recall 读索引 |
| `catalog_repair.py` | /save 后修索引 |
| `memory_read.py` | 读 doc 文件 |
| `memory_search.py` | 搜索 docs |
| `memory_init.py` | init 基础 |
| `cli.py` | CLI 调度（精简） |
| `utils.py` | 通用工具 |

### 5.2 删除/归档（~25 模块）

| 类别 | 模块 |
|------|------|
| durable 引擎 | durable_db, durable_store, durable_repo, durable_uri, durable_guard, durable_errors, durable_proposal_utils, durable_review, durable_mcp_tools |
| review 状态机 | project_review, docs_review |
| MCP server | mcp_server, mcp_toolspecs |
| 统一 workflow 路由 | project_memory_view, project_memory_write, project_memory_projection |
| session-extract | session_extract, session_extract_cli |
| discovery lane | decision_discovery, discovery_cli, discovery_context, discovery_signals |
| review/rollback CLI | review_cli, rollback_cli |

### 5.3 新增

| 产物 | 说明 |
|------|------|
| `commands/init.md` | /init workflow 模板 |
| `commands/recall.md` | /recall workflow 模板 |
| `commands/save.md` | /save workflow 模板 |

## 6. 知识判断框架

### 6.1 什么值得保存 — 后悔测试（借鉴 Nocturne）

核心判断：**这次会话结束后，如果没记下来会后悔吗？**

等价表述：**新会话没有这条信息，会走弯路吗？**

具体包括：
- 决策结论（选了什么、为什么选）
- 项目约束（必须做什么、不能做什么）
- 架构选型理由（技术栈、设计模式选择）
- 踩过的坑（排障结论、绕过方案）

### 6.2 什么不值得保存（反面清单）

- 代码本身已经表达的事实
- 临时调试过程
- 还没形成结论的讨论
- 通用知识（非项目特有）

### 6.3 分类简化

LLM 在 /save 时只需判断两件事：
1. 值不值得存 — 用后悔测试
2. 放哪个目录 — architect / dev / pm / qa 四选一

### 6.4 写入前去重（借鉴 Memory Palace）

`/save` 写入前搜索已有 docs，判断是新增还是更新已有文档：
- 搜索命中近似内容 → 更新已有文档（合并/追加）
- 未命中 → 新增文档
- 完全重复 → 跳过

替代 v2 的 proposal 状态机，只是一个搜索+判断步骤。

### 6.5 Disclosure 标签（借鉴 Nocturne）

每条知识附"何时需要这条信息"的场景描述：
- 好例子："当修改 MCP 相关代码时"、"当讨论部署策略时"
- 坏例子："重要的"、"记住"

`/recall` 可据此按当前任务上下文选择性加载。

## 7. 与 v2 的关系

- v2 的存储格式（`.memory/docs/` + `.memory/catalog/`）完整继承
- v2 的流程控制层（MCP + 规则 + review 状态机）全部替换
- v2 积累的项目知识内容原样保留
- 本质是"删掉控制 LLM 行为的复杂度，换成固定 workflow 模板"

## 8. 跨平台一致性

| 平台 | /init | /recall | /save | LLM 自主 save |
|------|-------|---------|-------|---------------|
| Claude Code | slash command | slash command | slash command | 直接 Edit 文件 |
| Codex | slash command | slash command | slash command | 直接 Edit 文件 |

不依赖 hooks、不依赖 MCP、不依赖规则遵从。两个平台完全一致。

## 9. 参考项目借鉴

### 9.1 CCG-Workflow — 架构模式

| 借鉴点 | 应用 |
|--------|------|
| 固定 workflow 模板替代规则 | 三个 command 都是确定性脚本 |
| 用户显式调用控制流程 | 不依赖 LLM 自觉 |
| 状态通过文件传递 | `.memory/` 就是状态文件 |
| 模板详尽、规则极少 | CLAUDE.md 大幅精简 |

### 9.2 OpenClaw Memory Fusion — 存储与分层

| 借鉴点 | 应用 |
|--------|------|
| MEMORY.md 热缓存（~200 行） | BRIEF.md 派生摘要 |
| 三层记忆分级（hot/warm/deep） | BRIEF(hot) → docs(warm) → catalog(deep) |
| 滚动"近期更新"区 | `/save` 可维护 BRIEF.md 中的近期变更区 |
| 写入时提炼结论，不存原文 | `/save` 的核心动作 |

### 9.3 Nocturne Memory — 判断与标注

| 借鉴点 | 应用 |
|--------|------|
| 后悔测试 | `/save` 核心判断标准 |
| Disclosure 字段（何时回忆） | 每条知识附适用场景标签 |
| 优先级分层 (P0/P1/P2) | `/recall` 按优先级渐进加载 |
| 必须先读再写 | `/save` 写入前搜索已有内容 |

### 9.4 Memory Palace — 写入防护

| 借鉴点 | 应用 |
|--------|------|
| Write Guard 去重 | `/save` 写入前搜索，判断新增 vs 更新 |
| Compact 紧凑化 | `/save` 提炼结论，BRIEF.md 是 docs 的紧凑视图 |
| 优雅降级 | BRIEF.md 丢失时退化到直接读 docs |

### 9.5 明确不借鉴的部分

| 来源 | 不借鉴 | 原因 |
|------|--------|------|
| Memory Palace | 9 个 MCP tool、vitality 衰减、FastAPI server | 过重，v3 去 MCP |
| OpenClaw | 三层 cron 调度、Telegram 通知、QMD 索引 | 运行时模型不同，v3 无 cron |
| Nocturne | 图数据库、UUID node 体系、changeset 快照 | 过重，v3 用纯文件 |
| CCG | 多模型协作编排 | 不相关，v3 只做记忆 |
