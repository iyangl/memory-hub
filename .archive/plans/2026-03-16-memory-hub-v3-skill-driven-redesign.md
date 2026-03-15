# Memory Hub v3 Skill-Driven Redesign

日期：2026-03-16
状态：已确认方向，待详细设计

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

### 3.1 保留

- `.memory/docs/` — 纯 markdown，按领域分目录，是 /recall 的数据源
- `.memory/catalog/` — 索引文件，/recall 用它决定加载什么

### 3.2 简化

目录结构保持现有：

```
.memory/docs/
  architect/   ← 架构决策、技术选型
  dev/         ← 开发约定、编码规范
  pm/          ← 产品决策、需求结论
  qa/          ← 测试策略、质量约定
```

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

### 6.1 什么值得保存（正面清单）

核心判断：**新会话没有这条信息，会走弯路吗？**

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
1. 值不值得存 — 用正面/反面清单
2. 放哪个目录 — architect / dev / pm / qa 四选一

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
