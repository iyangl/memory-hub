# ADR 0001: Use Event Sourcing for Memory Core

- Status: Accepted
- Date: 2026-02-07

## Context
The system must preserve every interaction turn, allow deterministic replay, and support derived views (facts, decisions, context packs) without losing history.

## Decision
Use event sourcing with an append-only `raw_events` store as the single source of truth.

## Consequences
### Positive
- Full auditability and reproducible timelines.
- Flexible projections for new read models without data loss.
- Natural fit for incremental context extraction.

### Negative
- Requires strict schema/version discipline.
- Projection complexity and eventual consistency management.
- More operational logic than direct CRUD storage.

## Alternatives Considered
1. CRUD-first memory table
- Rejected: cannot reliably reconstruct historical state and reasoning.

2. Snapshot-only transcripts
- Rejected: weak provenance and difficult decision lineage tracking.

## Follow-up
- Enforce append-only DB constraints on `raw_events`.
- Add projector offset checkpoints for crash-safe resume.

