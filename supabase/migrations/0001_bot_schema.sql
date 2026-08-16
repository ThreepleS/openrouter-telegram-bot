-- Migration: port local bot.db (SQLite) schema to Supabase Postgres.
-- Applied via Supabase Management API / SQL editor.

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    api_key TEXT,
    api_key_provider TEXT NOT NULL DEFAULT 'openrouter',
    api_key_openrouter TEXT,
    api_key_openai TEXT,
    api_key_gemini TEXT,
    api_key_groq TEXT,
    api_key_huggingface TEXT,
    api_key_venice TEXT,
    selected_model TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT 'Ты — полезный и дружелюбный AI-ассистент.',
    context_limit INTEGER NOT NULL DEFAULT 10,
    stats_display TEXT NOT NULL DEFAULT 'full',
    theme TEXT NOT NULL DEFAULT 'dark',
    key_mode TEXT NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS whitelist (
    user_id BIGINT PRIMARY KEY,
    note TEXT DEFAULT '',
    access_type TEXT NOT NULL DEFAULT 'permanent',
    access_expires_at BIGINT,
    added_at BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_stats (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tokens_used INTEGER NOT NULL,
    timestamp BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_models (
    user_id BIGINT NOT NULL,
    model_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    meta TEXT,
    short_id TEXT,
    added_at BIGINT,
    context INTEGER,
    mod_in TEXT,
    mod_out TEXT,
    price_prompt TEXT,
    price_completion TEXT,
    description TEXT,
    is_free INTEGER,
    PRIMARY KEY (user_id, model_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages (user_id);
CREATE INDEX IF NOT EXISTS idx_api_stats_user_id ON api_stats (user_id);
CREATE INDEX IF NOT EXISTS idx_user_models_user_id ON user_models (user_id);

-- Row Level Security: disable for service_role (bot uses service_role key).
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE whitelist DISABLE ROW LEVEL SECURITY;
ALTER TABLE messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE api_stats DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_models DISABLE ROW LEVEL SECURITY;
