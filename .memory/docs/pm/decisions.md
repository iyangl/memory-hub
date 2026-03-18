# 需求结论与产品决策

## v3 产品决策 — 2026-03-16 ~ 2026-03-18

### 结论 v3-1：Skill-Driven 架构替代规则驱动

背景：v2 的大量复杂度花在"控制 LLM 怎么用记忆系统"上，但 LLM 大概率无法可靠遵守 300+ 行流程规则。上下文窗口增长（200k+）改变了前提——项目知识可以直接作为上下文存在。

结论：
- 从"用规则约束 LLM 行为"转向"用固定 workflow 模板驱动 LLM 执行"
- 三个 command：/init（首次扫描）、/recall（加载记忆）、/save（保存记忆）
- 用户显式控制流程切换，不依赖 LLM 自觉

### 结论 v3-2：三层信任模型

背景：需要平衡确定性和灵活性。

结论：
- Layer 1（/recall）：用户显式调用，100% 可靠
- Layer 2（LLM 自主写 inbox）：最佳努力，遵守就赚到，不遵守不影响
- Layer 3（/save）：用户显式调用，确定性入口 + LLM 辅助执行

### 结论 v3-3：移除全部 v2 复杂度

背景：MCP server、durable store、proposal/review 状态机、discovery lane、session-extract 增加了大量维护成本，但实际使用频率低。

结论：
- MCP server（7 个 tool）整体移除
- durable store（SQLite + proposal/review/rollback）整体移除
- discovery lane 移除
- session-extract 移除
- 归档到 .archive/，保留 git history 可追溯

### 结论 v3-4：docs/ 是唯一正本

背景：v2 中 docs lane 和 durable store 双正本带来"该写哪里"的认知负担。

结论：
- docs/ 固定为唯一正本
- BRIEF.md 和 catalog/ 都是派生产物，可从 docs 重建
- 不存在"两个正本冲突"的可能

### 结论 v3-5：跨平台一致性

背景：Claude Code 和 Codex 的能力差异不应导致行为差异。

结论：
- 不依赖 hooks、不依赖 MCP、不依赖规则遵从
- 两个平台使用同一份 workflow 模板
- Codex 通过 AGENTS.md 引用 .claude/commands/ 模板

---

## v1-v2 历史结论（已归档）

v1-v2 阶段的 15 条产品结论记录了从 v1 MVP 到 v2 统一记忆面的演进过程，包括：durable memory 收口、统一目录收敛、skill 入口精简、docs lane 主从关系确立、统一写入口、review surface、hybrid recall、session-extract、decision discovery 等决策。

这些结论在 v3 中已不适用（相关组件已归档），完整历史记录见 `.archive/` 目录下的方案文档。
