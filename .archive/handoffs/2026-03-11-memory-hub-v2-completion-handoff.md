# Memory Hub v2 Completion Handoff

日期：2026-03-11
目的：归档 v2 主线开发完成态、真实会话验收结果，以及换电脑后继续开发的最小环境准备。

## 1. 当前结论

截至 2026-03-11，Memory Hub 的 v2 主线已经完成，当前状态可以定义为：

- `Phase 2A` 统一目录与底座：完成
- `Phase 2B` 统一读取入口与主 skill：完成
- `Phase 2C` 统一写入入口与 catalog 内化：完成
- `Phase 2D` 统一 review surface：完成
- `Phase 2E` 本地 hybrid recall：完成
- `Phase 2F` 自动会话提炼：完成

当前对外 memory skill surface 已收口为两个：

- `project-memory`
- `memory-admin`

当前统一根目录与存储基线：

- `.memory/`
- `.memory/docs/`
- `.memory/catalog/`
- `.memory/_store/memory.db`

当前主 workflow 已统一为：

- 读取：`memory-hub.read_memory(...)` / `memory-hub.search_memory(...)`
- 写入：`memory-hub.capture_memory(...)` / `memory-hub.update_memory(...)`
- review 展示：`memory-hub.show_memory_review(...)`
- 审批与回滚：CLI `memory-hub review ...` / `memory-hub rollback ...`
- 会话提炼：`memory-hub session-extract --file ...`

## 2. 已冻结的产品前提

v2 当前已经锁定的设计前提：

1. 这是项目级系统，不是用户级单库。
2. 每个项目自己的 durable store 固定为 `.memory/_store/memory.db`。
3. `docs lane` 是正式项目知识主文档。
4. DB 是最小控制面，不是统一知识正文主库。
5. `durable-only` 继续由 DB 主存。
6. `docs-backed / dual-write` 以 docs 为正文主文档，DB 只保留摘要、引用、状态和必要索引。
7. docs 变更默认走轻审查；durable review 与 docs change review 共用展示层，但不共用状态机。
8. rollback 仍然只属于 durable-only 的 durable review 语义。
9. 历史布局和旧 DB 状态不再被当成产品兼容承诺；修复成本高于手动处理成本时，优先显式报错和手动处理。

## 3. 当前仓库基线

关键基线文件：

- `README.md`
- `AGENTS.md`
- `.memory/docs/pm/decisions.md`
- `.memory/docs/architect/decisions.md`
- `skills/project-memory/SKILL.md`
- `skills/memory-admin/SKILL.md`
- `.archive/plans/2026-03-11-memory-hub-v2-design-draft.md`
- `.archive/plans/2026-03-11-memory-hub-v2-roadmap.md`
- `.archive/plans/2026-03-11-memory-hub-phase2c-plan.md`
- `.archive/plans/2026-03-11-memory-hub-phase2d-plan.md`
- `.archive/plans/2026-03-11-memory-hub-phase2e-plan.md`
- `.archive/plans/2026-03-11-memory-hub-phase2f-plan.md`

仓库内 memory skills 当前只有：

- `skills/project-memory/SKILL.md`
- `skills/memory-admin/SKILL.md`

说明：

- `durable-memory` 已并入 `project-memory` 内部 branch，不再作为独立可见 skill。
- 旧的 `memory-*` / `catalog-*` / `durable-memory` legacy skills 已从仓库和全局可见 skill surface 中清理。

## 4. MCP 与技能基线

当前 `memory-hub` MCP server 暴露的 tools 仍有 7 个：

- `read_memory`
- `search_memory`
- `capture_memory`
- `update_memory`
- `show_memory_review`
- `propose_memory`
- `propose_memory_update`

其中：

- `capture_memory` / `update_memory` / `show_memory_review` 是 v2 主入口
- `propose_memory` / `propose_memory_update` 仅作为兼容入口保留，不是默认 workflow

当前规则中已经明确：

- `doc://...` 与 `catalog://...` 必须通过 `memory-hub.read_memory(ref=...)` 读取
- 不要把它们当成 MCP resource
- 不要使用 `read_mcp_resource`
- 不要虚构 server 名，例如 `memory`

## 5. 真实会话测试结论

完整的真实会话测试日志见：

- `1.log`

结论：

- 整体符合要求
- 主链路已经达标
- 允许存在少量“顺序不够理想但结果正确”的可接受偏差

已确认通过的点：

1. 统一读面调用正确：
   - 新会话中已经不再出现 `read_mcp_resource`
   - 不再把 `doc://...` / `catalog://...` 当 resource
   - 不再虚构 `memory` server
2. `docs-only` / `durable-only` / `dual-write` 三条主写路径都跑通了。
3. `show_memory_review(...)` 会在 approve/reject 前先展示详情。
4. 只有在用户明确输入：
   - `批准此提案`
   - `拒绝此提案`
   - `暂不处理`
   之后，agent 才会继续执行 review 分流动作。
5. pending review 分流正确：
   - 不会绕过 review
   - 不会偷偷新建重复提案
   - 不会在 pending target 上继续强行 update
6. recall 正常：
   - 能回忆已生效规则
   - 能明确区分已被拒绝、因此不生效的规则
7. session-extract 主链测试通过：
   - 只产出候选
   - 仍然进入 unified write lane 和 review surface
   - 不会直接写 active state

当前接受的非阻塞偏差：

- 普通“理解项目分层”的问题，有时仍会先做一点代码检索，再回到 memory 读取
- 这说明路由顺序不是完全线性的
- 但根据当前产品决策，这不构成阻塞项，也不再继续为此投入高成本强约束

## 6. 自动化与手工验证结果

本轮最终确认的验证结果：

- `pytest -q`
  - 结果：`95 passed`
- `bin/selftest-phase1c`
  - 结果：成功
- `python3 -m lib.cli catalog-repair`
  - 连续运行 2 次，均为 clean

额外完成的手工验证：

- unified read
- unified write
- docs review
- durable review
- dual-write
- pending review split
- hybrid recall
- session-extract

## 7. 换电脑后的最小环境准备

新电脑继续开发时，最小步骤如下。

### 7.1 安装与运行

在仓库根目录执行：

```bash
pip install -e .
```

如果要跑测试：

```bash
pip install -e .[dev]
```

当前 console scripts：

- `memory-hub`
- `memory-hub-mcp`

### 7.2 MCP 接线

项目内已有 `.mcp.json`，当前内容等价于：

- server 名：`memory-hub`
- command：`python3 -m lib.mcp_server`
- `cwd`：仓库根目录
- `MEMORY_HUB_PROJECT_ROOT=.` 

如果换电脑后客户端支持项目级 `.mcp.json`，直接启用即可。

如果需要手动配全局 MCP，核心等价配置是：

```json
{
  "mcpServers": {
    "memory-hub": {
      "command": "python3",
      "args": ["-m", "lib.mcp_server"],
      "cwd": "/absolute/path/to/memory-hub",
      "env": {
        "PYTHONPATH": "/absolute/path/to/memory-hub",
        "MEMORY_HUB_PROJECT_ROOT": "/absolute/path/to/memory-hub"
      }
    }
  }
}
```

### 7.3 Codex 全局技能

当前本机全局 `~/.agents/skills` 中只保留：

- `project-memory`
- `memory-admin`
- `find-skills`（无关 skill）

换电脑后，如 Codex 不自动读取仓库内 skills，需要把下面两个目录同步到新机器的 `~/.agents/skills/`：

- `skills/project-memory/`
- `skills/memory-admin/`

完成后必须新开 `codex-cli` 会话，旧会话不会自动刷新 skill。

### 7.4 Claude 项目设置

仓库中已有：

- `.claude/settings.local.json`

如果新电脑也要用 Claude 做验收，可直接参考该文件开启项目级 MCP。

## 8. 换电脑后的第一轮验证

换电脑后，建议先做这一轮最小验证。

1. 新开 `codex-cli` 会话
2. 确认可见 memory skills 只有：
   - `project-memory`
   - `memory-admin`
3. `/mcp` 中确认存在 `memory-hub`
4. 在仓库根目录执行：

```bash
pytest -q
bin/selftest-phase1c
python3 -m lib.cli catalog-repair
python3 -m lib.cli catalog-repair
```

5. 再跑一轮自然语言会话验证，至少覆盖：
   - 普通仓库理解
   - docs-only 写入
   - durable-only 写入
   - dual-write 写入
   - pending review split
   - session-extract

## 9. 当前不再建议投入的方向

以下内容当前不再建议作为主线继续投入：

- 为了让普通自然语言请求 100% 严格按固定顺序执行，而继续堆更重的全局规则
- 为旧 `.memoryhub/`、旧 DB、旧布局继续做复杂自动迁移
- 恢复 legacy skill surface

当前策略已经明确：

- 保持现状
- 接受少量“顺序不完美但结果正确”的自然语言路由偏差
- 仅在真实使用中再次出现明显错误时，再做局部修正

## 10. 下一阶段建议

当前主线开发已经完成，下一阶段不是继续架构重构，而是：

- 在新电脑上恢复环境
- 进入真实使用观察
- 只做问题驱动的小修

Claude 增强交互仍可延后，不阻塞当前 v2 使用。

## 11. docs 文件何时会真正被修改

当前规则下，docs 文件不会因为普通读取、检索、show review 或一般代码分析被直接改写。

真正会触发 docs 文件落盘修改的前提只有一条：

- 某次统一写入被路由到 `docs-only` 或 `dual-write`
- 并且对应的 `docs_change_review` 被明确批准

具体分支如下：

1. `docs-only`
   - 入口通常是：
     - `capture_memory(kind="docs", ...)`
     - 或 `capture_memory(kind="auto", doc_domain=..., 但没有 memory_type)`
   - 系统先创建持久 `docs_change_review`
   - 只有 review 被批准后，才会真正写入 `.memory/docs/...`

2. `dual-write`
   - docs 仍是正文主文档
   - 系统创建 `docs_change_review`，同时挂一个 linked durable proposal
   - 只有 docs review 被批准后，docs 文件才会落盘；关联 durable proposal 同步处理

3. `update_memory(ref="doc://...", ...)`
   - 不会直接改文件
   - 先生成 docs review
   - 若该 `doc://...` 已绑定 durable memory，则走 `dual-write` 更新
   - 若已有 pending review，则不会继续改，只会分流回现有 review

4. `session-extract`
   - 只会间接触发 docs 候选
   - 最终仍复用 `capture_memory / update_memory`
   - 进入 docs review 后，批准才落盘

不会触发 docs 文件修改的情况：

- `read_memory(...)`
- `search_memory(...)`
- `show_memory_review(...)`
- 普通代码分析 / 架构讨论
- `durable-only` 的 create / update
- 命中 pending docs review 时再次 update
- agent 直接写 `.memory/docs/*`

当前产品心智可以压缩成一句话：

- docs 文件的真正落盘条件，不是“用户说了新知识”，而是“统一写入口命中 docs lane，并且 docs review 被批准”

## 12. session-extract 的真实边界与后续方向

本轮讨论已明确：当前 `session-extract` 的能力边界不能描述成“自动从开发过程里发现所有重要知识”。

更准确的说法是：

- 它已经能从会话文本里提炼新增知识候选
- 但它还不能稳定从“纯代码改动本身”中自动发现所有隐含的新规则、例外规则或设计决策

当前 `session-extract` 的真实语义：

1. 输入是 transcript，不是代码 diff 发现器
2. 优先支持显式标注：
   - `docs[...]`
   - `durable[...]`
   - `dual[...]`
3. 未标注时，使用本地启发式分类 + hybrid recall：
   - 关键词判断 route
   - `search_project_memory(...)` 定位 update target
4. 它能提炼“会话中已经被表达出来的稳定结论”
5. 它不能保证提炼“只隐含在代码修改里、从未被说出来的知识”

因此，当前 v2 的 tradeoff 已经明确：

- 优点：不会因为每次改代码都自动写 memory，避免大量噪音和 token 浪费
- 缺点：如果重要决策从未在会话中被表达出来，就存在遗漏风险

我们已经确认，这不是 v2 设计失败，而是 v2 当前更强的是：

- `write control`
- `review control`
- `recall quality`

但还没有完整解决：

- `knowledge discovery`

后续最合理的新方向，不是“放开自动写入”，而是补一条新的 candidate discovery lane：

- 名称建议：`decision discovery lane`
- 或：`change-aware memory discovery`

这条 lane 的职责应是：

1. 不直接写 active docs 或 active durable state
2. 只发现并生成 candidate
3. 重点抓：
   - 默认规则被打破
   - 新例外规则出现
   - docs 与实现发生偏离
   - 会影响未来决策的稳定结论
4. 候选再进入现有 docs review / durable review

当前可以接受的正式结论是：

- v2 已经具备“安全地记”
- 但下一阶段若继续增强，最值得做的是“更可靠地发现该记什么”
