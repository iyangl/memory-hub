# Memory Hub — Codex Repo Rules

## Surface Routing

- `.memory/` is the repository knowledge surface.
- `.memoryhub/` is the durable memory control plane.
- Do not treat them as interchangeable.

Use `.memory/` for:

- repository design decisions
- project constraints and conventions
- catalog and module index maintenance

Use durable memory for information that is:

- useful across future sessions
- not stably recoverable from code alone
- best modeled as `identity`, `decision`, `constraint`, or `preference`

## Durable-Memory Trigger

When a request or intermediate conclusion enters durable-memory territory, enter the
`durable-memory` skill. The skill owns the workflow from that point on.

Do not enter the durable-memory skill for:

- ordinary code review or architecture discussion
- one-off answers that do not need cross-session recall
- repository knowledge updates that belong in `.memory/`

## Hard Boundaries

- Do not edit `.memoryhub/` or `memory.db` directly.
- Do not use `.memory/` file writes as a substitute for durable memory.
- Do not approve or reject durable memory before showing proposal details and
  receiving explicit user confirmation.
- Never rollback durable memory on the user's behalf.
- Do not bypass the `durable-memory` skill by calling durable-memory tools from
  generic repo rules.

## Review Handoff Policy

- On the first durable-memory action in a session, the first durable-memory tool
  call must be `read_memory("system://boot")`.
- Before boot is loaded, do not call `read_memory(uri)`, `search_memory(...)`,
  `propose_memory(...)`, or `propose_memory_update(...)`.
- After `PROPOSAL_CREATED`, automatically inspect proposal details with
  `memory-hub review show <proposal_id>` before stopping or asking for a
  decision.

- Only approved memories can be updated.
- If the closest target is a pending proposal, stop at human review split.
- If the closest target is a pending proposal, inspect queue state, then run
  `memory-hub review show <proposal_id>` before asking for a decision.
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
- `memory-hub review show <proposal_id>`
- `memory-hub review approve <proposal_id> ...`
- `memory-hub review reject <proposal_id> ...`

## `.memory/` Workflow

Before scoped change or feature work:

1. `catalog-read topics`
2. `memory.read` related files
3. `memory.search` if catalog lookup is insufficient

When `.memory/` or catalog changes:

- update the module catalog if file structure changed
- finish with `memory-hub catalog-repair`
