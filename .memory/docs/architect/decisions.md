# 设计决策日志

### 决策 1 — 2026-02-26
背景：`memory-hub write` 通过 stdin/heredoc 传入内容，AI agent 调用时频繁出错（isatty 检测失败、heredoc 格式化错误、shell 转义问题）。`catalog-update` 同样依赖 stdin 传 JSON。
方案：
- A: 拆分为 AI 直接写文件 + `memory-hub index` 只管索引注册；`catalog-update` 改为 `--file` 参数 ← 选择
- B: 保留 `write` 但增加 `--file` 参数（一条命令包办写文件 + 更新索引）
- C: 保留 stdin 方案，优化 SKILL.md 提示让 AI 更好地使用 heredoc
选择原因：A 最符合"脚本是执行器，AI 是决策者"的核心理念。AI 最擅长文件写入（原生工具），CLI 的真正价值在索引管理（去重、section 定位），不在内容写入。拆分后每一步都简单可靠，零转义问题。
影响：破坏性变更 — `memory-hub write` 删除，`catalog-update` 需 `--file` 参数。所有使用旧接口的项目需同步更新 skill 和工作流。

### 决策 2 — 2026-03-10
背景：v1 MVP 已明确要从旧 `.memory/` 文件直写模型迁移到 `MCP proposal -> CLI review -> SQLite` 的新控制面。如果先写实现再补接口定义，MCP、CLI、Skill、文档很容易再次漂移，重演当前“设计和真实行为不一致”的问题。
方案：
- A: 先写 SQLite schema 和命令，再边实现边补接口文档
- B: 先冻结 v1 外部契约：不变量、URI 规则、状态机、MCP/CLI 返回结构、错误码，再按契约实现 ← 选择
- C: 继续沿用参考项目的现成接口，后续再收缩到适合 Memory Hub 的 MVP
选择原因：B 能最早锁定 durable memory 的外部行为边界，直接约束实现、测试和提示词，并用最小成本消除“代码一套、Skill 一套、文档一套”的漂移风险。相比 A，它把返工点前移；相比 C，它保留了 MVP 的范围控制，不会把参考项目的复杂度整包引入。
影响：后续开发以 `.archive/plans/2026-03-10-memory-hub-v1-contract-draft.md` 为契约基线推进。schema、MCP、CLI、测试都必须从契约反推，不再先实现后找补。

### 决策 3 — 2026-03-10
背景：在细化 schema 和测试样例时，create proposal 的 URI 何时确定、update proposal 保存“delta”还是保存“物化后的候选全文”，会直接影响 review 队列展示、approve 的确定性、stale proposal 处理和事务测试的写法。
方案：
- A: create proposal 在 approve 时再分配 URI；update proposal 只保存 patch/append delta
- B: create proposal 在创建时就生成并保留 `target_uri`；update proposal 同时保存 patch/append 意图与物化后的候选 `content` ← 选择
- C: create proposal 由 agent 自行提供 URI；update proposal 只在 approve 时重新读取 base version 并回放 patch
选择原因：B 让 review 队列看到的目标 URI 与 approve 后结果一致，避免审查前后标识漂移；同时让 approve 直接写 proposal 已保存的候选全文，不依赖再次回放 patch，从而简化 stale proposal 判断、review diff 计算和原子性测试。
影响：`memory_proposals.target_uri` 对 create/update 都是必备字段；update proposal 需要保存 `content` 与 `content_hash`，`patch_*` / `append_content` 只用于 review 展示与审计，不再作为 approve 时的唯一事实源。

### 决策 4 — 2026-03-10
背景：Phase 1C 需要把 durable memory 控制面暴露给 MCP 客户端，但当前项目仍坚持 v1 MVP 的零运行时依赖约束。若直接引入 `mcp` Python SDK 或其他服务框架，会增加安装、打包、版本兼容和调试面；若继续只停留在 repo/service 层，则无法验证“真正的 MCP tool surface”。
方案：
- A: 引入第三方 MCP SDK，直接使用现成 server/tool 装饰器
- B: 先实现一个无依赖的最小 stdio JSON-RPC MCP server，只覆盖 `initialize`、`tools/list`、`tools/call`、`ping` 与 4 个 durable memory tools ← 选择
- C: 暂不实现 MCP，只保留 Python API，等 v2 再接协议层
选择原因：B 保留了 v1 的依赖收敛目标，同时足以验证 MCP 入口、tool schema、错误语义和本地客户端接线。它把“协议面”与“业务层”分开：tool handler 负责 durable memory 契约，server 只负责 JSON-RPC/stdin-stdout 转发。后续如果决定引入正式 MCP SDK，也可以直接复用 handler，不需要重写 proposal/review/store 逻辑。
影响：v1 MCP 采用最小协议实现，不支持 SSE、资源订阅、tool list changed 通知等增强能力；客户端接入优先使用 `python -m lib.mcp_server` 或等价命令。若未来改用第三方 MCP 框架，应保持现有 4 个 tool 名称、参数契约和结构化返回不变。

### 决策 5 — 2026-03-10
背景：Phase 1D 进入客户端接线与工作流切换时，仓库里同时存在 `.memory/` 文件型知识库和 `.memoryhub/` durable memory v1。若不明确区分，README、CLAUDE 和 skills 很容易继续把“项目知识维护”和“LLM 长期记忆控制面”混成同一种写法，导致 agent 误用 `index` 或直接写文件。
方案：
- A: 直接废弃 `.memory/` 文档与命令，只保留 durable memory v1
- B: 保留两套 surface，但在文档和 skill 中显式分层：`.memory/` 负责项目知识，`.memoryhub/` 负责 durable memory proposal/review/MCP ← 选择
- C: 继续沿用原来的统一表述，默认 AI 自行理解差异
选择原因：B 与当前实现最一致，且迁移成本最低。文件型知识命令仍服务项目内知识与 catalog；durable memory v1 则通过 MCP tools 和 CLI 审查面提供给 LLM。把两套边界写清楚，能显著降低后续客户端接线、skill 编排和人工 review 时的误操作概率。
影响：`README.md`、`CLAUDE.md`、`REDESIGN.md` 和 repo skills 需要同步区分两套工作流；新增 `memory-hub-mcp` 作为 MCP server 的显式启动入口。后续如果决定逐步收缩旧 `.memory/` surface，也应以此分层为前提逐步迁移，而不是继续混用命令语义。

### 决策 6 — 2026-03-10
背景：Phase 1D 的真实会话验收表明，`memory-hub` 的 MCP/CLI/SQLite 已经可用，但把 durable-memory 的具体工具调用直接写在全局规则里，会让普通代码任务和 durable-memory 任务在行为层发生耦合。参考 `ccg-workflow` 后，确认更稳定的做法应是：规则识别语境，workflow/skill 决定是否调用工具。
方案：
- A: 继续在 `CLAUDE.md` / 全局规则中直接点名 `read_memory/search_memory/propose_*`
- B: 收紧全局规则，只保留 durable-memory 语境识别与硬边界；把 boot/search/propose/update/pending 分流全部下沉到 `durable-memory` skill ← 选择
- C: 进一步扩展协议层，为 pending proposal 新增 amend/update 能力，再回头重写规则
选择原因：B 能最小代价消除“全局规则直接操作 MCP”的耦合，让 `.memory/` 项目知识流与 durable-memory 长期记忆流在行为层彻底分开。它也与当前产品边界保持一致：v1 不新增 `amend pending proposal`，pending proposal 只进入人工审查分流。
影响：新增仓库级 `AGENTS.md` 作为 Codex 主规则入口；`CLAUDE.md` 精简为语境识别与硬边界；`skills/durable-memory/SKILL.md` 重写为真正的 workflow 决策树；新增会话级行为验收清单（后续已升级为 Phase 1F 文件名）。MCP/CLI/SQLite 契约保持不变。

### 决策 7 — 2026-03-10
背景：Phase 1E 的真实会话验收暴露出两个行为缺口：首次进入 durable-memory 时没有把 `system://boot` 作为第一条工具调用；proposal 创建后也只是停在 pending，没有像 `ccg-workflow` 那样主动把用户带入下一步确认。另一方面，Codex 常规会话没有稳定可用的结构化确认工具，不能要求用户始终进入 Plan Mode。
方案：
- A: 继续保持“proposal 创建后只报 pending，用户自行运行 review CLI”
- B: 修正 skill：把 boot-first 提升为硬约束；proposal 创建或命中 pending proposal 后自动 `review show`，再按宿主能力进入确认分流；允许在用户显式确认后由 agent 代理执行 `review approve/reject` ← 选择
- C: 等待 Codex 提供稳定的结构化提问工具后再优化交互
选择原因：B 能在不改 MCP/CLI/SQLite 契约的前提下，直接修复当前会话级验收失败项，同时给 Codex 提供不依赖 Plan Mode 的降级路径；Claude 若具备 `AskUserQuestion`，则可继续使用更好的结构化确认体验。这个方案只放宽 `approve/reject`，仍然把 `rollback` 留在人工手动边界内。
影响：`skills/durable-memory/SKILL.md` 必须明确规定 first-call boot、`review show` handoff、宿主能力分流和固定确认短语；`AGENTS.md`、`CLAUDE.md`、`README.md` 与行为验收清单同步收紧。Codex 使用的全局 `durable-memory` skill 副本必须与仓库内 skill 保持同步，并在同步后重启会话。

### 决策 8 — 2026-03-11
背景：v2 在 Phase 2B 到 Phase 2F 期间已经把 docs/catalog/durable/review 的统一入口收敛到 `project-memory`，但仓库和全局 skill 安装里仍残留一个独立可见的 `durable-memory` skill。继续保留第三个可见 skill，会让用户误以为 durable flow 仍是独立产品入口，也与“对外只保留两个 skill”的 v2 目标冲突。
方案：
- A: 保留 `durable-memory` 作为第三个可见 skill，只在文档里强调它是内部子流程
- B: 把 boot-first、proposal routing、pending review split 与确认分流全部并入 `project-memory`，移除独立可见的 `durable-memory` skill ← 选择
- C: 彻底放弃 durable-specific workflow，把 proposal/review 细节重新写回全局规则
选择原因：B 不改变 SQLite、MCP、CLI 的任何外部契约，只收口行为层入口，能以最小改动让 v2 的产品形态与实现一致。它也保留了 durable-specific 纪律，只是把这部分逻辑下沉成 `project-memory` 内部 branch，而不是继续暴露为第三个 skill。
影响：`skills/project-memory/SKILL.md` 需要吸收 durable-memory workflow 全部内容；仓库级规则与 README/CLAUDE 只保留 `project-memory` 与 `memory-admin` 两个可见 skill；全局安装的 `durable-memory` skill 副本应移除。历史文档可保留旧记录，但当前基线与新会话不再暴露第三个 skill。
