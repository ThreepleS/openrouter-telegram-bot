// Edge Function: добавить модель в избранное (аналог api_favorite_add).
import { verifyInitData, extractUser, getEnv, getSupabase, isBlacklisted, ensureUser, auditLog, checkRateLimit, corsPreflight, withCORS } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }));
}

function sha1Short(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

Deno.serve(async (req: Request) => {
  const pre = corsPreflight(req);
  if (pre) return pre;
  if (req.method !== "POST") return json({ ok: false, error: "РњРµС‚РѕРґ РЅРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ" }, 405);
  let payload: any;
  try { payload = await req.json(); } catch { return json({ ok: false, error: "РќРµРІРµСЂРЅС‹Р№ JSON" }, 400); }

  const initData = payload.init_data || "";
  const user = extractUser(initData);
  let userId: number | null = null;
  if (BOT_TOKEN && initData && user) {
    if (!(await verifyInitData(initData, BOT_TOKEN))) return json({ ok: false, error: "Невалидные данные Telegram" }, 401);
    userId = user.id;
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);
  const modelId = (payload.model_id || "").trim();
  if (!modelId) return json({ ok: false, error: "Не указан model_id" }, 400);

  const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "favorites_add_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }
  if (await isBlacklisted(supabase, userId)) {return json({ ok: false, error: "Нет доступа" }, 401);
  }
  await ensureUser(supabase, userId);

  const row = {
    user_id: userId,
    model_id: modelId,
    display_name: (payload.display_name || modelId).trim(),
    meta: payload.meta || null,
    short_id: sha1Short(modelId),
    blocked_at: Math.floor(Date.now() / 1000),
    context: payload.context ?? null,
    mod_in: payload.mod_in ?? null,
    mod_out: payload.mod_out ?? null,
    price_prompt: payload.price_prompt ?? null,
    price_completion: payload.price_completion ?? null,
    description: payload.description ?? null,
    is_free: payload.is_free === undefined ? null : (payload.is_free ? 1 : 0)};
  await supabase.from("user_models").upsert(row, { onConflict: "user_id,model_id" });
  await auditLog(supabase, userId, "favorites_add", true, modelId);
  return json({ ok: true, model_id: modelId });
});





