// Edge Function: settings (сохранение ключей/модели/промпта). Аналог api_settings.
import { verifyInitData, extractUser, getEnv, getSupabase, isBlacklisted, ensureUser, getUser, PROVIDER_KEY_COLS, auditLog, checkRateLimit, encryptField, decryptField, encryptApiKey, decryptApiKey, corsPreflight, withCORS } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");
const PROVIDER_LABELS: Record<string, string> = { openrouter: "OpenRouter", openai: "OpenAI", gemini: "Gemini", groq: "Groq", huggingface: "HuggingFace", venice: "Venice AI" };
const ADMIN_ID = Number(getEnv("ADMIN_ID") || 0);

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }));
}

Deno.serve(async (req: Request) => {
  try {
  const pre = corsPreflight(req);
  if (pre) return pre;
  if (req.method !== "POST") return json({ ok: false, error: "Метод не поддерживается" }, 405);
  let payload: any;
  try { payload = await req.json(); } catch { return json({ ok: false, error: "Неверный JSON" }, 400); }

  const initData = payload.init_data || "";
  const user = extractUser(initData);
  let userId: number | null = null;
  if (BOT_TOKEN && initData && user) {
    if (!(await verifyInitData(initData, BOT_TOKEN))) return json({ ok: false, error: "Невалидные данные Telegram" }, 401);
    userId = user.id;
  } else if (getEnv("WEB_APP_DEV") && payload.user_id) {
    userId = Number(payload.user_id);
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);

  const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "settings_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }
  if (await isBlacklisted(supabase, userId)) return json({ ok: false, error: "Нет доступа" }, 401);
  await ensureUser(supabase, userId);

  const updates: any = {};
  if (payload.api_key) {
    const key = String(payload.api_key).trim();
    let provider = payload.api_key_provider || (await getUser(supabase, userId))?.api_key_provider || "openrouter";
    if (!PROVIDER_LABELS[provider]) return json({ ok: false, error: "Неизвестный провайдер" }, 400);
    if (/^[•]+$/.test(key)) {
      return json({ ok: false, error: "Невалидный ключ" }, 400);
    }
    const encrypted = await encryptApiKey(key);
    updates.api_key = encrypted;
    updates.api_key_provider = provider;
    const col = PROVIDER_KEY_COLS[provider];
    if (col) updates[col] = encrypted;
  }

  const providerKeys = payload.provider_keys;
  if (providerKeys && typeof providerKeys === "object") {
    for (const p of Object.keys(providerKeys)) {
      if (!PROVIDER_KEY_COLS[p]) continue;
      const v = providerKeys[p] ? String(providerKeys[p]).trim() : null;
      if (v && /^[•]+$/.test(v)) continue;
      updates[PROVIDER_KEY_COLS[p]] = v ? await encryptApiKey(v) : null;
    }
  }
  if (payload.selected_model) updates.selected_model = String(payload.selected_model).trim();
  if (payload.system_prompt !== undefined && payload.system_prompt !== null) updates.system_prompt = await encryptField(String(payload.system_prompt));
  if (payload.context_limit !== undefined) {
    let cl = Number(payload.context_limit);
    if (isNaN(cl)) return json({ ok: false, error: "Лимит контекста должен быть числом" }, 400);
    cl = Math.max(1, Math.min(100, cl));
    updates.context_limit = cl;
  }
  if (payload.stats_display !== undefined) {
    const sd = payload.stats_display;
    if (!["disabled", "compact", "full"].includes(sd)) return json({ ok: false, error: "Неизвестный режим статистики" }, 400);
    updates.stats_display = sd;
  }
  if (payload.theme) {
    const t = String(payload.theme).trim();
    if (!["dark", "light", "midnight", "aurora", "sunset", "cyber", "neon", "lava", "ocean", "catppuccin", "custom"].includes(t)) return json({ ok: false, error: "Неизвестная тема" }, 400);
    updates.theme = t;
  }
  if (payload.notify_sound !== undefined) updates.notify_sound = payload.notify_sound ? 1 : 0;
  if (payload.notify_vibrate !== undefined) updates.notify_vibrate = payload.notify_vibrate ? 1 : 0;
  if (payload.notify_sound_id !== undefined) updates.notify_sound_id = String(payload.notify_sound_id);
  if (payload.vib_strength !== undefined) {
    let vs = Number(payload.vib_strength);
    if (isNaN(vs)) return json({ ok: false, error: "Сила вибрации должна быть числом" }, 400);
    vs = Math.max(10, Math.min(200, vs));
    updates.vib_strength = vs;
  }
  if (payload.key_mode) {
    const km = String(payload.key_mode).trim();
    if (!["auto", "manual"].includes(km)) return json({ ok: false, error: "Неверный режим ключей" }, 400);
    updates.key_mode = km;
  }

  if (payload.recommended_models !== undefined) {
    const fresh = await getUser(supabase, userId);
    if (Number(userId) !== ADMIN_ID && !fresh?.is_admin) return json({ ok: false, error: "Только администратор может изменять рекомендуемые модели" }, 403);
    const models = Array.isArray(payload.recommended_models) ? payload.recommended_models : [];
    const { error: siteError } = await supabase
      .from("site_settings")
      .upsert({ key: "recommended_models", value: JSON.stringify(models) }, { onConflict: ["key"] });
    if (siteError) return json({ ok: false, error: `❌ Не удалось сохранить рекомендуемые модели: ${siteError.message}` }, 500);
  }

  if (Object.keys(updates).length) {
    const { error } = await supabase.from("users").update(updates).eq("user_id", userId);
    if (error) {
      return json({ ok: false, error: `❌ Не удалось сохранить ключи: ${error.message}` }, 500);
    }
  }
  await auditLog(supabase, userId, "settings_save", true);

  const templatesAction = String(payload.templates_action || "").trim();
  if (templatesAction) {
    if (templatesAction === "list") {
      const { data, error } = await supabase
        .from("templates")
        .select("*")
        .eq("user_id", userId)
        .order("updated_at", { ascending: false });
      if (error) return json({ ok: false, error: error.message }, 500);
      const templates = await Promise.all((data || []).map(async (t: any) => ({
        ...t,
        text: await decryptField(t.text || ""),
        original_text: await decryptField(t.original_text || ""),
      })));
      return json({ ok: true, templates });
    }
    if (templatesAction === "save") {
      const list = Array.isArray(payload.templates) ? payload.templates : [];
      const now = Date.now();
      for (const t of list) {
        const id = String(t.id || "").trim() || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(now) + Math.random());
        await supabase.from("templates").upsert({
          id,
          user_id: userId,
          name: String(t.name || "").trim(),
          text: await encryptField(String(t.text || "").trim()),
          recommended: !!t.recommended,
          original_text: await encryptField(String(t.originalText || t.original_text || "").trim()),
          updated_at: now,
          created_at: Number(t.created_at) || now}, { onConflict: "id" });
      }
      await auditLog(supabase, userId, "templates_save", true);
      return json({ ok: true });
    }
    if (templatesAction === "delete") {
      const id = String(payload.id || "").trim();
      if (!id) return json({ ok: false, error: "id обязателен" }, 400);
      await supabase.from("templates").delete().eq("id", id).eq("user_id", userId);
      await auditLog(supabase, userId, "templates_delete", true);
      return json({ ok: true });
    }
    return json({ ok: false, error: "Неизвестное действие templates_action" }, 400);
  }

  const fresh = await getUser(supabase, userId);
  const isAdminUser = !!fresh?.is_admin;
  let recommendedModels: string[] = [];
  if (isAdminUser) {
    const { data: siteRec } = await supabase
      .from("site_settings")
      .select("value")
      .eq("key", "recommended_models")
      .maybeSingle();
    if (siteRec && siteRec.value) {
      try { recommendedModels = JSON.parse(siteRec.value); } catch { recommendedModels = []; }
    }
  }
  return json({
    ok: true,
    settings: {
      selected_model: fresh?.selected_model,
      system_prompt: fresh?.system_prompt,
      context_limit: fresh?.context_limit,
      stats_display: fresh?.stats_display,
      api_key_provider: fresh?.api_key_provider,
      key_mode: fresh?.key_mode,
      theme: fresh?.theme,
      notify_sound: fresh?.notify_sound,
      notify_vibrate: fresh?.notify_vibrate,
      notify_sound_id: fresh?.notify_sound_id,
      vib_strength: fresh?.vib_strength,
      is_admin: isAdminUser,
      recommended_models: recommendedModels,
    }});
  } catch (e: any) {
    console.error("[settings] fatal", e);
    return json({ ok: false, error: `Внутренняя ошибка: ${e?.message || e}` }, 500);
  }
});




