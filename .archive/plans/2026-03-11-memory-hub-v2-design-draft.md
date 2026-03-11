# Memory Hub v2 统一项目记忆面设计草案

日期：2026-03-11  
状态：草案已冻结，作为 v2 目标形态基线

## 1. 目标

v2 收敛成一个项目级统一记忆系统，不再把历史双目录形态当作长期产品心智。

固定前提：

- 唯一根目录：`.memory/`
- 项目级 durable store：`.memory/_store/memory.db`
- `docs lane` 是正式项目知识主文档
- DB 是最小控制面，不是统一知识正文主库
- `durable-only` 内容继续由 DB 主存
- `docs-backed / dual-write` 内容以 docs 为正文主文档
- `docs-backed / dual-write` 的版本与回滚回到 docs 侧
- durable rollback 只保留给 `durable-only`

## 2. 目录布局

```text
.memory/
├── manifest.json
├── docs/
│   ├── architect/
│   ├── pm/
│   ├── dev/
│   └── qa/
├── catalog/
│   ├── topics.md
│   └── modules/
└── _store/
    ├── memory.db
    ├── projections/
    └── exports/
```

其中：

- `docs/`：正式项目知识正文
- `catalog/`：文档索引，内部自动维护
- `_store/memory.db`：durable review / status / recall 的最小控制面

## 3. 内部路由

统一系统内部固定三种结果：

- `docs-only`
  - 只进入 docs
  - 适合正式项目知识
  - 走 docs 轻审查
- `durable-only`
  - 只进入 durable DB
  - 适合用户偏好、身份、跨会话习惯等不应进入正式项目文档的长期记忆
  - 走 proposal / review / rollback / audit
- `dual-write`
  - docs 是主文档
  - DB 只保留 `doc_ref`、摘要、状态和必要索引
  - 不长期双存完整正文

## 4. DB 的角色

DB 负责：

- durable-only proposal / review / approve / reject / rollback / audit
- docs-backed / dual-write 的必要控制信息与引用
- `system://boot` 所需投影
- 混合检索所需索引和摘要
- review surface 的结构化数据

DB 不负责：

- 作为 docs-backed / dual-write 的长期全文主库
- 统一承接所有知识的全文版本链
- 替代 docs 成为项目正式知识面

## 5. Skill 设计

v2 对外主入口固定为：

- `project-memory`
  - 统一项目记忆主入口
  - 负责读 docs / catalog / durable / review
  - 负责把 durable 写入意图路由到内部 durable branch
- `memory-admin`
  - 维护与诊断
  - repair / diagnose / session-extract

## 6. MCP 设计

v2 主接口固定为：

- `read_memory(ref, anchor?)`
- `search_memory(query, scope=docs|durable|all, type?, limit?)`
- `capture_memory(...)`
- `update_memory(...)`
- `show_memory_review(...)`

统一 ref：

- `system://...`
- `doc://<bucket>/<name>`
- `catalog://topics`
- `catalog://modules/<name>`
- 现有 durable URI：`identity://...` / `decision://...` / `constraint://...` / `preference://...`

## 7. Review Surface

review surface 分成两类：

- `durable review`
  - 适用于 durable-only
  - proposal / approve / reject / rollback / audit
- `docs change review`
  - 适用于 docs-only / dual-write 的 docs 变更
  - 轻审查：查看 diff、确认应用、拒绝应用

共同原则：

- 展示层可以统一
- 状态机不能混用
- CLI 仍是 durable review 的唯一权威执行面

## 8. 设计边界

v2 不做：

- 用户级单库
- 多租户、远程服务、图数据库
- 让 DB 重新成为所有知识的全文主库
- 一次性大切换
- 把历史布局兼容或自动迁移当成产品能力
