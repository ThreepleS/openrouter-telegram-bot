// Edge Function: список моделей провайдера (аналог api_models).
import { verifyInitData, extractUser, getEnv, getSupabase, API_ENDPOINTS, isWhitelisted, ensureUser, getUser, buildUserProviderKeys, getProviderApiKey, resolveEffectiveApiKey, normalizeProviderModel, isOpenrouterFreeModel, providerLabel, auditLog, checkRateLimit, corsPreflight, withCORS } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }));
}

async function fetchProviderModels(provider: string, key: string, showFreeOnly: boolean): Promise<[any[], string | null]> {
  if (provider === "gemini") {
    const models: any[] = [];
    try {
      const u = `${API_ENDPOINTS.gemini_models}?pageSize=1000`;
      const r = await fetch(u, { headers: { "x-goog-api-key": key } });
      if (!r.ok) return [[], `Ошибка API Gemini (${r.status})`];
      const data = await r.json();
      const raw = data.models || [];
      const base: any[] = [];
      for (const m of raw) {
        const id = m.baseModelId || m.id || m.name || "";
        if (!id) continue;
        const methods = m.supportedGenerationMethods || m.supported_generation_methods || [];
        const acts = m.supportedActions || m.supported_actions || [];
        if (!methods.includes("generateContent") && !acts.includes("generateContent")) {
          if (/embedding|^aqa|text-embedding/.test(id)) continue;
        }
        base.push({ id, name: id });
      }
      const BATCH = 8;
      for (let i = 0; i < base.length; i += BATCH) {
        const chunk = base.slice(i, i + BATCH);
        const detailed = await Promise.all(chunk.map(async (b) => {
          try {
            const clean = b.id.replace(/^models\//, "");
            const dr = await fetch(`${API_ENDPOINTS.gemini_models}/${clean}`, { headers: { "x-goog-api-key": key } });
            const detail = dr.ok ? await dr.json() : null;
            return normalizeProviderModel("gemini", Object.assign({}, b, { _detail: detail }));
          } catch {
            return normalizeProviderModel("gemini", b);
          }
        }));
        models.push(...detailed.filter(Boolean));
      }
    } catch (e: any) {
      if (models.length) return [models, null];
      return [[], `Ошибка Gemini: ${e?.message || e}`];
    }
    models.sort((a, b) => a.id.localeCompare(b.id));
    return [models, null];
  }

  let url = "";
  const headers: Record<string, string> = {};
  if (provider === "openrouter") {
    url = API_ENDPOINTS.openrouter_models;
    headers.Authorization = `Bearer ${key}`;
    headers["HTTP-Referer"] = "https://t.me/openrouter_bot";
    headers["X-Title"] = "OpenRouter Telegram Bot";
  } else if (provider === "openai") { url = API_ENDPOINTS.openai_models; headers.Authorization = `Bearer ${key}`; }
  else if (provider === "groq") { url = API_ENDPOINTS.groq_models; headers.Authorization = `Bearer ${key}`; }
  else if (provider === "huggingface") { url = API_ENDPOINTS.huggingface_models; headers.Authorization = `Bearer ${key}`; }
  else if (provider === "venice") {
    const types = ["text", "image", "code", "embedding", "upscale", "video"];
    const all: any[] = [];
    for (const t of types) {
      try {
        const r = await fetch(API_ENDPOINTS.venice_models + "?type=" + t, { headers: { Authorization: `Bearer ${key}` } });
        if (!r.ok) continue;
        const d = await r.json();
        const arr = d.data || [];
        for (const m of arr) all.push(m);
      } catch { /* тип недоступен — пропускаем */ }
    }
    const normalized: any[] = [];
    for (const m of all) {
      const nm = normalizeProviderModel("venice", m);
      if (nm) normalized.push(nm);
    }
    normalized.sort((a, b) => a.id.localeCompare(b.id));
    return [normalized, null];
  } else return [[], "Неизвестный провайдер"];

  try {
    const r = await fetch(url, { headers });
    if (!r.ok) return [[], `Ошибка API ${providerLabel(provider)} (${r.status})`];
    const data = await r.json();
    const raw = data.data || [];
    const normalized: any[] = [];
    for (const m of raw) {
      const model = normalizeProviderModel(provider, m);
      if (!model) continue;
      if (showFreeOnly && provider === "openrouter" && !model.is_free) continue;
      normalized.push(model);
    }
    normalized.sort((a, b) => a.id.localeCompare(b.id));
    return [normalized, null];
  } catch (e: any) {
    return [[], `Ошибка ${providerLabel(provider)}: ${e?.message || e}`];
  }
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
    if (!(await verifyInitData(initData, BOT_TOKEN))) return json({ ok: false, error: "Невалидные данные Telegram" }, 401);
    userId = user.id;
  } else if (getEnv("WEB_APP_DEV") && payload.user_id) {
    userId = Number(payload.user_id);
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "models_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }
  if (!(await isWhitelisted(supabase, userId))) {return json({ ok: false, error: "Нет доступа" }, 401);
  }
  await ensureUser(supabase, userId);
  const userRow = await getUser(supabase, userId);

  let provider = payload.provider || userRow?.api_key_provider || "openrouter";
  if (!["openrouter", "paid", "gemini", "venice", "openai", "groq", "huggingface"].includes(provider)) {
    provider = userRow?.api_key_provider || "openrouter";
  }

  const dbKeys = buildUserProviderKeys(userRow);
  const key = await resolveEffectiveApiKey(supabase, userRow, provider === "paid" ? "openrouter" : provider);
  if (!key) return json({ ok: false, error: `Укажи API-ключ ${providerLabel(provider)} в настройках` }, 400);

  if (provider === "paid") {
    const [models, err] = await fetchProviderModels("openrouter", key, false);
    if (err) return json({ ok: false, error: err }, 502);
    const paid = models.filter((m) => !m.is_free);
    await auditLog(supabase, userId, "models_paid", true);
    return json({ ok: true, provider: "paid", category: "paid", models: paid });
  }

  const showFreeOnly = provider === "openrouter";
  const [models, err] = await fetchProviderModels(provider, key, showFreeOnly);
  if (err) return json({ ok: false, error: err }, 502);
  const category = (provider === "openrouter" || provider === "gemini" || provider === "venice") ? "free" : "all";
  await auditLog(supabase, userId, "models_list", true);
  return json({ ok: true, provider, category, models });
});
