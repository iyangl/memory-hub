# Memory Hub v1 Schema 细化草案
日期：2026-03-10
状态：Draft v0.1
关联：[v1 契约草案](/Users/sunpure/Documents/Code/memory-hub/.archive/plans/2026-03-10-memory-hub-v1-contract-draft.md)

## 1. 目标
本稿只定义支撑 v1 契约所需的最小 SQLite schema，不引入检索增强、导出、后台 worker、alias、图结构。

## 2. 设计原则
1. approved memory 是当前真相，version 是历史链，proposal 是待审输入。
2. proposal 必须可直接驱动 review，不依赖重新计算 patch。
3. update proposal 必须防 stale approve。
4. rollback 必须追加新版本，不修改旧版本内容。
5. schema 优先服务契约测试和事务边界，而不是追求通用性。

## 3. 表清单
v1 最小表：
- `schema_migrations`
- `approved_memories`
- `memory_versions`
- `memory_proposals`
- `audit_events`

## 4. 表结构
### 4.1 `schema_migrations`
用途：记录 migration 版本。

建议字段：
- `version TEXT PRIMARY KEY`
- `applied_at TEXT NOT NULL`
- `checksum TEXT NOT NULL`

### 4.2 `approved_memories`
用途：当前生效版本的聚合快照。

建议字段：
- `uri TEXT PRIMARY KEY`
- `type TEXT NOT NULL CHECK (type IN ('identity','decision','constraint','preference'))`
- `title TEXT NOT NULL`
- `content TEXT NOT NULL`
- `content_hash TEXT NOT NULL`
- `recall_when TEXT NOT NULL DEFAULT ''`
- `why_not_in_code TEXT NOT NULL`
- `source_reason TEXT NOT NULL`
- `current_version_id INTEGER NOT NULL UNIQUE`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

建议索引：
- `idx_approved_memories_type(type)`
- `idx_approved_memories_updated_at(updated_at DESC)`

约束：
- `uri` 全局唯一
- `content_hash` 不承担唯一约束，只用于 guard / 测试 / diff 缓存

### 4.3 `memory_versions`
用途：版本链和 rollback 基线。

建议字段：
- `version_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `uri TEXT NOT NULL`
- `version_number INTEGER NOT NULL`
- `type TEXT NOT NULL CHECK (type IN ('identity','decision','constraint','preference'))`
- `title TEXT NOT NULL`
- `content TEXT NOT NULL`
- `content_hash TEXT NOT NULL`
- `recall_when TEXT NOT NULL DEFAULT ''`
- `why_not_in_code TEXT NOT NULL`
- `source_reason TEXT NOT NULL`
- `supersedes_version_id INTEGER REFERENCES memory_versions(version_id)`
- `created_at TEXT NOT NULL`
- `created_by TEXT NOT NULL`
- `created_via TEXT NOT NULL CHECK (created_via IN ('approve','rollback'))`

建议索引：
- `UNIQUE(uri, version_number)`
- `idx_memory_versions_uri_created_at(uri, created_at DESC)`

约束：
- `version_number` 对同一 `uri` 单调递增
- create approve 生成 `version_number=1`
- rollback 也写新行，只是 `content` 复制自历史目标版本

### 4.4 `memory_proposals`
用途：待审 proposal 队列。

建议字段：
- `proposal_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `proposal_kind TEXT NOT NULL CHECK (proposal_kind IN ('create','update'))`
- `status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected'))`
- `target_uri TEXT NOT NULL`
- `base_version_id INTEGER REFERENCES memory_versions(version_id)`
- `type TEXT NOT NULL CHECK (type IN ('identity','decision','constraint','preference'))`
- `title TEXT NOT NULL`
- `content TEXT NOT NULL`
- `content_hash TEXT NOT NULL`
- `recall_when TEXT NOT NULL DEFAULT ''`
- `why_not_in_code TEXT NOT NULL`
- `source_reason TEXT NOT NULL`
- `patch_old_string TEXT`
- `patch_new_string TEXT`
- `append_content TEXT`
- `guard_decision TEXT NOT NULL CHECK (guard_decision='PENDING_REVIEW')`
- `guard_reason TEXT NOT NULL`
- `guard_target_uri TEXT`
- `created_at TEXT NOT NULL`
- `created_by TEXT NOT NULL`
- `reviewed_at TEXT`
- `reviewed_by TEXT`
- `review_note TEXT`

建议索引：
- `idx_memory_proposals_status_created_at(status, created_at ASC)`
- `idx_memory_proposals_target_uri(target_uri)`
- `idx_memory_proposals_base_version_id(base_version_id)`
- `UNIQUE(target_uri, status) WHERE proposal_kind='create' AND status='pending'`

约束：
- create proposal：`base_version_id IS NULL`
- update proposal：`base_version_id IS NOT NULL`
- create proposal 的 `target_uri` 在 proposal 创建时就分配并保留
- update proposal 的 `content` 是基于 `base_version_id` 物化后的候选全文
- `patch_*` / `append_content` 只用于 review 展示与审计，不用于 approve 时重算内容

说明：
- v1 不存 `NOOP` / `UPDATE_TARGET` proposal 行
- 如需避免重复 pending update，可后续追加唯一索引 `(target_uri, base_version_id, content_hash) WHERE status='pending'`

### 4.5 `audit_events`
用途：记录 approve / reject / rollback。

建议字段：
- `event_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `event_type TEXT NOT NULL CHECK (event_type IN ('approve','reject','rollback'))`
- `proposal_id INTEGER REFERENCES memory_proposals(proposal_id)`
- `uri TEXT NOT NULL`
- `from_version_id INTEGER REFERENCES memory_versions(version_id)`
- `to_version_id INTEGER REFERENCES memory_versions(version_id)`
- `actor TEXT NOT NULL`
- `note TEXT NOT NULL DEFAULT ''`
- `created_at TEXT NOT NULL`

建议索引：
- `idx_audit_events_uri_created_at(uri, created_at DESC)`
- `idx_audit_events_proposal_id(proposal_id)`

## 5. URI 保留策略
create proposal 时立即生成 `target_uri`：
1. `slug = kebab_case(title)`
2. 先检查 `approved_memories.uri`
3. 再检查 `memory_proposals.target_uri WHERE proposal_kind='create' AND status='pending'`
4. 冲突则顺延 `-2`、`-3`

结论：
- review 阶段看到的 URI 与 approve 后一致
- 不需要在 approve 时重新分配 URI

## 6. update proposal 物化策略
update proposal 创建流程：
1. 读取 `approved_memories` 当前行
2. 取出 `current_version_id` 作为 `base_version_id`
3. 在内存里应用 patch 或 append
4. 得到候选 `content`
5. 将 `content` 与 `patch_*`/`append_content` 一起写入 `memory_proposals`

结论：
- `review show` 可直接对比 `base_version.content` 与 `proposal.content`
- `approve` 不依赖再次回放 patch
- 即使 proposal 之后变 stale，也不会丢失原始候选内容

## 7. 事务边界
### 7.1 approve
单事务步骤：
1. 读取并锁定 pending proposal
2. 如为 update，校验 `approved_memories.current_version_id == base_version_id`
3. 计算 `next_version_number`
4. 插入 `memory_versions`
5. create 时插入 `approved_memories`；update 时更新 `approved_memories`
6. 更新 `memory_proposals.status='approved'`
7. 写入 `audit_events`

### 7.2 reject
单事务步骤：
1. 读取并锁定 pending proposal
2. 更新 `memory_proposals.status='rejected'`
3. 写入 `audit_events`

### 7.3 rollback
单事务步骤：
1. 读取 `approved_memories` 当前版本
2. 读取目标 `memory_versions`
3. 校验目标版本 `uri` 一致
4. 插入新 `memory_versions(created_via='rollback')`
5. 更新 `approved_memories`
6. 写入 `audit_events`

## 8. 初版不做
以下内容不进 v1 schema：
- FTS 表
- embeddings / gist / tags
- 导出 markdown 表
- review snapshot 表
- 软删除字段
- alias / path / graph 表

## 9. 实现前必须补的 repository 接口
建议最小 repository/service 接口：
- `get_approved_by_uri(uri)`
- `search_approved(query, type, limit)`
- `insert_create_proposal(...)`
- `insert_update_proposal(...)`
- `list_pending_proposals()`
- `get_proposal_detail(proposal_id)`
- `approve_proposal(proposal_id, reviewer, note)`
- `reject_proposal(proposal_id, reviewer, note)`
- `rollback_memory(uri, to_version_id, reviewer, note)`

## 10. 本稿冻结的新增决策
1. create proposal 在创建阶段保留 `target_uri`。
2. update proposal 同时保存“物化后的候选全文”和“原始 patch/append 意图”。
3. approve 永远写 proposal 已保存的 `content`，不重新回放 patch。
