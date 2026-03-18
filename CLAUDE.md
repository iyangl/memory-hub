# Memory Hub — 使用规则

## 三个 Command

| Command | 触发 | 作用 |
|---------|------|------|
| `/memory-hub:init` | 首次接入项目 | 扫描项目，生成初始记忆 |
| `/memory-hub:recall` | 会话开始时 | 加载 BRIEF.md 到上下文 |
| `/memory-hub:save` | 会话结束前 | 提炼知识，合并到 docs |

模板位于 `.claude/commands/memory-hub/`，按步骤执行即可。

## Layer 2（最佳努力）

工作过程中如果产生了新知识（决策、约束、约定），
可以写入 `.memory/inbox/` 暂存。`/memory-hub:save` 时会合并。

写入方式：Write 工具 → `.memory/inbox/{ISO时间戳}_{短名}.md`

格式：纯 markdown，不需要 frontmatter。内容是提炼后的结论。

不写入的场景：只读了代码、只执行了已有方案、没产生新的"为什么"或"不要什么"。

## 存储结构

```
.memory/
  BRIEF.md          ← 派生摘要（/recall 读取）
  docs/             ← 唯一正本（所有知识在这里）
    architect/      ← 架构决策、技术选型
    dev/            ← 开发约定、编码规范
    pm/             ← 产品决策、需求结论
    qa/             ← 测试策略、质量约定
  catalog/          ← 派生索引（定位用）
    topics.md
    modules/
  inbox/            ← Layer 2 临时写入区
```

## 硬边界

- 不直接编辑 `.memory/docs/`（由 `/memory-hub:save` 负责）
- 不直接编辑 `.memory/catalog/`（由 CLI 负责）
- 不直接编辑 `.memory/BRIEF.md`（由 CLI 生成）

## 维护

```bash
python3 -m lib.cli catalog-repair
python3 -m lib.cli brief
```

## CLI 命令

```bash
memory-hub init                # 创建 .memory/ 骨架
memory-hub read <bucket> <file> [--anchor <heading>]
memory-hub list <bucket>
memory-hub search "<query>"
memory-hub index <bucket> <file> --topic <name> --summary "<desc>"
memory-hub catalog-read [topics|<module>]
memory-hub catalog-update --file <path>
memory-hub catalog-repair
memory-hub brief               # 重建 BRIEF.md
```
