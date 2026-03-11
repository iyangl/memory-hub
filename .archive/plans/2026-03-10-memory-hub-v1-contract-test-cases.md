# Memory Hub v1 契约测试样例
日期：2026-03-10
状态：Draft v0.1
关联：
- [v1 契约草案](/Users/sunpure/Documents/Code/memory-hub/.archive/plans/2026-03-10-memory-hub-v1-contract-draft.md)
- [v1 schema 细化草案](/Users/sunpure/Documents/Code/memory-hub/.archive/plans/2026-03-10-memory-hub-v1-schema-draft.md)

## 1. 目标
本稿定义“实现前就能写”的契约测试样例，优先覆盖：
- MCP 参数校验
- write guard 行为
- proposal 队列行为
- approve / reject / rollback 原子性
- system URI 读取约束

## 2. 测试分层
1. MCP 合约测试：参数、返回 JSON、错误码
2. Repository/Service 测试：schema、事务、版本链
3. CLI 契约测试：exit code + envelope + 状态变更

## 3. 基础夹具
### 3.1 初始 approved 数据
夹具 A：
- `identity://assistant-role`
  - `type=identity`
  - `title=Assistant Role`
  - `content=You are the repository coding assistant.`
  - `current_version_id=1`
- `constraint://do-not-edit-durable-memory-directly`
  - `type=constraint`
  - `title=Do Not Edit Durable Memory Directly`
  - `content=Agent must use propose_* tools for durable memory changes.`
  - `current_version_id=2`

### 3.2 初始 version 数据
夹具 B：
- version 1 -> `identity://assistant-role`
- version 2 -> `constraint://do-not-edit-durable-memory-directly`

### 3.3 时间与 actor
为避免脆弱测试，统一使用固定值：
- `created_at=2026-03-10T12:00:00Z`
- `reviewed_at=2026-03-10T12:05:00Z`
- `actor=test-reviewer`

## 4. MCP 合约测试样例
### 4.1 `read_memory`
1. `read_memory("system://boot")`
   - 期望：`ok=true`
   - `code=MEMORY_READ`
   - 只返回 `identity` 与 `constraint`
   - 排序为 `identity` 在前，`constraint` 在后
2. `read_memory("decision://missing")`
   - 期望：`ok=false`
   - `code=MEMORY_NOT_FOUND`
3. `read_memory("bad-uri")`
   - 期望：`ok=false`
   - `code=INVALID_URI`

### 4.2 `search_memory`
1. `search_memory("durable memory")`
   - 期望：只搜索 approved
   - 不返回 pending / rejected proposal
2. `search_memory("", null, 10)`
   - 期望：`ok=false`
   - `code=EMPTY_QUERY`
3. `search_memory("assistant", "bad", 10)`
   - 期望：`ok=false`
   - `code=INVALID_TYPE`
4. `search_memory("assistant", null, 0)`
   - 期望：`ok=false`
   - `code=INVALID_LIMIT`

### 4.3 `propose_memory`
1. create 成功入队
   - 输入：新的 `decision`
   - 期望：`ok=true`
   - `code=PROPOSAL_CREATED`
   - `data.proposal_kind=create`
   - `data.status=pending`
   - `data.target_uri` 已分配且稳定
2. 重复内容命中 NOOP
   - 输入：内容与已存在 approved 完全一致
   - 期望：`ok=true`
   - `code=NOOP`
   - 不写入 proposal 表
3. 高重合命中 UPDATE_TARGET
   - 输入：与已有 approved 高重合
   - 期望：`ok=true`
   - `code=UPDATE_TARGET`
   - `data.guard_target_uri` 非空
4. 缺少 `why_not_in_code`
   - 期望：`ok=false`
   - `code=MISSING_WHY_NOT_IN_CODE`
5. guard 异常
   - 期望：`ok=false`
   - `code=GUARD_UNAVAILABLE`

### 4.4 `propose_memory_update`
1. patch 成功入队
   - 输入：`old_string/new_string`
   - 前置：`old_string` 在 base version 唯一命中
   - 期望：`ok=true`
   - `code=PROPOSAL_CREATED`
   - proposal 中保存物化后的 `content`
2. append 成功入队
   - 输入：`append="\n- new rule"`
   - 期望：`ok=true`
   - `code=PROPOSAL_CREATED`
3. patch + append 同时传
   - 期望：`ok=false`
   - `code=PATCH_MODE_CONFLICT`
4. `old_string` 缺失
   - 期望：`ok=false`
   - `code=MISSING_OLD_STRING`
5. `new_string` 缺失
   - 期望：`ok=false`
   - `code=MISSING_NEW_STRING`
6. `old_string` 不存在
   - 期望：`ok=false`
   - `code=OLD_STRING_NOT_FOUND`
7. `old_string` 命中多处
   - 期望：`ok=false`
   - `code=OLD_STRING_NOT_UNIQUE`
8. `old_string == new_string`
   - 期望：`ok=false`
   - `code=IDENTICAL_PATCH`
9. 空 append
   - 期望：`ok=false`
   - `code=EMPTY_APPEND`
10. 没有任何更新字段
   - 期望：`ok=false`
   - `code=NO_UPDATE_FIELDS`

## 5. Repository / Service 测试样例
### 5.1 schema 约束
1. `approved_memories.uri` 唯一
2. `memory_versions(uri, version_number)` 唯一
3. pending create proposal 的 `target_uri` 唯一
4. update proposal 必须有 `base_version_id`
5. create proposal 不允许有 `base_version_id`

### 5.2 create proposal 行为
1. proposal 创建时保留 `target_uri`
2. 第二个同 title proposal 自动 suffix 为 `-2`
3. `NOOP` / `UPDATE_TARGET` 不落库

### 5.3 update proposal 物化
1. proposal 保存 `patch_*` 与物化后的 `content`
2. base version 后续即使变化，proposal 的 `content` 保持不变

### 5.4 approve
1. approve create
   - 写入 `memory_versions(version_number=1)`
   - 写入 `approved_memories`
   - proposal 状态变 `approved`
   - 写入 `audit_events`
2. approve update
   - `version_number` 加 1
   - `approved_memories.current_version_id` 切到新版本
   - 旧版本仍可查询
3. approve stale proposal
   - 前置：approved 当前版本已变化
   - 期望：事务失败
   - `code=STALE_PROPOSAL`
   - 不新增 version，不改 proposal 状态
4. approve 事务中途失败
   - 期望：不留下部分 version / approved 更新
   - `code=APPROVE_TRANSACTION_FAILED`

### 5.5 reject
1. reject pending proposal
   - 只改 proposal 状态
   - 不改 approved
   - 写入 audit
2. reject 无 note
   - `code=MISSING_REVIEW_NOTE`
3. reject 非 pending
   - `code=PROPOSAL_NOT_PENDING`

### 5.6 rollback
1. rollback 到历史版本成功
   - 生成新 version
   - `approved_memories.current_version_id` 指向新 version
   - 新 version 内容等于目标历史版本内容
2. rollback 到不属于该 uri 的版本
   - `code=ROLLBACK_TARGET_MISMATCH`
3. rollback 事务中途失败
   - `code=ROLLBACK_TRANSACTION_FAILED`
   - 不留下部分更新

## 6. CLI 契约测试样例
### 6.1 `review list`
1. 有 2 条 pending proposal
   - exit code = 0
   - `code=REVIEW_QUEUE_OK`
   - `data.items` 数量正确
2. 无 pending proposal
   - exit code = 0
   - `data.items=[]`

### 6.2 `review show`
1. show create proposal
   - `current_memory=null`
   - `computed_diff` 是空基线到 proposal content 的 diff
2. show update proposal
   - `current_memory.uri == proposal.target_uri`
   - `base_version.version_id == proposal.base_version_id`
3. 不存在 proposal
   - exit code = 1
   - `code=PROPOSAL_NOT_FOUND`

### 6.3 `review approve`
1. approve 成功
   - exit code = 0
   - `code=PROPOSAL_APPROVED`
   - 返回 `proposal_id`、`uri`、`from_version_id`、`to_version_id`、`audit_event_id`
2. 重复 approve 同一 proposal
   - exit code = 1
   - `code=PROPOSAL_NOT_PENDING`

### 6.4 `review reject`
1. reject 成功
   - exit code = 0
   - `code=PROPOSAL_REJECTED`
2. 缺少 `--note`
   - exit code = 1
   - `code=MISSING_REVIEW_NOTE`

### 6.5 `rollback`
1. rollback 成功
   - exit code = 0
   - `code=ROLLBACK_APPLIED`
   - 返回 `uri`、`from_version_id`、`to_version_id`、`audit_event_id`
2. 目标版本不存在
   - exit code = 1
   - `code=VERSION_NOT_FOUND`

## 7. 第一批必须先写的测试
建议先实现这 12 条：
1. `read_memory(system://boot)` 只返回 identity/constraint
2. `propose_memory` 成功创建 create proposal 并保留 target_uri
3. `propose_memory` 重复内容返回 `NOOP`
4. `propose_memory_update` patch 成功时保存物化后的 `content`
5. `propose_memory_update` old_string 多命中返回 `OLD_STRING_NOT_UNIQUE`
6. `propose_memory_update` 空 append 返回 `EMPTY_APPEND`
7. `approve` create 生成 version 1 + approved row + audit
8. `approve` update 生成新 version 且 proposal 变 approved
9. `approve` stale proposal 返回 `STALE_PROPOSAL` 且无部分提交
10. `reject` 只改 proposal 状态，不改 approved
11. `rollback` 生成新 version，不直接回指旧 version
12. CLI 业务错误返回 exit code 1，系统错误返回 exit code 2

## 8. 暂不进第一批测试
以下可放到第二批：
- search 排序细节的精确断言
- reviewer / note 的审计展示格式
- 大文本 diff 渲染
- 性能测试与 FTS 细节
