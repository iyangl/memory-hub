# Memory Hub v3 Skill-Driven Redesign -- 深度审查报告

**审查时间**: 2026-03-16
**审查依据**: v3 方案摘要、已确认决策 C1/C2、现有 v2 代码库完整阅读

---

## Phase 0 决策结果（已全部收敛 2026-03-16）

| # | 决策项 | 结论 | 理由 |
|---|--------|------|------|
| D1 | Disclosure 标签 | Phase 1 不引入 | 降低 LLM 写入负担，先跑通最简流程 |
| D2 | 目录分类 | 硬编码四类（architect/dev/pm/qa） | v2 实际使用验证够用，简化 CLI 和 BRIEF 逻辑 |
| D3 | BRIEF.md git 跟踪 | 跟踪 | clone 后直接可用，团队共享同一份 BRIEF |
| D4 | inbox/ git 跟踪 | 不跟踪（.gitignore） | 临时写入区，丢了无所谓，避免污染 git history |
| D5 | durable memory 数据 | 直接归档不导出 | 有价值的知识已在 docs 中，_store/ 整体归档 |
| D6 | inbox 文件格式 | 纯 markdown，无 frontmatter。命名：{ISO时间戳}_{short-name}.md。一文件一条知识。/save 后删除 | 格式门槛越低 LLM 写入概率越高，Layer 2 是最佳努力 |
| D7 | BRIEF.md 拼接规则 | 按 bucket 分组，每 doc 提取第一个 ## 标题+首段（截断 3 行），空文件跳过，总长度 ~200 行，超出则截断 2 行。/save 后自动重建 | 机械式确定性生成，不依赖 LLM |
| D8a | slash command 载体 | .claude/commands/ | 与 CCG 一致，CC 原生支持，Codex 通过 AGENTS.md 引用 |
| D8b | memory-admin skill | 移除，维护操作通过 CLI 直接调用 | v3 只保留 3 command，维护用 `python3 -m lib.cli catalog-repair` |

### D6 详细设计：inbox 机制

```
.memory/inbox/
  2026-03-16T14-30-00_design-decision.md
  2026-03-16T15-00-00_new-constraint.md
```

- **格式**：纯 markdown，不要求 frontmatter
- **命名**：`{ISO时间戳}_{短语义名}.md`（时间戳保证唯一性和排序）
- **粒度**：一个文件一条知识
- **生命周期**：/save 合并后直接删除
- **容量**：不设上限，长期不执行 /save 时由用户自行处理
- **git**：inbox/ 加入 .gitignore

### D7 详细设计：BRIEF.md 拼接规则

**参与拼接的 doc**：docs/ 下四个 bucket 中所有 .md 文件，跳过空文件

**"首段"定义**：第一个 ## 标题 + 该标题后到下一个 ## 之间的第一个非空段落。无 ## 标题时取前 5 行。每条截断 3 行。

**输出格式**：
```markdown
# Project Brief

## architect
### tech-stack.md
<首段摘要>

### decisions.md
<首段摘要>

## dev
### conventions.md
<首段摘要>
...
```

**排序**：bucket 按固定序（architect → dev → pm → qa），bucket 内按文件名字母序

**长度控制**：目标 ~200 行，超出时每条截断到 2 行

**更新时机**：每次 /save 完成后自动重新生成

---

## 审查结果

### 1. /init workflow 模板设计

- **状态**: 待细化
- **评估理由**: v3 `/init` 的功能目标（首次扫描项目，生成初始记忆）与 v2 `memory_init.py` 的骨架创建有根本差异。v2 init 只做目录骨架 + 空模板文件 + catalog-repair，不做任何项目扫描。v3 `/init` 如果要做"扫描项目生成初始记忆"，这是 LLM 行为，不是 CLI 行为 -- 意味着 `/init` 的主体逻辑在 skill 模板里（prompt engineering），而 CLI 只负责骨架创建。
- **需要补充的具体问题**:
  1. `/init` 是 skill 模板（LLM 执行流程）还是 CLI 命令？如果是 skill 模板，CLI 部分（骨架创建）是否保留为 `memory-hub init` 命令？
  2. 如果 `/init` 扫描项目生成 docs，这些 docs 是直接写入 `docs/` 还是先进 `inbox/` 再由 `/save` 合并？
  3. `/init` 需要生成 BRIEF.md 吗？还是 BRIEF.md 只在 `/recall` 时按需生成？
  4. v2 的 `manifest.json` 是否保留？如果保留，layout_version 如何更新？
  5. `/init` 对已有 `.memory/` 目录的处理策略 -- v2 直接 fail("ALREADY_INITIALIZED")，v3 是否改为增量更新（对应问题 I1）？
  6. init 后是否仍自动执行 catalog-repair？

### 2. /recall workflow 模板设计（含 BRIEF.md 机械拼接规则）

- **状态**: 待细化
- **评估理由**: `/recall` 的核心行为是"加载记忆到上下文"。C2 已确认 BRIEF.md 通过机械式拼接生成，但拼接的触发时机、拼接后如何注入 LLM 上下文、以及上下文持久性（W1）仍未定义。
- **需要补充的具体问题**:
  1. `/recall` 是每次会话开始时手动调用，还是由 CLAUDE.md 规则自动触发？
  2. `/recall` 是否只读 BRIEF.md，还是同时读 catalog/topics.md 以便后续按需深入？
  3. BRIEF.md 是在 `/recall` 时即时生成（读 docs 目录 -> 拼接），还是预先缓存为文件？如果是缓存文件，何时更新？
  4. `/recall` 注入后的上下文如何在会话中持久化？（W1 未决问题）-- 是依赖 LLM 的上下文窗口，还是有某种 session state？
  5. 当 docs 数量增长后，BRIEF.md 超出合理 token 预算时的降级策略是什么？
  6. `/recall` 是否需要读取 `inbox/` 中未合并的内容？

### 3. /save workflow 模板设计（含 inbox -> docs 合并、去重、catalog repair）

- **状态**: 待讨论
- **评估理由**: `/save` 是 v3 最复杂的 command，承担了 v2 中 `capture_memory + update_memory + docs_review + catalog-repair` 的全部写入职责。但其内部流程涉及多个设计决策点尚未收敛。
- **决策问题**:
  1. **inbox 合并策略**: `/save` 从 inbox 合并到 docs 时，是逐条人工确认，还是批量自动合并？如果自动合并，去重判断（W5）如何保证质量？
  2. **去重机制**: v2 依赖 MCP write guard + SQLite 做去重，v3 移除后去重完全依赖 LLM 搜索判断（W5）。这是否意味着 `/save` 必须是 LLM 驱动的（非纯 CLI）？如果是，离线执行（无 LLM）时怎么办？
  3. **冲突处理**: inbox 中多条记录指向同一 doc 时的合并策略。
  4. **原子性**: v2 有 SQLite 事务保证 approve 原子性。v3 文件操作的原子性如何保证？单个 `/save` 可能修改多个 docs 文件 + catalog，中间失败如何回滚？
  5. **catalog-repair 内化还是外部调用**: `/save` 完成后是否自动触发 catalog-repair？还是 catalog 更新已经内化到 `/save` 流程中？
  6. **审查环节是否保留**: v2 有 proposal -> review -> approve 三步。v3 的 `/save` 是直接落盘还是需要用户确认？如果直接落盘，"后悔测试"的安全网只剩 git，这是否可接受（I3）？
  7. **新增 doc 的 bucket 分类**: `/save` 时需要判断知识属于 architect/dev/pm/qa（W2 四类可能不够用）。这个判断由谁做？

### 4. inbox 机制详细设计

- **状态**: 待细化
- **评估理由**: C1 已确认 Layer 2 写入目标为 `.memory/inbox/`，但 inbox 的内部设计几乎是空白。
- **需要补充的具体问题**:
  1. **目录结构**: inbox 下是否有子目录分类？还是平铺文件？
  2. **文件命名**: 用时间戳？UUID？语义名？命名规则直接影响去重和排序。
  3. **文件格式**: 纯 markdown？带 frontmatter 的 markdown（附元数据如来源会话、创建时间、建议 bucket）？
  4. **单条 vs 多条**: 一个 inbox 文件包含一条知识，还是可以包含多条？
  5. **生命周期**: 被 `/save` 合并后的 inbox 文件是删除、移动到 archive、还是标记已处理？
  6. **清理策略**: inbox 长期不执行 `/save` 时的积压处理。inbox 有容量上限吗？
  7. **与 git 的关系**: inbox 文件是否应该被 git 跟踪？如果跟踪，多人协作时的冲突问题。如果不跟踪（.gitignore），则失去 I3 的 git 安全网。

### 5. BRIEF.md 机械式拼接的具体规则

- **状态**: 待细化
- **评估理由**: C2 确认了"每个 doc 提取标题+首段"的机械式拼接，但具体规则需要精确定义才能编码。
- **需要补充的具体问题**:
  1. **"首段"的定义**: 第一个 `##` 标题后的第一个段落？文件开头到第一个标题之间的内容？第一个非空行？
  2. **字数/行数限制**: 每条摘要的最大长度是多少？
  3. **排序规则**: 按 bucket 分组？按文件名字母序？按最后修改时间？
  4. **哪些 doc 参与拼接**: `docs/` 下所有 `.md` 文件？还是只有在 catalog/topics.md 中注册的？空文件（如初始化时的空 decisions.md）是否跳过？
  5. **输出格式**: BRIEF.md 的 markdown 结构是什么样的？是否包含指向原始 doc 的链接？
  6. **更新时机**: 每次 `/save` 后自动重新生成？还是只在 `/recall` 时按需生成？
  7. **总长度预算**: BRIEF.md 的目标 token 数是多少？超出时的截断策略？

### 6. Layer 2 行为规范（LLM 自主写 inbox 的触发条件、格式要求）

- **状态**: 待讨论
- **评估理由**: Layer 2 是"最佳努力"层，LLM 自主判断何时写入 inbox。这是 v3 最难规范化的部分，因为它本质上是 prompt engineering 问题，而非代码设计问题。
- **决策问题**:
  1. **触发条件的表达方式**: 写在 CLAUDE.md 中作为规则？写在 skill 模板中？如何确保不同 LLM 宿主（CC/Codex）行为一致？
  2. **"后悔测试"的可操作性**: "会话结束后没记下来会后悔吗"这个标准主观性很强。是否需要更具体的触发信号（如"做出了设计决策"、"发现了约束"等，类似 v2 REDESIGN.md 的列表）？
  3. **写入格式强制**: LLM 写 inbox 时，frontmatter 元数据（建议 bucket、知识类型、来源描述）是必填还是可选？格式不合规时 `/save` 如何处理？
  4. **频率控制**: 是否需要防止 LLM 过于频繁写 inbox（每次对话都写）或过于保守（几乎不写）？
  5. **跨平台一致性**: CC 和 Codex 的 LLM 行为差异如何处理？同一个 skill 模板在不同宿主上的触发行为可能不同。
  6. **反面清单的机器可检查性**: "代码本身能表达的不存" -- 这个判断完全依赖 LLM，是否需要某种 lint 机制？

### 7. CLAUDE.md 精简设计

- **状态**: 就绪
- **评估理由**: 方向明确 -- 从当前 ~300 行的复杂流程规则精简为 3 command 的简单路由。当前 CLAUDE.md 的主要复杂度来自 durable branch、review 流程、MCP 约束、写入路由，这些在 v3 中全部移除。精简后的 CLAUDE.md 只需要定义：(1) `/init`、`/recall`、`/save` 三个 command 的入口；(2) Layer 2 自主写入 inbox 的行为规范；(3) 硬边界（不直接编辑 docs、不绕过 inbox 等）。
- **备注**: 具体内容取决于 Layer 2 行为规范（环节 6）的定义结果。CLAUDE.md 的精简本身不是瓶颈。

### 8. 代码精简与归档策略

- **状态**: 待细化
- **评估理由**: 保留/归档清单已给出，大方向明确。但归档的执行步骤和保留模块的改造细节需要进一步定义。
- **需要补充的具体问题**:
  1. **归档方式**: 移入 `.archive/v2/` 目录？直接删除（依赖 git history）？保留但标记 deprecated？
  2. **保留模块的改造**: `paths.py` 需要新增 `inbox/` 和 `BRIEF.md` 的路径定义；需要移除 `_store/`、`projections/` 相关路径。`cli.py` 的 COMMANDS 字典需要大幅精简。`envelope.py` 是否仍然需要？v3 的 3 个 command 是否仍走 JSON envelope 输出？
  3. **MCP server 的处理**: `mcp_server.py` 和 `mcp_toolspecs.py` 确认移除。`durable_mcp_tools.py` 确认移除。但需要确认 `memory-hub-mcp` 这个 pyproject.toml 入口也一并移除。
  4. **pyproject.toml 更新**: scripts 入口需要同步更新。
  5. **tests/ 的处理策略**: 现有测试哪些保留、哪些归档，需要和保留模块一一对应。

### 9. v2 -> v3 数据迁移

- **状态**: 待细化
- **评估理由**: 方案明确保留 `.memory/docs/` 和 `.memory/catalog/` 数据。但需要处理被移除组件的残留物。
- **需要补充的具体问题**:
  1. **`_store/` 目录处理**: `memory.db`、`projections/boot.json`、`projections/search.json` -- 是手动删除还是由迁移脚本处理？
  2. **`manifest.json` 更新**: `layout_version` 从 "2F" 升级到 "3" 或类似标识。`store_root`、`store_db`、`projection_root` 字段移除。新增 `inbox_root` 字段。
  3. **新增 `inbox/` 目录**: 迁移时自动创建还是首次 `/save` 或 Layer 2 写入时按需创建？
  4. **新增 `BRIEF.md`**: 迁移时根据现有 docs 生成初始版本？还是首次 `/recall` 时按需生成？
  5. **catalog/topics.md 兼容性**: 现有 topics.md 格式是否需要调整？
  6. **迁移是否需要脚本**: 还是纯手动操作 + 文档指引（与 v2 结论 12 的精神一致）？

### 10. skill 目录结构调整

- **状态**: 待讨论
- **评估理由**: 从 `project-memory`/`memory-admin` 两个 skill 转向 3 个 slash command，涉及 skill 目录的完全重组。但 slash command 在 Claude Code 中的实现机制（是否仍是 `skills/` 目录下的 SKILL.md）需要确认。
- **决策问题**:
  1. **slash command 的实现载体**: Claude Code 的 `/command` 是通过 `.claude/commands/` 目录实现的，而非 `skills/` 目录。Codex 的 slash command 机制可能不同。v3 需要在两个平台上都支持，载体选什么？
  2. **是否保留 skill 目录**: 如果 `/init`、`/recall`、`/save` 走 `.claude/commands/`，那 `skills/` 目录是否完全废弃？
  3. **`memory-admin` 是否保留**: v3 方案只提到 3 个 command，但 catalog-repair 等维护操作仍然需要入口。是否需要第 4 个 command 或保留 memory-admin skill？
  4. **Codex 兼容性**: Codex 是否支持 slash command？如果不支持，Codex 上如何触发 `/init`、`/recall`、`/save`？

### 11. CLI 命令调整

- **状态**: 待细化
- **评估理由**: CLI 从 12 个命令精简到约 3-4 个，大方向明确但需要确认最终 CLI surface。
- **需要补充的具体问题**:
  1. **v3 CLI 的最终命令列表**: 是否仍需要 `memory-hub init`、`memory-hub catalog-repair`？是否新增 `memory-hub brief`（生成 BRIEF.md）、`memory-hub save`（inbox 合并）？
  2. **CLI 与 slash command 的关系**: `/init` 调用 `memory-hub init` 吗？还是 `/init` 完全是 skill/prompt 驱动，不调用 CLI？
  3. **移除命令确认**: `review`、`rollback`、`session-extract`、`discover`、`catalog-update`、`list`、`index` -- 这些全部移除？`search`、`read` 是否保留为内部工具？
  4. **JSON envelope 是否保留**: v3 的 CLI 是否仍然输出 JSON envelope？如果 CLI 只是 slash command 的内部工具，是否可以改为更简单的输出格式？

### 12. 测试策略

- **状态**: 待细化
- **评估理由**: 现有测试基于 v2 的 MCP/SQLite/proposal 契约，大部分需要归档或重写。
- **需要补充的具体问题**:
  1. **保留测试**: `tests/test_paths.py`、`tests/test_envelope.py`、`tests/test_catalog_repair.py`、`tests/test_memory_init.py`、`tests/test_memory_read.py`、`tests/test_memory_search.py` -- 这些是否全部保留？需要哪些修改？
  2. **新增测试**: BRIEF.md 机械拼接逻辑需要测试。inbox 文件创建/读取需要测试。`/save` 的 inbox->docs 合并逻辑需要测试（如果有 CLI 部分）。
  3. **归档测试**: 所有 `test_durable_*`、`test_mcp_*`、`test_project_review_*`、`test_docs_review_*` -- 确认归档。
  4. **端到端测试**: v2 有 `bin/selftest-phase1c`。v3 需要等价的端到端验证吗？
  5. **行为测试**: Layer 2 的 LLM 自主写入行为无法用传统测试覆盖。是否需要定义验收场景？

### 13. Disclosure 标签的取舍

- **状态**: 待讨论
- **评估理由**: Disclosure 标签（每条知识附"何时需要"的场景描述）是 v3 方案中的特色设计。但 W4 指出其实际收益存疑 -- 机械拼接的 BRIEF.md 不会利用 Disclosure 标签，只有 LLM 在处理深度阅读时才可能利用它。
- **决策问题**:
  1. **收益/成本分析**: Disclosure 标签增加了 LLM 写入 inbox 时的认知负担和格式复杂度。在 BRIEF.md 只做标题+首段拼接的模型下，Disclosure 标签只对 `/save` 合并时的分类和 LLM 自主检索有价值。
  2. **是否 Phase 1 必要**: 建议 v3 Phase 1 不引入 Disclosure 标签，先用最简格式跑通 inbox -> docs 流程。如果后续发现分类或检索质量不够，再引入 Disclosure 作为增强。
  3. **如果保留**: 标签格式是什么？在 frontmatter 里？在正文的固定位置？`/save` 合并到 docs 后标签如何处理（保留还是丢弃）？

### 14. 目录分类的扩展策略

- **状态**: 待讨论
- **评估理由**: W2 指出四个目录（architect/dev/pm/qa）可能不够用。当前 v2 的 `paths.py` 将 `BUCKETS = ("pm", "architect", "dev", "qa")` 硬编码。
- **决策问题**:
  1. **硬编码 vs 动态**: 如果改为动态，谁负责创建新 bucket？LLM 自主创建还是用户手动创建？
  2. **v2 中已有的额外文件**: 当前 `.memory/docs/` 下已经有 `qa/qa-strategy.md`、`qa/memory-相关逻辑变更必须补自动化测试和自测记录.md`、`dev/记忆相关写入必须经过统一写入口.md` 等文件，说明实际使用中四类是够用的（知识分散在四类之内的不同文件中）。
  3. **建议**: 维持硬编码四类作为 v3 Phase 1 的策略。如果需要扩展，不是增加 bucket 数量，而是在 bucket 内增加文件（v2 的做法已经验证了这条路径）。这个决策与 BRIEF.md 拼接规则相关 -- 硬编码四类让拼接逻辑更简单可控。

---

## 设计冲突与遗漏

### 冲突 1: /save 的"确定性"与"LLM 依赖"矛盾

v3 方案称 `/save` 是 Layer 3（确定性），但 `/save` 的核心逻辑 -- inbox 去重、知识分类、docs 合并 -- 几乎都需要 LLM 判断。这与"确定性"标签矛盾。建议重新定义：`/save` 是"用户显式触发的确定性入口"（触发时机确定），但合并执行过程可以是"LLM 辅助的最佳努力"。

### 冲突 2: 移除 review 机制 vs 安全网

v2 的 proposal -> review -> approve 三步为知识写入提供了人工审查安全网。v3 移除后，`/save` 直接落盘到 docs，安全网只剩 git（I3）。但 git 作为安全网要求：(1) inbox 和 docs 都被 git 跟踪；(2) 用户有 git 使用意识；(3) `/save` 前自动 commit 或有明确提示。这些前提都需要明确。

### 冲突 3: BRIEF.md "派生产物" vs "唯一数据源"

v3 方案称 BRIEF.md 是"派生产物"（从 docs 生成），同时又是 `/recall` 的"主要数据源"。如果 BRIEF.md 是派生的，它应该可以随时从 docs 重新生成，这意味着它不需要被 git 跟踪（可以放在 `.gitignore`）。但如果它是 `/recall` 的主要数据源且不被跟踪，首次 clone 项目后需要一个重建步骤。需要明确 BRIEF.md 是否被 git 跟踪。

### 遗漏 1: 多项目部署的 inbox 隔离

v2 通过 `MEMORY_HUB_PROJECT_ROOT` 环境变量支持为不同项目提供记忆服务。v3 中 inbox 写入如果由 LLM 直接写文件（而非通过 CLI/MCP），如何确保写入正确项目的 inbox？

### 遗漏 2: catalog/ 在 v3 中的角色

v3 方案保留 `catalog/`，但 `/recall` 以 BRIEF.md 为主要数据源，catalog 的用途变得模糊。需要明确 catalog 在 v3 中的定位：是仍然作为按需深入的索引（v2 的用法），还是退化为 BRIEF.md 生成的中间数据？

### 遗漏 3: AGENTS.md / Codex 规则同步

v2 有 AGENTS.md 作为 Codex 主规则入口。v3 精简后 AGENTS.md 也需要同步更新。方案中没有提及。

### 遗漏 4: 现有 durable memory 数据的处理

`.memory/_store/memory.db` 中可能已有 approved memories。v3 移除 durable store 后，这些数据是否需要导出到 docs？还是视为已被 docs 覆盖而直接丢弃？

### 遗漏 5: envelope.py 的命运

v3 的 3 个 slash command 如果主要是 skill 模板（prompt 驱动），LLM 不需要 JSON envelope 来解析 CLI 输出。但如果 `/save` 的合并逻辑仍以 CLI 形式存在，envelope 仍有价值。需要明确 v3 CLI 的输出契约。

### 遗漏 6: search 能力的退化

v2 有 hybrid recall（lexical + semantic），v3 移除后，按需检索能力退化为纯文件读取 + LLM 上下文内匹配。对于大型项目（docs 文件多），`/recall` 的 BRIEF.md 可能不够用，但又没有 search 命令作为兜底。是否保留 `memory-hub search` 作为内部工具？

---

## 落地节点排序

### 依赖关系图

```
Phase 0 (基础决策)
  |- 环节 14: 目录分类策略 (硬编码四类 vs 动态)
  |- 环节 13: Disclosure 标签取舍
  |- 环节 10: skill 目录结构 (slash command 实现载体)
  |- 环节 4: inbox 机制详细设计
  |- 环节 5: BRIEF.md 拼接规则
  '- 环节 6: Layer 2 行为规范

Phase 1 (核心实现 -- 可并行)
  |- 环节 8: 代码精简与归档 ----------- (无依赖，可最先启动)
  |- 环节 9: v2->v3 数据迁移 ---------- (依赖 环节 4 的 inbox 设计)
  |- 环节 1: /init 实现 -------------- (依赖 环节 5 的 BRIEF.md 规则)
  |- 环节 2: /recall 实现 ------------ (依赖 环节 5 的 BRIEF.md 规则)
  '- 环节 3: /save 实现 -------------- (依赖 环节 4, 5, 6, 13, 14)

Phase 2 (接线与精简)
  |- 环节 7: CLAUDE.md 精简 ---------- (依赖 环节 6 的 Layer 2 规范)
  |- 环节 11: CLI 命令调整 ----------- (依赖 Phase 1 的实现结果)
  '- 环节 10: skill 部署 ------------- (依赖 环节 7)

Phase 3 (验证)
  '- 环节 12: 测试策略 --------------- (依赖 Phase 1 + Phase 2)
```

### 建议实施顺序

**第一步: 决策收敛 (Phase 0)** -- 预估 2 任务点

以下决策必须在编码前全部敲定：

1. inbox 目录结构、文件格式、命名规则、生命周期（环节 4）
2. BRIEF.md 拼接的精确规则（环节 5）
3. `/init`、`/recall`、`/save` 的 CLI vs skill 边界（环节 1/2/3 的前提）
4. Disclosure 标签：Phase 1 不引入（建议）
5. 目录分类：Phase 1 硬编码四类（建议）
6. slash command 的技术载体：`.claude/commands/` vs `skills/`
7. git 跟踪策略：inbox 和 BRIEF.md 是否进 `.gitignore`
8. 现有 durable memory 数据的处理策略

**第二步: 代码精简 (Phase 1a)** -- 预估 3 任务点

可以最先启动，不依赖任何设计决策：

1. 归档 25 个模块到 `.archive/v2/`
2. 清理 `cli.py` 的 COMMANDS 字典
3. 清理 `pyproject.toml` 的 scripts 入口
4. 归档对应的测试文件
5. 删除 `bin/selftest-phase1c`

**第三步: 数据迁移 + 基础设施 (Phase 1b)** -- 预估 2 任务点

与第二步可并行：

1. `paths.py` 新增 inbox 和 BRIEF.md 路径
2. `manifest.json` 更新 layout_version
3. `memory_init.py` 适配（创建 inbox 目录）
4. 编写迁移指引文档（手动操作步骤）

**第四步: BRIEF.md 生成逻辑 (Phase 1c)** -- 预估 2 任务点

1. 编写 `lib/brief.py`：机械式拼接逻辑
2. 单元测试
3. 集成到 CLI（`memory-hub brief`）或集成到 `/recall` 流程

**第五步: /init + /recall 实现 (Phase 1d)** -- 预估 3 任务点

1. `/init` skill 模板编写
2. `/recall` skill 模板编写
3. 端到端验证

**第六步: /save 实现 (Phase 1e)** -- 预估 4 任务点

最复杂的环节，依赖前面所有步骤：

1. inbox -> docs 合并逻辑
2. catalog-repair 触发
3. BRIEF.md 重新生成
4. `/save` skill 模板编写
5. 端到端验证

**第七步: 规则精简与部署 (Phase 2)** -- 预估 2 任务点

1. CLAUDE.md 重写
2. AGENTS.md 同步更新
3. README.md 更新
4. skill 目录调整

**第八步: 测试与验收 (Phase 3)** -- 预估 2 任务点

1. 更新/新增单元测试
2. 编写端到端验收场景
3. CC 和 Codex 双平台验证

### 并行任务

以下任务可以并行推进：

- Phase 1a（代码精简） || Phase 0（决策收敛）
- Phase 1b（数据迁移基础设施） || Phase 1a（代码精简）
- `/init` 实现 || `/recall` 实现（Phase 1d 内部并行）
- CLAUDE.md 精简 || AGENTS.md 更新 || README.md 更新（Phase 2 内部并行）

### 总预估工作量

**20 任务点**（1 点 = 1-2 小时）

其中 Phase 0（决策收敛）是关键路径瓶颈 -- 8 个待决策问题中任何一个变更都可能影响后续实现。建议在一次集中讨论中完成所有 Phase 0 决策，避免反复。
