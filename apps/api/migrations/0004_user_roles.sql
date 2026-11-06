CREATE TABLE IF NOT EXISTS user_roles (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL CHECK(role IN ('admin','editor','viewer')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_user_roles_email ON user_roles(email);
