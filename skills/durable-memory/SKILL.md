---
name: durable-memory
description: "durable memory workflow 入口：先判断是否值得沉淀，再由 skill 决定是否调用 MCP 与 CLI"
tools: ["Bash"]
---

## Purpose

This skill owns the durable-memory workflow once the conversation enters a
durable-memory context.

It decides:

- whether the information should enter durable memory at all
- whether to read/search existing approved memory
- whether to create a new proposal or update an approved memory
- how to hand proposals off into human review

Do not bypass the control plane by editing `.memoryhub/` or `memory.db`.

## Entry Criteria

Enter this skill only when the information is all of the following:

- useful across future sessions
- not stably recoverable from code alone
- high-value enough to justify durable memory
- classifiable as `identity`, `decision`, `constraint`, or `preference`

Do not use this skill for:

- ordinary code reading or repository analysis
- one-off explanations that do not need recall
- `.memory/` project knowledge maintenance

## Workflow Ownership

Global rules should only identify the durable-memory context and enter this
skill. This skill decides whether MCP or CLI needs to be called.

## Session Flow

### Step 1: Qualify the memory

Before any tool call, answer these questions:

1. Will this matter in future sessions?
2. Is it unavailable from reading code alone?
3. Can `why_not_in_code` and `source_reason` be stated clearly?
4. Does it fit one of the four allowed types?

If any answer is no, explicitly refuse to enter the durable-memory write flow.

### Step 2: Load boot memory first

On the first durable-memory action in the current session, the first
durable-memory tool call must be:

```text
read_memory("system://boot")
```

Before boot is loaded, do not call:

- `read_memory(uri)`
- `search_memory(query, type?, limit?)`
- `propose_memory(...)`
- `propose_memory_update(...)`

Do not load boot memory for every new session by default. Load it only when the
session actually enters a durable-memory action, but once it does, boot must be
first.

### Step 3: Inspect existing approved memory first

If the target URI is known:

- `read_memory(uri)`

If the target URI is not known:

- `search_memory(query, type?, limit?)`

Search/read only tells you about approved memory. Pending proposals are not part
of the read/search surface.

### Step 4: Proposal routing

If no relevant approved memory exists, create a new proposal:

```text
propose_memory(type, title, content, recall_when, why_not_in_code, source_reason)
```

If a relevant approved memory exists, update it without full replace:

```text
propose_memory_update(uri, old_string?, new_string?, append?, recall_when?, why_not_in_code?, source_reason)
```

Never:

- write directly to `.memoryhub/`
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

1. run:
   ```bash
   python3 -m lib.cli review show <proposal_id>
   ```
2. if `review show` fails, report the exact failure and give the precise retry
   command; do not invent proposal details
3. show the proposal summary and diff
4. enter review handoff
5. do not claim it is already approved

### Step 6: Pending proposal branch

If the closest target is a pending proposal, do not call
`propose_memory_update` against its URI.

Instead:

1. inspect the queue with:
   ```bash
   python3 -m lib.cli review list
   ```
2. identify the relevant `proposal_id`
3. run:
   ```bash
   python3 -m lib.cli review show <proposal_id>
   ```
4. if `review show` fails, report the exact failure and give the precise retry
   command; do not invent proposal details
5. show the current pending proposal summary and diff
6. enter review handoff

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
