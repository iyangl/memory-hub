# Memory Hub — Codex 使用规则

## 三个 Command

| Command | 触发方式 | 作用 |
|---------|----------|------|
| 初始化记忆 | 用户说"初始化记忆"/"init memory" | 扫描项目，生成初始记忆 |
| 加载记忆 | 用户说"加载记忆"/"recall memory" | 加载 BRIEF.md 到上下文 |
| 保存记忆 | 用户说"保存记忆"/"save memory" | 提炼知识，合并到 docs |

### 执行方式

Codex 没有 slash command，按以下流程执行：

**初始化记忆**：按 `.claude/commands/memory-hub/init.md` 的步骤执行。

**加载记忆**：按 `.claude/commands/memory-hub/recall.md` 的步骤执行。

**保存记忆**：按 `.claude/commands/memory-hub/save.md` 的步骤执行。

## Layer 2（最佳努力）

工作过程中如果产生了新知识（决策、约束、约定），
可以写入 `.memory/inbox/` 暂存。保存记忆时会合并。

写入方式：直接写入 `.memory/inbox/{ISO时间戳}_{短名}.md`

格式：纯 markdown，不需要 frontmatter。内容是提炼后的结论。

## 存储结构

```
.memory/
  BRIEF.md          <- 派生摘要（加载记忆时读取）
  docs/             <- 唯一正本（所有知识在这里）
    architect/      <- 架构决策、技术选型
    dev/            <- 开发约定、编码规范
    pm/             <- 产品决策、需求结论
    qa/             <- 测试策略、质量约定
  catalog/          <- 派生索引（定位用）
    topics.md
    modules/
  inbox/            <- Layer 2 临时写入区
```

## 硬边界

- 不直接编辑 `.memory/docs/`（由保存记忆流程负责）
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

## 测试

```bash
pytest -q
```

## 退出码

- `0` 成功
- `1` 业务错误
- `2` 系统错误
