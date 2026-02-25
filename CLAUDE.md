# Memory Hub — AI 行为指引

本项目使用 Memory Hub 管理项目知识。`.memory/` 目录存储代码读不到的知识（设计决策、约束、演进历史、隐性前提、已知取舍）。

## Skill 列表

| Skill | 命令 |
|-------|------|
| `memory.init` | `memory-hub init` |
| `memory.read` | `memory-hub read <bucket> <file> [--anchor <anchor>]` |
| `memory.list` | `memory-hub list <bucket>` |
| `memory.search` | `memory-hub search "<query>"` |
| `memory.write` | `memory-hub write <bucket> <file> --topic <name> --summary "<desc>" [--anchor <anchor>] [--mode append\|overwrite] <<'EOF' ... EOF` |
| `catalog.read` | `memory-hub catalog-read [topics\|<module>]` |
| `catalog.update` | `memory-hub catalog-update <<'EOF' <json> EOF` |
| `catalog.repair` | `memory-hub catalog-repair` |

## 何时 Read

**触发条件：即将修改代码或做决策之前。**

1. 判断任务类型：
   - `quick_fix`（目标文件明确的单点修改）→ 可跳过 catalog.read topics
   - `scoped_change` / `feature_work` → 先 `catalog.read topics`
2. 定位到相关话题后，`memory.read` 读取对应知识文件
3. 要修改某个功能模块时，`catalog.read <module>` 读取详细索引
4. 修改代码或做设计决策前，至少加载 1 个相关 `memory.read`

兜底：`catalog.read topics` 找不到相关话题时，用 `memory.search` 跨桶检索。

## 何时 Write

**触发条件：产生了新的、代码里读不到的知识。**

判断标准：如果下一个会话的 AI 不知道这件事，会不会做出错误的决定？会 → 写，不会 → 不写。

1. 做出设计决策时 → `architect/` 桶，Decision Log 格式
2. 发现或确认约束时 → 对应桶
3. 需求讨论达成结论时 → `pm/` 桶
4. 建立代码约定时 → `dev/` 桶
5. 修改文件结构时 → 标记 `catalog_dirty = true`
6. 往基础文件新增话题段落时 → 同步注册到 topics.md

## 任务结束时

- 若 `catalog_dirty = true` → 执行 `catalog.update`
- 若本次发生过 `memory.write` 或 `catalog.update` → 执行 `catalog.repair`：
  - `ai_actions` 非空 → 立即自愈，再次 repair 确认清零
  - `manual_actions` 非空 → 向用户报告

## 决策演进格式

不删除旧决策，追加新决策并标注废弃关系：

```markdown
### 决策 N — <日期>
背景：<问题>
方案：
- A: <描述> ← 选择
- B: <描述>
选择原因：<为什么>
废弃：决策 M 的方案 X 不再使用（如适用）
```

## 文件管理

1. 先 `catalog.read topics` 看话题是否已有知识文件
2. 有 → `memory.write` 追加
3. 没有 → `memory.write` 创建新文件（自动注册）
