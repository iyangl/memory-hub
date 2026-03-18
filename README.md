# Memory Hub

文件型项目知识库，为 AI 助手提供按需检索的项目记忆。

## 核心原则

- docs/ 是唯一正本，BRIEF.md 和 catalog/ 都是派生产物
- 三个 command 驱动：init / recall / save
- 只沉淀代码读不到的信息
- 纯文件存储，无外部依赖

## 安装

### 前置条件

- Python 3.10+
- 运行时无第三方依赖

### 直接运行

```bash
python3 -m lib.cli <command> [args]
```

### pip 安装

```bash
pip install -e .
memory-hub <command> [args]
```

## 存储结构

```
.memory/
  BRIEF.md          <- 派生摘要（/recall 读取）
  manifest.json     <- 布局版本
  docs/             <- 唯一正本
    architect/      <- 架构决策、技术选型
    dev/            <- 开发约定、编码规范
    pm/             <- 产品决策、需求结论
    qa/             <- 测试策略、质量约定
  catalog/          <- 派生索引
    topics.md
    modules/
  inbox/            <- Layer 2 临时写入区（不跟踪 git）
```

## 三个 Command

| Command | 平台 | 作用 |
|---------|------|------|
| `/memory-hub:init` | Claude Code slash command | 首次扫描项目，生成初始记忆 |
| `/memory-hub:recall` | Claude Code slash command | 加载 BRIEF.md 到上下文 |
| `/memory-hub:save` | Claude Code slash command | 提炼知识，合并到 docs |

Codex 用户：按 AGENTS.md 中的触发词调用，执行相同的模板流程。

模板位于 `.claude/commands/memory-hub/`。

### 运行模型

```
会话开始           工作过程            会话结束
   |                 |                  |
/recall          Layer 2 写入       /save
读 BRIEF.md      inbox 暂存         inbox -> docs
注入上下文       （最佳努力）        重建 BRIEF.md
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
memory-hub catalog-repair      # 修复 catalog 索引
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

## 许可

MIT
