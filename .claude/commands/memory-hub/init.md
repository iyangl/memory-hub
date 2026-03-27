---
description: '首次扫描项目，生成初始记忆'
---

# /memory-hub:init — 初始化项目记忆

扫描项目代码库，创建 `.memory/` 骨架并填充初始知识文档。

## 上下文

- 用户意图：$ARGUMENTS
- 本命令只需运行一次。如果 `.memory/` 已存在，转为增量更新模式。

---

## 执行流程

**严格按以下步骤顺序执行。**

### Step 1：前置检查

检查 `.memory/` 是否已存在：

```bash
ls .memory/manifest.json 2>/dev/null
```

- **不存在** → 继续 Step 2（全新初始化）
- **已存在** → 跳到 Step 6（增量更新模式）

### Step 2：创建骨架

```bash
python3 -m lib.cli init
```

此命令创建：
- `.memory/docs/` — 四个 bucket（architect/dev/pm/qa）+ 空模板文件
- `.memory/catalog/` — topics.md 骨架 + modules/ 目录
- `.memory/inbox/` — Layer 2 临时写入区
- `.memory/manifest.json` — 布局版本 v3

### Step 3：扫描项目，填充知识

以下内容由你（LLM）分析生成，不是 CLI 命令。

#### 3a. 收集项目信息

读取以下文件以了解项目：

1. 项目根目录文件列表（`ls -la`）
2. 包管理文件（`package.json` / `pyproject.toml` / `go.mod` / `Cargo.toml` 等）
3. 入口文件（`main.*` / `index.*` / `app.*` 等）
4. 配置文件（`.env.example` / `tsconfig.json` / `Makefile` 等）
5. 现有文档（`README.md` / `CONTRIBUTING.md` 等）

#### 3b. 生成 tech-stack.md

根据收集的信息，用 Edit 工具写入 `.memory/docs/architect/tech-stack.md`：

内容应包含：
- 语言和版本
- 运行时依赖（列出关键的，不是全部）
- 构建系统
- 关键设计约束

#### 3c. 生成 conventions.md

用 Edit 工具写入 `.memory/docs/dev/conventions.md`：

内容应包含：
- 目录结构概览
- 命名约定（如果能从代码推断）
- 测试约定

#### 3d. 生成 architecture.md

**关键约束：必须用 Read 工具实际读取源码文件。禁止仅从文件名推测。**

1. 用 Read 工具读取项目入口文件（main.* / index.* / app.* 等）
2. 追踪 import 链 1-2 层，Read 被 import 的关键文件
3. 多模块项目：Read 每个模块的入口文件（main.* / index.* / lib.* 等）

根据实际阅读的代码，用 Edit 工具写入 `.memory/docs/architect/architecture.md`：

**必填 section（4 个）：**

```markdown
# 项目架构

## 整体架构
<描述系统的整体设计风格和分层方式，引用源码路径>

## 模块依赖关系
<描述模块间的依赖方向和调用关系，引用源码路径>

## 关键设计模式
<描述代码中使用的核心设计模式，引用源码路径>

## 通信机制
<描述模块间通信方式（函数调用/事件/消息等），引用源码路径>
```

**每个 claim 必须引用至少一个源码路径。**

#### 3e. 注册到 topics.md

对每个写入的文件执行：

```bash
python3 -m lib.cli index <bucket> <filename> --topic <主题名> --summary <一句话描述>
```

示例：
```bash
python3 -m lib.cli index architect tech-stack.md --topic "技术栈" --summary "语言、依赖、构建系统和关键约束"
python3 -m lib.cli index dev conventions.md --topic "开发约定" --summary "目录结构、命名和测试约定"
python3 -m lib.cli index architect architecture.md --topic "架构" --summary "模块关系、依赖方向、设计模式和通信机制"
```

### Step 4：生成代码模块索引

#### 4a. CLI 扫描模块脚手架

```bash
python3 -m lib.cli scan-modules
```

此命令自动完成：
- 检测项目类型（Python/Node/Go/Rust 等）
- 通过 `git ls-files` 获取受版本控制的文件列表
- 扫描顶层目录和容器目录（packages/apps/services 等）
- 每个子目录至少选 1 个代表文件，保证覆盖
- 输出 JSON 脚手架，含 `dir_tree`（2 层目录结构）和 `total_files`

#### 4b. Round 1：结构分析（每个模块）

**关键约束：必须用 Read 工具实际读取文件。禁止仅从文件名推测。**

对 4a 输出中的每个模块，按以下顺序分析：

1. **Read 模块清单文件**（从 `files` 列表中找 `pubspec.yaml` / `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` 等）
2. **Read 模块入口文件**（从 `files` 列表中找 `main.*` / `index.*` / `app.*` / `__init__.py` / `lib.rs` / `mod.rs` 等）
3. 根据实际读取内容，填写：
   - `summary` — 一句话模块职责
   - `purpose` — 2-3 句详细描述（基于代码内容，不是文件名）
   - `internal_deps` — 依赖的其他模块（从 import/require 语句提取）

#### 4c. Round 2：深度分析（选择性）

从模块列表中选择**非平凡模块**（排除 root、配置类、纯资源类模块）进行深度分析。

**限制：最多 8 个模块。** 模块总数 >15 时只对前 8 个非平凡模块执行此步骤。

对每个选中模块：

1. 从 `files` 列表选 2-3 个**核心源码文件**（排除配置/清单文件），用 Read 工具读取
2. 识别关键 class / interface / type / function，填写 `key_abstractions`（格式：`ClassName — 作用说明`）
3. 修正 `files` 中每个文件的 `description`（基于实际内容，不是文件名猜测）

#### 4d. 组装 JSON

将分析结果写入 `/tmp/modules.json`，格式：

```json
{
  "modules": [
    {
      "name": "模块名",
      "summary": "一句话模块职责",
      "purpose": "2-3句详细描述",
      "key_abstractions": ["ClassName — 作用说明"],
      "internal_deps": ["模块名 — 依赖原因"],
      "dir_tree": "保留 scan-modules 输出的 dir_tree",
      "total_files": 42,
      "files": [
        {"path": "相对路径", "description": "文件说明"}
      ]
    }
  ]
}
```

可选字段（`purpose`, `key_abstractions`, `internal_deps`）如无内容可省略。
`name` 会被自动 sanitize 为安全文件名。

#### 4e. 写入模块索引

```bash
python3 -m lib.cli catalog-update --file /tmp/modules.json
```

### Step 5：生成 BRIEF.md

```bash
python3 -m lib.cli brief
```

### Step 6：增量更新模式

如果 `.memory/` 已存在，执行以下操作：

1. 读取现有 BRIEF.md 了解已有知识
2. 扫描项目变化（新文件、新依赖等）
3. 用 Edit 工具更新过时的 docs 文件
4. 对新增知识执行 Step 3e 的注册流程
5. 执行 Step 4（重新扫描模块索引）
6. 执行 Step 5（重建 BRIEF.md）

### Step 7：修复 catalog

```bash
python3 -m lib.cli catalog-repair
```

检查输出中的 `ai_actions` 和 `manual_actions`，处理所有问题。

### Step 8：质量门

向用户展示摘要：

```
## 初始化结果

### 已创建文件
- <列出所有写入的 docs 文件>

### 模块索引
- 识别 X 个模块（其中 Y 个完成深度分析）

### BRIEF.md
- X 行

### 不确定项
- <列出分析中不确定的内容，请求用户确认>
```

---

## 安全边界

1. **只写 `.memory/` 目录** — 不修改项目源代码
2. **不猜测** — 不确定的内容标为 unknown，不编造
3. **不过度填充** — 只写有信心的知识，宁缺勿滥
4. **必须 Read** — 所有语义信息必须基于实际读取的源码，禁止仅从文件名推测
