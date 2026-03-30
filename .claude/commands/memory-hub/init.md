---
description: '首次扫描项目，生成初始记忆'
---

# /memory-hub:init — 初始化项目记忆

扫描项目并创建 recall-first 所需的初始记忆骨架与导航产物。

## 上下文

- 用户意图：$ARGUMENTS
- 本命令只用于首次初始化。如果 `.memory/` 已存在，应停止并返回 `ALREADY_INITIALIZED`；后续请改用 `/memory-hub:recall`、`brief` 或 `catalog-repair`。

---

## 执行流程

### Step 1：前置检查

```bash
ls .memory/manifest.json 2>/dev/null
```

- 不存在 → 继续初始化
- 已存在 → 停止并报告 `ALREADY_INITIALIZED`

### Step 2：创建骨架

```bash
py -3 -m lib.cli init
```

此命令创建：
- `.memory/docs/`
- `.memory/catalog/`
- `.memory/inbox/`
- `.memory/session/`
- `.memory/BRIEF.md`
- `.memory/manifest.json`

### Step 3：填充高价值 docs

由你（LLM）读取项目实际文件后生成：
- `architect/tech-stack.md`
- `dev/conventions.md`
- 必要时补充高价值决策 / 约束 / 验证策略

目标不是做代码摘要，而是先沉淀：
- 决策
- 约束
- 风险
- 验证重点
- 模块阅读导航所需背景

### Step 4：生成模块导航脚手架

先执行：

```bash
py -3 -m lib.cli scan-modules --out .memory/session/scan-modules.json
```

注意：该 CLI 的 stdout 是 envelope，而 `--out` 写出的文件是裸 `{"project_type": ..., "modules": [...]}`。后续供 `catalog-update` 使用时，优先直接传 `--out` 生成的文件；不要把 stdout 的 envelope 直接当作裸 `modules` JSON。

### Step 5：写入模块导航卡

Step 4 的 `--out` 文件可直接作为 `catalog-update` 输入。

然后：

```bash
py -3 -m lib.cli catalog-update --file .memory/session/scan-modules.json
```

### Step 6：重建 base brief

```bash
py -3 -m lib.cli brief
```

BRIEF 的目标是 boot summary，不是 docs 首段拼盘。

### Step 7：质量门

向用户报告：
- 创建了哪些基础文件
- 识别了哪些模块
- 哪些入口/风险/验证重点已沉淀
- 仍有哪些 unknowns

---

## 安全边界

1. 只写 `.memory/`
2. 不猜测，不编造
3. 必须基于实际 Read 的内容生成语义信息
4. 优先保证导航质量，而不是堆砌摘要数量
