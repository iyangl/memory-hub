# Memory Hub 全量备份 + 架构目录方案（讨论稿）

- 日期：2026-02-09
- 执行者：Codex
- 状态：讨论中（Draft v1）

## 1. 背景与目标

我们希望在项目迭代过程中，始终保持对整体架构的掌控能力，具体包括：

1. 可以恢复任意时刻代码状态（防丢失、防误改）。
2. 可以快速理解系统整体设计（模块、通信、数据流、设计模式）。
3. 可以追踪“文件/类/函数”之间的关联关系（谁定义、谁调用、谁依赖）。
4. 可以快速定位某功能的实现路径与测试覆盖情况。

本方案不是单纯“代码备份”，而是建立一个“可恢复 + 可理解”的项目知识底座。

---

## 2. 方案总览：双轨备份

采用“双轨并行”策略：

### 2.1 轨道A：源码快照备份（Recovery）

目标：确保项目可恢复。

建议保存内容：

- Git 历史快照：`git bundle`
- 工作区快照：当前文件树压缩包（含未提交变更）
- 元信息：`manifest.json`（commit、分支、时间戳、文件哈希、dirty 状态）

优点：

- 可靠恢复。
- 支持对比不同时间点。

局限：

- 不直接回答“架构是什么、模块如何协作”。

### 2.2 轨道B：架构目录索引（Catalog）

目标：确保项目可理解。

建议保存内容：

- 文件目录卡（每个文件的职责说明）
- 符号目录卡（类/函数/常量）
- 依赖与调用关系图
- 关键业务流程图
- 架构决策记录（ADR 风格）
- 测试映射（功能 -> 测试）

优点：

- 便于认知与沟通。
- 有助于新人接力与长期维护。

局限：

- 若不自动刷新，容易过时。

---

## 3. 初始化时机（第一次建立）

### 3.1 基线初始化（必须）

触发条件：

- 仓库中不存在 `.codex/library/`。

初始化动作：

1. 生成一次全量源码快照（轨道A）。
2. 生成一次全量架构目录（轨道B）。
3. 产出“架构总览页”，作为后续讨论入口。

### 3.2 强制重建基线（可选触发）

满足任一条件即建议重建：

- 核心模块重构（如 `server.py`、`sync.py`、`store.py`）。
- 数据库 schema 重大调整。
- 大规模目录迁移或模块拆分。
- 跨分支迁移到长期维护分支。

---

## 4. 同步时机（保持目录新鲜）

### 4.1 热同步（高频、轻量）

建议时机：会话结束（`memory-push` 前后）。

策略：

- 仅处理本次变更文件（增量刷新）。
- 更新对应文件卡、符号卡、调用边。

### 4.2 温同步（中频、中量）

建议时机：每次 commit 后。

策略：

- 重建模块关系图。
- 刷新测试映射。

### 4.3 冷同步（低频、全量）

建议时机：每日或每周一次。

策略：

- 全仓重扫，纠偏增量同步可能遗漏。
- 产出健康检查报告（索引完整率、孤立符号数等）。

---

## 5. 目录产物设计（图书馆目录）

建议目录结构：

```text
.codex/library/
  snapshots/
    <snapshot_id>/
      source.bundle
      working-tree.zip
      manifest.json
  catalog/
    <snapshot_id>/
      repo_profile.md
      modules.json
      files_index.jsonl
      symbols_index.jsonl
      call_graph.json
      tests_map.json
      patterns.md
      contracts.md
      flows/
        flow_pull.md
        flow_push.md
        flow_resolve_conflict.md
```

字段说明（核心）：

- `files_index.jsonl`：路径、语言、行数、职责、入口级别、变更热度。
- `symbols_index.jsonl`：符号名、类型、签名、定义位置、入边/出边。
- `call_graph.json`：跨文件调用关系边（caller -> callee）。
- `modules.json`：模块边界与依赖方向。
- `tests_map.json`：功能点、关联实现文件、覆盖测试文件。

---

## 6. 以 `memory_hub/policy.py` 为例

本节用于说明“目录不是抽象概念”，而是可落地条目。

### 6.1 文件卡示例（files_index）

- 文件：`memory_hub/policy.py`
- 职责：任务类型识别、角色映射、上下文摘要裁剪、角色合法性校验。
- 主要被调用方：`memory_hub/sync.py`
- 风格标签：表驱动策略、兜底回退。

### 6.2 符号卡示例（symbols_index）

1. `resolve_task_type(task_prompt, requested_task_type)`
   - 规则：显式参数优先，其次关键词匹配，最后回退到 `planning`。
   - 位置：`memory_hub/policy.py`
2. `roles_for_task(task_type)`
   - 规则：基于任务类型映射角色组合。
3. `truncate_to_budget(text, max_tokens)`
   - 规则：按字符预算裁剪（`max_tokens * 4`，下限 400）。
4. `build_context_brief(role_payloads, open_loops_top, handoff_latest, max_tokens)`
   - 规则：拼接角色上下文、open loops、最新 handoff，最终走预算裁剪。
5. `normalize_role(role)`
   - 规则：角色规范化 + 合法性校验。

### 6.3 关系卡示例（call_graph）

- `session_sync_pull -> resolve_task_type`
- `session_sync_pull -> roles_for_task`
- `session_sync_pull -> build_context_brief`

### 6.4 模式卡示例（patterns）

- 任务识别：关键词表驱动（中英混合词典）。
- 角色注入：固定角色池 + 任务映射。
- 失败处理：自动回退到 `planning` 保证可用性。

### 6.5 测试映射示例（tests_map）

- 直接覆盖：`tests/test_policy.py`
- 间接覆盖：`tests/test_sync_flow.py`（通过 `session_sync_pull` 间接验证策略行为）。

---

## 7. 针对当前 Memory Hub 的落地建议

### 7.1 优先级建议

P0（先做）

1. 建立 `.codex/library/` 基线目录。
2. 先产出 `repo_profile.md` + `modules.json` + `files_index.jsonl`。
3. 完成 `policy.py/sync.py/store.py/server.py` 四大核心文件的符号卡与调用图。

P1（随后）

1. 增加 `tests_map.json`。
2. 增加三条关键流程图（pull/push/resolve_conflict）。
3. 增加 ADR 风格决策记录。

P2（增强）

1. 增加变更热度统计。
2. 增加“孤立模块/未覆盖功能”预警。
3. 增加目录完整性评分。

### 7.2 目录更新约定（建议）

- 会话结束：至少更新受影响文件的目录卡。
- 合并前：刷新模块关系图与测试映射。
- 每周：执行一次全量重建。

---

## 8. 讨论议题（待你拍板）

我们接下来建议逐项确认以下问题：

1. **存储粒度**：是否保存每次会话一个 `snapshot_id`？
2. **保留策略**：快照保留 30 天、90 天，还是长期保留？
3. **目录深度**：是否从“函数级关系图”开始，还是先做“文件级关系图”？
4. **自动化程度**：第一阶段手动生成，还是直接脚本化全自动？
5. **质量门槛**：是否设定目录完整率阈值（如 ≥95%）？

---

## 9. 总结

核心结论：

- “全量代码备份”解决恢复问题，
- “全量架构目录”解决理解与掌控问题，
- 双轨并行才是长期可维护的方案。

本稿作为讨论基线，后续可升级为执行版（含脚本、字段 schema、更新命令、验收标准）。
