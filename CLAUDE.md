# Memory Hub — Claude Code 使用规则

## 三个 Command

| Command | 触发 | 作用 |
|---------|------|------|
| `/memory-hub:init` | 首次接入项目，或 `.memory/` 尚不存在时 | 创建显式记忆所需的最小骨架 |
| `/memory-hub:recall` | 会话开始时，或长会话中上下文变模糊时 | 默认执行 `search -> read`，只加载与当前任务直接相关的 durable docs |
| `/memory-hub:save` | 会话结束前 | 提炼 durable knowledge，生成 `save-request`，调用 `save` core 执行写入 |

模板位于 `.claude/commands/memory-hub/`，按步骤执行即可。

## 显式记忆规则

- `.memory/docs/` 是唯一正本；默认 recall 只依赖 durable docs 本身
- recall 的核心是“先 search，再决定读什么”，不是把所有文档都读一遍
- 默认不读取 `BRIEF.md`
- 默认不执行 `recall-plan` / `working-set` / `execution-contract`
- `brief` / `catalog/` / module cards 只作为 legacy/兼容能力保留，不再是默认前置
- Phase 2 之前，底层 core 若仍会生成部分 legacy 产物，也不应被默认 workflow 消费
- 保存阶段默认走 `memory-hub save --file <save.json>` correctness core
- 每条候选知识都要显式判定为 `noop | create | append | merge | update`
- 非 `noop` 保存必须提供 search + read evidence，且 working set 不能原样落长期 docs
- `create` 不强制要求 `index`；若提供 `index`，则继续维护 legacy `topics.md`
- `noop` 是合法成功结果，不需要为了保存而保存

## Layer 2（最佳努力）

工作过程中如果产生了新知识（决策、约束、约定、验证重点），可以写入 `.memory/inbox/` 暂存。`/memory-hub:save` 时再决定是否进入长期 docs。

写入方式：Write 工具 → `.memory/inbox/{ISO时间戳}_{短名}.md`

格式：纯 markdown，不需要 frontmatter。内容应是提炼后的结论，不是 working set 原文。

不写入的场景：只读了代码、只执行了已有方案、没有新增的“为什么 / 不要什么 / 要验证什么”。

## Repo 协作产物路由（本项目约定）

以下规则只用于本仓库的协作与接力，不属于 memory-hub 通用数据模型：

- `.memory/inbox/`：Layer 2 临时候选知识；不要求跨设备保留，不作为 Git-tracked handoff 材料
- `.memory/session/`：当前任务 / 当前会话的运行态产物；不要求跨设备保留，不作为 Git-tracked handoff 材料
- 需要 Git 跟踪的设计草案、实施计划、跨电脑接力材料：统一写入 `.claude/plan/`
- 只有确认应进入长期知识库的内容，才通过 `/memory-hub:save` 进入 `.memory/docs/`

换句话说：`record this / 记录下来` 若目的是为了后续开发接力，应优先落到 `.claude/plan/`；若目的是暂存候选知识，再写入 `.memory/inbox/`。

## 存储结构

```text
.memory/
  manifest.json     <- 布局版本
  docs/             <- 唯一正本（所有长期知识都在这里）
    architect/      <- 架构决策、技术选型
    dev/            <- 开发约定、编码规范
    pm/             <- 产品决策、需求结论
    qa/             <- 测试策略、质量约定
  catalog/          <- legacy 派生索引（兼容用）
    topics.md
    modules/
  inbox/            <- Layer 2 临时写入区
  session/          <- save-request / save-trace 等会话产物
```

## 硬边界

- 不直接编辑 `.memory/docs/`（仅 `/memory-hub:init` 创建基础文件；其余长期知识由 `/memory-hub:save` 和 `memory-hub save --file <save.json>` 负责）
- 不直接编辑 `.memory/catalog/` 来伪造 legacy 索引
- `working-set` 不能原样写回 docs
- `BRIEF.md` / `catalog/` 不再是默认流程成功前提

## 维护

```bash
py -3 -m lib.cli catalog-repair
py -3 -m lib.cli brief
```

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
