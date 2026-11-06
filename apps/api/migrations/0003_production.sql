CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, settings_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS characters (id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', reference_asset_keys_json TEXT NOT NULL DEFAULT '[]', attributes_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS scenes (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL, prompt TEXT NOT NULL DEFAULT '', character_ids_json TEXT NOT NULL DEFAULT '[]', settings_json TEXT NOT NULL DEFAULT '{}', sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS job_logs (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, level TEXT NOT NULL DEFAULT 'info', message TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS provider_tests (id TEXT PRIMARY KEY, provider TEXT NOT NULL, ok INTEGER NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS asset_uploads (id TEXT PRIMARY KEY, object_key TEXT NOT NULL, upload_id TEXT NOT NULL, parts_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'initiated', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id);
CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id,sort_order);
CREATE INDEX IF NOT EXISTS idx_job_logs_job ON job_logs(job_id,created_at);
