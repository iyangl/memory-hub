CREATE TABLE IF NOT EXISTS catalog_meta (
    project_id TEXT PRIMARY KEY,
    catalog_version TEXT NOT NULL,
    source_root TEXT,
    total_files INTEGER NOT NULL DEFAULT 0,
    indexed_files INTEGER NOT NULL DEFAULT 0,
    coverage_pct REAL NOT NULL DEFAULT 0,
    last_indexed_at TEXT,
    last_full_rebuild TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_files (
    project_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    import_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, file_path)
);

CREATE INDEX IF NOT EXISTS idx_catalog_files_project_updated
    ON catalog_files (project_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS catalog_edges (
    edge_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    from_file TEXT NOT NULL,
    to_module TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source_type TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_catalog_edges_project_from
    ON catalog_edges (project_id, from_file);

CREATE INDEX IF NOT EXISTS idx_catalog_edges_project_confidence
    ON catalog_edges (project_id, confidence DESC);
