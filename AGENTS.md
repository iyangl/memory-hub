# Memory Hub — Codex 使用规则

## 三个 Command

| Command | 触发方式 | 作用 |
|---------|----------|------|
| 初始化记忆 | 用户说“初始化记忆” / “init memory” | 建立 recall-first 骨架、基础 docs、catalog、`BRIEF.md` |
| 加载记忆 | 用户说“加载记忆” / “recall memory” | 读取 `BRIEF.md`，执行 `recall-plan`，按需进入 light/deep recall |
| 保存记忆 | 用户说“保存记忆” / “save memory” | 提炼 durable knowledge，生成 `save-request`，调用 `save` core 并重建派生产物 |

Codex 没有 slash command，按 `.claude/commands/memory-hub/init.md`、`recall.md`、`save.md` 的模板步骤执行。

## Recall-first 协议

### 初始化记忆

- 若 `.memory/` 不存在，先运行 `py -3 -m lib.cli init`
- 读取实际项目文件，补齐高价值 docs
- 运行 `scan-modules --out ...` 生成模块导航脚手架
- 运行 `catalog-update` / `catalog-repair` / `brief`，产出导航卡和 base brief

### 加载记忆

- 先确保 `.memory/`、`BRIEF.md`、catalog 已存在
- 先读 `BRIEF.md` 作为 boot summary
- 对当前任务执行 `py -3 -m lib.cli recall-plan --task "..." --out .memory/session/recall-plan.json`
- 根据 planner 结果决定 `skip | light | deep`
- 若 `search_first = true`，必须先 search / catalog-read / read，再决定来源
- 若为 `deep`，执行 `py -3 -m lib.cli working-set --plan-file .memory/session/recall-plan.json`
- working set 是压缩、去重、限长后的任务上下文，保留来源、原因和 evidence gaps

### 保存记忆

- 候选来源包括 `.memory/inbox/`、当前会话结论、working set 中已确认的长期知识
- 先做后悔测试，不值得长期记忆的内容直接判定为 `noop`
- 所有非 `noop` 写入都必须先 search，再 read 目标 doc
- 每条候选必须显式归类为：`noop | create | append | merge | update`
- 将保存决策整理为 `save-request.json`
- 运行 `py -3 -m lib.cli save --file .memory/session/save-request.json`
- `save` core 会强校验 evidence、阻止 working-set 原样写回，并在非 `noop` 后自动重建 `BRIEF.md` 与 `catalog-repair`

## Layer 2（最佳努力）

工作过程中如果产生了新知识（决策、约束、约定、验证重点），可以写入 `.memory/inbox/` 暂存；保存记忆时再决定是否进入长期 docs。

写入方式：直接写入 `.memory/inbox/{ISO时间戳}_{短名}.md`

格式：纯 markdown，不需要 frontmatter。内容是提炼后的结论，而不是 working set 原文。

## 存储结构

```text
.memory/
  BRIEF.md          <- base brief（加载记忆时优先读取）
  manifest.json     <- 布局版本
  docs/             <- 唯一正本
    architect/
    dev/
    pm/
    qa/
  catalog/          <- 派生索引（topics + module cards）
    topics.md
    modules/
  inbox/            <- Layer 2 临时写入区
  session/          <- recall-plan / working-set / save-request 等会话产物
```

## 硬边界

- 不直接编辑 `.memory/docs/`（由保存记忆流程和 `save` core 负责）
- 不直接编辑 `.memory/catalog/`（由 CLI 负责）
- 不直接编辑 `.memory/BRIEF.md`（由 `brief` 重建）
- 不允许跳过 `Read Before Write`
- 不允许把 `working-set` 原样写回长期 docs
- `noop` 是合法成功结果

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
memory-hub save --file <path>
```

## 测试

```bash
pytest -q
```

## 退出码

- `0` 成功
- `1` 业务错误
- `2` 系统错误
