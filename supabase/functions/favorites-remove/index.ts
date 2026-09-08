// Edge Function: удалить модель из избранного (аналог api_favorite_remove).
import { verifyInitData, extractUser, getEnv, getSupabase, isBlacklisted, ensureUser, auditLog, checkRateLimit, corsPreflight, withCORS } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");

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
    if (!(await verifyInitData(initData, BOT_TOKEN))) return json({ ok: false, error: "Невалидные данные Telegram" }, 401);
    userId = user.id;
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);
  const modelId = (payload.model_id || "").trim();
  if (!modelId) return json({ ok: false, error: "Не указан model_id" }, 400);

  const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "favorites_remove_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }
  if (await isBlacklisted(supabase, userId)) {return json({ ok: false, error: "Нет доступа" }, 401);
  }
  await ensureUser(supabase, userId);

  const { count } = await supabase.from("user_models").delete().eq("user_id", userId).eq("model_id", modelId);
  await auditLog(supabase, userId, "favorites_remove", true, modelId);
  return json({ ok: true, removed: count ?? 0, model_id: modelId });
});




