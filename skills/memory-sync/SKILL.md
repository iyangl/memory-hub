---
name: memory-sync
description: Combined entry skill for boundary sync, supporting start (pull+task) and finish (push).
---

# Skill: memory-sync

## Purpose
Provide a single global entry for boundary sync:
- session start: pull context before task execution
- session end: push session deltas

## Modes
1. `start <task prompt>`
- Trigger `memory-pull` flow first.
- Build execution context from pull response.
- Continue task execution with injected context.

2. `finish`
- Trigger `memory-push` flow with zero user payload.
- Return sync summary (`sync_id`, `memory_version`, conflict state, catalog job).

## Required behavior
1. New session must use `start` before coding.
2. Session wrap-up must use `finish`.
3. On pull failure: continue in no-memory mode and report reason.
4. On push conflict: resolve with `merge_note` by default.

## Output
- `start`: task result + injection summary.
- `finish`: sync result + retry hint when failed.
