# Memory Hub 重构开发计划

> 基于 REDESIGN.md，从零重建 Memory Hub。
> 脚本语言：Python（跨平台）| Skill 格式：Claude Code + Codex 双兼容

---

## Phase 0：清理与项目骨架

### 0.1 清理旧代码
- 删除：`memory_hub/`、`tests/`、`scripts/`、`samples/`、`skills/`、`migrations/`（如果独立存在）
- 删除：`pyproject.toml`、`.mcp.json`、`README.md`、`HANDOFF.md`、`AGENTS.md`、`GLOBAL_SKILLS.md`、`HARDENING_GATE.md`、`memory_catalog_plan.md`、`risk_backlog.md`
- 删除：`.codex/` 目录
- 保留：`REDESIGN.md`、中文文档（`分享草稿.md`、`分享终稿.md`、`了解 AI...md`、`验收指标.md`）、`.git/`、`.claude/`、`.gitignore`

### 0.2 新建项目骨架
```
memory-hub/
├── bin/                        # CLI 入口
│   └── memory-hub              # Python 可执行入口脚本
├── lib/                        # 核心 Python 模块
│   ├── __init__.py
│   ├── envelope.py             # 统一 JSON envelope + 退出码
│   ├── paths.py                # .memory/ 路径常量与解析
│   ├── memory_init.py          # memory.init 实现
│   ├── memory_read.py          # memory.read 实现
│   ├── memory_list.py          # memory.list 实现
│   ├── memory_search.py        # memory.search 实现
│   ├── memory_write.py         # memory.write 实现
│   ├── catalog_read.py         # catalog.read 实现
│   ├── catalog_update.py       # catalog.update 实现
│   └── catalog_repair.py       # catalog.repair 实现
├── skills/                     # Skill 提示词（双格式）
│   ├── memory-init/
│   │   └── SKILL.md
│   ├── memory-read/
│   │   └── SKILL.md
│   ├── memory-list/
│   │   └── SKILL.md
│   ├── memory-search/
│   │   └── SKILL.md
│   ├── memory-write/
│   │   └── SKILL.md
│   ├── catalog-read/
│   │   └── SKILL.md
│   ├── catalog-update/
│   │   └── SKILL.md
│   └── catalog-repair/
│       └── SKILL.md
├── tests/                      # 测试
│   ├── __init__.py
│   └── ...
├── CLAUDE.md                   # AI 行为指引（核心）
├── REDESIGN.md                 # 设计文档（保留）
├── pyproject.toml              # 新的包配置
├── .gitignore                  # 更新
└── README.md                   # 新的项目说明
```

### 0.3 基础设施
- `pyproject.toml`：Python 3.10+，无外部依赖，定义 `memory-hub` CLI 入口
- `lib/envelope.py`：统一 JSON 输出函数 `ok(data, manual_actions=[])` / `fail(code, message, details={})`
- `lib/paths.py`：`.memory/` 路径解析（桶名验证、基础文件列表、modules 路径）
- `bin/memory-hub`：CLI 分发器，`memory-hub <command> [args]` → 调用对应 `lib/` 模块
- 退出码：0=成功，1=业务错误，2=系统错误

---

## Phase 1：核心读写脚本（memory.* 系列）

### 1.1 memory.read
- 输入：`<bucket> <file>`
- 逻辑：验证桶名 → 拼路径 → 读文件 → 返回内容
- 错误：文件不存在 → `FILE_NOT_FOUND`，桶名非法 → `INVALID_BUCKET`
- 锚点检测：如果调用方传了 `--anchor`，检查锚点是否存在，不存在时在 `manual_actions` 中提示

### 1.2 memory.list
- 输入：`<bucket>`
- 逻辑：列出桶内所有 `.md` 文件，返回文件名列表
- 错误：桶不存在 → `BUCKET_NOT_FOUND`

### 1.3 memory.search
- 输入：`<query>`
- 逻辑：跨四个桶（pm/architect/dev/qa）全文检索，返回匹配的文件路径 + 匹配行
- 实现：简单的逐文件 substring/regex 匹配，不需要索引
- 返回：`[{file, line_number, line_content, context}]`

### 1.4 memory.write
- 输入：`<bucket> <file> --topic <话题名> --summary <描述> [--anchor <锚点>] [--mode append|overwrite]`，内容通过 stdin 传入
- 内容传入方式：stdin（避免命令行转义和长度限制问题）
- AI 决定写什么内容，脚本保证写入过程的一致性和格式正确性
- 写入模式：
  - `append`（默认）：追加到文件末尾。适用于新增决策条目、新增知识段落
  - `overwrite`：覆盖整个文件内容。适用于 AI 重构/重写文件（如拆分话题时）
- 逻辑（强一致顺序）：
  1. 验证桶名和文件名
  2. 从 stdin 读取 markdown 内容
  3. 根据 mode 写入知识文件（原子写：先写 `.tmp`，再 rename）
  4. 更新 `catalog/topics.md` 知识文件索引部分（追加或更新该话题条目）
- 基础文件保护：不允许删除或重命名基础文件（但允许 overwrite 其内容）
- 新文件：文件不存在时自动创建（无论 mode）

---

## Phase 2：Catalog 系列脚本

### 2.1 catalog.read
- 输入：`[topics|<module>]`
- `topics` → 读 `catalog/topics.md`
- `<module>` → 读 `catalog/modules/<module>.md`
- 错误：文件不存在 → `CATALOG_NOT_FOUND`

### 2.2 catalog.update
- 输入：通过 stdin 接收 JSON 格式的模块索引数据（AI 生成）
- 职责：仅负责**写入**代码模块索引，不做"判断什么是关键文件"的决策
  1. 接收 AI 传入的模块列表和文件索引
  2. 写入 `catalog/modules/*.md`
  3. 更新 `catalog/topics.md` 的「代码模块」部分
- 不触碰 topics.md 的「知识文件」部分（那是 memory.write 的职责）
- "哪些文件该索引、怎么描述"由 AI 在 Skill 提示词中决定——AI 读目录结构和关键文件后，把结果通过脚本写入
- 每次调用全量覆盖代码模块部分（AI 每次重新生成完整模块列表）
- 完成后自动调用 `catalog.repair`

#### stdin JSON Schema

```json
{
  "modules": [
    {
      "name": "auth",
      "summary": "用户认证与授权",
      "files": [
        {"path": "src/auth/login.py", "description": "登录入口"},
        {"path": "src/auth/middleware.py", "description": "认证中间件"}
      ]
    }
  ]
}
```

脚本处理逻辑：
- 遍历 `modules` 数组，为每个 module 生成 `catalog/modules/<name>.md`
- module md 文件格式：标题 + 文件列表（每行一个 `- path — description`）
- 更新 `catalog/topics.md`「代码模块」section：每个 module 一行 `- <name> — <summary>`
- 如果 `catalog/modules/` 下有旧文件不在新 modules 列表中，删除旧文件

### 2.3 catalog.repair
- 固定检查项：
  1. 死链接：topics.md 指向不存在的文件 → 自动删除
  2. 缺注册：桶内文件存在但 topics.md 未索引 → 自动补注册
  3. 重复 topic：同一话题出现多次 → 列入 `manual_actions`
  4. 无效锚点：`#锚点` 指向的标题不存在 → 列入 `manual_actions`
- 输出：`{fixed: [...], manual_actions: [...]}`

---

## Phase 3：memory.init

### 3.1 初始化流程
- 检查 `.memory/` 是否已存在，已存在则报错 `ALREADY_INITIALIZED`
- 创建目录结构：
  ```
  .memory/
  ├── pm/decisions.md            # 空模板
  ├── architect/tech-stack.md    # 空模板（init 不自动填充，由 AI 在 Skill 流程中填充）
  ├── architect/decisions.md     # 空模板
  ├── dev/conventions.md         # 空模板
  ├── qa/strategy.md             # 空模板
  └── catalog/
      ├── topics.md              # 空骨架（带标题结构）
      └── modules/               # 空目录
  ```

### 3.2 关于 init 的职责边界
REDESIGN.md 说 init 时 AI 扫描项目生成 catalog 和基础文件内容。但脚本本身不做 AI 推理——脚本只负责创建目录和空模板。**AI 填充内容的逻辑写在 Skill 提示词里**，AI 调用脚本创建骨架后，自己读项目文件、生成内容、再通过 `memory.write` 和 `catalog.update` 写入。

### 3.3 init 完成后
- 自动调用 `catalog.repair` 检查一致性
- 输出 `unknowns` 段（由 Skill 提示词指导 AI 生成，不是脚本生成）

---

## Phase 4：Skill 提示词

### 4.1 每个原子 Skill 一个 SKILL.md
双格式兼容：frontmatter 同时包含 Claude Code 和 Codex 所需字段。

```yaml
---
name: memory-read
description: 精准读取 .memory/ 中某个桶的某个文件
tools: ["Bash"]
---
```

### 4.2 Skill 内容结构
每个 SKILL.md 包含：
- Purpose：一句话说明
- Input：参数说明
- Required flow：调用 `bin/memory-hub <command>` 的具体步骤
- Output：期望返回格式
- Error handling：失败时的行为

### 4.3 memory-init Skill 详细流程

这是最复杂的 Skill，提示词需要指导 AI 完成以下步骤：

**Step 1：创建骨架**
```bash
memory-hub init
```
脚本创建 `.memory/` 目录结构和空模板文件。

**Step 2：扫描项目，生成技术栈知识**
AI 自行执行（不通过脚本）：
1. 读取项目根目录文件列表
2. 读取包管理文件（`package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` / `pom.xml` 等，取存在的）
3. 读取入口文件（`main.*` / `index.*` / `app.*` / `server.*` 等）
4. 读取配置文件（`.env.example` / `tsconfig.json` / `webpack.config.*` 等）

根据读到的内容，生成 `tech-stack.md` 内容，通过脚本写入：
```bash
echo "<markdown content>" | memory-hub write architect tech-stack.md \
  --topic tech-stack --summary "技术栈、关键依赖、使用方式与限制" --mode overwrite
```

**Step 3：生成代码约定知识**
AI 根据 Step 2 读到的项目结构，生成 `conventions.md` 内容：
```bash
echo "<markdown content>" | memory-hub write dev conventions.md \
  --topic conventions --summary "目录命名规则、模块组织方式、代码约定" --mode overwrite
```

**Step 4：扫描项目模块，生成 Catalog**
AI 分析项目目录结构，识别功能域和关键文件，构造 JSON 传给脚本：
```bash
echo '<modules json>' | memory-hub catalog-update
```

**Step 5：质量门**
AI 列出 `unknowns`——无法明确归入任何功能域的文件或目录，输出给用户确认。
`catalog.repair` 在 init 和 catalog-update 完成后自动执行，AI 检查其输出中的 `manual_actions`，如有则提示用户。

**Step 6：完成**
输出初始化摘要：创建了哪些文件、识别了哪些模块、有哪些 unknowns 需要确认。

---

## Phase 5：CLAUDE.md（AI 行为指引）

### 5.1 内容
将 REDESIGN.md 中「AI 行为规则」章节转化为 CLAUDE.md 中的可执行指令：
- 何时 Search/Read 的触发条件
- 何时 Write/Update 的触发条件
- 判断标准：下一个会话的 AI 不知道这件事会不会做错决定
- 决策演进的记录格式
- 文件管理规则

### 5.2 Skill 触发规则
参考验收指标.md 中的触发规则建议稿，写入 CLAUDE.md。

---

## Phase 6：测试

### 6.1 单元测试
每个 `lib/` 模块对应一个测试文件：
- `test_envelope.py`：JSON envelope 格式验证
- `test_paths.py`：路径解析、桶名验证
- `test_memory_read.py`：正常读取、文件不存在、非法桶名
- `test_memory_list.py`：列出文件、空桶
- `test_memory_search.py`：匹配、无结果、跨桶
- `test_memory_write.py`：新建文件、追加、topics.md 自动更新、基础文件保护
- `test_catalog_read.py`：读 topics、读 module、不存在
- `test_catalog_update.py`：模块索引生成
- `test_catalog_repair.py`：四项检查（死链接、缺注册、重复 topic、无效锚点）
- `test_memory_init.py`：目录创建、已存在报错、repair 自动触发

### 6.2 集成测试
- 完整 init → write → read → search 流程
- write 后 topics.md 一致性验证
- catalog.update → catalog.repair 链式调用

---

## Phase 7：收尾

### 7.1 README.md
- 项目定位、安装方式、CLI 用法、Skill 安装说明

### 7.2 .gitignore 更新
- 不预设 `.memory/` 的 gitignore 策略，由用户自己决定是否提交到 git

---

## 实施顺序与依赖

```
Phase 0（清理+骨架）
  ↓
Phase 1（memory.read/list/search/write）← 核心，其他都依赖
  ↓
Phase 2（catalog.read/update/repair）← 依赖 Phase 1 的 paths 和 envelope
  ↓
Phase 3（memory.init）← 依赖 Phase 1 + 2 的所有脚本
  ↓
Phase 4（Skill 提示词）← 依赖所有脚本完成
  ↓
Phase 5（CLAUDE.md）← 依赖 Skill 定义完成
  ↓
Phase 6（测试）← 可以和 Phase 1-3 并行，每完成一个模块就写对应测试
  ↓
Phase 7（收尾）
```

---

## 设计原则

**脚本是执行器，AI 是决策者。**

- 脚本只负责文件读写、一致性保证、格式校验
- 所有需要"判断"的事（什么是关键文件、写什么内容、怎么描述）都由 AI 在 Skill 提示词中完成
- 脚本通过 stdin 接收 AI 生成的内容，通过统一 JSON envelope 返回结果
- 这样脚本行为可测试、可回归，AI 的智能行为通过提示词迭代

---

## 待确认项

（已全部确认，无待确认项）
