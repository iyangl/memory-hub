# MVP Plan - 5 Weeks

## Milestone 1 (Week 1): Core Storage and Daemon Skeleton
### Deliverables
1. `memory-hubd` process skeleton with MCP tool registration.
2. SQLite schema for:
- `raw_events`
- `turns`
- `projection_offsets`
- `memory_facts`
- `decisions`
- `decision_edges`
- `artifact_links`
3. Append-only constraints for `raw_events`.

### Exit Criteria
1. Can append and replay raw events for a test session.
2. DB rejects update/delete on `raw_events`.

## Milestone 2 (Week 2): Mandatory Turn Protocol
### Deliverables
1. `turn.begin`, `event.append`, `turn.end`.
2. Short-lived `ack_token` issuance and verification.
3. Fail-closed precondition checks for protected operations.

### Exit Criteria
1. Protected operations fail without valid `ack_token`.
2. Turn lifecycle coverage is measurable.

## Milestone 3 (Week 3): Retrieval and Context Pack
### Deliverables
1. `memory.search` (keyword baseline, optional embedding enhancement).
2. `context.pack` assembly:
- recent events
- relevant facts
- decision lineage snapshot
3. Projector worker from `raw_events` to `memory_facts`.

### Exit Criteria
1. Context packs are generated deterministically for a given input.
2. Projection lag remains within target budget under local load.

## Milestone 4 (Week 4): Decision Graph and Isolation Hardening
### Deliverables
1. `decision.record`, `decision.supersede`.
2. `artifact_links` integration with commit/file references.
3. Hard per-project routing checks and storage path isolation tests.

### Exit Criteria
1. Decision evolution can be replayed as a timeline.
2. Cross-project queries are blocked by default.

## Milestone 5 (Week 5): Client Integration and Audit Readiness
### Deliverables
1. Integrate one IDE client and one CLI client.
2. `audit.replay` with filters by project/session/turn/time.
3. Backup/export script and smoke-test suite.

### Exit Criteria
1. Turn completion rate >= 99% on integrated clients.
2. 24-hour local run without data corruption.
3. Replay output can reconstruct complete selected sessions.

## Global Definition of Done
1. Every stored turn has immutable provenance metadata.
2. No memory sharing across projects by default.
3. Core tools are documented with request/response schemas.
4. Operational runbook exists for start, stop, backup, and restore.

