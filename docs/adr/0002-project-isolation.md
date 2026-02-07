# ADR 0002: Enforce Physical Per-Project Memory Isolation

- Status: Accepted
- Date: 2026-02-07

## Context
The project requires strict non-sharing of memory across projects by default, with minimal configuration risk.

## Decision
Use physical storage isolation per project:
- Separate SQLite DB per project.
- Separate index directory per project.
- No cross-project query APIs in v1.

## Consequences
### Positive
- Strong default privacy boundary.
- Lower chance of accidental data leakage.
- Simpler mental model for personal multi-repo workflows.

### Negative
- Duplicate storage for shared concepts.
- No global search across projects unless explicit future feature.
- More migration steps if consolidation is needed later.

## Alternatives Considered
1. Single DB with logical `project_id` partitioning
- Rejected for v1: easier to misconfigure and accidentally query across boundaries.

2. Shared memory pool with tags
- Rejected: violates default non-sharing requirement.

## Follow-up
- Require `project_id` in every API call.
- Add hard checks that session binding matches project route.
- Keep cross-project federation as an explicit future ADR.

