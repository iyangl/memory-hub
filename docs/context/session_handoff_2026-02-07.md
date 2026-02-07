# Session Handoff - 2026-02-07

## Purpose
Carry the architecture and execution context from this session into a new project without relying on chat memory inheritance.

## Scope
- Build a local-first Memory MCP Hub for personal use.
- Guarantee every dialog turn is persisted into `raw_events`.
- Support multi-project isolation with no memory sharing by default.
- Track solution evolution with explicit decision lineage.

## Decisions Made
1. Architecture: local backend-first design, optional local UI.
2. Storage model: event sourcing with append-only `raw_events`.
3. Isolation model: physical isolation per project (separate DB and index path).
4. Enforcement model: fail-closed turn protocol (`turn.begin` -> `event.append` -> `turn.end`).
5. Memory model: dual-track
- Truth layer: full raw event log.
- Retrieval layer: projected facts + decision graph + searchable index.
6. Licensing posture for MVP:
- Do not copy AGPL/PolyForm source code into this project.
- Design inspiration is allowed; implementation must be original.

## Required Capabilities (MVP)
- Ingestion: `turn.begin`, `event.append`, `turn.end`
- Search/context: `memory.search`, `context.pack`
- Decision tracking: `decision.record`, `decision.supersede`
- Audit: `audit.replay`
- Isolation guardrails: hard project boundary checks on every read/write path

## Non-Goals (MVP)
- Cloud multi-tenant deployment
- Cross-project memory federation
- Complex ranking pipelines and advanced model orchestration

## Risks
- Some MCP clients may not expose lifecycle hooks; full turn capture then needs a wrapper.
- If token precondition checks are bypassed, event completeness degrades quickly.
- Schema evolution in event sourcing can get expensive without version discipline.

## First Implementation Target
- Ship a working local daemon with SQLite and strict turn preconditions before adding vector retrieval.

## Startup Prompt For New Session
Use this exact prompt in the new project:

`Read docs/context/session_handoff_2026-02-07.md, docs/architecture/memory_hub_v1.md, and docs/backlog/mvp_5_weeks.md first. Then start implementation from Milestone 1 and keep all writes append-only for raw_events.`

