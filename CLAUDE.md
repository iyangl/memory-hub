# Memory Hub — Claude Code 使用规则

## 三个 Command

| Command | 触发 | 作用 |
|---------|------|------|
| `/memory-hub:init` | 首次接入项目，或 `.memory/` 尚不存在时 | 建立 recall-first 骨架、基础 docs、catalog、`BRIEF.md` |
| `/memory-hub:recall` | 会话开始时，或长会话中上下文变模糊时 | 读取 `BRIEF.md`，执行 `recall-plan`，按需进入 light/deep recall |
| `/memory-hub:save` | 会话结束前 | 提炼 durable knowledge，生成 `save-request`，调用 `save` core 并重建派生产物 |

模板位于 `.claude/commands/memory-hub/`，按步骤执行即可。

## Recall-first 规则

- `.memory/docs/` 是唯一正本；`BRIEF.md`、`catalog/`、`session/` 都是派生产物
- recall 的核心是“先定位，再决定读什么”，不是把所有文档都读一遍
- 对当前任务先做 `recall-plan`，再根据 `skip | light | deep` 选择读取范围
- 若 `search_first = true`，必须先 search / catalog-read / read，再决定来源
- deep recall 使用 `working-set` 组织任务级上下文；working set 会做去重、压缩、限长，并偏向决策 / 约束 / 风险 / 验证
- 保存阶段默认走 `memory-hub save --file <save.json>` correctness core
- 每条候选知识都要显式判定为 `noop | create | append | merge | update`
- 非 `noop` 保存必须提供 search + read evidence，且 working set 不能原样落长期 docs
- `noop` 是合法成功结果，不需要为了保存而保存

## Layer 2（最佳努力）

工作过程中如果产生了新知识（决策、约束、约定、验证重点），可以写入 `.memory/inbox/` 暂存。`/memory-hub:save` 时再决定是否进入长期 docs。

写入方式：Write 工具 → `.memory/inbox/{ISO时间戳}_{短名}.md`

格式：纯 markdown，不需要 frontmatter。内容应是提炼后的结论，不是 working set 原文。

不写入的场景：只读了代码、只执行了已有方案、没有新增的“为什么 / 不要什么 / 要验证什么”。

## 存储结构

```text
.memory/
  BRIEF.md          <- base brief，/recall 的 boot summary
  manifest.json     <- 布局版本
  docs/             <- 唯一正本（所有长期知识都在这里）
    architect/      <- 架构决策、技术选型
    dev/            <- 开发约定、编码规范
    pm/             <- 产品决策、需求结论
    qa/             <- 测试策略、质量约定
  catalog/          <- 派生索引（定位用）
    topics.md
    modules/
  inbox/            <- Layer 2 临时写入区
  session/          <- recall-plan / working-set / save-request 等会话产物
```

## 硬边界

- 不直接编辑 `.memory/docs/`（由 `/memory-hub:save` 和 `memory-hub save --file <save.json>` 负责）
- 不直接编辑 `.memory/catalog/`（由 CLI 负责）
- 不直接编辑 `.memory/BRIEF.md`（由 `brief` 生成）
- `working-set` 不能原样写回 docs
- `save` core 会自动重建 `BRIEF.md` 与 `catalog-repair`，不要手工伪造结果

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
memory-hub inbox-list
memory-hub inbox-clean [--before <ISO>]
memory-hub modules-check
```
