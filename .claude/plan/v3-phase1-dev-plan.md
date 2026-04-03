# Memory Hub v3 — Phase 1 详细开发计划

> 基于 Phase 0 已收敛的全部决策，精确到文件和函数级别。
> 前置条件：Phase 0 决策结果见 `.claude/plan/v3-deep-review.md`
> 2026-04 清理注记：旧 repo-local skill / MCP / 自测入口已完成移除；现行入口以 `lib/cli.py` 与 `.claude/commands/memory-hub/*.md` 为准。

---

## 依赖关系总览

```
Step 1 (代码精简)          ← 无依赖，可立即启动
Step 2 (基础设施改造)      ← 依赖 Step 1（归档后才改保留模块）
Step 3 (BRIEF.md 生成逻辑) ← 依赖 Step 2（paths.py 新增路径后）
Step 4 (/init command)     ← 依赖 Step 2 + Step 3
Step 5 (/recall command)   ← 依赖 Step 3
Step 6 (/save command)     ← 依赖 Step 2 + Step 3
Step 7 (规则与文档)         ← 依赖 Step 4 + 5 + 6
Step 8 (测试与验收)         ← 依赖全部

可并行：Step 4 || Step 5 || Step 6（三个 command 实现可并行）
可并行：Step 1 期间可同步起草 Step 4/5/6 的 workflow 模板
```

---

## Step 1：代码精简与归档

### 1.1 归档模块

将以下 25 个 `lib/` 模块移入 `.archive/v2-lib/`（保留 git history 可追溯）：

| 模块 | 归档原因 |
|------|---------|
| `durable_db.py` | durable store 移除 |
| `durable_store.py` | durable store 移除 |
| `durable_repo.py` | durable store 移除 |
| `durable_uri.py` | durable store 移除 |
| `durable_guard.py` | durable store 移除 |
| `durable_errors.py` | durable store 移除 |
| `durable_proposal_utils.py` | durable store 移除 |
| `durable_review.py` | durable store 移除 |
| `durable_mcp_tools.py` | MCP 移除 |
| `mcp_server.py` | MCP 移除 |
| `mcp_toolspecs.py` | MCP 移除 |
| `project_memory_view.py` | 统一 workflow 路由移除 |
| `project_memory_write.py` | 统一 workflow 路由移除 |
| `project_memory_projection.py` | 统一 workflow 路由移除 |
| `project_review.py` | review 状态机移除 |
| `docs_review.py` | review 状态机移除 |
| `docs_memory.py` | 统一 workflow 路由移除 |
| `session_extract.py` | 被 /save 替代 |
| `session_extract_cli.py` | 被 /save 替代 |
| `decision_discovery.py` | discovery lane 归档 |
| `discovery_cli.py` | discovery lane 归档 |
| `discovery_context.py` | discovery lane 归档 |
| `discovery_signals.py` | discovery lane 归档 |
| `review_cli.py` | review CLI 移除 |
| `rollback_cli.py` | rollback 移除 |

### 1.2 归档测试

将以下测试移入 `.archive/v2-tests/`：

| 测试文件 | 归档原因 |
|---------|---------|
| `test_durable_cli.py` | durable 移除 |
| `test_durable_proposals.py` | durable 移除 |
| `test_durable_review.py` | durable 移除 |
| `test_durable_schema.py` | durable 移除 |
| `test_mcp_server.py` | MCP 移除 |
| `test_decision_discovery.py` | discovery 移除 |
| `test_session_extract.py` | session-extract 移除 |
| `durable_test_support.py` | durable 辅助模块移除 |

### 1.3 归档旧 repo-local skill 目录

将旧 repo-local skill 目录移入 `.archive/v2-skills/`，不再作为当前协作入口。

### 1.4 清理 CLI 命令注册

**文件**：`lib/cli.py`

早期 Phase 1 草案曾预估会大幅收缩命令面；现行命令面以 `lib/cli.py` 为准：

```python
COMMANDS = {
    "init": "lib.memory_init",
    "read": "lib.memory_read",
    "list": "lib.memory_list",
    "search": "lib.memory_search",
    "index": "lib.memory_index",
    "catalog-read": "lib.catalog_read",
    "catalog-update": "lib.catalog_update",
    "catalog-repair": "lib.catalog_repair",
    "brief": "lib.brief",
    "scan-modules": "lib.scan_modules",
    "recall-plan": "lib.recall_planner",
    "working-set": "lib.session_working_set",
    "execution-contract": "lib.execution_contract",
    "save": "lib.memory_save",
    "inbox-list": "lib.inbox_list",
    "inbox-clean": "lib.inbox_clean",
    "modules-check": "lib.modules_check",
}
```

旧的探索/审批/回退类入口已退出当前架构。

### 1.5 清理 pyproject.toml

**文件**：`pyproject.toml`

移除旧 MCP console script 入口。

### 1.6 清理 .mcp.json

如果项目根目录存在 `.mcp.json`，移入 `.archive/v2-config/`。

### 1.7 验证

```bash
# 确认保留模块可正常导入
python3 -c "from lib import paths, envelope, catalog_read, catalog_repair, memory_read, memory_search, memory_init, memory_list, memory_index, catalog_update, utils, cli"

# 确认 CLI 可运行
python3 -m lib.cli catalog-repair

# 确认保留测试通过
python3 -m pytest tests/test_paths.py tests/test_envelope.py tests/test_memory_init.py tests/test_memory_read.py tests/test_memory_list_search.py tests/test_memory_index.py tests/test_catalog.py -v
```

---

## Step 2：基础设施改造

### 2.1 更新 paths.py

**文件**：`lib/paths.py`

新增常量和函数：

```python
# 新增常量
INBOX_DIR = "inbox"
BRIEF_FILE = "BRIEF.md"

# 新增函数
def inbox_root(project_root: Path | None = None) -> Path:
    """Return the .memory/inbox/ directory path."""
    return memory_root(project_root) / INBOX_DIR

def brief_path(project_root: Path | None = None) -> Path:
    """Return path to .memory/BRIEF.md."""
    return memory_root(project_root) / BRIEF_FILE
```

移除（或标记 deprecated）：
- 常量：`STORE_DIR`、`PROJECTIONS_DIR`、`MEMORY_DB_FILE`、`BOOT_PROJECTION_FILE`、`SEARCH_PROJECTION_FILE`
- 函数：`store_root()`、`store_db_path()`、`projections_root()`、`boot_projection_path()`、`search_projection_path()`

### 2.2 更新 memory_init.py

**文件**：`lib/memory_init.py`

改动点：

1. **MANIFEST 常量更新**：
```python
MANIFEST = {
    "layout_version": "3",
    "docs_root": "docs",
    "catalog_root": "catalog",
    "inbox_root": "inbox",
    "brief_file": "BRIEF.md",
    "project_scope": "project",
}
```
移除：`store_root`、`store_db`、`projection_root`

2. **创建 inbox 目录**：在 `run()` 函数中，catalog 目录创建后新增：
```python
inbox_dir = paths.inbox_root(project_root)
inbox_dir.mkdir(parents=True, exist_ok=True)
```

3. **移除 _store 目录创建**：删除以下行：
```python
store_dir = paths.store_root(project_root)
store_dir.mkdir(parents=True, exist_ok=True)
paths.projections_root(project_root).mkdir(parents=True, exist_ok=True)
```

4. **init 后生成初始 BRIEF.md**：在 catalog-repair 之后，调用 brief 生成：
```python
from lib.brief import generate_brief
generate_brief(project_root)
```

### 2.3 更新 .gitignore

在项目根 `.gitignore` 中添加：

```gitignore
# Memory Hub v3 — inbox 是临时写入区，不跟踪
.memory/inbox/
# 保留 .memory/inbox/ 目录本身（git 不跟踪空目录，用 .gitkeep）
!.memory/inbox/.gitkeep
```

### 2.4 现有 .memory/ 数据迁移

不写迁移脚本（与 v2 结论 12 一致），手动操作：

1. 归档 `_store/` → `.archive/v2-store/`
2. 删除 `manifest.json`（init 会重建，或手动改 layout_version）
3. 创建 `inbox/` 目录 + `.gitkeep`
4. 现有 `docs/` 和 `catalog/` 内容原样保留

### 2.5 验证

```bash
# 确认 paths.py 新函数可用
python3 -c "from lib.paths import inbox_root, brief_path; print(inbox_root()); print(brief_path())"

# 确认现有测试仍通过（paths 测试可能需要更新）
python3 -m pytest tests/test_paths.py -v
```

---

## Step 3：BRIEF.md 生成逻辑

### 3.1 新建 lib/brief.py

**文件**：`lib/brief.py`（新建）

核心函数：

```python
def generate_brief(project_root: Path | None = None) -> str:
    """从 docs/ 机械式拼接生成 BRIEF.md 内容并写入文件。返回生成的内容。"""
```

**拼接规则**（D7 决策）：

1. 遍历四个 bucket，固定顺序：`architect` → `dev` → `pm` → `qa`
2. 每个 bucket 内，按文件名字母序遍历所有 `.md` 文件
3. 跳过空文件（内容为空或只有空白）
4. 每个文件提取：
   - 第一个 `## ` 标题（如果有）
   - 该标题后到下一个 `## ` 之间的第一个非空段落
   - 如果没有 `## ` 标题，取文件前 5 行
   - 每条摘要截断到 3 行
5. 输出格式：

```markdown
# Project Brief

## architect
### tech-stack.md
<摘要>

### decisions.md
<摘要>

## dev
### conventions.md
<摘要>
```

6. 总行数检查：如果超过 200 行，重新生成，每条截断到 2 行
7. 写入 `.memory/BRIEF.md`

**CLI 入口**：

```python
def run(args: list[str]) -> None:
    """CLI: memory-hub brief [--project-root <path>]"""
```

### 3.2 辅助函数

```python
def _extract_first_section(content: str, max_lines: int = 3) -> str:
    """从 markdown 内容提取第一个 ## 标题和首段。"""

def _is_empty_doc(content: str) -> bool:
    """判断文档是否为空（只有空白或标题没有正文）。"""
```

### 3.3 测试

**文件**：`tests/test_brief.py`（新建）

测试用例：
- 正常 docs 目录 → 生成正确的 BRIEF.md
- 空文件被跳过
- 无 `##` 标题时取前 5 行
- 超 200 行时自动截断到 2 行
- 空 docs 目录 → 生成只有标题的 BRIEF.md
- bucket 顺序正确（architect → dev → pm → qa）
- 文件名字母序正确

### 3.4 验证

```bash
# 用现有 .memory/docs/ 测试
python3 -m lib.cli brief
cat .memory/BRIEF.md
wc -l .memory/BRIEF.md  # 应 <= 200 行
```

---

## Step 4：/init command 模板

### 4.1 新建 workflow 模板

**文件**：`.claude/commands/memory-hub/init.md`（新建）

这是 Claude Code slash command 模板（`/memory-hub:init`）。

**模板内容要点**：

1. **前置检查**：`.memory/` 是否已存在
   - 已存在 → 提示用户，询问是否增量更新
   - 不存在 → 继续

2. **创建骨架**：
   ```bash
   python3 -m lib.cli init
   ```

3. **扫描项目，填充知识**（LLM 执行，非 CLI）：
   - 读取项目根目录文件列表
   - 读取包管理文件（package.json / pyproject.toml / go.mod 等）
   - 读取入口文件和配置文件
   - 生成 `tech-stack.md` 内容 → 直接 Edit 写入 `.memory/docs/architect/tech-stack.md`
   - 生成 `conventions.md` 内容 → 直接 Edit 写入 `.memory/docs/dev/conventions.md`
   - 调用 `python3 -m lib.cli index` 注册到 topics.md

4. **生成代码模块索引**：
   - LLM 分析项目目录结构
   - 构造 modules JSON 文件
   - 调用 `python3 -m lib.cli catalog-update --file <json>`

5. **生成 BRIEF.md**：
   ```bash
   python3 -m lib.cli brief
   ```

6. **质量门**：列出 unknowns，要求用户确认

### 4.2 Codex 兼容

**文件**：`AGENTS.md` 中引用同一份模板

在 AGENTS.md 中添加指引：当用户说"初始化记忆"/"init memory"时，按 `.claude/commands/memory-hub/init.md` 的流程执行。

---

## Step 5：/recall command 模板

### 5.1 新建 workflow 模板

**文件**：`.claude/commands/memory-hub/recall.md`（新建）

**模板内容要点**：

1. **读取 BRIEF.md**：
   ```bash
   cat .memory/BRIEF.md
   ```
   - 文件存在 → 内容注入当前上下文
   - 文件不存在 → 降级：生成 BRIEF.md 后读取
     ```bash
     python3 -m lib.cli brief
     cat .memory/BRIEF.md
     ```

2. **可选深入**：如果用户提供了任务描述，根据 BRIEF.md 中的信息判断是否需要读取完整 doc：
   ```bash
   python3 -m lib.cli read <bucket> <file>
   ```

3. **上下文提示**：注入后提示用户——长会话中如果感觉 LLM 遗忘了项目上下文，可以重新调用 `/memory-hub:recall`

### 5.2 Codex 兼容

AGENTS.md 中添加指引：当用户说"加载记忆"/"recall memory"时，按模板流程执行。

---

## Step 6：/save command 模板

### 6.1 新建 workflow 模板

**文件**：`.claude/commands/memory-hub/save.md`（新建）

**模板内容要点**：

1. **收集待保存知识**（LLM 执行）：
   - 扫描 `.memory/inbox/` 中的文件（Layer 2 产物）
   - 回顾当前会话中的决策、约束、约定
   - 应用"后悔测试"：会话结束后没记下来会后悔吗？
   - 反面排除：代码本身能表达的不存

2. **对每条知识执行合并**（LLM 执行）：
   - 判断 bucket 分类（architect / dev / pm / qa）
   - 去重检查：
     ```bash
     python3 -m lib.cli search "<关键词>"
     ```
   - 命中已有 doc → 用 Edit 工具追加/更新到已有文件
   - 未命中 → 用 Write 工具创建新文件
   - 注册到 topics.md：
     ```bash
     python3 -m lib.cli index <bucket> <file> --topic <name> --summary <desc>
     ```

3. **清理 inbox**（确定性）：
   - 删除已处理的 inbox 文件

4. **重建 BRIEF.md**（确定性）：
   ```bash
   python3 -m lib.cli brief
   ```

5. **修复 catalog**（确定性）：
   ```bash
   python3 -m lib.cli catalog-repair
   ```
   - 处理 `ai_actions`（LLM 自愈）
   - 报告 `manual_actions`（提示用户）

6. **展示摘要**：告诉用户保存了什么、更新了什么、跳过了什么

### 6.2 Layer 2 行为规范

在 `/save` 模板的注释区域或 CLAUDE.md 中定义 LLM 自主写入 inbox 的行为：

**触发信号**（建议性，非强制）：
- 做出了设计决策（选了方案 A 否了方案 B）
- 发现或确认了约束（这个模块不能用 X）
- 需求讨论达成了结论
- 建立了代码约定（错误处理统一用这个模式）
- 踩了坑（排障结论、绕过方案）

**写入方式**：直接用 Write 工具写入 `.memory/inbox/{时间戳}_{名称}.md`

**格式**：纯 markdown，不要求 frontmatter。内容应是提炼后的结论，不是原始对话。

**不写入的场景**：只读了代码、只执行了已有方案、没产生新的"为什么"或"不要什么"。

### 6.3 Codex 兼容

AGENTS.md 中添加指引：当用户说"保存记忆"/"save memory"时，按模板流程执行。

---

## Step 7：规则与文档更新

### 7.1 CLAUDE.md 重写

从当前 ~300 行精简为 ~50 行：

```markdown
# Memory Hub — 使用规则

## 三个 Command

| Command | 触发 | 作用 |
|---------|------|------|
| /memory-hub:init | 首次接入项目 | 扫描项目，生成初始记忆 |
| /memory-hub:recall | 会话开始时 | 加载 BRIEF.md 到上下文 |
| /memory-hub:save | 会话结束前 | 提炼知识，合并到 docs |

## Layer 2（最佳努力）

工作过程中如果产生了新知识（决策、约束、约定），
可以写入 `.memory/inbox/` 暂存。/save 时会合并。
不强依赖。

## 硬边界

- 不直接编辑 `.memory/docs/`（由 /save 负责）
- 不直接编辑 `.memory/catalog/`（由 CLI 负责）
- 不直接编辑 `.memory/BRIEF.md`（由 CLI 生成）

## 维护

catalog-repair: `python3 -m lib.cli catalog-repair`
```

### 7.2 AGENTS.md 同步

与 CLAUDE.md 内容一致，增加 Codex 特有的指引（如何触发 3 个 command）。

### 7.3 README.md 更新

- 移除 MCP 相关内容
- 移除 durable memory 相关内容
- 更新为 3 command 模型
- 更新 CLI 命令列表
- 更新存储结构图

### 7.4 清理其他文件

- 移除 `HANDOFF.md`（如存在）
- 移除 `GLOBAL_SKILLS.md`（如存在）
- 更新 `REDESIGN.md` 或移入 `.archive/`（v3 方案文档取代）

---

## Step 8：测试与验收

### 8.1 更新保留测试

需要更新的测试文件：

| 测试文件 | 改动 |
|---------|------|
| `test_paths.py` | 新增 `inbox_root`、`brief_path` 测试；移除 `store_*` 路径测试 |
| `test_memory_init.py` | 验证 init 创建 inbox/、不创建 _store/、生成 BRIEF.md |
| `test_catalog.py` | 无改动（catalog-repair 逻辑不变） |
| `test_memory_read.py` | 无改动 |
| `test_memory_list_search.py` | 无改动 |
| `test_memory_index.py` | 无改动 |
| `test_envelope.py` | 无改动 |

### 8.2 新增测试

| 测试文件 | 覆盖内容 |
|---------|---------|
| `test_brief.py` | BRIEF.md 生成逻辑（Step 3.3 中已详述） |

### 8.3 端到端验收场景

#### 场景 A：全新项目

1. `python3 -m lib.cli init` → 骨架创建 + inbox/ + BRIEF.md
2. 手动写入几个 docs 文件
3. `python3 -m lib.cli brief` → BRIEF.md 正确反映 docs 内容
4. `python3 -m lib.cli catalog-repair` → 报告缺注册项
5. `python3 -m lib.cli index ...` → 注册后 repair 清零

#### 场景 B：/recall 流程

1. 读 BRIEF.md → 内容正确
2. 删除 BRIEF.md → /recall 降级生成后读取
3. 长会话后重新 /recall → 内容一致

#### 场景 C：/save 流程

1. 手动在 inbox/ 创建测试文件
2. 执行 /save → inbox 文件被合并到 docs，inbox 被清理
3. BRIEF.md 被重建
4. catalog-repair 无异常

#### 场景 D：跨平台

1. 在 Claude Code 中测试 `/memory-hub:init`、`/memory-hub:recall`、`/memory-hub:save`
2. 在 Codex 中按 AGENTS.md 指引测试同等操作

---

## 文件变更清单

### 新增文件

| 文件 | Step | 说明 |
|------|------|------|
| `lib/brief.py` | 3 | BRIEF.md 机械拼接逻辑 |
| `tests/test_brief.py` | 3 | brief 测试 |
| `.claude/commands/memory-hub/init.md` | 4 | /init workflow 模板 |
| `.claude/commands/memory-hub/recall.md` | 5 | /recall workflow 模板 |
| `.claude/commands/memory-hub/save.md` | 6 | /save workflow 模板 |

### 修改文件

| 文件 | Step | 改动 |
|------|------|------|
| `lib/paths.py` | 2 | 新增 inbox/BRIEF 路径，移除 store 路径 |
| `lib/memory_init.py` | 2 | 更新 MANIFEST，创建 inbox，移除 _store，生成 BRIEF |
| `lib/cli.py` | 1 | 精简 COMMANDS 字典，新增 brief |
| `pyproject.toml` | 1 | 移除旧 MCP console script 入口 |
| `.gitignore` | 2 | 添加 .memory/inbox/ |
| `CLAUDE.md` | 7 | 重写为 ~50 行 |
| `AGENTS.md` | 7 | 同步更新 |
| `README.md` | 7 | 更新为 v3 |
| `tests/test_paths.py` | 8 | 更新路径测试 |
| `tests/test_memory_init.py` | 8 | 更新 init 测试 |

### 归档（移入 .archive/）

| 内容 | Step | 目标 |
|------|------|------|
| 25 个 lib/*.py 模块 | 1 | `.archive/v2-lib/` |
| 8 个 tests/*.py 文件 | 1 | `.archive/v2-tests/` |
| 旧 repo-local 主 skill 目录 | 1 | `.archive/v2-skills/` |
| 旧 repo-local 维护 skill 目录 | 1 | `.archive/v2-skills/` |
| `.memory/_store/` | 2 | `.archive/v2-store/` |
| `.mcp.json`（如存在） | 1 | `.archive/v2-config/` |

### 删除

| 内容 | Step | 说明 |
|------|------|------|
| `skills/` 目录 | 1 | 归档后删除空目录 |
| `.memory/manifest.json` | 2 | init 会重建 |
