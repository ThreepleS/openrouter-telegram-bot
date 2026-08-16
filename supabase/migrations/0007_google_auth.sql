-- Migration: add google_id for Google OAuth users
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id text;
CREATE UNIQUE INDEX IF NOT EXISTS users_google_id_idx ON users(google_id);
