-- Migration: enable RLS for site_settings table
ALTER TABLE public.site_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_site_settings" ON public.site_settings FOR ALL TO service_role USING (true) WITH CHECK (true);
