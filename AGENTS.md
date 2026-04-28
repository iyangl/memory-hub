# Memory Hub — Codex 使用规则

## 三个 Command

| Command | 触发方式 | 作用 |
|---------|----------|------|
| 初始化记忆 | 用户说“初始化记忆” / “init memory” | 创建显式记忆所需的最小骨架 |
| 加载记忆 | 用户说“加载记忆” / “recall memory” | 默认执行 `search -> read`，只加载与当前任务直接相关的 durable docs |
| 保存记忆 | 用户说“保存记忆” / “save memory” | 提炼 durable knowledge，生成 `save-request`，调用 `save` core 执行写入 |

Codex 没有 slash command，按 `.claude/commands/memory-hub/init.md`、`recall.md`、`save.md` 的模板步骤执行。

## 显式记忆协议

### 初始化记忆

- 若 `.memory/` 不存在，先运行 `python3 -m lib.cli init`
- 默认只把 `init` 当作最小骨架入口；Phase 2 之前，底层 core 若仍顺带生成 legacy 产物，也不作为后续前置
- 不再在初始化阶段补齐高价值 docs 或扫描模块

### 加载记忆

- 默认主路径是 `search -> read`
- 对当前任务先执行 `python3 -m lib.cli search "..."`
- 只读取与当前任务直接相关的 durable docs：`python3 -m lib.cli read <bucket> <file>`
- 可选用 `python3 -m lib.cli list <bucket>` 辅助定位
- 无命中时，直接说明没有可复用显式记忆，并转入源码或当前任务上下文
- `brief` / `catalog-read` / `recall-plan` / `working-set` / `execution-contract` 都只作为 legacy/兼容能力，不是默认路径

### 保存记忆

- 候选来源包括 `.memory/inbox/` 与当前会话中明确成立的长期结论
- 先做后悔测试，不值得长期记忆的内容直接判定为 `noop`
- 所有非 `noop` 写入都必须先 search，再 read 目标 doc
- 每条候选必须显式归类为：`noop | create | append | merge | update`
- 将保存决策整理为 `save-request.json`
- 运行 `python3 -m lib.cli save --file .memory/session/save-request.json`
- `save` core 会强校验 evidence，并阻止 working-set 原样写回；legacy `topics.md` 仅在提供 `index` 时维护

## Layer 2（最佳努力）

工作过程中如果产生了新知识（决策、约束、约定、验证重点），可以写入 `.memory/inbox/` 暂存；保存记忆时再决定是否进入长期 docs。

写入方式：直接写入 `.memory/inbox/{ISO时间戳}_{短名}.md`

格式：纯 markdown，不需要 frontmatter。内容是提炼后的结论，而不是 working set 原文。

## 存储结构

```text
.memory/
  manifest.json     <- 布局版本
  docs/             <- 唯一正本
    architect/
    dev/
    pm/
    qa/
  catalog/          <- legacy/兼容索引
    topics.md
    modules/
  inbox/            <- Layer 2 临时写入区
  session/          <- save-request / save-trace 等会话产物
```

## 硬边界

- 不直接编辑 `.memory/docs/`（初始化记忆创建基础文件除外；其余长期知识由保存记忆流程和 `save` core 负责）
- 不允许跳过 `Read Before Write`
- 不允许把 `working-set` 原样写回长期 docs
- `noop` 是合法成功结果
- `BRIEF.md` / `catalog/` 不再是默认流程前置条件

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

## 测试

```bash
pytest -q
```

## 退出码

- `0` 成功
- `1` 业务错误
- `2` 系统错误
