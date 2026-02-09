BEGIN;

CREATE TABLE IF NOT EXISTS project_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    memory_version INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_state_current (
    project_id TEXT NOT NULL,
    role TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    version INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by_client TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    PRIMARY KEY (project_id, role, memory_key)
);

CREATE TABLE IF NOT EXISTS role_state_versions (
    version_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    role TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    created_by_client TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    supersedes_version_id TEXT,
    memory_version INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_role_versions_project_role_key_version
    ON role_state_versions (project_id, role, memory_key, memory_version DESC);

CREATE TABLE IF NOT EXISTS handoff_packets (
    handoff_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    ttl_expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by_client TEXT NOT NULL,
    memory_version INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_handoff_project_created
    ON handoff_packets (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS open_loops (
    loop_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    details TEXT,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    priority INTEGER NOT NULL,
    owner_role TEXT,
    created_at TEXT NOT NULL,
    created_by_client TEXT NOT NULL,
    closed_at TEXT,
    closed_by_client TEXT,
    memory_version INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_open_loops_project_status
    ON open_loops (project_id, status, priority, created_at);

CREATE TABLE IF NOT EXISTS sync_audit (
    sync_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('pull', 'push', 'resolve_conflict')),
    client_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sync_audit_project_time
    ON sync_audit (project_id, created_at DESC);

COMMIT;
