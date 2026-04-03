# execution-contract Phase 2 handoff

> 日期：2026-04-03
> 状态：in-progress / review 后待收尾
> 用途：当前实现状态、剩余问题与下一步接力说明

## 当前已完成

### 代码实现

已完成 Phase 2 最小实现的主体落地：

- `lib/cli.py`
  - 已注册 `execution-contract` 命令
- `lib/execution_contract.py`
  - 已实现从 `working-set` 生成 `execution-contract`
  - 已实现默认输出到 `.memory/session/<slug>-execution-contract.json`
  - 已实现 `FILE_NOT_FOUND` / `INVALID_JSON` / `INVALID_WORKING_SET` 错误路径
  - 已实现 `allowed_sources` 去重
  - 已实现中文 task 的 hash fallback 文件名
  - 已将 `durable_candidates` 占位过滤改为复用 `lib.session_working_set.DURABLE_CANDIDATE_PLACEHOLDER`
  - 已收紧 `task` / `source_plan` / `summary` 的非空白校验
- `lib/session_working_set.py`
  - 已提取共享常量 `DURABLE_CANDIDATE_PLACEHOLDER`

### 测试

已补齐：

- `tests/test_execution_contract.py`
  - 正常构建
  - `known_context` 去重
  - `allowed_sources` 去重
  - `primary_evidence_gap` -> `required_evidence` / `success_criteria`
  - `--out` 写文件
  - 默认输出文件名
  - 中文 task 默认输出名 hash fallback
  - placeholder durable candidate 过滤
  - `FILE_NOT_FOUND`
  - `INVALID_JSON`
  - `INVALID_WORKING_SET`
  - 坏嵌套字段
  - 空白必填字段
- `tests/test_memory_flow.py`
  - deep recall 主链已扩到 `execution-contract`

### 文档

已同步：

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `.claude/commands/memory-hub/recall.md`

### 验证

本地已通过：

```bash
python3 -m pytest -q
```

结果：`170 passed`

## 当前 review 结论

最新一轮双模型 review：

- Gemini：`PASS`，未发现 blocker
- Codex：仍有 1 个 **Major**

### 剩余 Major

`execution-contract.goal` 的语义来源不对。

当前实现：
- `lib/execution_contract.py` 中 `goal <- working_set.summary`

但现状里：
- `lib/session_working_set.py` 的 `summary` 实际来自 `why_these` 拼接
- 它表达的是“为什么推荐这些来源/为什么现在要读这些”
- 不等于任务目标本身

也就是说，当前 `goal` 字段在标准 deep recall 链路下，会被写成“来源选择理由”，而不是“act 前真正目标”。

## 建议的下一步

### Step 1：修正 `goal` 语义

优先方案（最小改动）：

- 把 `execution-contract.goal` 改为直接取 `working_set.task`
- 保留 `working_set.summary` 继续承担 resume-pack 的“来源摘要/why_these 压缩”角色
- 不在本阶段回头改 `working-set` schema

这样做的原因：
- 不需要扩 `working-set` schema
- 不引入新的 planner / working-set 推断链
- 能立刻让 `goal` 回到“任务目标”语义

### Step 2：补测试

至少补两类：

1. `tests/test_execution_contract.py`
   - 断言 `goal == task`
   - 不再断言 `goal == summary`

2. `tests/test_memory_flow.py`
   - 在真实 deep recall 链路里断言 `execution-contract.goal == recall task`
   - 用来防止 `goal <- summary(why_these)` 再次回归

### Step 3：回归验证

```bash
python3 -m pytest -q tests/test_execution_contract.py tests/test_memory_flow.py
python3 -m pytest -q
```

### Step 4：再跑一次 review

等 `goal` 语义修正后，再跑一轮 `/ccg:review`。

如果 review 无新的 Major / Critical，Phase 2 就可以视为完成。

## 不建议现在做的事

- 不要顺手改 `working-set.summary` 语义
- 不要新增 `working_set.goal` 字段
- 不要扩 `save-request` 或 `memory_save.py`
- 不要把 `execution-contract` 升级为 save 的正式输入
- 不要现在统一 `working-set` 与 `execution-contract` 的默认命名策略，除非用户明确要求顺手收口这一类一致性问题

## 推荐 commit message

```text
feat(memory): 新增 execution-contract 并收紧契约校验
```

如果把下一步 `goal` 语义修正单独提交，可用：

```text
fix(memory): 修正 execution-contract 的 goal 语义
```
