# execution-contract Phase 2 最小实现计划

> 日期：2026-04-03
> 状态：draft
> 用途：项目内 Git 跟踪的 Phase 2 实施计划

## Context

Phase 1 已把 `working-set` 语义升级为 `resume-pack(v1)`，并暴露了 `primary_evidence_gap` 与 `verification_focus`。当前主链仍是：`task -> recall-plan -> if deep: working-set -> act -> save-request -> save`。缺口在于：`working-set` 解决了“恢复上下文”，`save` 解决了“durable 写回”，但两者之间缺少一个 act 前的机器可读边界对象。

Phase 2 的目标不是改写 recall/save core，而是在 `working-set` 之后、实际执行之前新增一个薄的 `execution-contract` session artifact，把“允许做什么、必须补什么 evidence、什么算完成、写回只期待什么”固定下来。

## 推荐方案

### 1. 新增命令与模块

- 在 `lib/cli.py` 注册：`"execution-contract": "lib.execution_contract"`
- 新增 `lib/execution_contract.py`
- CLI 形态：
  - `memory-hub execution-contract --working-set-file <path> [--project-root <path>] [--out <file>]`
- v1 只接受 `working-set` 文件作为输入；不支持直接从 raw task / raw docs 生成
- 默认输出模式复用 `lib/session_working_set.py`：
  - 用 `sanitize_module_name()` 生成 slug
  - 用 `paths.session_file_path()` 落到 `.memory/session/<slug>-execution-contract.json`
  - 用 `atomic_write()` 写入
  - envelope `data` 中返回 `output_file`
- `working_set.source_plan` 只作为 provenance 透传；v1 不重新读取 planner，避免引入第二套推断路径

### 2. execution-contract 输出契约

建议 schema：

```json
{
  "version": "1",
  "task": "...",
  "source_working_set": "...",
  "source_plan": "...",
  "goal": "...",
  "known_context": ["..."],
  "primary_evidence_gap": "string | null",
  "allowed_sources": [{"type": "doc|module", "path": "...", "reason": "..."}],
  "disallowed_behaviors": ["..."],
  "verification_focus": ["..."],
  "success_criteria": ["..."],
  "required_evidence": ["..."],
  "durable_candidates": ["..."]
}
```

字段来源：
- `task` <- `working_set.task`
- `source_working_set` <- 当前输入文件路径
- `source_plan` <- `working_set.source_plan`
- `goal` <- `working_set.summary`
- `known_context` <- 压缩后 `items[*].summary`，去重、保序；语义是“resume-pack 提供的可依赖上下文摘要”，不是独立验证后的事实
- `primary_evidence_gap` <- `working_set.primary_evidence_gap`
- `allowed_sources` <- `working_set.priority_reads + items[*].sources`，按 `(type, path)` 去重；保留已有 `reason`
- `verification_focus` <- `working_set.verification_focus`
- `required_evidence` <- 若有 `primary_evidence_gap`，则为 `[primary_evidence_gap]`，否则 `[]`
- `success_criteria` <- 若有 `primary_evidence_gap`，则为 `["解决 primary_evidence_gap"]`；否则为 `[]`。不直接复用 `verification_focus`，避免把“验证焦点”误当作“完成判据”
- `disallowed_behaviors` <- 静态规则：禁止猜来源、禁止跳过 read-before-write、禁止把 session artifact 原样写回 durable docs、禁止绕过 `save` core，并包含 `allow_noop / require_search_and_read_for_non_noop / forbid_verbatim_session_writeback` 这类 save 不变量的文本化前置声明
- `durable_candidates` <- 直接透传 `working_set.durable_candidates`，不再额外包装 `writeback_expectation`

### 3. 关键实现边界

- `execution-contract` 只负责 act 前边界；不承载 `resume-pack` 的全量上下文、不承载 `verification-ledger` 的执行日志、不承载 `save-request` 的 durable 写入动作
- `known_context` 是 source-dependent 的上下文摘要，不冒充执行后验证过的事实
- `verification_focus` 与 `success_criteria` 必须分开：前者表示执行时该盯住什么，后者表示什么算完成
- 不改 `lib/memory_save.py`
- 不改 `save-request` schema
- 不改 `working-set` schema 与 `version`
- 不新增 `resume` 命令
- 不直接读取 raw docs/module cards 重新抽取事实；所有内容都从 final `working-set` 投影，保持 contract 薄且稳定

### 4. 宿主与文档接线

#### `.claude/commands/memory-hub/recall.md`

当前 deep 分支直接执行 `working-set`，但没有稳定输出路径；由于 `working-set` 默认文件名依赖 task slug，Phase 2 接线时应显式指定 `--out`：

```bash
py -3 -m lib.cli working-set --plan-file .memory/session/recall-plan.json --out .memory/session/working-set.json
py -3 -m lib.cli execution-contract --working-set-file .memory/session/working-set.json --out .memory/session/execution-contract.json
```

接入位置：
- 放在 deep recall 的 `working-set` 之后、`确认就绪` 之前（新增 Step 5.5）
- Step 6 汇报时一并说明已生成 `working-set` / `execution-contract`、当前 `primary_evidence_gap`、`verification_focus`

#### 文档同步

需要同步：
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`

更新点：
- CLI 命令表新增 `memory-hub execution-contract --working-set-file <path> [--out <file>]`
- deep recall 描述改为：`working-set(resume-pack)` 后可生成 `execution-contract` 作为 act 前边界

**本阶段不改** `.claude/commands/memory-hub/save.md`：contract 仍只是一种 session artifact，不是 save 的正式输入契约。

### 5. 测试策略

#### 新增 `tests/test_execution_contract.py`

复用 `tests/test_session_working_set.py` 的轻量 tmp-path fixture 模式，覆盖：
- 正常从 working-set 构建 contract
- `known_context` 只取压缩后 item summaries，去重保序，并明确其不是独立验证后的事实
- `allowed_sources` 对 `priority_reads` 与 `item.sources` 去重
- `verification_focus` 只来自 `working_set.verification_focus`
- `success_criteria` 只由 `primary_evidence_gap` 是否存在来推导，不直接复用 `verification_focus`
- `required_evidence` 只来自 `primary_evidence_gap`
- `durable_candidates` 直接透传，不再嵌套静态 save 不变量
- `--out` 写文件成功
- 未传 `--out` 时生成默认 session 文件并返回 `output_file`
- 缺少 working-set 文件 -> `FILE_NOT_FOUND`
- working-set JSON 非法 -> `INVALID_JSON`
- working-set 结构缺关键字段 -> 业务错误（新增明确错误码）

#### 更新 `tests/test_memory_flow.py`

在现有 deep recall E2E 上扩一段：
- `memory_init -> catalog_update/scan_modules -> brief -> recall_plan --out -> working_set --out -> execution_contract --out`
- 只断言 session artifact 已生成、关键字段存在，不触发 save

#### 验证命令

```bash
python3 -m pytest -q tests/test_execution_contract.py tests/test_memory_flow.py
python3 -m pytest -q
```

## 关键文件

- `lib/execution_contract.py`
- `lib/cli.py`
- `.claude/commands/memory-hub/recall.md`
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`
- `tests/test_execution_contract.py`
- `tests/test_memory_flow.py`

## 复用点

- `lib/session_working_set.py`：默认输出文件 + `output_file` 模式、`working-set` 作为唯一上游
- `lib/paths.py`：`session_file_path()`
- `lib/utils.py`：`atomic_write()`、`sanitize_module_name()`
- `lib/envelope.py`：统一成功/失败 envelope
- `tests/test_session_working_set.py`：轻量 dict 单测模式
- `tests/test_memory_flow.py`：主链 E2E 模式
- `tests/test_memory_save.py`：CLI guard / session artifact contract 的错误测试模式
