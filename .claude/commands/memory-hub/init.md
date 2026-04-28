---
description: '首次扫描项目，生成初始记忆'
---

# /memory-hub:init — 初始化项目记忆

创建显式记忆所需的最小骨架，不在初始化阶段生成派生产物或猜测高价值知识。

## 上下文

- 用户意图：$ARGUMENTS
- 本命令只用于首次初始化。如果 `.memory/` 已存在，应停止并返回 `ALREADY_INITIALIZED`；后续请改用 `/memory-hub:recall`、`brief` 或 `catalog-repair`。

---

## 执行流程

### Step 1：前置检查

如果 `.memory/manifest.json` 已存在，停止并返回 `ALREADY_INITIALIZED`。

### Step 2：创建最小骨架

```bash
python3 -m lib.cli init
```

默认工作流中，只把 `init` 视为“确保最小骨架存在”的入口。Phase 2 之前，底层 core 仍可能顺带产出 legacy 派生产物，但后续流程不应依赖它们。

最小骨架至少包括：
- `.memory/docs/`
- `.memory/catalog/`
- `.memory/catalog/modules/`
- `.memory/inbox/`
- `.memory/session/`
- `.memory/manifest.json`
- 各 bucket 的基础 doc 文件

### Step 3：结束初始化

向用户报告：
- 已创建哪些基础文件
- 默认流程不再要求消费 `BRIEF.md`
- 默认流程不再要求依赖 `catalog-repair` 结果
- 当前初始化不再扫描模块或补齐高价值 docs
- 若现阶段 core 仍顺带生成 legacy 产物，可忽略，不作为后续前置

如需开始使用，后续直接走：
- `search`
- `read`
- `save`

---

## 安全边界

1. 只写 `.memory/`
2. 不猜测，不编造
3. 必须基于实际 Read 的内容生成语义信息
4. 优先保证导航质量，而不是堆砌摘要数量
