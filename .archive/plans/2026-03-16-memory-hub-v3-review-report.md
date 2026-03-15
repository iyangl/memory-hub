# Memory Hub v3 Skill-Driven 重构方案审查报告

日期：2026-03-16
审查方式：Claude 架构审查（Codex/Gemini 未连接）

## Critical

### C1. Layer 2（LLM 自主 save）缺乏格式防护

LLM 直接 Edit `.memory/docs/` 文件，可能造成：
- 格式损坏（破坏 markdown 结构、覆盖已有内容）
- 写入错误目录（把架构决策写进 qa/）
- 写入低质量内容（未经提炼的会话片段）

`/save` 虽然能做最终清理，但如果 LLM 在 Layer 2 已经把 docs 弄乱了，`/save` 的去重和提炼逻辑会面对脏数据。

**建议**：Layer 2 不应直接编辑 docs 正本。改为写入一个 scratch 区（如 `.memory/inbox/`），`/save` 从 inbox 合并到 docs。inbox 丢了无所谓，docs 始终干净。

### C2. `/save` 重建 BRIEF.md 的"重建"定义模糊

方案说"/save 先写 docs，再从 docs 重新生成 BRIEF.md"。但"从 docs 生成 BRIEF.md"这个操作本身需要 LLM 做摘要 — 这又回到了依赖 LLM 判断的问题。

如果 BRIEF.md 是 LLM 生成的摘要，那每次 `/save` 生成的 BRIEF.md 可能不一样（不同 LLM、不同上下文）。这和"确定性"的目标矛盾。

**建议**：明确 BRIEF.md 的生成规则。两个选项：
- A）机械式拼接：从每个 doc 文件提取前 N 行（标题+第一段），不依赖 LLM 摘要
- B）LLM 摘要：接受非确定性，但加上 brief-repair CLI 命令作为确定性回退

## Warning

### W1. `/recall` 注入后的上下文持久性未定义

`/recall` 把 BRIEF.md 注入上下文后，如果会话很长（>100 轮对话），这些信息会被上下文压缩机制丢弃。用户可能以为"已经 recall 了"，但实际上 LLM 已经忘了。

**建议**：在 `/recall` 的 workflow 模板里说明：长会话中可以重新调用 `/recall` 刷新上下文。或者在 BRIEF.md 中标注"如果你看不到这段内容，请用户重新调用 /recall"。

### W2. 四个目录分类可能不够用

architect / dev / pm / qa 四分类是当前项目的结构。但其他项目可能需要不同的分类（ops、security、data、design 等）。

**建议**：分类不硬编码在 workflow 模板里。`/init` 时根据项目特征生成分类目录，`/save` 时读取实际存在的目录作为分类选项。

### W3. 迁移路径未具体化

v2 的 durable store（memory.db）中有已审批的记忆数据。方案说"移除 durable store"，但没说这些数据怎么办。

**建议**：写一个一次性迁移脚本：从 memory.db approved_memories 表导出内容到 `.memory/docs/` 对应目录，然后归档 memory.db。

### W4. Disclosure 标签的实际收益存疑

Nocturne 的 disclosure 配合它的 URI 图路由系统有意义（可以自动触发 recall）。但在 v3 里，`/recall` 只是读 BRIEF.md，disclosure 标签写在 docs 里却不会被自动使用。

**建议**：要么去掉 disclosure（简化），要么在 `/recall` 的 workflow 中增加一步：如果用户传入了任务描述，则根据 disclosure 标签选择性加载补充 docs。

### W5. `/save` 的去重依赖 LLM 搜索判断

"/save 写入前搜索已有 docs，判断新增 vs 更新" — 这个搜索和判断仍然由 LLM 执行。如果 LLM 搜索不到已有内容（搜索词不匹配），就会创建重复文档。

**建议**：去重步骤用 Grep 做关键词匹配（确定性），而不是让 LLM 自由搜索。在 workflow 模板里写死：`Grep 搜索标题关键词 → 列出候选 → LLM 判断是否匹配`。

## Info

### I1. `/init` 是一次性操作，但可能需要增量更新

项目演化后，tech stack、目录结构可能变化。`/init` 只在首次运行，后续变化靠 `/save` 逐步更新。但某些结构性变化（新增子模块、切换框架）可能需要一次性重新扫描。

**建议**：考虑 `/init --refresh` 模式，非破坏性地补充已有 docs。

### I2. catalog-repair 作为唯一 CLI 工具可能不够

方案说"保留 catalog-repair 作为 /save 收尾步骤"。但如果引入 BRIEF.md，还需要 brief-repair。如果引入 inbox，还需要 inbox 处理。

**建议**：保留一个极简 CLI 入口（`memory-hub repair`），内部同时处理 catalog 和 BRIEF 的重建。

### I3. git 作为 Layer 2 的安全网需要用户意识

方案说"LLM 直接编辑 docs，git 兜底"。但这要求用户在 `/save` 之前不要 commit，否则错误内容也被 commit 了。

**建议**：在 `/save` workflow 的开头加一步检查 `.memory/` 的 git diff，如果有未经 `/save` 处理的改动（Layer 2 的产物），先展示给用户确认。

## 审查总结

| 等级 | 数量 | 关键问题 |
|------|------|---------|
| Critical | 2 | Layer 2 格式防护、BRIEF.md 生成确定性 |
| Warning | 5 | 上下文持久性、分类扩展性、迁移路径、disclosure 收益、去重可靠性 |
| Info | 3 | init 增量更新、CLI 工具补全、git 安全网 |

方案大方向正确 — 从规则驱动到 skill 驱动的转变解决了 v2 的根本矛盾。关键是 C1（inbox 隔离 Layer 2 写入）和 C2（BRIEF.md 生成规则确定化）需要在实施前确定。

## 待决策项

- [ ] C1: Layer 2 写入目标 — 直接写 docs 还是引入 inbox 隔离区？
- [ ] C2: BRIEF.md 生成方式 — 机械式拼接还是 LLM 摘要？
- [ ] W2: 目录分类 — 硬编码四类还是 /init 动态生成？
- [ ] W4: Disclosure 标签 — 保留还是去掉？
