CREATE TABLE IF NOT EXISTS catalog_jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_catalog_jobs_project_status
    ON catalog_jobs (project_id, status, updated_at);

CREATE TABLE IF NOT EXISTS drift_reports (
    report_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    method TEXT NOT NULL,
    drift_score REAL NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_drift_reports_project_created
    ON drift_reports (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS consistency_links (
    link_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sync_id TEXT NOT NULL,
    memory_version INTEGER NOT NULL,
    catalog_version TEXT NOT NULL,
    consistency_status TEXT NOT NULL CHECK (consistency_status IN ('ok', 'degraded', 'unknown')),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_consistency_links_project_created
    ON consistency_links (project_id, created_at DESC);
