-- Gemini Prompt Caching table
CREATE TABLE IF NOT EXISTS gemini_cache (
    user_id BIGINT NOT NULL,
    model_id TEXT NOT NULL,
    cache_name TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, model_id)
);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_gemini_cache_expires ON gemini_cache(expires_at);

-- Updated at trigger (using storage schema function)
CREATE TRIGGER update_gemini_cache_updated_at
    BEFORE UPDATE ON gemini_cache
    FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();