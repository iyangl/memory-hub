# Agent Guidance

## Goal
Keep Memory Hub focused on boundary sync for cross IDE/CLI sessions.

## Rules
1. Use `memory-pull` before executing a new-session task prompt.
2. Use `memory-push` at session end without requiring a new prompt.
3. Do not enforce per-turn full transcript logging.
4. Keep project isolation strict by `project_id`.
