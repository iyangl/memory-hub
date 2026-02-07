-- Memory Hub v1 schema
-- Append-only enforcement is applied to raw_events via triggers.

BEGIN;

CREATE TABLE IF NOT EXISTS raw_events (
    event_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    stream_id TEXT NOT NULL,
    stream_seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    idempotency_key TEXT,
    trace_id TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_events_stream_seq
    ON raw_events (stream_id, stream_seq);

CREATE INDEX IF NOT EXISTS idx_raw_events_project_time
    ON raw_events (project_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_raw_events_turn
    ON raw_events (project_id, session_id, turn_id);

CREATE TRIGGER IF NOT EXISTS raw_events_no_update
BEFORE UPDATE ON raw_events
BEGIN
    SELECT RAISE(ABORT, 'raw_events is append-only');
END;

CREATE TRIGGER IF NOT EXISTS raw_events_no_delete
BEFORE DELETE ON raw_events
BEGIN
    SELECT RAISE(ABORT, 'raw_events is append-only');
END;

CREATE TABLE IF NOT EXISTS turns (
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    status TEXT NOT NULL,
    ack_token_hash TEXT,
    expires_at TEXT,
    PRIMARY KEY (project_id, session_id, turn_id)
);

CREATE TABLE IF NOT EXISTS projection_offsets (
    projector_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL,
    stream_seq INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_facts (
    fact_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    fact_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_event_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    superseded_by TEXT
);

CREATE TABLE IF NOT EXISTS decision_edges (
    edge_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    from_decision_id TEXT NOT NULL,
    to_decision_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_links (
    link_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_ref TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

COMMIT;
