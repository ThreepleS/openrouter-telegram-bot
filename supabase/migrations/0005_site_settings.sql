-- Migration: site settings for global flags like whitelist toggle
CREATE TABLE IF NOT EXISTS public.site_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at BIGINT NOT NULL DEFAULT extract(epoch from now())::bigint
);

INSERT INTO public.site_settings (key, value, updated_at) VALUES ('whitelist_enabled', 'true', extract(epoch from now())::bigint) ON CONFLICT (key) DO NOTHING;
