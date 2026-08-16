// Edge Function: dialogs (CRUD for dialogs stored in Supabase Postgres).
import { verifyInitData, extractUser, getEnv, getSupabase, isWhitelisted, ensureUser, auditLog, checkRateLimit, corsPreflight, withCORS } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");
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
      
      const ok = await verifyInitData(initData, BOT_TOKEN);
      
      if (!ok) return json({ ok: false, error: "Невалидные данные Telegram", step: "verifyInitData" }, 401);
      userId = user.id;
    } else if (getEnv("WEB_APP_DEV") && payload.user_id) {
      userId = Number(payload.user_id);
    }
    if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя", step: "extractUser" }, 401);const supabase = getSupabase(true);
    
    if (ADMIN_ID && String(userId) === String(ADMIN_ID)) {
      
    } else if (!(await isWhitelisted(supabase, userId))) {
      
      return json({ ok: false, error: "Нет доступа", step: "isWhitelisted" }, 401);
    }
    
    await ensureUser(supabase, userId);

    if (!(await checkRateLimit(supabase, userId))) {
      await auditLog(supabase, userId, "dialogs_rate_limited", false);
      return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
    }

    const action = String(payload.action || "").trim();

    if (action === "list") {
      const { data, error } = await supabase
        .from("dialogs")
        .select("*")
        .eq("user_id", userId)
        .order("updated_at", { ascending: false });
      if (error) return json({ ok: false, error: error.message }, 500);
      await auditLog(supabase, userId, "dialogs_list", true);
      return json({ ok: true, dialogs: data || [] });
    }

    if (action === "create") {
      const id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
      const now = Date.now();
      const name = payload.name || `Диалог от ${new Date().toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
      const row = {
        id,
        user_id: userId,
        name,
        messages: payload.messages || [],
        model: payload.model || "",
        created_at: now,
        updated_at: now};
      const { data, error } = await supabase.from("dialogs").insert(row).select("*").single();
      if (error) return json({ ok: false, error: error.message }, 500);
      await auditLog(supabase, userId, "dialogs_create", true);
      return json({ ok: true, dialog: data });
    }

    if (action === "update") {
      const id = String(payload.id || "").trim();
      if (!id) return json({ ok: false, error: "id обязателен" }, 400);
      const updates: any = { updated_at: Date.now() };
      if (payload.name !== undefined) updates.name = String(payload.name).trim() || updates.name;
      if (payload.messages !== undefined) updates.messages = payload.messages;
      if (payload.model !== undefined) updates.model = String(payload.model).trim();
      const { data, error } = await supabase.from("dialogs").update(updates).eq("id", id).eq("user_id", userId).select("*").single();
      if (error) return json({ ok: false, error: error.message }, 500);
      await auditLog(supabase, userId, "dialogs_update", true);
      return json({ ok: true, dialog: data });
    }

    if (action === "delete") {
      const id = String(payload.id || "").trim();
      if (!id) return json({ ok: false, error: "id обязателен" }, 400);
      const { error } = await supabase.from("dialogs").delete().eq("id", id).eq("user_id", userId);
      if (error) return json({ ok: false, error: error.message }, 500);
      await auditLog(supabase, userId, "dialogs_delete", true);
      return json({ ok: true, deleted: true });
    }

    return json({ ok: false, error: "Неизвестное действие" }, 400);
  } catch (e: any) {
    return json({ ok: false, crash: String(e?.message || e), stack: String(e?.stack || "").substring(0, 800) }, 500);
  }
});
