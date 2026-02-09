# Memory Hub (Greenfield)

Local-first MCP memory backend with role-isolated context sync for cross IDE/CLI session handoff.

## Core workflow

- `memory-pull <task prompt>`: pull memory first, then execute the task.
- `memory-push`: sync current session deltas without a new prompt.

## MCP tools

- `session.sync.pull`
- `session.sync.push`
- `session.sync.resolve_conflict`

## Run server

```bash
python -m memory_hub.server --root ~/.memory-hub
```

## Test

```bash
python -m unittest discover -s tests -v
```
