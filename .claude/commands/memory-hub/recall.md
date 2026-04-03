---
description: '加载项目记忆到当前上下文'
---

# /memory-hub:recall — 加载项目记忆

按 recall-first 协议加载项目记忆：先读 base brief，再判定是否需要 search / light / deep recall。

## 上下文

- 用户任务描述：$ARGUMENTS

---

## 执行流程

### Step 1：确保 recall 上下文存在

如果仓库尚未初始化 `.memory/`，先执行：

```bash
py -3 -m lib.cli init
```

如果 `.memory/` 已存在，至少重建 BRIEF：

```bash
py -3 -m lib.cli brief
```

注意：`brief` 只负责重建 `BRIEF.md`，不负责补齐整个 catalog；未初始化时必须先 `init`。

### Step 1.5：检查 module cards 时效性（可选）

```bash
py -3 -m lib.cli modules-check
```

如果返回有 `stale`、`added` 或 `removed`，提示用户是否重新执行：

```bash
py -3 -m lib.cli scan-modules --out .memory/session/scan-modules.json
py -3 -m lib.cli catalog-update --file .memory/session/scan-modules.json
```

### Step 2：读取 base brief

读取 `.memory/BRIEF.md`，将其作为 boot summary 注入上下文。

### Step 3：执行 recall-plan 并保存结果

如果用户提供了任务描述（`$ARGUMENTS`），先执行：

```bash
py -3 -m lib.cli recall-plan --task "$ARGUMENTS" --out .memory/session/recall-plan.json
```

planner 的职责：
- 判断 `skip | light | deep`
- 判断 `task_kind`
- 判断是否需要 `search_first`
- 推荐相关 docs / modules
- 给出 `why_these`
- 明确 `evidence_gaps`

### Step 4：Search Before Guess

如果 planner 返回 `search_first = true`：

1. 先 search / catalog-read 定位相关对象
2. 再决定应该读取哪些 docs 或 module cards
3. 不允许仅凭任务文本直接猜来源

可用命令：

```bash
py -3 -m lib.cli search "<关键词>"
py -3 -m lib.cli catalog-read topics
py -3 -m lib.cli catalog-read <module>
py -3 -m lib.cli read <bucket> <filename>
```

### Step 5：按 recall 深度执行

#### `skip`
- 不再额外读取，直接开始工作
- 或仅补充读取极少量高相关来源

#### `light`
- 读取 base brief + 少量相关 docs / module cards
- 推荐来源时必须说明 `why_these`

#### `deep`
- 先根据 planner 结果构建 working set：

```bash
py -3 -m lib.cli working-set --plan-file .memory/session/recall-plan.json
```

- working set 会把高相关来源压缩成去重、限长、可直接消费的任务上下文
- module item 会尽量带上约束、风险、验证重点
- 再把 working set 注入当前上下文
- 如果 `evidence_gaps` 仍存在，先补读，再开始工作

### Step 6：确认就绪

向用户简短确认：
- 已读取的知识范围
- recall level
- 若为 deep，说明已生成 working set
- 若仍有 evidence gaps，明确列出

---

## 注意事项

- BRIEF.md 是派生产物，不直接手改
- recall 的核心不是“读得越多越好”，而是“先定位、再决定读什么”
- 长会话中如果感觉上下文变得模糊，可以重新调用 `/memory-hub:recall`
