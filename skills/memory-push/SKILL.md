---
name: memory-push
description: Push structured session deltas to memory hub without requiring a new prompt.
---

# Skill: memory-push

## Purpose
Sync current session with zero user payload.

## Input
No user input. Client auto-fills required fields.

## Required flow
1. Extract structured session deltas:
- `session_summary`
- `role_deltas`
- `decisions_delta`
- `open_loops_new`
- `open_loops_closed`
- `files_touched`
2. Call `session.sync.push`.
3. If response is `needs_resolution`, call `session.sync.resolve_conflict` with default `strategy=merge_note`.
4. Return sync result:
- `sync_id`
- `memory_version`
- `consistency_stamp`
- `catalog_job`
- conflict status

## Failure behavior
- Return exact error payload and retry suggestion.
