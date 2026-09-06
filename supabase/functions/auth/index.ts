// Edge Function: auth (аналог api_auth + api_whoami).
import { verifyInitData, extractUser, getEnv, getSupabase, isBlacklisted, ensureUser, getUser, auditLog, checkRateLimit, decryptField, corsPreflight, withCORS, resolveEffectiveApiKey } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");
const ADMIN_ID = Number(getEnv("ADMIN_ID") || 0);

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }));
}

Deno.serve(async (req: Request) => {
  const pre = corsPreflight(req);
  if (pre) return pre;
  if (req.method !== "POST") return json({ ok: false, error: "Метод не поддерживается" }, 405);
  let payload: any;
  try { payload = await req.json(); } catch { return json({ ok: false, error: "Неверный JSON" }, 400); }

  const initData = payload.init_data || "";
  const user = extractUser(initData);
  let userId: number | null = null;
  if (BOT_TOKEN && initData && user) {
    const ok = await verifyInitData(initData, BOT_TOKEN);
    await auditLog(getSupabase(true), user.id, "auth_verify", ok);
    if (!ok) return json({ ok: false, error: "Невалидные данные Telegram" }, 401);
    userId = user.id;
  } else if (getEnv("WEB_APP_DEV") && payload.user_id) {
    userId = Number(payload.user_id);
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);

  const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }

  if (await isBlacklisted(supabase, userId)) {
    await auditLog(supabase, userId, "auth_blacklist_fail", false);
    return json({ ok: false, error: "Нет доступа. Запросите доступ у администратора." }, 401);
  }
  await auditLog(supabase, userId, "auth_success", true);

  const userRow = await getUser(supabase, userId);
  if (userRow == null) return json({ ok: false, error: "Укажи API-ключ в настройках" }, 401);

  const apiKey = userRow.api_key || "";
  const apiKeyProvider = userRow.api_key_provider || "openrouter";
  const dbKeys = ["openrouter", "openai", "gemini", "groq", "huggingface", "venice"]
    .map((p) => userRow["api_key_" + p])
    .some((k) => k && k.trim());
  const autoKey = userRow.key_mode === "auto"
    ? await Promise.all(["openrouter", "gemini"].map((p) => resolveEffectiveApiKey(supabase, userRow, p)))
    : [];
  const hasKey = !!(apiKey || dbKeys || autoKey.some((k) => k && String(k).trim()));

  const limit = Math.max(1, Math.min(200, Number(userRow.context_limit) || 10));
  let history: any[] = [];
  try {
    const { data: hist } = await supabase
      .from("messages")
      .select("role, content, image_url")
      .eq("user_id", userId)
      .order("id", { ascending: false })
      .limit(limit);
    history = await Promise.all((hist || []).reverse().map(async (m: any) => ({
      role: m.role,
      content: await decryptField(m.content || ""),
      image: m.image_url || null})));
  } catch (_) {
    history = [];
  }

  let recommendedModels: string[] = [];
  try {
    const { data: siteRec } = await supabase
      .from("site_settings")
      .select("value")
      .eq("key", "recommended_models")
      .maybeSingle();
    if (siteRec && siteRec.value) {
      try { recommendedModels = JSON.parse(siteRec.value); } catch { recommendedModels = []; }
    }
  } catch (_) {
    recommendedModels = [];
  }

  return json({
    ok: true,
    user_id: userId,
    is_admin: userId === ADMIN_ID,
    needs_key: !hasKey,
    history,
    settings: {
      selected_model: userRow.selected_model,
      system_prompt: userRow.system_prompt,
      context_limit: userRow.context_limit,
      stats_display: userRow.stats_display,
      api_key_provider: userRow.api_key_provider,
      key_mode: userRow.key_mode,
      theme: userRow.theme,
      notify_sound: userRow.notify_sound,
      notify_vibrate: userRow.notify_vibrate,
      notify_sound_id: userRow.notify_sound_id,
      vib_strength: userRow.vib_strength,
      recommended_models: recommendedModels}});
});




