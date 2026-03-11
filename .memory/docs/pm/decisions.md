# 需求结论与产品决策

### 结论 1 — 2026-03-11
背景：Phase 1F 完成后，Codex 路径的真实会话验收已基本符合预期；Claude 路径暂时搁置，不再阻塞当前版本收口。
结论：
- 若暂不要求 Claude 的增强交互一并完成，则 durable-memory v1 MVP 可视为完成。
- Codex 路径作为当前默认使用路径。
- 后续工作从“继续重构”切换为“真实使用 + 体验优化 + Claude 补验”。

### 结论 2 — 2026-03-11
背景：近期收尾事项中的 review 队列清理、真实任务观察和 backlog 归类已完成，剩余问题已不再属于 MVP 阻塞项。
结论：
- review 队列清理完成后，当前 durable memory 状态可进入真实使用。
- 真实任务观察通过后，boot-first、review show handoff 和文本三分叉可按当前规则继续使用。
- 延期项统一进入 post-MVP backlog，不再混入 v1 结论。

### 结论 3 — 2026-03-11
背景：v1 MVP 已收口，下一阶段需要开始规划 post-MVP 路线，但必须避免把远期平台化能力混入 v2 主线，重新放大范围。
结论：
- v2 主线只包含四项能力：自动会话提炼、语义检索 / 混合检索、review surface 提升、统一项目记忆面的目录收敛与运维策略。
- Claude 路径补验、Claude 结构化确认交互、review 摘要 / diff 展示优化继续归入 v1.x 体验优化，不纳入 v2 主线。
- 多租户、远程服务、图结构、alias、多跳关系等平台化方向明确降级为更后续版本议题，不参与 v2 范围定义。

### 结论 4 — 2026-03-11
背景：v1 通过把 `.memory/` 和 `.memoryhub/` 分层，先解决了 durable memory 的控制面问题，但从产品心智上看，它们仍然属于同一个项目记忆系统。若在 v2 继续把两者作为彼此独立的目录和工作流暴露给用户，会持续带来“该写哪里、该读哪里、如何保持一致”的认知负担。
结论：
- v2 需要把 `.memory/` 收敛为统一项目记忆根目录，而不是继续维持两个并列产品面。
- 用户侧应逐步收敛到统一的项目记忆工作流；旧 `.memoryhub` 只保留为 v1 过渡期历史背景，不再作为长期产品结构。
- 因此，v2 的重点是统一记忆面的路由、同步和运维策略，而不是继续为旧目录设计迁移或导出心智。
- v2 不要求立即合并为单一物理存储，但必须开始收敛为单一产品入口、单一路由规则和清晰的一致性策略。

### 结论 5 — 2026-03-11
背景：在制定 v2 roadmap 时，需要明确 durable store 的归属范围，以及是否允许通过中间过渡状态把统一目录、统一入口和能力增强混在一起推进。
结论：
- v2 固定为项目级系统，不是用户级单库；每个项目自己的 durable store 固定为 `.memory/_store/memory.db`。
- v2 roadmap 固定采用“先统一底座、再统一入口、再增强能力”的顺序，不做一次性大切换。
- 每个 phase 都必须具备独立发布、独立验收和独立回滚边界。
- Claude 增强交互收尾继续留在 v1.x 旁路线，不阻塞 v2 主线。

### 结论 6 — 2026-03-11
背景：在进一步讨论 v2 的统一记忆面时，明确了 docs lane 与 durable DB 的主从关系。若继续把 DB 视为所有知识的正文主库，会重新引入双正文和双版本链复杂度，与“正式项目知识主文档”目标冲突。
结论：
- `docs lane` 固定为正式项目知识主文档。
- DB 在 v2 中只承担最小控制面职责，而不是统一知识正文主库。
- `durable-only` 继续由 DB 主存；`docs-backed / dual-write` 以 docs 为正文主文档。
- `docs-backed / dual-write` 的版本与回滚回到 docs 侧；durable rollback 只保留给 `durable-only`。

### 结论 7 — 2026-03-11
背景：v2 进入 Phase 2B 后，需要先统一“怎么读”，让 agent 不再手工判断读 docs、catalog 还是 durable，同时把新的主入口与旧 durable flow 的关系定清。
结论：
- `project-memory` 成为统一项目记忆的主 skill，负责 docs / catalog / durable / review 的读取与路由。
- durable-specific workflow 收敛进 `project-memory` 内部 durable branch，不再保留独立可见 skill。
- `read_memory`、`search_memory` 与 `show_memory_review` 作为 Phase 2B 的统一读面落地；写入统一化留到后续 Phase 2C。
- 旧 `memory-read` / `catalog-read` 等原子 skill 不再是产品主入口。

### 结论 13 — 2026-03-11
背景：在 Phase 2F 后，仓库对外仍然可见 `durable-memory` skill，这与“对外只保留 `project-memory` 与 `memory-admin` 两个 skill”的 v2 目标不一致，也会让用户继续把 durable 分支误解为独立入口。
结论：
- `durable-memory` 的 boot-first、proposal routing、pending review split 与确认分流全部并入 `project-memory`。
- v2 对外只保留两个可见 skill：`project-memory` 与 `memory-admin`。
- durable memory 仍然保留为系统内部能力和 MCP/CLI 工作流，但不再以独立 skill 暴露。

### 结论 14 — 2026-03-11
背景：在移除独立 `durable-memory` 之后，仓库和全局 skill 安装中仍残留 `memory-read`、`memory-search`、`catalog-read` 等旧原子 skill。继续保留这批 skill，会让 v2 已经收敛好的统一入口再次裂开，也会让新会话继续暴露错误的产品心智。
结论：
- 旧 `memory-*` / `catalog-*` skill 从可见 skill surface 中移除。
- `project-memory` 成为唯一的项目记忆主入口；`memory-admin` 成为唯一的维护入口。
- 若仍需保留底层 CLI 命令，它们只作为内部执行器存在，不再通过独立 skill 直接暴露给用户或 agent。

### 结论 8 — 2026-03-11
背景：Phase 2C 需要统一写入入口，同时又不能让 DB 重新退化成所有知识的正文主库；此外，catalog 不应继续成为 agent 需要手工维护的显式步骤。
结论：
- 新统一写入口固定为 `capture_memory(kind=auto|docs|durable, ...)` 与 `update_memory(ref, mode=patch|append, ...)`。
- `docs-only` 与 `durable-only` 完整打通；`dual-write` 采用“docs 主文档 + durable 摘要 proposal + doc_ref 关联”的方式落地。
- docs 变更当前先以 inline preview 形式返回，不在 Phase 2C 引入持久 docs review surface；review surface uplift 继续留到 Phase 2D。
- catalog 更新与修复内化到 docs lane 写入流程，agent 默认不再手工拼 `memory.index + catalog.repair` 作为主写路径。

### 结论 9 — 2026-03-11
背景：Phase 2D 需要把 docs 轻审查从 Phase 2C 的 inline preview 升级为持久 review surface，同时保持 `docs lane` 为正文主文档、CLI 为权威审查执行面。
结论：
- docs 变更进入持久 `docs_change_review` 队列，不再在统一写入口里直接落盘。
- `show_memory_review` 与 `review list/show/approve/reject` 同时支持 durable review 和 docs change review。
- `dual-write` 改为“docs review + linked durable proposal”模型；批准 docs review 时同步批准关联的 durable proposal。
- `rollback` 仍只适用于 durable-only，不进入 docs review 语义。

### 结论 10 — 2026-03-11
背景：Phase 2E 需要在不引入远程搜索服务和 embedding 基础设施的前提下，提高统一项目记忆系统的 recall 质量，并让 `system://boot` 与 `scope=all` 不再依赖临时内联拼装。
结论：
- `_store/projections/boot.json` 与 `_store/projections/search.json` 成为统一 recall 投影视图。
- `read_memory(system://boot)` 改为读取 boot projection。
- `search_memory(scope=all)` 改为本地 hybrid recall：docs 文本匹配 + durable 结构化匹配 + 轻量 token overlap 语义分。
- hybrid recall 若被显式关闭，系统必须返回 lexical 降级，并通过 `degraded/degrade_reasons` 明示，不允许 silent fallback。

### 结论 11 — 2026-03-11
背景：Phase 2F 需要把“自动会话提炼”接入统一项目记忆系统，但又不能引入新的旁路状态机、直接写 active docs，或绕过已有 review / catalog / route 规则。
结论：
- Phase 2F 以本地 `session-extract` 入口落地，而不是新增一套独立 MCP 主接口。
- 会话提炼器只生成 `docs-only`、`durable-only`、`dual-write` 三类候选，并全部复用现有 `capture_memory / update_memory` unified write lane。
- docs / dual-write 候选进入 docs change review；durable-only 候选进入 durable proposal / review；不会直接写 active state。
- 提炼器允许显式标注 `docs[...]`、`durable[...]`、`dual[...]` 提高确定性；未标注时使用本地启发式分类与 hybrid recall 定位更新目标。

### 结论 12 — 2026-03-11
背景：v2 已被明确为新产品基线。继续为旧 `.memoryhub/`、旧目录布局或历史 DB 状态投入复杂迁移逻辑，只会把实现、测试和文档心智重新拖回兼容模式，收益低于手动处理成本。
结论：
- v2 不承担历史布局或旧 DB 状态的平滑自动迁移义务。
- 若遇到旧状态异常，优先显式报错并给出手动清理、重建或重新初始化指引，而不是继续叠加迁移补丁。
- 可以保留最小的内部 schema 演进机制，但不再把 migrate / compatibility 作为产品能力或主文档承诺。

### Post-MVP Backlog 分层

v1.x 体验优化：
- Claude 路径补验
- Claude 结构化确认交互验证
- review 摘要 / diff 展示优化

v2 主线：
- 自动会话提炼
- 语义检索 / 混合检索
- review surface 提升
- 统一项目记忆面的目录收敛与运维策略

更后续版本：
- 图结构、alias、多跳关系
- 多租户、远程部署
