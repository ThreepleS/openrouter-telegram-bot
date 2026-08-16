-- Migration: key_mode toggle and auto-keys for OpenRouter/Gemini

ALTER TABLE users ADD COLUMN IF NOT EXISTS key_mode text NOT NULL DEFAULT 'manual';

INSERT INTO public.site_settings (key, value, updated_at)
VALUES ('auto_key_openrouter', '', extract(epoch from now())::bigint),
       ('auto_key_gemini', '', extract(epoch from now())::bigint)
ON CONFLICT (key) DO NOTHING;
