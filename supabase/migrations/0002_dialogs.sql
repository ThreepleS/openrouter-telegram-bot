-- Migration: add dialogs table for cross-device sync
CREATE TABLE IF NOT EXISTS dialogs (
    id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    model TEXT NOT NULL DEFAULT '',
    created_at BIGINT NOT NULL DEFAULT 0,
    updated_at BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_dialogs_user_id ON dialogs (user_id);
CREATE INDEX IF NOT EXISTS idx_dialogs_user_updated ON dialogs (user_id, updated_at DESC);

ALTER TABLE dialogs DISABLE ROW LEVEL SECURITY;
