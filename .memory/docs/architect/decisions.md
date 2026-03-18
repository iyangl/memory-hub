# 设计决策日志

## v3 架构决策 — 2026-03-16 ~ 2026-03-18

### 决策 v3-1：从规则驱动转向 Skill 驱动

背景：v2 的 CLAUDE.md 300+ 行流程规则、7 个 MCP tool + 复杂路由、review 状态机，LLM 大概率无法可靠遵守。平台差异（Claude Code 有 hooks，Codex 没有）加剧了问题。

选择：用固定 workflow 模板（slash command）驱动 LLM 执行，替代用规则约束 LLM 行为。三个 command：`/init`、`/recall`、`/save`。

影响：移除 MCP server、durable store、proposal/review 状态机、discovery lane。CLAUDE.md 从 ~300 行精简到 ~65 行。

### 决策 v3-2：移除 MCP server

背景：MCP tool 能做的（读/写/搜索文件），skill 模板通过 Read/Write/Edit/Bash 全能做。MCP 的唯一"优势"是格式约束，但模板里写清楚格式示例效果相同。

选择：整体移除 `lib/mcp_server.py`、`lib/mcp_toolspecs.py`、`lib/durable_mcp_tools.py` 及所有 7 个 MCP tool。

### 决策 v3-3：移除 durable store

背景：durable store（SQLite + proposal/review/rollback）增加了大量复杂度，但实际有价值的知识已在 docs/ 中。

选择：直接归档 `_store/`（D5），不导出到 docs。docs/ 是唯一正本。

### 决策 v3-4：BRIEF.md 机械拼接

背景：需要一个轻量的项目知识摘要供 `/recall` 注入上下文。

选择：从 docs/ 机械式拼接（D7）——按 bucket 固定序（architect -> dev -> pm -> qa），每个 doc 提取首段摘要（截断 3 行），总长度目标 ~200 行。BRIEF.md 跟踪 git（D3），丢失时可从 docs 重建。

### 决策 v3-5：inbox 隔离层

背景：LLM 工作过程中可能产生新知识，需要一个低门槛的暂存区。

选择：`.memory/inbox/` 作为 Layer 2 临时写入区（D4/D6）。纯 markdown，无 frontmatter，命名 `{ISO时间戳}_{短名}.md`，不跟踪 git，`/save` 合并后删除。

### 决策 v3-6：硬编码四类 bucket

背景：v2 实际使用验证四类（architect/dev/pm/qa）够用。

选择：Phase 1 硬编码四类（D2），不引入动态 bucket。需要扩展时在 bucket 内增加文件。

### 决策 v3-7：slash command 载体

背景：需要选择 workflow 模板的技术载体。

选择：`.claude/commands/memory-hub/` 目录（D8a），Claude Code 原生支持，Codex 通过 AGENTS.md 引用同一份模板。移除 `skills/` 目录（D8b），维护操作通过 CLI 直接调用。

---

## v1-v2 历史决策（已归档）

以下决策属于 v1-v2 架构，v3 中相关组件已移除。保留作为演进背景参考。

### 决策 1 — 2026-02-26
AI 直接写文件 + `memory-hub index` 只管索引注册。移除 `memory-hub write` 命令。

### 决策 2 — 2026-03-10
先冻结 v1 外部契约（不变量、URI 规则、状态机），再按契约实现。

### 决策 3 — 2026-03-10
create proposal 在创建时就生成 `target_uri`；update proposal 保存物化后的候选 `content`。

### 决策 4 — 2026-03-10
最小无依赖 stdio JSON-RPC MCP server（v3 已移除 MCP）。

### 决策 5 — 2026-03-10
`.memory/` 负责项目知识，`.memoryhub/` 负责 durable memory（v3 已统一为纯 docs）。

### 决策 6 — 2026-03-10
规则识别语境，workflow/skill 决定是否调用工具（v3 延续此思路，进一步简化为 3 command）。

### 决策 7 — 2026-03-10
boot-first 硬约束 + proposal 创建后自动 review show + 宿主能力分流（v3 已移除 durable flow）。

### 决策 8 — 2026-03-11
durable-memory workflow 并入 project-memory，对外只保留两个 skill（v3 进一步简化为 0 skill + 3 command）。
