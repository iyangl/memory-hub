---
description: '提炼并持久化本次会话中的项目知识'
---

# /memory-hub:save — 保存项目记忆

从当前会话和 inbox 中提炼有价值的知识，合并到 docs/ 正本，重建 BRIEF.md。

## 上下文

- 用户补充说明：$ARGUMENTS

---

## 执行流程

### Step 1：收集待保存知识

从两个来源收集：

#### 1a. 扫描 inbox

```bash
ls .memory/inbox/*.md 2>/dev/null
```

读取每个 inbox 文件的内容。

#### 1b. 回顾当前会话

回顾本次会话中产生的知识，应用**后悔测试**筛选：

> 这次会话结束后，如果没记下来会后悔吗？
> 新会话没有这条信息，会走弯路吗？

**值得保存的**：
- 做出了设计决策（选了方案 A 否了方案 B）
- 发现或确认了约束（这个模块不能用 X）
- 需求讨论达成了结论
- 建立了代码约定（错误处理统一用这个模式）
- 踩了坑（排障结论、绕过方案）

**不值得保存的**：
- 代码本身已经表达的事实
- 临时调试过程
- 还没形成结论的讨论
- 通用知识（非项目特有）

### Step 2：对每条知识执行合并

对 Step 1 中筛选出的每条知识，按以下流程处理：

#### 2a. 分类

判断属于哪个 bucket：
- **architect** — 架构决策、技术选型、设计模式
- **dev** — 开发约定、编码规范、工具配置
- **pm** — 产品决策、需求结论、版本规划
- **qa** — 测试策略、质量约定、验收标准

#### 2b. 去重检查

```bash
python3 -m lib.cli search "<知识的关键词>"
```

#### 2c. 写入

根据去重结果：

- **命中已有文档且内容近似** → 用 Edit 工具更新已有文件（追加或修改段落）
- **未命中** → 用 Write 工具创建新文件到 `.memory/docs/<bucket>/<名称>.md`
- **完全重复** → 跳过，记录到摘要中

#### 2d. 注册到 topics

对新创建的文件：

```bash
python3 -m lib.cli index <bucket> <filename> --topic <主题名> --summary <一句话描述>
```

### Step 3：清理 inbox

删除已处理的 inbox 文件：

```bash
rm .memory/inbox/<已处理的文件>
```

保留 `.gitkeep`：
```bash
ls .memory/inbox/.gitkeep 2>/dev/null || touch .memory/inbox/.gitkeep
```

### Step 4：重建 BRIEF.md

```bash
python3 -m lib.cli brief
```

### Step 5：修复 catalog

```bash
python3 -m lib.cli catalog-repair
```

检查输出：
- `ai_actions` → 自动处理（如死链修复）
- `manual_actions` → 提示用户手动处理

### Step 6：展示摘要

向用户展示本次保存的结果：

```
## 保存结果

### 新增
- <bucket>/<filename> — <一句话描述>

### 更新
- <bucket>/<filename> — <更新了什么>

### 跳过（重复）
- <描述> — 与 <已有文件> 内容重复

### 来源
- inbox: X 条已处理
- 会话提炼: Y 条

### BRIEF.md
- 已重建，共 Z 行
```

---

## Layer 2：工作过程中的自主写入

在日常工作中（不是 /save 流程），如果你产生了新知识，可以主动写入 inbox 暂存。

### 触发信号

- 做出了设计决策（选了方案 A 否了方案 B）
- 发现或确认了约束（这个模块不能用 X）
- 需求讨论达成了结论
- 建立了代码约定（错误处理统一用这个模式）
- 踩了坑（排障结论、绕过方案）

### 写入方式

用 Write 工具写入：

```
.memory/inbox/{ISO时间戳}_{短语义名}.md
```

示例：`.memory/inbox/2026-03-18T14-30-00_design-decision.md`

### 格式

纯 markdown，不需要 frontmatter。内容应是提炼后的结论，不是原始对话。

### 不写入的场景

- 只读了代码，没产生新知识
- 只执行了已有方案
- 没产生新的"为什么"或"不要什么"

---

## 安全边界

1. **docs/ 是唯一正本** — 所有知识最终写入 docs/，不存在其他正本
2. **BRIEF.md 是派生产物** — 只通过 `python3 -m lib.cli brief` 重建，不手动编辑
3. **catalog/ 是派生索引** — 只通过 CLI 命令维护，不手动编辑
4. **git 是安全网** — 所有变更可通过 git 回溯
