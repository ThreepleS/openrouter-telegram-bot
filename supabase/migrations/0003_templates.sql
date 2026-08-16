-- Migration: add templates table for cross-device sync
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    recommended BOOLEAN NOT NULL DEFAULT false,
    original_text TEXT NOT NULL DEFAULT '',
    created_at BIGINT NOT NULL DEFAULT 0,
    updated_at BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_templates_user_id ON templates (user_id);
CREATE INDEX IF NOT EXISTS idx_templates_user_updated ON templates (user_id, updated_at DESC);

ALTER TABLE templates DISABLE ROW LEVEL SECURITY;
