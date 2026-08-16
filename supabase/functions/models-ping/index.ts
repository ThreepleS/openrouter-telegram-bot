// Edge Function: пинг бесплатных моделей провайдера (аналог api_models_ping).
import { verifyInitData, extractUser, getEnv, getSupabase, API_ENDPOINTS, isWhitelisted, ensureUser, getUser, buildUserProviderKeys, getProviderApiKey, resolveEffectiveApiKey, detectProvider, normalizeModelId, normalizeProviderModel, modelIdForProvider, buildOpenAIMessages, auditLog, checkRateLimit, corsPreflight, withCORS } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }));
}

async function pingOne(provider: string, modelId: string, key: string, systemPrompt: string): Promise<[string, string]> {
  let url = "";
  const headers: Record<string, string> = {};
  const normalized = normalizeModelId(provider, modelId);
  if (provider === "gemini") {
    url = API_ENDPOINTS.gemini_chat.replace("{model}", normalized).replace(":generateContent", ":streamGenerateContent") + "?alt=sse";
    headers["Content-Type"] = "application/json";
    headers["x-goog-api-key"] = key;
  } else if (provider === "openrouter") {
    url = API_ENDPOINTS.openrouter_chat;
    headers.Authorization = `Bearer ${key}`;
    headers["Content-Type"] = "application/json";
    headers["HTTP-Referer"] = "https://t.me/openrouter_bot";
    headers["X-Title"] = "OpenRouter Telegram Bot";
  } else if (provider === "venice") {
    url = API_ENDPOINTS.venice_chat;
    headers.Authorization = `Bearer ${key}`;
    headers["Content-Type"] = "application/json";
  } else {
    return ["error", "ping РЅРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ РґР»СЏ РїСЂРѕРІР°Р№РґРµСЂР°"];
  }

  const messages = [{ role: "user", content: "Ping" }];
  const payload = provider === "gemini"
    ? { contents: [{ role: "user", parts: [{ text: "Ping" }] }], system_instruction: { parts: [{ text: systemPrompt }] } }
    : { model: normalized, messages: buildOpenAIMessages(systemPrompt, messages, provider, normalized), stream: false };

  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 10000);
    const r = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload), signal: ctrl.signal });
    clearTimeout(t);
    if (!r.ok) return ["error", `HTTP ${r.status}`];
    return ["ok", "OK"];
  } catch (e: any) {
    return ["error", `${e?.message || e}`];
  }
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
  } else if (getEnv("WEB_APP_DEV") && payload.user_id) {
    userId = Number(payload.user_id);
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "models_ping_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }
  if (!(await isWhitelisted(supabase, userId))) {return json({ ok: false, error: "Нет доступа" }, 401);
  }
  await ensureUser(supabase, userId);
  const userRow = await getUser(supabase, userId);

  let provider = payload.provider || "openrouter";
  if (!["openrouter", "gemini", "venice"].includes(provider)) provider = "openrouter";

  const dbKeys = buildUserProviderKeys(userRow);
  const key = await resolveEffectiveApiKey(supabase, userRow, provider);
  if (!key) return json({ ok: false, error: "Укажи API-ключ" }, 400);

  let models: any[] = [];
  try {
    const u = provider === "openrouter" ? API_ENDPOINTS.openrouter_models : provider === "gemini" ? API_ENDPOINTS.gemini_models : API_ENDPOINTS.venice_models;
    const h: Record<string, string> = provider === "gemini" ? { "x-goog-api-key": key } : { Authorization: `Bearer ${key}` };
    const r = await fetch(u, { headers: h });
    const data = await r.json();
    const raw = data.data || data.models || [];
    for (const m of raw) {
      const nm = normalizeProviderModel(provider, m);
      if (!nm) continue;
      if (provider === "openrouter" && !nm.is_free) continue;
      models.push({ id: nm.id });
    }
  } catch (e: any) {
    return json({ ok: false, error: `Ошибка получения списка: ${e?.message || e}` }, 502);
  }

  const results: any[] = [];
  for (const m of models) {
    const mid = m.id;
    const pingId = modelIdForProvider(provider, mid);
    const [status, info] = await pingOne(provider, pingId, key, userRow?.system_prompt || "");
    results.push({ model_id: mid, status, info });
  }
  const working = results.filter((r) => r.status === "ok").map((r) => r.model_id);
  const failed = results.filter((r) => r.status !== "ok").map((r) => r.model_id);
  await auditLog(supabase, userId, "models_ping", true, `${provider}:${working.length}/${results.length}`);
  const resp = json({
    ok: true,
    provider,
    pinged_at: Math.floor(Date.now() / 1000),
    total: results.length,
    working: working.length,
    failed: failed.length,
    results});return resp;
});

