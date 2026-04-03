# Memory Hub

面向 AI 助手的文件型项目记忆系统，采用 recall-first 工作流：先定位，再决定读取哪些知识，最后只把值得长期保留的结论写回 durable docs。

## 核心原则

- `.memory/docs/` 是唯一正本；`BRIEF.md`、`catalog/`、`session/` 都是派生产物
- 三个 command 驱动主循环：`init / recall / save`
- recall 不是“把所有资料都读一遍”，而是先做 `recall-plan`，再按 `skip | light | deep` 决定读取范围
- deep recall 通过 `working-set` 组装任务级上下文；当前可将其视为 `resume-pack(v1)`，working set 会做压缩、去重、限长，并显式给出 `primary_evidence_gap` 与 `verification_focus`
- 在 `working-set(resume-pack)` 之后，可继续生成 `execution-contract` 作为 act 前的机器可读边界
- 保存阶段遵守 `Read Before Write`，并显式判定 `noop | create | append | merge | update`
- `memory-hub save --file <save.json>` 是代码级 correctness core：非 `noop` 必须带 search/read evidence，写后自动重建 `BRIEF.md` 与 `catalog-repair`
- 只沉淀代码本身读不到的长期知识，例如决策、约束、风险、验证重点、业务口径

## 适用场景

- 会话会跨天、跨人接力
- 项目存在稳定的决策、约束、测试策略，需要反复 recall
- 希望把“应该先看什么、为什么看、看完要验证什么”固化成导航产物

## 安装

### 前置条件

- Python 3.10+
- 运行时无第三方依赖

### 直接运行

```bash
py -3 -m lib.cli <command> [args]
# 例如：py -3 -m lib.cli scan-modules --out .memory/session/scan-modules.json
```

### pip 安装

```bash
pip install -e .
memory-hub <command> [args]
```

## 存储结构

```text
.memory/
  BRIEF.md          <- base brief，/recall 的 boot summary
  manifest.json     <- 布局版本
  docs/             <- 唯一正本
    architect/      <- 架构决策、技术选型
    dev/            <- 开发约定、编码规范
    pm/             <- 产品决策、需求结论
    qa/             <- 测试策略、质量约定
  catalog/          <- 派生索引
    topics.md       <- 全局 topics 索引
    modules/        <- 模块导航卡
  inbox/            <- Layer 2 临时写入区
  session/          <- recall-plan / working-set / execution-contract / save-request 等会话产物
```

## 三个 Command

| Command | 平台 | 作用 |
|---------|------|------|
| `/memory-hub:init` | Claude Code slash command | 首次接入项目时建立 recall-first 骨架，并按初始化流程生成基础 docs 与派生产物 |
| `/memory-hub:recall` | Claude Code slash command | 读取 `BRIEF.md`，执行 `recall-plan`，按需进入 light/deep recall |
| `/memory-hub:save` | Claude Code slash command | 提炼 durable knowledge，生成 `save-request`，调用 `save` core 并重建派生产物 |

其他 host 可复用 `.claude/commands/memory-hub/` 中的同名模板流程。

在 Windows 环境下，优先使用 `py -3 -m lib.cli ...`。

## Recall-first 运行模型

1. **首次接入**：运行 `init`，建立 `.memory/` 骨架，并按初始化流程生成基础 docs、catalog、`BRIEF.md`；若 `.memory/` 已存在，`init` 会直接返回 `ALREADY_INITIALIZED`
2. **会话开始**：运行 `recall`，先读 base brief，再执行 `recall-plan`
3. **Search Before Guess**：如果 planner 返回 `search_first = true`，先搜索和定位，再决定读哪些 docs / module cards
4. **按需深入**：
   - `skip`：直接开始工作或只补读极少量来源
   - `light`：读取 base brief + 少量相关 docs / module cards
   - `deep`：构建压缩后的 `working-set`（当前按 `resume-pack(v1)` 理解），把高相关来源整理成任务级上下文，并优先暴露 `primary_evidence_gap` 与 `verification_focus`；必要时再生成 `execution-contract`，把 act 前边界固定下来
5. **工作过程**：如产生新知识，可把候选结论暂存到 `.memory/inbox/`
6. **会话结束**：运行 `save`，通过后悔测试筛选 durable knowledge，显式判定 `noop/create/append/merge/update`，再调用 `save` core 执行写入与重建

## 关键产物

### `BRIEF.md`

- base brief / boot summary
- 供 `/memory-hub:recall` 优先读取
- 是派生产物，不直接手改

### `catalog/topics.md` 与 `catalog/modules/*.md`

- 用于定位知识和模块导航
- 模块卡关注“何时阅读、入口、阅读顺序、约束、风险、验证重点”
- 由 `scan-modules --out ...` / `catalog-update --file <scan-json>` / `catalog-repair` 维护

### `session/*`

- 保存当前任务的 recall plan、working set、execution-contract、save request、save trace 等会话产物（例如 `*.json`）
- `save-trace` 推荐落在 `.memory/session/save-trace/`，采用每次 save 一个独立 artifact 的模型
- 只服务当前会话或当前任务
- 不应原样写回长期 docs

## CLI 命令

```bash
memory-hub init
memory-hub read <bucket> <file> [--anchor <heading>]
memory-hub list <bucket>
memory-hub search "<query>"
memory-hub index <bucket> <file> --topic <name> --summary "<desc>"
memory-hub catalog-read [topics|<module>]
memory-hub catalog-update --file <path>
memory-hub catalog-repair
memory-hub brief
memory-hub scan-modules [--out <file>]
memory-hub recall-plan --task "<task>" [--out <file>]
memory-hub working-set --plan-file <path> [--out <file>]
memory-hub execution-contract --working-set-file <path> [--out <file>]
memory-hub save --file <path>
memory-hub inbox-list
memory-hub inbox-clean [--before <ISO>]
memory-hub modules-check
```

## Save Core 约束

- 非 `noop` entry 必须带 `evidence.search_queries` 与 `evidence.read_refs`
- `append / merge / update` 必须先读取目标 doc
- `create` 必须带 `index.topic / index.summary`
- `append` 只允许新增 heading；重复 heading 会失败
- `update` 必须说明 `payload.supersedes`
- `update` 的 supersedes 追溯信息会尽力写入 `.memory/session/save-trace/<artifact>.json`，用于记录被替换目标、替换原因与前后摘要；trace 写入失败不会回滚 durable docs
- `save` 返回值中的 `data.trace` 形状为 `{ update_supersedes, trace_file, warning }`；`trace_file` 使用仓库内相对路径，并指向当前这次 save 生成的单个 trace artifact
- 旧的 `.memory/session/save-trace.jsonl` 视为 legacy session artifact：新实现不再读取它，可安全忽略或删除
- 本设计只解决 trace artifact 的并发覆盖问题，不承诺解决整个 `save` 流程的并发安全
- working set 不能原样写回 docs
- 只要发生非 `noop` durable 写入，就会自动重建 `BRIEF.md` 并执行 `catalog-repair`

## 硬边界

- 不直接编辑 `.memory/docs/`；只有初始化阶段允许 `/memory-hub:init` 生成初始 docs，其余长期知识由 `save` 流程和 `memory-hub save --file <save.json>` 维护
- 不直接编辑 `.memory/catalog/`，导航索引由 CLI 维护
- 不直接编辑 `.memory/BRIEF.md`，它始终由 `brief` 重建
- `working-set` 只用于任务级 recall，不可原样回灌到 docs
- `noop` 是合法结果，不需要“为了保存而保存”

## 测试

```bash
pytest -q
```

## 退出码

- `0` 成功
- `1` 业务错误
- `2` 系统错误

## 许可

MIT
