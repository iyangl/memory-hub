---
description: '加载项目记忆到当前上下文'
---

# /memory-hub:recall — 加载项目记忆

读取 BRIEF.md 将项目知识注入当前会话上下文，支持按需深入阅读完整文档。

## 上下文

- 用户任务描述：$ARGUMENTS

---

## 执行流程

### Step 1：读取 BRIEF.md

```bash
cat .memory/BRIEF.md
```

- **文件存在** → 读取内容，继续 Step 2
- **文件不存在** → 降级处理：

```bash
python3 -m lib.cli brief
cat .memory/BRIEF.md
```

### Step 2：注入上下文

将 BRIEF.md 的内容作为项目背景知识记住。这些信息包括：
- 项目技术栈和关键约束
- 开发约定
- 产品决策
- 测试策略

### Step 3：按需深入

如果用户提供了任务描述（$ARGUMENTS），根据 BRIEF.md 中的信息判断是否需要读取完整文档。

判断标准：BRIEF.md 中的摘要是否已经包含足够的上下文来完成任务？

- **摘要足够** → 直接开始工作
- **需要深入** → 读取相关完整文档：

```bash
python3 -m lib.cli read <bucket> <filename>
```

也可以通过搜索定位相关文档：

```bash
python3 -m lib.cli search "<关键词>"
```

### Step 4：确认就绪

向用户简短确认已加载的知识范围：

```
已加载项目记忆：
- <列出 BRIEF.md 中的主要知识领域>
- <如果深入读取了额外文档，列出>

可以开始工作了。
```

---

## 注意事项

- 长会话中如果感觉项目上下文变得模糊，可以重新调用本命令刷新
- BRIEF.md 是 docs/ 的派生摘要，不包含独有数据
- 如需更新 BRIEF.md 内容，应通过 `/memory-hub:save` 先更新 docs，BRIEF.md 会自动重建
