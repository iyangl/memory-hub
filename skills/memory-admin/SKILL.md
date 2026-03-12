---
name: memory-admin
description: "项目记忆维护入口：repair/diagnose/discover/session-extract，不参与主 workflow"
tools: ["Bash"]
---

## Purpose

Use this skill only for maintenance and diagnostics of the unified project
memory system.

Typical tasks:

- run catalog repair
- inspect current code changes for memory-worthy decision candidates
- inspect manifest / store layout
- diagnose index drift or missing refs
- run transcript distillation through the CLI extractor

## Scope

This skill is not the primary workflow for reading or writing memory.

Primary workflow:

- `project-memory`

## Allowed Actions

- `memory-hub catalog-repair`
- `memory-hub discover [--summary-file <summary>]`
- `memory-hub session-extract --file <session-transcript>`
- inspect `.memory/manifest.json`
- inspect `.memory/docs/`, `.memory/catalog/`, `.memory/_store/`
- inspect `.memory/_store/projections/boot.json` and `search.json`
- diagnose CLI / MCP behavior issues

## Session Distillation

Use `memory-hub session-extract --file <session-transcript>` when the user asks
to distill a completed conversation into memory candidates.

This is a CLI maintenance action, not an MCP tool call. Do not invent
`session_extract(...)` or any other MCP tool name for it.

The extractor:

- classifies transcript chunks into docs-only / durable-only / dual-write
- routes them through the existing unified write lane
- creates docs change reviews or durable proposals instead of writing active
  state directly

Do not use this skill to bypass the normal write lane.

## Decision Discovery

Use `memory-hub discover` when the user asks whether the current code changes
contain new rules, exceptions, or docs drift worth turning into memory
candidates.

This command is read-only. It does not write active docs or approved durable
memory. It only returns structured candidates with:

- why the candidate is worth capturing
- which changed files and existing refs support it
- whether it likely belongs in `docs-only`, `durable-only`, or `dual-write`

If the user wants to continue after reviewing candidates, route the chosen item
through the existing unified write lane instead of inventing a direct apply
path.
