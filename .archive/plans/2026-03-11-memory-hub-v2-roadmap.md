# Memory Hub v2 Roadmap

日期：2026-03-11  
状态：已冻结，作为 v2 主线实施基线

## 1. Summary

v2 的主线固定为：在保持当前 durable engine 可用的前提下，把当前分散的记忆入口收敛成一个项目级统一记忆系统。

固定前提：

- 唯一根目录：`.memory/`
- 项目级存储：每项目一套 `.memory/_store/memory.db`
- `docs lane` 是正式项目知识主文档
- DB 是最小控制面，不是统一知识正文主库
- `durable-only` 继续由 DB 主存
- `docs-backed / dual-write` 以 docs 为正文主文档
- docs-backed / dual-write 的版本与回滚回到 docs 侧
- durable rollback 只保留给 `durable-only`
- review 的权威执行面继续是 CLI

固定路线：

1. 先统一底座
2. 再统一入口
3. 再增强能力

每个 phase 都必须具备：

- 独立发布
- 独立验收
- 独立回滚

明确不在 v2 主线处理：

- 用户级单库
- 多租户、远程服务、图数据库
- 一次性大切换
- Claude 增强交互收尾

## 2. Phase 2A：统一目录与底座

目标：统一目录与 durable store 位置，但不改主 workflow。

交付：

- `.memory/manifest.json`
- `.memory/docs/...`
- `.memory/catalog/...`
- `.memory/_store/memory.db`
- 路径层统一以 `.memory/` 为唯一根

边界：

- durable CLI/MCP 名称与行为不改
- durable URI 不改
- 不把历史 `.memoryhub/` 目录迁移当成产品承诺

验收：

- 新项目只生成 `.memory/`
- durable 回归继续通过
- 不再暴露双顶层目录心智

## 3. Phase 2B：统一读取入口与主 skill

目标：统一“怎么读”，让 agent 不再手工判断读 docs、catalog 还是 durable。

交付：

- 新主 skill：`project-memory`
- 新统一读接口：
  - `read_memory(ref, anchor?)`
  - `search_memory(query, scope=docs|durable|all, type?, limit?)`
  - `show_memory_review(proposal_id|ref)`
- 统一 ref：
  - `system://...`
  - `doc://<bucket>/<name>`
  - `catalog://topics`
  - `catalog://modules/<name>`
  - 现有 durable URI
- durable-specific workflow 合并进 `project-memory` 内部 branch，不再保留独立可见 skill

保留：

- 当前 durable `read_memory/search_memory` 继续可用，但不作为主入口强调

验收：

- 普通 repo 知识读取不再要求拼 `catalog-read + memory-read`
- 旧 `memory-*` / `catalog-*` skill 不再出现在可见 skill surface 中
- `read_memory` 可统一读取 docs / catalog / durable / system
- `search_memory(scope=all)` 返回 lane 与统一 ref

## 4. Phase 2C：统一写入入口与 catalog 内化

目标：统一“怎么写”，并明确 docs 与 durable 的主从关系。

交付：

- 新统一写接口：
  - `capture_memory(kind=auto|docs|durable, ...)`
  - `update_memory(ref, mode=patch|append, ...)`
- 三种内部路由：
  - `docs-only`
  - `durable-only`
  - `dual-write`
- 路由语义固定为：
  - `docs-only`：正文只进 docs，走 docs 轻审查
  - `durable-only`：正文进 DB，走 durable proposal / review
  - `dual-write`：docs 为正文主文档，DB 只存 `doc_ref`、摘要、状态、索引
- catalog 自动更新 / 修复内化到 docs 写入流程
- 新维护 skill：`memory-admin`

保留：

- `propose_memory/propose_memory_update` 当前继续可用，但不属于 v2 主入口
- 人类仍可手工编辑 docs；agent 默认不能裸写 docs

验收：

- `capture_memory(kind=auto)` 稳定路由到 docs-only / durable-only / dual-write
- `update_memory` 正确处理 doc ref、approved durable-only ref、pending durable proposal ref
- catalog 自动维护且无脏索引

## 5. Phase 2D：Review surface 提升

目标：统一 review 展示层，但明确区分 durable review 与 docs 轻审查。

交付：

- `show_memory_review` 成为统一只读 review 入口
- review surface 同时展示：
  - `durable review`
  - `docs change review`
- CLI `review show` 使用同源数据视图
- `project-memory` 的 handoff 全部建立在统一 review 数据上

兼容：

- approve / reject / rollback 继续只由 CLI 执行
- MCP / UI 只展示和引导，不执行 rollback
- docs 轻审查不复用 durable proposal 状态机

验收：

- agent 不再需要解析 CLI 文本来理解 proposal / diff
- docs-only / dual-write / durable-only 三类对象都能统一展示
- CLI 仍是唯一权威执行面

## 6. Phase 2E：语义 / 混合检索

目标：在统一读写稳定后，再提升 recall 与搜索质量。

交付：

- `search_memory(scope=all)` 支持混合检索：
  - docs 文本检索
  - durable 结构化检索
  - 可扩展语义检索层
- 统一结果模型：
  - `ref`
  - `lane`
  - `source_kind`
  - `score`
  - `snippet`
- `system://boot` 生成改为基于统一投影视图

兼容：

- 本地优先，不引入远程搜索服务
- 语义层不可用时显式降级

验收：

- `scope=all` 稳定返回 docs + durable 混合结果
- 排序、来源、降级都可解释

## 7. Phase 2F：自动会话提炼

目标：最后接入自动沉淀，并严格复用统一写入面。

交付：

- 会话提炼器只生成统一候选：
  - docs candidate
  - durable candidate
  - dual-write candidate
- 所有候选进入 unified write lane：
  - docs 候选进入 docs 轻审查变更流
  - durable 候选进入 durable proposal / review
  - dual-write 候选写 docs 主文档，并同步 DB 摘要 / 引用

兼容：

- 不自动 approve durable proposal
- 不自动直接写 active docs
- 不绕过 review / catalog / route 规则

验收：

- 自动提炼不会直接改 `.memory/docs/*` 或 active durable state
- durable 候选继续走 review
- docs / dual-write 候选进入统一应用流

## 8. Public Interfaces

最终主入口：

- Skill：
  - `project-memory`
  - `memory-admin`
- MCP：
  - `read_memory(ref, anchor?)`
  - `search_memory(query, scope, type?, limit?)`
  - `capture_memory(...)`
  - `update_memory(...)`
  - `show_memory_review(...)`

当前保留的次级入口：

- durable MCP legacy 入口：
  - `read_memory`
  - `search_memory`
  - `propose_memory`
  - `propose_memory_update`
- CLI 权威入口继续保留：
  - `review approve`
  - `review reject`
  - `rollback`

## 9. Implementation Rules

- v2 仍是项目级系统，不是用户级单库
- `docs lane` 是正式项目知识主文档
- DB 是最小控制面，不是统一知识正文主库
- docs-backed / dual-write 的版本与回滚回到 docs 侧
- durable rollback 只保留给 durable-only
- docs 变更默认采用轻审查，而不是 durable proposal 状态机
- Claude 增强交互不阻塞 v2 主线
- 历史布局或旧 DB 状态异常时，优先显式报错与手动处理，不把自动迁移当成产品承诺

## 10. Follow-up Candidate：新项目 Bootstrap / Intake

定位：

- 该项作为当前冻结 v2 基线之外的后续候选，不改写 2A~2F 的 phase 定义
- 目标是补齐“`init` 只创建骨架，不负责首轮项目认知初始化”的产品缺口
- 入口优先收敛到 `memory-admin`，不新增第三个可见 skill

目标：

- 让一个全新项目从“尚未接入 `.memory/`”到“拥有首批可审查的项目记忆候选”形成单条流程
- 降低 agent 首次接入项目时手工拼装扫描步骤的负担
- 保持 `project-memory` 作为日常主入口，bootstrap 只负责首次接入和必要的 intake refresh

建议流程：

1. 检测目标项目是否缺少 `.memory/`
2. 若缺失，先运行 `memory-hub init --project-root <repo>`
3. 扫描仓库基础上下文：
   - repo 文件地图
   - `README`
   - 语言/包管理清单
   - CI / test 配置
   - 主入口与核心目录
4. 生成首批项目知识候选：
   - tech stack
   - run / build / test 方式
   - 模块边界与目录地图
   - 开发约定与关键约束
5. 候选统一进入既有 write lane：
   - 默认优先 `docs-only`
   - 只有跨会话且代码中不可稳定恢复的信息才进入 `durable-only` 或 `dual-write`
6. 进入既有 review handoff，并在结束时执行 `catalog-repair`

边界：

- 不直接写 active docs
- 不绕过 durable review 或 docs review
- 不把 bootstrap 变成新的通用 MCP 主入口
- 不在首次扫描时默认制造 durable 噪音
- 若 `.memory/` 已存在，应降级为非破坏性的 intake refresh，而不是重新 init

候选交付：

- `memory-admin` 下的新项目 bootstrap / intake workflow
- 面向 agent 的固定首轮扫描顺序与最小信息集
- 缺少 `.memory/` 时的明确错误提示与下一步引导

候选验收：

- 新项目可在一次流程内完成 `.memory/` 初始化与首批知识候选生成
- 首轮扫描输出至少覆盖 tech stack、运行/测试方式、核心模块地图
- 全流程继续复用现有 unified write lane 与 review surface
- 已初始化项目重复执行时不会破坏现有 docs / durable state

## 11. Follow-up Candidate：End-of-Task Probe

定位：

- 该项作为当前冻结 v2 基线之外的后续候选，不改写 2A~2F 的 phase 定义
- 目标是补齐“任务结束后经常没有再检查一次本次工作是否值得沉淀”的 workflow 缺口
- 该能力是内部收尾步骤，不新增新的公开 skill / MCP 主入口

目标：

- 让 agent 在 task-oriented 会话结束前，默认做一次高阈值记忆自检
- 让记忆沉淀从“用户提醒才做”变成“默认检查，允许 NOOP”
- 继续复用现有 unified write lane、review surface 与 boot-first discipline

边界：

- 不是每一轮对话都触发，而是每个任务结束前最多触发一次
- 不自动 approve docs review 或 durable proposal
- 不直接写 active docs 或 approved durable state
- 仍然优先 `NOOP`，并对 durable 维持高门槛

候选交付：

- 一个内部 `end-of-task probe` workflow
- 固定的三问自检模板与 `NOOP` 判定规则
- 与 Phase 2F 提炼逻辑共享的分类 / 去重 / update-target 定位能力

参考设计：

- `.archive/plans/2026-03-11-memory-hub-end-of-task-probe-design.md`
