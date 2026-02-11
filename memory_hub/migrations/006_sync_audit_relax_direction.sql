CREATE TABLE IF NOT EXISTS sync_audit_new (
    sync_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    client_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    error_code TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);

INSERT OR IGNORE INTO sync_audit_new
    SELECT sync_id, project_id, direction, client_id, session_id,
           request_json, response_json, error_code, latency_ms, created_at
    FROM sync_audit;

DROP TABLE sync_audit;

ALTER TABLE sync_audit_new RENAME TO sync_audit;

CREATE INDEX IF NOT EXISTS idx_sync_audit_project_time
    ON sync_audit (project_id, created_at DESC);
