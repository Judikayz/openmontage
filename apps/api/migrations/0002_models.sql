CREATE TABLE IF NOT EXISTS models (
 id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 source_url TEXT NOT NULL,
 repo_id TEXT NOT NULL,
 revision TEXT NOT NULL DEFAULT 'main',
 model_type TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'registered',
 total_bytes INTEGER NOT NULL DEFAULT 0,
 stored_bytes INTEGER NOT NULL DEFAULT 0,
 file_count INTEGER NOT NULL DEFAULT 0,
 manifest_json TEXT,
 object_keys_json TEXT,
 error TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_models_status ON models(status,updated_at);
