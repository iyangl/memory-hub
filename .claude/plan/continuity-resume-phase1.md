# continuity / resume Phase 1 实施方案

> 日期：2026-04-03
> 状态：draft
> 用途：把定稿转成可直接编码的最小实现计划

## 目标

在不改 save core、不引入新命令的前提下，把现有 `working-set` 语义升级为 `resume-pack(v1)`：

1. `recall-plan` 新增 `primary_evidence_gap`
2. `working-set` 透传 `primary_evidence_gap`
3. `working-set` 新增 `verification_focus`
4. 保留现有 `durable_candidates`

## 明确不做

- `next_minimal_action`
- 顶层 `constraints`
- `execution-contract`
- `verification-ledger`
- 独立 `resume` 命令
- `save` core 改动

## 输出契约

### `lib/recall_planner.py`

保持现有 `evidence_gaps` 字段，新增：

```json
{
  "primary_evidence_gap": "string | null"
}
```

规则：
- 先按现有逻辑生成 `evidence_gaps`
- 使用去重后的最终 `evidence_gaps`
- `primary_evidence_gap = evidence_gaps[0] if evidence_gaps else null`
- 仅新增字段，不改变 `recall_level`、`search_first`、`why_these` 等既有逻辑
- `version` 保持 `"1"`，避免无意义 schema churn

### `lib/session_working_set.py`

在现有输出上新增两个顶层字段：

```json
{
  "primary_evidence_gap": "string | null",
  "verification_focus": ["..."]
}
```

规则：
- `primary_evidence_gap` 从 planner 结果透传，不在 working-set 阶段二次推断
- `verification_focus` 必须从 **压缩后的** `items[*].bullets` 中提取
- 只收集以 `"验证:"` 开头的 bullet
- 去掉前缀后写入结果
- 去重、保序
- 不额外扩容：`verification_focus` 只能是 final `items` 的子集投影，不能比 `items` 更丰富
- `durable_candidates` 逻辑保持不变

## 具体改动文件

### 1. `lib/recall_planner.py`

改动点：
- 在返回结果前先得到最终去重后的 `evidence_gaps`
- 基于该列表生成 `primary_evidence_gap`
- 在返回 JSON 中加入该字段

建议实现：
- 不改现有 gap 判定分支
- 只在返回前做一次归一化，避免后续字段漂移

### 2. `lib/session_working_set.py`

改动点：
- 新增 `_build_verification_focus(items: list[dict]) -> list[str]`
- 输入必须是 `_compress_items()` 之后的 `items`
- 在 `build_working_set()` 返回值中加入：
  - `primary_evidence_gap`
  - `verification_focus`

建议实现顺序：
- 先保留现有 `_module_item()` 生成 `"验证: ..."` bullet 的逻辑
- 先得到 `items = _compress_items(...)`
- 再用 `items` 生成 `verification_focus`

### 3. `tests/test_recall_planner.py`

新增/调整断言：
- 有多个 gap 时，`primary_evidence_gap` 等于去重后首项
- 无 gap 时，`primary_evidence_gap is None`
- 新字段不影响既有 `recall_level` 判断

### 4. `tests/test_session_working_set.py`

新增/调整断言：
- `working-set` 透传 `primary_evidence_gap`
- `verification_focus` 来自压缩后的 `items[*].bullets`
- 只提取 `"验证:"` 项，忽略其他 bullet
- 去重、保序
- 若某条 `验证:` bullet 因压缩被裁掉，不能回流进 `verification_focus`
- 无命中时返回空列表
- `durable_candidates` 行为不变

## 推荐实现顺序

1. 改 `lib/recall_planner.py`
2. 补 `tests/test_recall_planner.py`
3. 改 `lib/session_working_set.py`
4. 补 `tests/test_session_working_set.py`
5. 运行最小回归
6. 若改动超过 30 行，执行质量门检查

## 验证

```bash
python3 -m pytest -q tests/test_recall_planner.py tests/test_session_working_set.py
python3 -m pytest -q
```

## 兼容性与边界

- 这次是 additive change：旧字段保留，新字段只增不删
- `working-set` 仍只适用于 `deep` recall，`light/skip` 行为不变
- `primary_evidence_gap` 必须来源于 planner，而不是 working-set 自己猜
- `verification_focus` 必须是 `items` 的子集投影，不得引入第二套原始材料抽取逻辑
- 现有 `durable_candidates` 是 save hint，不重定义为 action plan
