// Edge Function: админ-панель (аналог api_admin_*). Единый endpoint с полем action.
import { verifyInitData, extractUser, getEnv, getSupabase, isBlacklisted, ensureUser, getUser, auditLog, checkRateLimit, corsPreflight, withCORS } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");
const ADMIN_ID = Number(getEnv("ADMIN_ID") || 0);

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }));
}

function requireFreshAuth(initData: string): boolean {
  const params = new URLSearchParams(initData);
  const authDate = params.get("auth_date");
  if (!authDate) return false;
  const ts = Number(authDate);
  if (!Number.isFinite(ts)) return false;
  return Date.now() / 1000 - ts < 300;
}

async function requireAdmin(supabase: any, payload: any, freshRequired = false): Promise<[number | null, string | null]> {
  const initData = payload.init_data || "";
  const user = extractUser(initData);
  let userId: number | null = null;
  if (BOT_TOKEN && initData && user) {
    if (!(await verifyInitData(initData, BOT_TOKEN))) return [null, "Невалидные данные Telegram"];
    userId = user.id;
  }
  if (userId == null) return [null, "Не удалось определить пользователя"];
  if (freshRequired && !requireFreshAuth(initData)) return [null, "Требуется повторная авторизация"];
  if (userId !== ADMIN_ID) return [null, "Только для администратора"];
  return [userId, null];
}

async function request2FA(supabase: any, adminId: number, action: string): Promise<boolean> {
  const code = String(Math.floor(100000 + Math.random() * 900000));
  const expires = Date.now() + 300000; // 5 минут
  await supabase.from("site_settings").upsert(
    { key: `2fa_${adminId}`, value: JSON.stringify({ code, expires, action }), updated_at: Math.floor(Date.now() / 1000) },
    { onConflict: "key" }
  );
  await auditLog(supabase, adminId, "admin_2fa_request", true, action);

  if (BOT_TOKEN) {
    try {
      await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: adminId,
          text: `🔐 <b>Подтверждение действия в админ-панели</b>\n\nДействие: <code>${action}</code>\nКод подтверждения: <code>${code}</code>\n\nСрок действия кода — 5 минут. Никому не передавайте этот код.`,
          parse_mode: "HTML",
        }),
      });
    } catch (e) {
      console.error("[admin 2fa] Failed to send Telegram message:", e);
    }
  }
  return true;
}

async function verify2FA(supabase: any, adminId: number, payload: any): Promise<boolean> {
  const code = String(payload.confirm || payload.code || "").trim();
  if (!code) return false;
  const { data } = await supabase.from("site_settings").select("value").eq("key", `2fa_${adminId}`).maybeSingle();
  if (!data || !data.value) return false;
  try {
    const stored = JSON.parse(data.value);
    if (!stored || stored.expires < Date.now()) {
      await supabase.from("site_settings").delete().eq("key", `2fa_${adminId}`);
      return false;
    }
    if (stored.code !== code) return false;
    // Одноразовое использование: сразу удаляем запись
    await supabase.from("site_settings").delete().eq("key", `2fa_${adminId}`);
    return true;
  } catch {
    return false;
  }
}

Deno.serve(async (req: Request) => {
  try {
    const pre = corsPreflight(req);
    if (pre) return pre;
    if (req.method !== "POST") return json({ ok: false, error: "Метод не поддерживается" }, 405);
    let payload: any;
    try { payload = await req.json(); } catch { payload = {}; }

    const supabase = getSupabase(true);
    const action = (payload.action || "").trim().toLowerCase();
    const subAction = (payload.sub_action || payload.act || "").trim().toLowerCase();
    const isDestructive = ["reset", "reset_all"].includes(action) || (action === "user" && ["reset", "clear"].includes(subAction));
    const [adminId, err] = await requireAdmin(supabase, payload, isDestructive);
    if (err) return json({ ok: false, error: err }, 401);

    if (!(await checkRateLimit(supabase, adminId!))) {
      await auditLog(supabase, adminId, "admin_rate_limited", false, action);
      return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
    }

    if (action === "request_2fa") {
      const neededFor = String(payload.for_action || "").trim() || "admin_action";
      await request2FA(supabase, adminId!, neededFor);
      return json({ ok: true, message: "Код подтверждения отправлен в Telegram боте" });
    }

    if (isDestructive && !(await verify2FA(supabase, adminId!, payload))) {
      await auditLog(supabase, adminId, "admin_2fa_fail", false, action);
      return json({ ok: false, error: "Требуется 2FA подтверждение", need_2fa: true }, 403);
    }

    const now = Math.floor(Date.now() / 1000);
    await auditLog(supabase, adminId!, "admin_" + action, true);

    if (action === "summary") {
      const { count: usersTotal } = await supabase.from("users").select("*", { count: "exact", head: true });
      const { data: bl } = await supabase.from("blacklist").select("user_id");
      const { count: msgTotal } = await supabase.from("messages").select("*", { count: "exact", head: true });
      const { data: stats } = await supabase.from("api_stats").select("tokens_used");
      const tokensTotal = (stats || []).reduce((s: number, r: any) => s + (r.tokens_used || 0), 0);
      const s24 = await supabase.from("api_stats").select("user_id").gte("timestamp", now - 86400);
      const s7 = await supabase.from("api_stats").select("user_id").gte("timestamp", now - 7 * 86400);
      const { data: blSetting } = await supabase.from("site_settings").select("value").eq("key", "blacklist_enabled").maybeSingle();
      return json({ ok: true, users_total: usersTotal || 0, blacklisted: (bl || []).length, messages_total: msgTotal || 0, tokens_total: tokensTotal, stats_24h: (s24.data || []).length, stats_7d: (s7.data || []).length, admin_id: ADMIN_ID, blacklist_enabled: blSetting?.value !== "false" });
    }

    if (action === "users") {
      const { data: users } = await supabase.from("users").select("*").order("user_id");
      const result = [];
      for (const u of users || []) {
        const { count: mc } = await supabase.from("messages").select("*", { count: "exact", head: true }).eq("user_id", u.user_id);
        const { data: st } = await supabase.from("api_stats").select("tokens_used").eq("user_id", u.user_id);
        const tokens = (st || []).reduce((s: number, r: any) => s + (r.tokens_used || 0), 0);
        const keys: any = {};
        for (const p of ["openrouter", "gemini", "venice"]) {
          const col = "api_key_" + p;
          keys[p] = { has: !!u[col] };
        }
        result.push({
          user_id: u.user_id, is_admin: u.user_id === ADMIN_ID, provider: u.api_key_provider || "openrouter",
          model: u.selected_model || "", context_limit: u.context_limit, message_count: mc || 0, tokens_total: tokens, keys});
      }
      return json({ ok: true, users: result });
    }

    if (action === "blacklist") {
      const sub = (payload.sub_action || payload.act || "").trim().toLowerCase();
      if (sub === "toggle") {
        const enabled = payload.enabled ? "true" : "false";
        await supabase.from("site_settings").upsert({ key: "blacklist_enabled", value: enabled, updated_at: now }, { onConflict: "key" });
        return json({ ok: true, blacklist_enabled: enabled === "true" });
      }
      if (sub === "setting") {
        const { data: cur } = await supabase.from("site_settings").select("value").eq("key", "blacklist_enabled").maybeSingle();
        return json({ ok: true, blacklist_enabled: (cur?.value !== "false") });
      }
      const sub2 = (payload.sub_action || payload.act || "").trim().toLowerCase();
      if (sub2 === "add") {
        const target = Number(payload.user_id);
        if (isNaN(target)) return json({ ok: false, error: "user_id должен быть числом" }, 400);
        let blockType = (payload.block_type || "permanent").toLowerCase();
        if (!["permanent", "temporary"].includes(blockType)) blockType = "permanent";
        let expires: number | null = null;
        if (blockType === "temporary" && payload.days) {
          const d = Number(payload.days);
          if (!isNaN(d)) expires = now + d * 86400;
        }
        await supabase.from("blacklist").upsert({ user_id: target, block_type: blockType, block_expires_at: expires, blocked_at: now }, { onConflict: "user_id" });
        await ensureUser(supabase, target);
        if (payload.block_reason) await supabase.from("blacklist").update({ block_reason: String(payload.block_reason) }).eq("user_id", target);
      } else if (sub2 === "remove") {
        const target = Number(payload.user_id);
        if (isNaN(target)) return json({ ok: false, error: "user_id должен быть числом" }, 400);
        if (target === ADMIN_ID) return json({ ok: false, error: "Нельзя удалить себя" }, 400);
        await supabase.from("blacklist").delete().eq("user_id", target);
      } else if (sub2 === "block_reason") {
        const target = Number(payload.user_id);
        if (isNaN(target)) return json({ ok: false, error: "user_id должен быть числом" }, 400);
        await supabase.from("blacklist").update({ block_reason: String(payload.block_reason || "") }).eq("user_id", target);
      } else if (sub2 === "add_days") {
        const target = Number(payload.user_id);
        if (isNaN(target)) return json({ ok: false, error: "user_id должен быть числом" }, 400);
        const days = Number(payload.days);
        if (isNaN(days) || days <= 0) return json({ ok: false, error: "days должен быть положительным числом" }, 400);
        const { data: cur } = await supabase.from("blacklist").select("block_expires_at").eq("user_id", target).single();
        let base = cur && cur.block_expires_at ? Number(cur.block_expires_at) : now;
        const newExpires = base + days * 86400;
        await supabase.from("blacklist").update({ block_expires_at: newExpires }).eq("user_id", target);
      }
      const { data: bl } = await supabase.from("blacklist").select("user_id, block_reason, block_type, block_expires_at, blocked_at").order("blocked_at", { ascending: true });
      return json({ ok: true, blacklist: bl || [] });
    }

    if (action === "user") {
      const sub = (payload.sub_action || payload.act || "").trim().toLowerCase();
      const target = Number(payload.user_id);
      if (isNaN(target)) return json({ ok: false, error: "user_id must be number" }, 400);
      if (sub === "clear") {
        await supabase.from("messages").delete().eq("user_id", target);
        return json({ ok: true, message: "История пользователя очищена." });
      }
      if (sub === "reset") {
        await supabase.from("messages").delete().eq("user_id", target);
        await supabase.from("api_stats").delete().eq("user_id", target);
        await supabase.from("user_models").delete().eq("user_id", target);
        await supabase.from("dialogs").delete().eq("user_id", target);
        await supabase.from("users").delete().eq("user_id", target);
        return json({ ok: true, message: "Пользователь сброшен." });
      }
      return json({ ok: false, error: "Неизвестное действие" }, 400);
    }

    if (action === "reset_all") {
      await supabase.from("messages").delete().neq("user_id", 0);
      await supabase.from("api_stats").delete().neq("user_id", 0);
      await supabase.from("user_models").delete().neq("user_id", 0);
      await supabase.from("dialogs").delete().neq("user_id", 0);
      await supabase.from("users").delete().neq("user_id", 0);
      return json({ ok: true, message: "Все пользователи сброшены." });
    }

    return json({ ok: false, error: "Неизвестное действие" }, 400);
  } catch (e: any) {
    console.error("[admin error]", e);
    return json({ ok: false, error: "Внутренняя ошибка сервера" }, 500);
  }
});
