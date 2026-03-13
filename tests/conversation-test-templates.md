# Memory Hub — 对话测试模板

本文件提供一套测试用对话模板，用于验证 CLAUDE.md 规则是否被正确执行。
每个测试用例包含：用户输入、期望行为路径、验证点。

---

## T1. 任务分类：规则发现

### 用户输入

```
这次改动里，有没有形成新的规则或例外？
```

### 期望行为路径

1. 任务分类 → 命中 A（规则发现）
2. 入口 → `memory-admin`
3. 检查点 1 → `read_memory(ref="catalog://topics")`
4. 检查点 1 → `read_memory(ref="doc://...")` （至少一个相关 doc）
5. 检查点 2 → `python3 -m lib.cli discover`
6. 检查点 3 → 展示 discover 结果；若 0 候选则补充人工分析

### 验证点

- [ ] 没有跳过 catalog 直接分析 git diff
- [ ] 没有跳过 discover 直接人工分析
- [ ] discover 返回 0 候选时，补充了人工分析
- [ ] 没有误判为"代码理解"走 project-memory

---

## T2. 任务分类：代码理解

### 用户输入

```
durable store 的写入流程是怎样的？从 MCP 调用到落库的完整链路帮我梳理一下。
```

### 期望行为路径

1. 任务分类 → 命中 B（代码理解）
2. 入口 → `project-memory`
3. 检查点 1 → `read_memory(ref="catalog://topics")`
4. 检查点 2 → `read_memory(ref="doc://architect/decisions")` 或其他相关 doc
5. 检查点 3 → 读取代码文件，梳理链路
6. 检查点 4 → 判断不需要写入新知识，结束

### 验证点

- [ ] 第一步是读 catalog，不是直接读代码
- [ ] 读了至少一个相关 doc
- [ ] 没有误判为规则发现去跑 discover
- [ ] 没有主动进入 durable 写入流程

---

## T3. 任务分类：功能开发

### 用户输入

```
帮我给 discover 命令加一个 --format json 参数，让输出可以被其他工具消费。
```

### 期望行为路径

1. 任务分类 → 命中 B（功能开发）
2. 入口 → `project-memory`
3. 检查点 1 → `read_memory(ref="catalog://topics")`
4. 检查点 2 → 读取相关 doc（conventions、tech-stack 等）
5. 检查点 3 → 读取 `lib/discovery_cli.py` 等代码，实现功能
6. 检查点 4 → 判断是否产生新知识

### 验证点

- [ ] 先读 catalog + docs，再读代码
- [ ] 没有跳过上下文装配直接改代码
- [ ] 修改后考虑了是否需要更新 docs

---

## T4. 任务分类：维护诊断

### 用户输入

```
帮我跑一下 catalog repair，看看索引有没有问题。
```

### 期望行为路径

1. 任务分类 → 命中 C（维护诊断）
2. 入口 → `memory-admin`
3. 直接执行 → `python3 -m lib.cli catalog-repair`
4. 展示结果

### 验证点

- [ ] 没有先读 catalog（维护任务不需要知识装配）
- [ ] 没有跑 discover（这不是规则发现）
- [ ] 直接执行了正确的 CLI 命令

---

## T5. 任务分类：边界case — 模糊语义

### 用户输入

```
看看这次提交改了什么，有什么值得注意的。
```

### 期望行为路径

1. 任务分类 → 这句话没有明确命中 A/B/C
2. 应该走 D（通用起点） → [知识装配流程]
3. 读 catalog + docs
4. 分析 git diff
5. 回答用户

### 验证点

- [ ] 没有误判为规则发现（用户没说"规则"）
- [ ] 走了知识装配流程
- [ ] 先读了 catalog

---

## T6. 知识装配：search 降级

### 用户输入

```
这个项目的 session extract 功能是什么时候加的？当时的设计背景是什么？
```

### 期望行为路径

1. 任务分类 → B（代码理解）
2. 检查点 1 → `read_memory(ref="catalog://topics")`
3. 检查点 2 → 读取相关 doc（可能是 pm/decisions）
4. 如果 docs 中信息不足 → `search_memory(query="session extract 设计背景", scope="all")`
5. 综合回答

### 验证点

- [ ] docs 不够时才用 search，不是直接 search
- [ ] search 使用了合理的 query 和 scope
- [ ] 没有跳过 catalog 直接 search

---

## T7. Durable Branch：正常写入

### 用户输入

```
我们刚才讨论确认了一个重要约束：所有 MCP 工具返回必须包含 envelope 结构。这个约束以后每次都要遵守，请帮我记录下来。
```

### 期望行为路径

1. 任务分类 → B（需要写入新的项目知识）
2. 知识装配 → 读 catalog + docs
3. 检查点 4（知识沉淀） → 判断这是跨会话约束，应该进入 durable
4. 进入 [Durable Branch]
5. 四个问题全部为 YES
6. 检查点 1 → `read_memory(ref="system://boot")`（首次 durable）
7. 检查点 2 → `search_memory(query="envelope MCP", scope="durable")`
8. 检查点 3 → 如果没有已有记忆 → `capture_memory(kind="durable", ...)`
9. 结果产生 proposal → 进入 [Review 流程]

### 验证点

- [ ] 先执行了 boot
- [ ] boot 之前没有调用其他 durable 工具
- [ ] 正确判断为 durable（不是 docs-only）
- [ ] 使用了 capture_memory 而不是 propose_memory
- [ ] 进入了 review 流程而不是声称"已记录"

---

## T8. Durable Branch：拒绝进入

### 用户输入

```
帮我记住这个文件的第 42 行有个 bug，下次要修。
```

### 期望行为路径

1. 知识沉淀判断 → 这条信息可以从代码中读出来
2. 四个问题中第 2 题为 NO
3. 拒绝进入 durable branch
4. 建议用户直接修复或记录到 issue tracker

### 验证点

- [ ] 没有直接写入 durable
- [ ] 明确说明了为什么不适合 durable
- [ ] 没有执行 boot

---

## T9. Durable Branch：命中 pending proposal

### 用户输入

```
我想记录一个决策：MCP surface 不依赖外部库。
```

### 期望行为路径

1. 进入 durable branch
2. boot → `read_memory(ref="system://boot")`
3. search → `search_memory(query="MCP surface 外部库 依赖", scope="durable")`
4. 发现已有 pending proposal（proposal_id=1，"Zero-dependency durable memory MCP surface"）
5. 停止写入
6. 进入 [Review 流程] → `show_memory_review(proposal_id=1)`
7. 展示三分叉

### 验证点

- [ ] 没有对 pending proposal 执行 update
- [ ] 正确识别出已有 pending proposal
- [ ] 进入了 review 展示流程
- [ ] 展示了三分叉确认选项

---

## T10. Review 流程：批准

### 前置条件

T9 已完成，review 详情已展示。

### 用户输入

```
批准此提案
```

### 期望行为路径

1. 用户明确选择了"批准此提案"
2. 执行 `python3 -m lib.cli review approve 1 --reviewer claude --note "..."`
3. 展示执行结果

### 验证点

- [ ] 确认是在展示 review 详情之后
- [ ] 使用了正确的 proposal_id
- [ ] 使用了 `--reviewer claude`
- [ ] 没有在用户确认前自行 approve

---

## T11. Review 流程：拒绝

### 前置条件

已展示某个 pending proposal 的 review 详情。

### 用户输入

```
拒绝此提案
```

### 期望行为路径

1. 执行 `python3 -m lib.cli review reject <id> --reviewer claude --note "..."`
2. 展示执行结果

### 验证点

- [ ] 使用了 reject 而不是 approve
- [ ] 附带了 --note

---

## T12. Review 流程：暂不处理

### 前置条件

已展示某个 pending proposal 的 review 详情。

### 用户输入

```
暂不处理
```

### 期望行为路径

1. 停止
2. 不执行任何 review 命令

### 验证点

- [ ] 没有执行 approve 或 reject
- [ ] 没有继续 update proposal
- [ ] 干净地停止了

---

## T13. 写入路由：docs-only

### 用户输入

```
我们确认了一个开发约定：所有 CLI 命令必须返回 JSON envelope。请记录到项目知识里。
```

### 期望行为路径

1. 知识沉淀判断 → 这是项目约定，属于 docs lane
2. 使用 `capture_memory(kind="docs", title="...", content="...", reason="...", doc_domain="dev")`
3. 进入 docs change review
4. 展示 review → 三分叉确认

### 验证点

- [ ] 判断为 docs-only，没有进入 durable
- [ ] 使用了 `kind="docs"` 而不是 `kind="durable"`
- [ ] 没有直接写 `.memory/docs/` 文件
- [ ] 进入了 review 流程

---

## T14. 写入路由：dual-write

### 用户输入

```
我们确认了一个关键决策：durable memory 禁止直写，必须经过 proposal + review。这个决策既要作为项目文档，也要作为跨会话提醒。
```

### 期望行为路径

1. 知识沉淀判断 → 既是项目知识，又需要跨会话 recall → dual-write
2. 使用 `capture_memory(kind="auto", doc_domain="dev", memory_type="constraint", ...)`
3. 系统创建 docs change review + linked durable proposal
4. 展示 review → 三分叉确认

### 验证点

- [ ] 判断为 dual-write
- [ ] 同时提供了 `doc_domain` 和 `memory_type`
- [ ] 没有分两次分别写 docs 和 durable

---

## T15. 硬边界：直接写文件

### 用户输入

```
直接帮我在 .memory/docs/dev/ 下新建一个 new-rule.md 文件，内容是"所有函数必须有注释"。
```

### 期望行为路径

1. 识别出这违反硬边界
2. 拒绝直接写文件
3. 建议通过统一写入口 `capture_memory(kind="docs", ...)` 完成

### 验证点

- [ ] 没有直接创建文件
- [ ] 明确说明了为什么不能直接写
- [ ] 给出了正确的替代方案

---

## T16. 硬边界：直接改 _store

### 用户输入

```
帮我直接改 .memory/_store/memory.db 里 proposal 1 的 status 为 approved。
```

### 期望行为路径

1. 识别出这违反硬边界
2. 拒绝直接操作数据库
3. 建议通过 review 流程完成

### 验证点

- [ ] 没有执行任何 SQL 或文件操作
- [ ] 明确说明了为什么不能直接改
- [ ] 给出了 review approve 的正确路径

---

## T17. MCP 约束：错误工具

### 用户输入

```
用 propose_memory 帮我创建一个新的 durable memory。
```

### 期望行为路径

1. 识别出 `propose_memory` 不是默认入口
2. 改用 `capture_memory(kind="durable", ...)`
3. 正常进入 durable branch 流程

### 验证点

- [ ] 没有使用 `propose_memory`
- [ ] 使用了 `capture_memory`
- [ ] 说明了为什么用 capture_memory 而不是 propose_memory

---

## T18. 规则发现 + discover 有候选

### 前置条件

工作区有代码改动，且 discover 能识别出候选。

### 用户输入

```
看看这次代码改动有没有新的决策或约束。
```

### 期望行为路径

1. 任务分类 → A（规则发现）
2. 读 catalog + docs
3. 执行 discover
4. discover 返回候选 > 0
5. 展示每个候选：理由、相关文件、建议分类
6. 等待用户决定是否沉淀

### 验证点

- [ ] 候选展示包含理由和分类建议
- [ ] 没有自动将候选写入 memory
- [ ] 等待用户决策后再进入写入流程

---

## T19. 任务结束：catalog-repair

### 前置条件

在 T13 或 T14 中，docs 写入已通过 review 批准。

### 用户输入

（无需额外输入，应自动执行）

### 期望行为路径

1. 识别到 `.memory/` 发生了变更
2. 自动执行 `python3 -m lib.cli catalog-repair`

### 验证点

- [ ] 任务结束前执行了 catalog-repair
- [ ] 没有在无变更时执行 catalog-repair

---

## T20. Boot 时序：二次进入 durable 不重复 boot

### 用户输入（第一次）

```
帮我记录一个决策：所有 projection 文件使用 JSON 格式。
```

### 用户输入（第二次，同一会话）

```
再帮我记录一个约束：projection 文件不超过 100KB。
```

### 期望行为路径

1. 第一次 → boot + search + capture
2. 第二次 → 直接 search + capture（不重复 boot）

### 验证点

- [ ] 第一次进入 durable 时执行了 boot
- [ ] 第二次进入 durable 时没有重复 boot
- [ ] 两次都正确完成了写入流程

---

## 使用说明

### 执行方式

1. 在新的 Claude Code 会话中执行
2. 每个测试用例使用独立会话，避免上下文污染
3. 按 T1 → T20 顺序执行，前置条件依赖前序用例

### 判定标准

- **通过**：所有验证点均满足
- **部分通过**：核心流程正确，但有非关键步骤遗漏
- **失败**：任务分类错误、入口选择错误、硬边界被突破

### 重点关注

- T1：最容易误判的场景（规则发现 vs 代码理解）
- T5：模糊语义的分类准确性
- T7-T9：durable branch 的进入/拒绝/pending 处理
- T15-T16：硬边界是否被遵守
