---
description: '加载项目记忆到当前上下文'
---

# /memory-hub:recall — 加载项目记忆

按显式记忆主路径加载项目记忆：优先 `search -> read`，只读取与当前任务直接相关的 durable docs。

## 上下文

- 用户任务描述：$ARGUMENTS

---

## 执行流程

### Step 1：确保最小骨架存在

如果仓库尚未初始化 `.memory/`，先执行：

```bash
python3 -m lib.cli init
```

默认工作流里，`init` 只用于确保最小目录与基础文件存在；即使当前 core 仍会顺带生成 legacy 产物，也不把它们当作 recall 前置。

### Step 2：先 search，再决定读什么

如果用户提供了任务描述（`$ARGUMENTS`），先提炼 1~3 个检索词，然后执行：

```bash
python3 -m lib.cli search "<关键词>"
```

原则：
1. 先用 search 定位 durable docs
2. 仅根据搜索命中决定读取范围
3. 不默认读取 `BRIEF.md`
4. 不默认执行 `recall-plan` / `working-set` / `execution-contract`

### Step 3：读取命中的 durable docs

对高相关命中，执行：

```bash
python3 -m lib.cli read <bucket> <filename>
```

必要时可先查看 bucket 文件列表：

```bash
python3 -m lib.cli list <bucket>
```

读取范围应保持最小化：
- 能回答当前任务即可
- 不因为存在 legacy catalog 就额外扩读
- 不把 module cards 作为默认前置依赖

### Step 4：无命中时的处理

如果 search 无法稳定定位相关 durable docs：
- 直接说明当前没有可复用的显式记忆
- 转入源码或当前任务上下文继续工作
- 不为了 recall 再额外生成派生产物

如确有兼容性需要，可显式使用 legacy 命令：
- `catalog-read`
- `brief`
- `recall-plan`
- `working-set`
- `execution-contract`

但这些都不是默认路径。

### Step 5：确认就绪

向用户简短确认：
- 搜索使用了哪些关键词
- 实际读取了哪些 durable docs
- 若无命中，明确说明“当前任务无可复用显式记忆”

---

## 注意事项

- durable docs 在 `.memory/docs/`，这是默认 recall 的唯一正本
- recall 的核心不是“读得越多越好”，而是“先 search，再决定读什么”
- `BRIEF.md`、`catalog/`、`working-set`、`execution-contract` 都视为 legacy/兼容能力，不再是默认前置
- 长会话中如果感觉上下文变得模糊，可以重新调用 `/memory-hub:recall`
