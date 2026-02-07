# Memory Hub v1 Architecture

## Goal
Provide a local-first MCP memory backend that records every turn, supports project isolation, and enables reproducible context assembly for LLM clients.

## High-Level Design
```text
LLM Client (IDE/CLI)
    |
    | MCP (stdio and optionally Streamable HTTP)
    v
Memory Hub Daemon
    - turn gatekeeper
    - event appender
    - projection workers
    - retrieval/context composer
    - decision graph manager
    |
    +-- per-project SQLite (events + read models)
    +-- per-project optional vector index
```

## Core Principles
1. Append-only source of truth for all interactions.
2. Physical project isolation by default.
3. Fail-closed preconditions for write completeness.
4. Read models are disposable projections from events.

## Runtime Components
1. MCP adapter
- Exposes tools/resources to clients.
- Injects `project_id`, `client_id`, and `session_id`.

2. Turn gatekeeper
- Enforces per-turn state machine.
- Issues short-lived `ack_token` on `turn.begin`.
- Rejects tool calls lacking valid token.

3. Event store
- `raw_events` append-only table.
- Monotonic sequence per stream.
- Idempotency key support.

4. Projectors
- Consume new events and update:
  - `memory_facts`
  - `decisions`
  - `decision_edges`
  - `artifact_links`
  - optional embedding index

5. Context composer
- Builds context bundle for LLM:
  - recent turns
  - relevant facts
  - active decision chain

6. Audit interface
- Deterministic replay by stream or time window.

## Data Model (v1)
1. `raw_events`
- `event_id` TEXT PK
- `project_id` TEXT NOT NULL
- `session_id` TEXT NOT NULL
- `turn_id` TEXT NOT NULL
- `stream_id` TEXT NOT NULL
- `stream_seq` INTEGER NOT NULL
- `event_type` TEXT NOT NULL
- `event_version` INTEGER NOT NULL
- `occurred_at` TEXT NOT NULL
- `actor` TEXT NOT NULL
- `source` TEXT NOT NULL
- `payload_json` TEXT NOT NULL
- `idempotency_key` TEXT
- `trace_id` TEXT

2. `turns`
- `project_id`, `session_id`, `turn_id` as composite key
- `status` in (`open`, `closed`, `incomplete`)
- `ack_token_hash`, `expires_at`

3. `memory_facts`
- projected stable facts with confidence and provenance

4. `decisions`
- immutable decision nodes (`decision_id`, title, rationale, status)

5. `decision_edges`
- lineage (`from_decision_id`, `to_decision_id`, `relation`)

6. `artifact_links`
- decision to code artifacts (`commit`, `file_path`, `pr`, `note`)

7. `projection_offsets`
- projector cursor checkpoint for resumable processing

## Turn Protocol (strict)
1. `turn.begin(project_id, session_id, turn_id)` -> returns `ack_token`.
2. `event.append(..., ack_token)` for user/assistant/tool events.
3. `turn.end(..., ack_token)` closes turn.
4. Any protected call without valid token -> reject with precondition error.

## MCP Tool Contract (v1)
1. `turn.begin`
2. `event.append`
3. `turn.end`
4. `memory.search`
5. `context.pack`
6. `decision.record`
7. `decision.supersede`
8. `audit.replay`

## Isolation Strategy
1. One project, one storage root:
- `~/.memory-hub/projects/<project_id>/events.db`
- `~/.memory-hub/projects/<project_id>/index/`
2. No cross-project queries in v1.
3. All APIs require explicit `project_id`, validated against session binding.

## Observability
1. Metrics
- turn completion rate
- append rejection rate
- projection lag
- retrieval latency

2. Health checks
- DB writable/readable
- projector alive
- index freshness

## Security (local-first)
1. Bind network listeners to localhost only.
2. Store only hashed `ack_token`.
3. Optional payload redaction before indexing.
4. Audit trail is immutable for forensic replay.

## Out of Scope (v1)
1. Multi-user auth and cloud synchronization.
2. Cross-project federated retrieval.
3. Automatic policy inference from raw event stream.

