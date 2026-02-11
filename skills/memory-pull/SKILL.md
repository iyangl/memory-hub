---
name: memory-pull
description: Pull synchronized project context before executing a new-session task prompt.
---

# Skill: memory-pull

## Purpose
Start a new task with synchronized state and architecture context.

## Input
Natural language task prompt from user.

## Required flow
1. Build MCP request for `session.sync.pull`:
- `project_id`
- `client_id`
- `session_id`
- `task_prompt`
- optional `task_type` and `max_tokens`
2. Call `session.sync.pull` first.
3. Confirm response includes:
- `context_brief`
- `catalog_brief`
- `consistency_stamp`
4. Use `context_brief + original task prompt` to execute the task.
5. Return task result with injection summary:
- resolved task type
- injected roles
- catalog freshness
- consistency stamp

## Failure behavior
- If pull fails, continue task execution in no-memory mode.
- Must state failure reason.
