// Edge Function: очистка истории (аналог api_chat_clear).
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
  } else if (getEnv("WEB_APP_DEV") && payload.user_id) {
    userId = Number(payload.user_id);
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);

  const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "chat_clear_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }
  if (await isBlacklisted(supabase, userId)) {
    await auditLog(supabase, userId, "chat_clear_blacklist_fail", false);
    return json({ ok: false, error: "Нет доступа" }, 401);
  }
  await ensureUser(supabase, userId);
  await supabase.from("messages").delete().eq("user_id", userId);
  await auditLog(supabase, userId, "chat_clear", true);
  return json({ ok: true, cleared: true });
});





