---
name: durable-memory
description: "通过 MCP tools 读写 durable memory proposal，并通过 CLI review/rollback 完成人工审查"
tools: ["Bash"]
---

## Purpose

Use durable memory v1 correctly:

- read/search through MCP
- write through `propose_memory` / `propose_memory_update`
- review through CLI

Do not bypass the control plane by editing `.memoryhub/` or `memory.db`.

## Preconditions

The MCP client must already be connected to:

```bash
python3 -m lib.mcp_server
```

or:

```bash
memory-hub-mcp
```

`MEMORY_HUB_PROJECT_ROOT` must point to the target project root.

## Required Flow

### Step 1: Load boot memory

Before the first durable memory operation in a session:

```text
read_memory("system://boot")
```

### Step 2: Read before update

- If you know the target URI: `read_memory(uri)`
- If you need to locate it first: `search_memory(query, type?, limit?)`

### Step 3: Propose instead of writing directly

New memory:

```text
propose_memory(type, title, content, recall_when, why_not_in_code, source_reason)
```

Update existing memory:

```text
propose_memory_update(uri, old_string?, new_string?, append?, recall_when?, why_not_in_code?, source_reason)
```

Rules:

- only `identity / decision / constraint / preference`
- no direct write to `.memoryhub/`
- no direct SQL
- no full replace

### Step 4: Human review via CLI

```bash
memory-hub review list
memory-hub review show <proposal_id>
memory-hub review approve <proposal_id> [--reviewer <id>] [--note <text>]
memory-hub review reject <proposal_id> --note <text> [--reviewer <id>]
memory-hub rollback <uri> --to-version <version_id> --note <text> [--reviewer <id>]
```

## Output Expectations

MCP tools return structured payloads with:

- `ok`
- `code`
- `message`
- `data`

CLI commands return JSON envelope and exit codes:

- `0` success
- `1` business error
- `2` system error

## Error Handling

- Missing boot read → load `system://boot` before proceeding
- Proposal returns `NOOP` → do not force a write
- Proposal returns `UPDATE_TARGET` → read target memory and propose an update instead
- CLI returns `STALE_PROPOSAL` → re-read current approved memory and regenerate proposal
