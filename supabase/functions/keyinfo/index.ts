// Edge Function: статус ключей провайдеров (аналог api_keyinfo).
import { verifyInitData, extractUser, getEnv, getSupabase, isBlacklisted, ensureUser, getUser, auditLog, checkRateLimit, corsPreflight, withCORS, resolveEffectiveApiKey } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }));
}

function maskKey(key: string): string {
  if (!key) return "";
  if (key.length <= 8) return "•".repeat(key.length);
  return key.slice(0, 4) + "•".repeat(Math.min(12, key.length - 8)) + key.slice(-4);
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
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);
  const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "keyinfo_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }
  if (await isBlacklisted(supabase, userId)) { return json({ ok: false, error: "Нет доступа" }, 401); }
  await ensureUser(supabase, userId);
  const userRow = await getUser(supabase, userId);

  const provider = userRow?.api_key_provider || "openrouter";
  const mode = userRow?.key_mode || "manual";
  const keys: any = {};
  for (const p of ["openrouter", "openai", "gemini", "groq", "huggingface", "venice"]) {
    let raw = "";
    if (mode === "auto" && (p === "openrouter" || p === "gemini")) {
      const autoKey = await resolveEffectiveApiKey(supabase, userRow, p);
      raw = autoKey;
      keys[p] = { has: !!autoKey, masked: autoKey ? "••••••••" : "", auto: true };
    } else {
      raw = userRow?.["api_key_" + p] || "";
      if (!raw && p === provider) raw = userRow?.api_key || "";
      if (raw && /^[•]+$/.test(raw)) raw = "";
      keys[p] = { has: !!raw, masked: raw ? maskKey(raw) : "", auto: false };
    }
  }
  await auditLog(supabase, userId, "keyinfo_view", true);
  return json({ ok: true, provider, key_mode: mode, keys });
});





