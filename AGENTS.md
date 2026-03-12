# Memory Hub — Codex Repo Rules

## Surface Routing

- `.memory/` is the unified project memory root.
- `.memory/docs/` is the repository knowledge lane.
- `.memory/_store/memory.db` is the durable memory control store.
- Do not treat docs lane and durable store as interchangeable.

Use `.memory/` for:

- repository design decisions
- project constraints and conventions
- catalog and module index maintenance

Use durable memory for information that is:

- useful across future sessions
- not stably recoverable from code alone
- best modeled as `identity`, `decision`, `constraint`, or `preference`

## Durable-Memory Trigger

Use `project-memory` as the primary memory workflow.

Use `memory-admin` only for maintenance and diagnostics.

When a request or intermediate conclusion enters durable-memory territory,
`project-memory` should route into its internal durable branch. That branch
owns proposal/update/review from that point on.

Do not enter the durable-memory branch for:

- ordinary code review or architecture discussion
- one-off answers that do not need cross-session recall
- repository knowledge updates that belong in `.memory/`

## Hard Boundaries

- Do not edit `.memory/_store/` or `memory.db` directly.
- Do not use `.memory/` file writes as a substitute for durable memory.
- Do not approve or reject durable memory before showing proposal details and
  receiving explicit user confirmation.
- Never rollback durable memory on the user's behalf.
- Do not bypass `project-memory` routing by calling durable-memory MCP tools
  directly from generic repo rules.
- Do not treat direct docs file writes as the default agent write path; use the
  unified write lane instead.

## Review Handoff Policy

- On the first durable-memory action in a session, the first durable-memory tool
  call must be the `memory-hub` MCP tool
  `read_memory(ref="system://boot")`.
- Before boot is loaded, do not call the `memory-hub` MCP tools
  `read_memory(ref=<non-system>)`, `search_memory(...)`, `capture_memory(...)`,
  `update_memory(...)`, `propose_memory(...)`, or `propose_memory_update(...)`.
- After a pending review target is created or matched, first inspect it with the
  `memory-hub` MCP tool `show_memory_review(...)`. Only use
  `memory-hub review show <proposal_id|ref>` as a CLI fallback if the MCP review
  view is unavailable.

- Only approved memories can be updated.
- If the closest target is a pending proposal, stop at human review split.
- If the closest target is a pending proposal, inspect queue state, then use
  `show_memory_review(...)` before asking for a decision.
- If the host provides a structured confirmation tool, use it. Otherwise present
  fixed text options:
  - `批准此提案`
  - `拒绝此提案`
  - `暂不处理`
- The LLM may execute `review approve/reject` only after proposal details were
  shown and the user explicitly chose one of the fixed approval actions. It may
  not amend, merge, reopen, or auto-approve without that confirmation.

Human review split:

- `memory-hub review list`
- `memory-hub review show <proposal_id|ref>`
- `memory-hub review approve <proposal_id|ref> ...`
- `memory-hub review reject <proposal_id|ref> ...`

## `.memory/` Workflow

Before scoped change or feature work:

1. enter `project-memory`
2. in Codex/Claude, call the `memory-hub` MCP tool `read_memory(ref="catalog://topics")`
3. read related `doc://...` refs through the same `read_memory(...)` tool
4. if needed, call `search_memory(..., scope=docs|all)` on the same `memory-hub` MCP server

Do not treat `catalog://...` or `doc://...` as MCP resources.
Do not use `read_mcp_resource`, and do not invent a server name such as `memory`.

For memory writes in Codex/Claude:

- default to the `memory-hub` MCP tools `capture_memory(...)` and
  `update_memory(...)`
- use `show_memory_review(...)` on the same server for review display
- treat `propose_memory(...)` and `propose_memory_update(...)` as compatibility
  entrypoints only, not the default workflow
- use `memory-hub session-extract --file <transcript>` only through the
  `memory-admin` maintenance path, not as a generic MCP action
- use `memory-hub discover [--summary-file <path>]` only through the
  `memory-admin` maintenance path when the user asks whether current code
  changes contain new decision / exception / docs drift candidates

When `.memory/` or catalog changes:

- use the unified write lane instead of invoking legacy memory/catalog skills
- finish with `memory-hub catalog-repair`
