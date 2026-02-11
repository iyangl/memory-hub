# Memory Hub

Local-first MCP backend for cross IDE/CLI context sync.

## Workflow

- `memory-pull <task prompt>`
  - calls `session.sync.pull`
  - calls `catalog.brief.generate`
  - merges context, then executes task
- `memory-push`
  - syncs structured session deltas
  - enqueues catalog refresh job

## MCP tools

- `session.sync.pull`
- `session.sync.push`
- `session.sync.resolve_conflict`
- `catalog.brief.generate`
- `catalog.health.check`

`catalog.health.check` includes: `freshness`, `catalog_version`, `coverage_pct`, `coverage`, `pending_jobs`, `drift_score`, `consistency_status`.

## Run server

```bash
python3 -m memory_hub.server --root ~/.memory-hub --workspace-root /path/to/repo
```

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

## Acceptance Evaluation

Evaluate cross-session carry-over hit rate with labeled JSONL samples:

```bash
python3 scripts/evaluate_handoff_hit_rate.py --input ./samples.jsonl
```

You can start from template: `samples/acceptance_template.jsonl`.

Sample line format:

```json
{"project_id":"project_a","expected":{"goal":1,"constraints":2,"decisions":1},"correct":{"goal":1,"constraints":2,"decisions":1}}
```
