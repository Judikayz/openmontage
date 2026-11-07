CREATE TABLE IF NOT EXISTS workflows (id TEXT PRIMARY KEY, name TEXT NOT NULL, config_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, workflow_id TEXT, status TEXT NOT NULL, provider TEXT NOT NULL, tool TEXT NOT NULL, payload_json TEXT NOT NULL, result_json TEXT, error TEXT, idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(workflow_id) REFERENCES workflows(id));
CREATE TABLE IF NOT EXISTS secrets (id TEXT PRIMARY KEY, provider TEXT NOT NULL UNIQUE, ciphertext TEXT NOT NULL, iv TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, cron TEXT NOT NULL, timezone TEXT NOT NULL DEFAULT 'Africa/Lagos', enabled INTEGER NOT NULL DEFAULT 1, next_run_at TEXT NOT NULL, last_run_at TEXT, created_at TEXT NOT NULL, FOREIGN KEY(workflow_id) REFERENCES workflows(id));
CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, object_key TEXT NOT NULL UNIQUE, content_type TEXT, size INTEGER, metadata_json TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(enabled,next_run_at);
