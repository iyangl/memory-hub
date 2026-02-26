# Memory Hub

项目知识库 + 按需检索。让 AI 在工作过程中主动取到所需的上下文，而不是靠用户每次手动喂，也不是会话开始一次性加载大包。

## 核心理念

**只存代码读不到的内容**：设计决策、约束集、演进历史、隐性前提、已知取舍。

**脚本是执行器，AI 是决策者**。所有脚本返回统一 JSON envelope，AI 通过 Skill 提示词驱动工作流。无服务进程、无数据库、无协议层。

## 安装

### 前置条件

- Python 3.10+
- 无外部依赖（纯标准库）

### 方式一：直接使用（推荐）

```bash
# 从项目根目录运行
python3 -m lib.cli <command> [args]
```

### 方式二：pip 安装

```bash
pip install -e .

# 安装后可直接使用
memory-hub <command> [args]
```

## 存储结构

```
.memory/
├── pm/decisions.md            # 需求结论与产品决策
├── architect/
│   ├── tech-stack.md          # 技术栈、关键依赖、使用方式与限制
│   └── decisions.md           # 设计决策日志（Decision Log 格式）
├── dev/conventions.md         # 代码约定、命名规则、模式
├── qa/strategy.md             # 测试策略与质量约束
└── catalog/
    ├── topics.md              # 轻量目录：所有内容的统一入口
    └── modules/               # 详细索引：每个功能域一个文件
```

## CLI 命令

### 初始化

```bash
memory-hub init
```

创建 `.memory/` 目录骨架和基础文件模板。已存在时返回 `ALREADY_INITIALIZED`。

### 知识读写

```bash
# 读取
memory-hub read <bucket> <file> [--anchor <heading>]

# 写入（内容通过 stdin 传入）
memory-hub write <bucket> <file> --topic <name> --summary "<desc>" [--mode append|overwrite] <<'EOF'
<markdown content>
EOF

# 列出桶内文件
memory-hub list <bucket>

# 跨桶全文检索
memory-hub search "<query>"
```

### Catalog 索引管理

```bash
# 读取索引
memory-hub catalog-read [topics|<module>]

# 更新代码模块索引（JSON 通过 stdin 传入）
memory-hub catalog-update <<'EOF'
{"modules": [{"name": "...", "summary": "...", "files": [{"path": "...", "description": "..."}]}]}
EOF

# 一致性检查与自愈
memory-hub catalog-repair
```

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 业务错误（详见 `code` 字段） |
| 2 | 系统错误 |

## AI Skill 集成

Memory Hub 通过 Skill 提示词与 AI 编码助手集成。`skills/` 目录包含 8 个原子 Skill：

| Skill | 说明 |
|-------|------|
| `memory-init` | 初始化 `.memory/` 并扫描项目生成知识库 |
| `memory-read` | 精准读取某个桶的某个文件 |
| `memory-list` | 列出桶内所有文件 |
| `memory-search` | 跨桶全文检索 |
| `memory-write` | 写知识文件 + 自动更新 topics.md |
| `catalog-read` | 读取轻量目录或功能域详细索引 |
| `catalog-update` | 更新代码模块索引 |
| `catalog-repair` | 一致性检查与自愈 |

### Claude Code

将 `skills/` 目录保留在项目中即可。Claude Code 会自动发现项目内的 `SKILL.md` 文件。

AI 行为规则写在 `CLAUDE.md` 中，指引 AI 何时该读、何时该写。

### OpenAI Codex

Skill 的 frontmatter 格式兼容 Codex 的 agents 约定。将 `skills/` 软链接或复制为 `.codex/skills/` 即可。

## 检索流程

```
1. catalog.read topics     → 读轻量目录，定位相关话题（几十行）
2. catalog.read <module>   → 只读该功能域的详细索引（十几行）
3. memory.read <bucket> <file> → 读相关知识文件
```

每一步只取最小需要的那一块。`memory.search` 作为 catalog 失效时的兜底安全网。

## 运行测试

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
```

## 许可

MIT
