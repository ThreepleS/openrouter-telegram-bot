-- Migration: enable RLS and add service_role policies for all tables
-- Edge Functions use service_role key which bypasses RLS by default,
-- but explicit policies make the security model clear and future-proof.

-- users
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_users" ON public.users FOR ALL TO service_role USING (true) WITH CHECK (true);

-- whitelist
ALTER TABLE public.whitelist ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_whitelist" ON public.whitelist FOR ALL TO service_role USING (true) WITH CHECK (true);

-- messages
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_messages" ON public.messages FOR ALL TO service_role USING (true) WITH CHECK (true);

-- api_stats
ALTER TABLE public.api_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_api_stats" ON public.api_stats FOR ALL TO service_role USING (true) WITH CHECK (true);

-- user_models
ALTER TABLE public.user_models ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_user_models" ON public.user_models FOR ALL TO service_role USING (true) WITH CHECK (true);

-- dialogs
ALTER TABLE public.dialogs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_dialogs" ON public.dialogs FOR ALL TO service_role USING (true) WITH CHECK (true);

-- templates
ALTER TABLE public.templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_templates" ON public.templates FOR ALL TO service_role USING (true) WITH CHECK (true);

-- audit_log
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_audit_log" ON public.audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);
