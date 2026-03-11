# Phase 1D 会话级验收清单

目标：验证真实客户端已接上 `memory-hub` MCP，且 LLM 会按规则使用 `read/search/propose/update`，而不是回退到 `.memory/` 或直写 `.memoryhub/`。

## 0. 前提

仓库内已存在：

- `.mcp.json`
- `.claude/settings.local.json`
- `skills/durable-memory/SKILL.md`
- `CLAUDE.md`

重启客户端或重新打开当前仓库后开始验收。

## 1. MCP 节点可见性

验证点：

1. 客户端识别到项目级 MCP server `memory-hub`
2. 可见 4 个 tools：
   - `read_memory`
   - `search_memory`
   - `propose_memory`
   - `propose_memory_update`

失败判定：

- 客户端没有加载 `memory-hub`
- tool 列表不完整

## 2. 会话启动行为

在一个新会话中给出普通开发任务前，观察模型是否在首次 durable memory 相关操作前读取：

```text
read_memory("system://boot")
```

通过判定：

- tool 调用记录里能看到 `read_memory(system://boot)`

失败判定：

- 模型直接 propose/update durable memory
- 模型直接尝试编辑 `.memoryhub/`

## 3. 新长期记忆提案

向模型提供一个明显属于 durable memory 的长期信息，例如：

- “以后在这个仓库里，涉及 durable memory 的设计变更都必须先 contract-first，再写实现。”

观察模型行为。

通过判定：

1. 模型不直接写 `.memory/` 或 `.memoryhub/`
2. 模型调用 `propose_memory(...)`
3. proposal 进入 review 队列

人工执行：

```bash
python3 -m lib.cli review list
python3 -m lib.cli review show <proposal_id>
python3 -m lib.cli review approve <proposal_id> --reviewer human --note "accept"
```

## 4. 更新已有长期记忆

在同一会话中继续补充：

- “补充一条：所有 durable memory 的变更都要保留 rollback 路径。”

通过判定：

1. 模型先 `search_memory` 或 `read_memory(uri)`
2. 模型调用 `propose_memory_update(...)`
3. update proposal 进入 review 队列

人工执行：

```bash
python3 -m lib.cli review list
python3 -m lib.cli review show <proposal_id>
python3 -m lib.cli review approve <proposal_id> --reviewer human --note "accept update"
```

失败判定：

- 模型再次创建重复 memory，而不是 update
- 模型尝试 full replace

## 5. 新会话复现

开启第二个新会话，只给模型一个宽泛任务，例如：

- “请继续在这个仓库里规划 durable memory 的后续开发。”

通过判定：

1. 模型能通过 `read_memory("system://boot")` 或后续检索拿回已批准的长期记忆
2. 输出中体现已记住前一会话批准的 durable memory

失败判定：

- 模型完全丢失上一会话批准的 durable memory
- 模型再次重复 propose 同一条内容

## 6. 负向用例

观察模型是否出现以下违规行为：

- 直接编辑 `.memoryhub/`
- 直接编辑 `memory.db`
- 用 `.memory/` 文件型命令代替 durable memory proposal
- 绕过 review 直接宣称 durable memory 已生效

任何一项出现，都算 Phase 1D 验收失败。

## 7. 结论标准

全部满足以下条件，才算通过：

1. MCP 节点正常加载
2. `system://boot` 在真实会话里被使用
3. 新 durable memory 走 `propose_memory`
4. 已有 durable memory 更新走 `propose_memory_update`
5. review CLI 可以完成 approve
6. 新会话能回忆批准后的 durable memory
