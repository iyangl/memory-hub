---
name: project-memory
description: "统一项目记忆主入口：负责读取 docs/catalog/durable，上下文装配、检索和 review handoff 路由"
tools: ["Bash"]
---

## Purpose

This is the primary memory workflow for the repository.

Use it to:

- load repository knowledge from `.memory/docs/`
- inspect catalog summaries and module indexes
- read durable memory boot/context when needed
- search across docs lane and durable lane
- capture docs-only / durable-only / dual-write knowledge
- update docs lane or durable lane through the unified write lane
- inspect review summaries for pending durable proposals and docs change reviews

Do not use it to bypass the durable control plane or write directly to
`.memory/_store/`.

## Primary Entry

Use this skill as the default and only user-visible memory entry for:

- ordinary repository analysis
- design and feature work that needs project knowledge
- deciding whether a conclusion belongs in docs lane or durable lane
- reading review summaries before human approval
- durable-memory routing once a task crosses into cross-session recall territory

## Read Flow

### Step 1: Start from unified refs

Prefer the unified MCP read surface:

- `read_memory(ref, anchor?)`
- `search_memory(query, scope=docs|durable|all, type?, limit?)`
- `show_memory_review(proposal_id|ref)`

Prefer the unified MCP write surface:

- `capture_memory(kind=auto|docs|durable, ...)`
- `update_memory(ref, mode=patch|append, ...)`

Use these refs:

- `system://boot`
- `doc://<bucket>/<name>`
- `catalog://topics`
- `catalog://modules/<name>`
- existing durable URIs such as `constraint://...`

In Codex and Claude, these refs are read through the `memory-hub` MCP tools.
They are not MCP resources and should not be loaded with `read_mcp_resource`.
Do not invent a server name such as `memory`; use the installed `memory-hub`
tool surface directly.

For the rest of this skill:

- every `read_memory(...)`, `search_memory(...)`, `capture_memory(...)`,
  `update_memory(...)`, and `show_memory_review(...)` call means the
  corresponding tool on the installed `memory-hub` MCP server
- do not treat these names as shell commands or MCP resources
- do not invent an alternative server name
- `propose_memory(...)` and `propose_memory_update(...)` are compatibility
  tools, not the default v2 workflow

### Step 2: Repository knowledge first

For ordinary repository work:

1. call `read_memory(ref="catalog://topics")`
2. call `read_memory(ref="doc://...")` for the relevant docs refs
3. if needed, call `search_memory(query, scope=docs|all, ...)`
4. `scope=all` now uses local hybrid recall backed by `_store/projections/search.json`

Do not enter durable-memory write flow for normal repository reading.

### Step 3: Durable branch when necessary

When the task explicitly enters durable-memory territory, stay inside this
skill and switch into the durable branch below.

`system://boot` is served from `_store/projections/boot.json`.

## Durable Branch

### Step 1: Qualify the memory

Before any durable tool call, answer these questions:

1. Will this matter in future sessions?
2. Is it unavailable from reading code alone?
3. Can `why_not_in_code` and `source_reason` be stated clearly?
4. Does it fit one of the four allowed types?

If any answer is no, explicitly refuse to enter the durable-memory write flow.

### Step 2: Load boot memory first

On the first durable-memory action in the current session, the first
durable-memory tool call must be:

```text
memory-hub.read_memory(ref="system://boot")
```

Before boot is loaded, do not call:

- `read_memory(ref=<non-system>)`
- `search_memory(query, scope="durable", type?, limit?)`
- `capture_memory(...)`
- `update_memory(...)`
- `propose_memory(...)`
- `propose_memory_update(...)`

Do not load boot memory for every new session by default. Load it only when the
session actually enters a durable-memory action, but once it does, boot must be
first.

### Step 3: Inspect existing approved memory first

If the target URI is known:

- `read_memory(ref=uri)`

If the target URI is not known:

- `search_memory(query, scope="durable", type?, limit?)`

Search/read only tells you about approved memory. Pending proposals are not part
of the read/search surface.

### Step 4: Proposal routing

If no relevant approved memory exists, create a new proposal:

```text
capture_memory(
  kind="durable",
  title,
  content,
  reason=source_reason,
  memory_type=type,
  recall_when=recall_when,
  why_not_in_code=why_not_in_code
)
```

If a relevant approved memory exists, update it without full replace:

```text
update_memory(
  ref=uri,
  mode="patch|append",
  old_string?,
  new_string?,
  append?,
  reason=source_reason,
  recall_when?,
  why_not_in_code?
)
```

Never:

- write directly to `.memory/_store/`
- issue direct SQL
- use full replace

### Step 5: Handle proposal results

If proposal returns `NOOP`:

- stop
- explain that no durable-memory write is needed

If proposal returns `UPDATE_TARGET`:

1. read the suggested target URI
2. if it is approved memory, switch to update flow
3. if it is not approved memory, stop at human review split

If proposal returns `PROPOSAL_CREATED`:

1. call:
   ```text
   show_memory_review(proposal_id|ref)
   ```
2. if MCP review display is unavailable, run the CLI fallback:
   ```bash
   python3 -m lib.cli review show <proposal_id|ref>
   ```
3. if both review paths fail, report the exact failure and give the precise
   retry command; do not invent proposal details
4. show the proposal summary and diff
5. enter review handoff
6. do not claim it is already approved

### Step 6: Pending proposal branch

If the closest target is a pending proposal, do not call
`update_memory(...)` or `propose_memory_update(...)` against its URI.

Instead:

1. inspect the queue with:
   ```bash
   python3 -m lib.cli review list
   ```
2. identify the relevant `proposal_id`
3. call:
   ```text
   show_memory_review(proposal_id|ref)
   ```
4. if MCP review display is unavailable, run the CLI fallback:
   ```bash
   python3 -m lib.cli review show <proposal_id|ref>
   ```
5. if both review paths fail, report the exact failure and give the precise
   retry command; do not invent proposal details
6. show the current pending proposal summary and diff
7. enter review handoff

### Step 7: Review handoff

If the host provides a structured confirmation tool such as Claude Code's
`AskUserQuestion`, use it with exactly three choices:

- `批准此提案`
- `拒绝此提案`
- `暂不处理`

If the host does not provide a structured confirmation tool, immediately output
the same three fixed text choices and wait for the user to reply with one of
them verbatim.

After the proposal summary has been shown:

- if the user replies `批准此提案`, you may execute:
  ```bash
  python3 -m lib.cli review approve <proposal_id> --reviewer <host> --note "<note>"
  ```
- if the user replies `拒绝此提案`, you may execute:
  ```bash
  python3 -m lib.cli review reject <proposal_id> --reviewer <host> --note "<note>"
  ```
- if the user replies `暂不处理`, stop without executing any review action

Use these defaults when the user does not provide a custom note:

- Codex host:
  - `reviewer`: `codex`
  - approve note: `Approved by explicit user confirmation in durable-memory workflow (codex).`
  - reject note: `Rejected by explicit user confirmation in durable-memory workflow (codex).`
- Claude host:
  - `reviewer`: `claude`
  - approve note: `Approved by explicit user confirmation in durable-memory workflow (claude).`
  - reject note: `Rejected by explicit user confirmation in durable-memory workflow (claude).`

Never:

- approve or reject before proposal details were shown
- claim approval happened if the CLI command failed
- approve, reject, or rollback without explicit user confirmation
- amend, merge, reopen, or update a pending proposal

## Review Flow

Use the `memory-hub` MCP tool `show_memory_review(...)` to inspect pending
durable proposals or docs change reviews before asking for or executing human
review actions.

Review display is read-only. Approval, rejection, and rollback still belong to
the CLI authority surface.

## Write Routing

Use these route rules:

- docs-only:
  - `kind=docs`
  - or `kind=auto` with `doc_domain` only
- durable-only:
  - `kind=durable`
  - or `kind=auto` with `memory_type` only
- dual-write:
  - `kind=auto` with both `doc_domain` and `memory_type`

Current Phase 2E behavior:

- docs-only writes create persistent docs change reviews
- durable-only writes continue to create durable proposals
- dual-write writes create docs change reviews linked to durable summary
  proposals via `doc_ref`
- approving a docs change review applies the docs file, repairs catalog, and
  if a linked durable proposal exists, approves it through the existing CLI
  authority path
- search results now include hybrid recall metadata:
  `search_kind`, `score`, `lexical_score`, and `semantic_score`
- if the user wants to distill a completed session into candidate memory items,
  hand off to `memory-admin` and run the CLI command
  `memory-hub session-extract --file <transcript>`

## Boundaries

Never:

- edit `.memory/docs/*` or `.memory/_store/*` directly on behalf of the agent
- treat docs lane and durable lane as interchangeable
- call durable approval actions before proposal details were shown
- bypass the durable branch inside `project-memory` for durable writes
