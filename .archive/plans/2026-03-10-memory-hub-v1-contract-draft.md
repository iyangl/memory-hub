# Memory Hub v1 契约草案
日期：2026-03-10
状态：Draft v0.1
定位：冻结 v1 MVP 的外部行为契约，作为实现、测试、Skill、CLAUDE 规则的共同基线。

## 1. 范围
本草案只冻结 5 条主链路：`propose_memory`、`propose_memory_update`、`review approve`、`review reject`、`rollback`。
v1 明确不做：语义检索、Web Review、自动提炼、多用户并发、旧 `.memory/` 迁移。

## 2. v1 不变量
1. durable memory 只能通过 MCP `propose_*` 进入系统。
2. agent 不允许直接写 `.memory*` 或 SQLite。
3. `read/search` 只读取 approved memory。
4. `system://*` 为只读系统 URI，v1 仅开放 `system://boot`。
5. durable memory 类型只允许：`identity / decision / constraint / preference`。
6. create proposal 必须包含 `why_not_in_code` 和 `source_reason`。
7. update proposal 必须包含 `source_reason`。
8. full replace 禁止；内容更新只允许 patch 或 append。
9. `approve` 必须是单事务；失败时不留下中间态。
10. `rollback` 必须生成新版本，不允许抹掉历史版本。

## 3. 资源模型
### 3.1 ApprovedMemory
当前生效的 durable memory。字段：`uri`、`type`、`title`、`content`、`recall_when`、`why_not_in_code`、`source_reason`、`current_version_id`、`created_at`、`updated_at`。
约束：一个 `uri` 在任意时刻只指向一个当前版本；`type` 与 `uri` domain 必须一致；`title` 与 `uri` 在创建后不可修改。

### 3.2 MemoryVersion
每次 approve 或 rollback 后产生一条新版本。字段：`version_id`、`version_number`、`uri`、`type`、`title`、`content`、`recall_when`、`why_not_in_code`、`source_reason`、`supersedes_version_id`、`created_at`、`created_by`。

### 3.3 MemoryProposal
待审写入请求。字段：`proposal_id`、`proposal_kind(create|update)`、`status(pending|approved|rejected)`、`target_uri`、`base_version_id`、`type`、`title`、`content`、`content_hash`、`recall_when`、`why_not_in_code`、`source_reason`、`patch_old_string`、`patch_new_string`、`append_content`、`guard_decision(NOOP|UPDATE_TARGET|PENDING_REVIEW)`、`guard_reason`、`guard_target_uri`、`created_at`、`reviewed_at`、`review_note`、`reviewed_by`。
约束：只有 `PENDING_REVIEW` 会真正写入 proposal 表；`NOOP` 与 `UPDATE_TARGET` 直接作为 MCP 返回，不入队；create proposal 在创建时生成并保留 `target_uri`；update proposal 在创建时固定 `base_version_id`，同时把 patch/append 物化成候选 `content`；approve 直接写 proposal 中保存的 `content`，不重新回放 patch。

### 3.4 AuditEvent
用于审计 approve / reject / rollback。字段：`event_id`、`event_type(approve|reject|rollback)`、`proposal_id`、`uri`、`from_version_id`、`to_version_id`、`actor`、`note`、`created_at`。

## 4. URI 契约
### 4.1 普通 memory URI
格式：
```text
<type>://<slug>
```
示例：`identity://assistant-role`、`constraint://do-not-edit-durable-memory-directly`、`decision://v1-contract-first`。
规则：
1. `type` 必须是四种 durable memory type 之一。
2. `<slug>` 由系统根据 `title` 生成，规则为小写 kebab-case。
3. 若同 type 下 slug 冲突，系统追加 `-2`、`-3` 等后缀。
4. agent 不传 `uri`；create 时由系统在 proposal 创建阶段生成并保留 `target_uri`。
5. approved 后 `uri` 不可修改。

### 4.2 系统 URI
v1 只保留 `system://boot`。
规则：只读；不参与写入；返回 approved 的 `identity` 与 `constraint`；排序固定为 `identity` 在前、`constraint` 在后、同类型内按 `created_at ASC`。

## 5. 状态机
### 5.1 create proposal
```text
请求 -> 参数校验 -> write guard -> 返回 NOOP / UPDATE_TARGET / PROPOSAL_CREATED
```
只有 guard 结果为 `PENDING_REVIEW` 才创建 proposal。approve 后生成 `ApprovedMemory`、`MemoryVersion(version_number=1)`、`AuditEvent(approve)`。

### 5.2 update proposal
```text
read current approved -> 生成候选新内容 -> 参数校验 -> write guard -> 返回 NOOP / UPDATE_TARGET / PROPOSAL_CREATED
```
update proposal 必须绑定 `base_version_id`。approve 时如果当前 `current_version_id != base_version_id`，返回 `STALE_PROPOSAL`。

### 5.3 review
`approve` 和 `reject` 只允许处理 `pending`。已 `approved/rejected` 的 proposal 再次操作，返回 `PROPOSAL_NOT_PENDING`。

### 5.4 rollback
仅允许对 approved memory 执行；输入必须指定 `uri + to_version_id`。rollback 语义不是“把 current_version_id 改回去”，而是以目标历史版本内容为基线生成一个新的最新版本，随后更新 `ApprovedMemory.current_version_id` 并写入 `AuditEvent(rollback)`。

## 6. 通用返回包络
MCP 与 CLI 统一返回 JSON：
```json
{
  "ok": true,
  "code": "PROPOSAL_CREATED",
  "message": "Proposal created.",
  "data": {},
  "degraded": false,
  "degrade_reasons": []
}
```
语义：`ok=true` 表示工具成功执行并返回确定结果，包含 `NOOP` 与 `UPDATE_TARGET`；`ok=false` 表示参数非法、资源不存在、状态冲突或系统失败。
CLI 退出码固定为：`0=成功`、`1=业务错误`、`2=系统错误`。

## 7. MCP 契约
### 7.1 `read_memory(uri)`
参数：`uri`，取值为 `system://boot` 或 approved memory URI。
成功码：`MEMORY_READ`。
返回 `data`：`uri`、`type`、`title`、`content`、`recall_when`、`current_version_id`、`updated_at`。
错误码：`INVALID_URI`、`MEMORY_NOT_FOUND`。

### 7.2 `search_memory(query, type?, limit?)`
参数：`query` 为非空字符串；`type` 可选；`limit` 默认 10，最大 50。
成功码：`SEARCH_OK`。
返回 `data.results[*]`：`uri`、`type`、`title`、`snippet`、`recall_when`、`updated_at`。
排序：`match_score DESC`、`updated_at DESC`、`uri ASC`。
错误码：`EMPTY_QUERY`、`INVALID_TYPE`、`INVALID_LIMIT`。

### 7.3 `propose_memory(type, title, content, recall_when, why_not_in_code, source_reason)`
成功结果：`PROPOSAL_CREATED`、`NOOP`、`UPDATE_TARGET`。
`PROPOSAL_CREATED.data`：`proposal_id`、`proposal_kind=create`、`status=pending`、`guard_decision=PENDING_REVIEW`。
`NOOP.data` / `UPDATE_TARGET.data`：`guard_decision`、`guard_reason`、`guard_target_uri`。
错误码：`INVALID_TYPE`、`EMPTY_TITLE`、`EMPTY_CONTENT`、`MISSING_WHY_NOT_IN_CODE`、`MISSING_SOURCE_REASON`、`GUARD_UNAVAILABLE`。

### 7.4 `propose_memory_update(uri, old_string?, new_string?, append?, recall_when?, why_not_in_code?, source_reason)`
规则：`old_string/new_string` 与 `append` 互斥；只允许 patch 或 append，不允许 full replace；`old_string` 必须在 base version 的 `content` 中唯一命中 1 处；至少要有一个更新项：内容 patch、append、`recall_when`、`why_not_in_code`；`source_reason` 必填；`type` 与 `title` 不可修改。
成功结果：`PROPOSAL_CREATED`、`NOOP`、`UPDATE_TARGET`。
`PROPOSAL_CREATED.data`：`proposal_id`、`proposal_kind=update`、`target_uri`、`base_version_id`、`status=pending`。
错误码：`INVALID_URI`、`MEMORY_NOT_FOUND`、`PATCH_MODE_CONFLICT`、`MISSING_OLD_STRING`、`MISSING_NEW_STRING`、`OLD_STRING_NOT_FOUND`、`OLD_STRING_NOT_UNIQUE`、`IDENTICAL_PATCH`、`EMPTY_APPEND`、`NO_UPDATE_FIELDS`、`FULL_REPLACE_FORBIDDEN`、`MISSING_SOURCE_REASON`、`GUARD_UNAVAILABLE`。

## 8. CLI 契约
### 8.1 `memory-hub review list`
成功码：`REVIEW_QUEUE_OK`。
返回 `data.items[*]`：`proposal_id`、`proposal_kind`、`status`、`type`、`title`、`target_uri`、`created_at`、`is_stale`。

### 8.2 `memory-hub review show <proposal_id>`
成功码：`PROPOSAL_DETAIL_OK`。
返回 `data`：`proposal`、`current_memory`、`base_version`、`computed_diff`。

### 8.3 `memory-hub review approve <proposal_id> [--reviewer <id>] [--note <text>]`
成功码：`PROPOSAL_APPROVED`。
返回 `data`：`proposal_id`、`uri`、`from_version_id`、`to_version_id`、`audit_event_id`。
错误码：`PROPOSAL_NOT_FOUND`、`PROPOSAL_NOT_PENDING`、`STALE_PROPOSAL`、`APPROVE_TRANSACTION_FAILED`。

### 8.4 `memory-hub review reject <proposal_id> --note <text> [--reviewer <id>]`
规则：`--note` 必填。
成功码：`PROPOSAL_REJECTED`。
返回 `data`：`proposal_id`、`status=rejected`、`audit_event_id`。
错误码：`PROPOSAL_NOT_FOUND`、`PROPOSAL_NOT_PENDING`、`MISSING_REVIEW_NOTE`。

### 8.5 `memory-hub rollback <uri> --to-version <version_id> --note <text> [--reviewer <id>]`
规则：`--note` 必填。
成功码：`ROLLBACK_APPLIED`。
返回 `data`：`uri`、`from_version_id`、`to_version_id`、`audit_event_id`。
错误码：`INVALID_URI`、`MEMORY_NOT_FOUND`、`VERSION_NOT_FOUND`、`ROLLBACK_TARGET_MISMATCH`、`MISSING_REVIEW_NOTE`、`ROLLBACK_TRANSACTION_FAILED`。

## 9. 错误码基线
输入校验：`INVALID_URI`、`INVALID_TYPE`、`INVALID_LIMIT`、`EMPTY_QUERY`、`EMPTY_TITLE`、`EMPTY_CONTENT`、`MISSING_WHY_NOT_IN_CODE`、`MISSING_SOURCE_REASON`、`PATCH_MODE_CONFLICT`、`MISSING_OLD_STRING`、`MISSING_NEW_STRING`、`OLD_STRING_NOT_FOUND`、`OLD_STRING_NOT_UNIQUE`、`IDENTICAL_PATCH`、`EMPTY_APPEND`、`NO_UPDATE_FIELDS`、`FULL_REPLACE_FORBIDDEN`、`MISSING_REVIEW_NOTE`。
资源与状态：`MEMORY_NOT_FOUND`、`PROPOSAL_NOT_FOUND`、`PROPOSAL_NOT_PENDING`、`VERSION_NOT_FOUND`、`STALE_PROPOSAL`、`ROLLBACK_TARGET_MISMATCH`、`READ_ONLY_SYSTEM_URI`。
写入守卫与事务：`GUARD_UNAVAILABLE`、`APPROVE_TRANSACTION_FAILED`、`ROLLBACK_TRANSACTION_FAILED`。

## 10. 本稿已冻结的关键决策
1. v1 采用结构化 JSON 契约，不使用自由文本返回。
2. create 时 agent 不自带 URI，系统在 proposal 创建阶段生成并保留 `target_uri`。
3. ordinary memory URI 采用 `<type>://<slug>`。
4. update proposal 采用 `base_version_id` 防止 stale approve，并保存物化后的候选 `content`。
5. v1 search 不引入 `scope_hint`、partial read、ancestor read。
6. v1 只开放 `system://boot`，不开放 `system://index/recent/audit`。
