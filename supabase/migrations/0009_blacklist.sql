-- Migration: rename whitelist to blacklist and flip access logic
BEGIN;
  ALTER TABLE public.whitelist RENAME TO blacklist;
  ALTER TABLE public.blacklist RENAME COLUMN access_type TO block_type;
  ALTER TABLE public.blacklist RENAME COLUMN access_expires_at TO block_expires_at;
  ALTER TABLE public.blacklist RENAME COLUMN added_at TO blocked_at;
  ALTER TABLE public.blacklist RENAME COLUMN note TO block_reason;
  UPDATE public.site_settings SET key = 'blacklist_enabled' WHERE key = 'whitelist_enabled';
COMMIT;
