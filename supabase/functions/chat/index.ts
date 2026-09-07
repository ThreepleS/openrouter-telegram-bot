// Edge Function: чат (аналог api_chat + stream_ai_api).
// Настоящий server-side streaming: ReadableStream отдаёт ndjson-события
// (start/delta/result) по мере поступления токенов от провайдера.

import { verifyInitData, extractUser, getEnv, getSupabase, API_ENDPOINTS, isBlacklisted, ensureUser, getUser, buildUserProviderKeys, detectProvider, normalizeModelId, getProviderApiKey, resolveEffectiveApiKey, buildOpenAIMessages, buildGeminiContents, extractOpenAIContent, extractGeminiContent, extractUsage, auditLog, checkRateLimit, encryptField, decryptField, corsPreflight, withCORS, getOrCreateGeminiCache, providerLabel } from "../_shared/shared.ts";

const BOT_TOKEN = getEnv("BOT_TOKEN");

function json(payload: any, status = 200) {
  return withCORS(new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" }}));
}

function historyToMessages(history: any[]): any[] {
  const messages: any[] = [];
  for (const m of history || []) {
    const item: any = { role: m.role || "user", content: m.content || "" };
    const img = m.image_url || m.image;
    if (img && typeof img === "string" && img.startsWith("data:")) {
      const comma = img.indexOf(",");
      if (comma >= 0) {
        item.image_bytes = img.slice(comma + 1);
        const mimeMatch = img.match(/^data:([^;]+);/);
        if (mimeMatch) item.image_mime = mimeMatch[1];
      }
    }
    messages.push(item);
  }
  return messages;
}

function getProviderHeaders(provider: string, key: string): Record<string, string> {
  const safeKey = String(key || "");
  if (!safeKey) return { "Content-Type": "application/json" };
  if (provider === "gemini") {
    return { "Content-Type": "application/json", "x-goog-api-key": safeKey };
  }
  const h: Record<string, string> = { "Authorization": `Bearer ${safeKey}`, "Content-Type": "application/json" };
  if (provider === "openrouter") {
    h["HTTP-Referer"] = "https://t.me/openrouter_bot";
    h["X-Title"] = "OpenRouter Telegram Bot";
  }
  return h;
}

function toHeaders(provider: string, key: string): Headers {
  const h = getProviderHeaders(provider, key);
  const out = new Headers();
  for (const [k, v] of Object.entries(h)) {
    out.set(k, String(v));
  }
  return out;
}

function getProviderUrl(provider: string, normalizedModel: string): string {
  if (provider === "gemini") {
    return API_ENDPOINTS.gemini_chat.replace("{model}", normalizedModel).replace(":generateContent", ":streamGenerateContent") + "?alt=sse";
  }
  if (provider === "openai") return API_ENDPOINTS.openai_chat;
  if (provider === "groq") return API_ENDPOINTS.groq_chat;
  if (provider === "huggingface") return "https://router.huggingface.co/v1/chat/completions";
  if (provider === "venice") return API_ENDPOINTS.venice_chat;
  return API_ENDPOINTS.openrouter_chat;
}

function buildPayload(provider: string, normalizedModel: string, systemPrompt: string, messages: any[]): any {
  if (provider === "gemini") {
    return {
      contents: buildGeminiContents(messages, provider, normalizedModel),
      system_instruction: { parts: [{ text: systemPrompt }] }};
  }
  const base = {
    model: normalizedModel,
    messages: buildOpenAIMessages(systemPrompt, messages, provider, normalizedModel),
    stream: provider !== "gemini"
  };
  if (["openrouter", "openai", "groq", "huggingface", "venice"].includes(provider)) {
    return { ...base, tools: [], tool_choice: "none" };
  }
  return base;
}

const STREAM_HEADERS = {
  "Content-Type": "application/x-ndjson; charset=utf-8",
  "Cache-Control": "no-cache, no-transform",
  "X-Accel-Buffering": "no"};

Deno.serve(async (req: Request) => {
 try {
  const pre = corsPreflight(req);
  if (pre) return pre;
  if (req.method !== "POST") return withCORS(new Response(JSON.stringify({ ok: false, error: "Метод не поддерживается" }), { status: 405, headers: { "Content-Type": "application/json; charset=utf-8" } }));

  let payload: any;
  try { payload = await req.json(); } catch { return json({ ok: false, error: "Неверный JSON" }, 400); }

  const initData = payload.init_data || "";
  const user = extractUser(initData);
  let userId: number | null = null;
  if (BOT_TOKEN && initData && user) {
    const ok = await verifyInitData(initData, BOT_TOKEN);
    await auditLog(getSupabase(true), user.id, "chat_verify", ok);
    if (!ok) return json({ ok: false, error: "Невалидные данные Telegram" }, 401);
    userId = user.id;
  } else if (getEnv("WEB_APP_DEV") && payload.user_id) {
    userId = Number(payload.user_id);
  }
  if (userId == null) return json({ ok: false, error: "Не удалось определить пользователя" }, 401);

  if (payload.compress) {
    const supabase = getSupabase(true);
    const userRow = await getUser(supabase, userId);
    if (!userRow) return json({ ok: false, error: "Пользователь не найден" }, 404);

    const dialogId = payload.dialog_id ? String(payload.dialog_id).trim() : null;
    let dialogRow: any = null;

    if (dialogId) {
      const { data: d } = await supabase
        .from("dialogs")
        .select("*")
        .eq("id", dialogId)
        .eq("user_id", userId)
        .maybeSingle();
      dialogRow = d;
    }

    if (!dialogRow) {
      const { data: latest } = await supabase
        .from("dialogs")
        .select("*")
        .eq("user_id", userId)
        .order("updated_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      dialogRow = latest;
    }

    let history: any[] = [];
    if (dialogRow && Array.isArray(dialogRow.messages) && dialogRow.messages.length > 0) {
      history = await Promise.all(dialogRow.messages.map(async (m: any) => {
        const decryptedContent = await decryptField(m.content || "");
        return {
          ...m,
          content: decryptedContent !== null ? decryptedContent : (m.content || "")
        };
      }));
    } else {
      const { data: hist } = await supabase
        .from("messages")
        .select("role, content, image_url")
        .eq("user_id", userId)
        .order("id", { ascending: true });

      const decrypted = await Promise.all((hist || []).map(async (m: any) => ({
        ...m,
        content: await decryptField(m.content || ""),
      })));
      history = historyToMessages(decrypted);
    }

    if (history.length < 5) {
      return json({ ok: true, summary: "История слишком коротка для сжатия (менее 5 сообщений)" });
    }

    // Split: keep last 4 messages, summarize the rest
    const toSummarize = history.slice(0, -4);
    const recent = history.slice(-4);

    const summaryPrompt = "Сделай краткое структурированное резюме диалога: ключевые факты, контекст, договорённости, имена, технические детали. Максимум 300 слов на русском языке.";
    const summaryHistory = [
      ...toSummarize.map((m: any) => ({ role: m.role || "user", content: m.content || "" })),
      { role: "user", content: summaryPrompt }
    ];

    const model = userRow.selected_model || "google/gemini-2.5-flash";
    const prov = detectProvider(model);
    const normModel = normalizeModelId(prov, model);
    const providerKey = await resolveEffectiveApiKey(supabase, userRow, prov);
    if (!providerKey || !String(providerKey).trim()) {
      return json({ ok: false, error: `Не указан API-ключ для генерации резюме (${prov})` }, 400);
    }

    let summaryUrl: string;
    let summaryBody: any;
    if (prov === "gemini") {
      summaryUrl = `${API_ENDPOINTS.gemini_chat.replace("{model}", normModel)}?key=${providerKey}`;
      summaryBody = {
        contents: buildGeminiContents(summaryHistory, prov, normModel),
        system_instruction: { parts: [{ text: summaryPrompt }] }
      };
    } else {
      summaryUrl = getProviderUrl(prov, normModel);
      summaryBody = {
        model: normModel,
        messages: buildOpenAIMessages(summaryPrompt, summaryHistory, prov, normModel),
        stream: false,
        tools: [],
        tool_choice: "none"
      };
    }
    const summaryHeaders = toHeaders(prov, providerKey);

    const summaryResp = await fetch(summaryUrl, {
      method: "POST",
      headers: summaryHeaders,
      body: JSON.stringify(summaryBody)
    });

    if (!summaryResp.ok) {
      const err = await summaryResp.text();
      return json({ ok: false, error: "Ошибка генерации резюме: " + err.slice(0, 300) }, 500);
    }

    const summaryData = await summaryResp.json();
    const summaryText = extractGeminiContent(summaryData) || extractOpenAIContent(summaryData) || "";
    if (!summaryText.trim()) {
      return json({ ok: false, error: "Не удалось сформировать текст резюме" }, 500);
    }

    const newHistory = [
      { role: "assistant", content: "📌 Резюме предыдущего контекста:\n" + summaryText.trim() },
      ...recent
    ];

    if (dialogRow) {
      const encryptedDialogMessages = await Promise.all(newHistory.map(async (m: any) => ({
        ...m,
        content: await encryptField(m.content || ""),
        stats: m.stats ? await encryptField(typeof m.stats === "object" ? JSON.stringify(m.stats) : String(m.stats)) : null
      })));

      await supabase.from("dialogs").update({
        messages: encryptedDialogMessages,
        updated_at: Date.now()
      }).eq("id", dialogRow.id).eq("user_id", userId);
    }

    // Also update legacy messages table for compatibility
    await supabase.from("messages").delete().eq("user_id", userId);
    for (const msg of newHistory) {
      const enc = await encryptField(msg.content || "");
      await supabase.from("messages").insert({ user_id: userId, role: msg.role, content: enc });
    }

    return json({ ok: true, summary: "Контекст успешно сжат, старые сообщения заменены резюме" });
  }

  const messageText = (payload.message || "").trim();
  const imageRaw = payload.image || null;
  if (payload.clear) {
    const supabaClear = getSupabase(true);
    await supabaClear.from("messages").delete().eq("user_id", userId);
    await auditLog(supabaClear, userId, "chat_clear", true);
    return json({ ok: true, cleared: true });
  }
  if (!messageText && !imageRaw) return json({ ok: false, error: "Пустое сообщение" }, 400);

  const supabase = getSupabase(true);
  if (!(await checkRateLimit(supabase, userId))) {
    await auditLog(supabase, userId, "chat_rate_limited", false);
    return json({ ok: false, error: "Слишком много запросов. Подождите минуту." }, 429);
  }

  if (await isBlacklisted(supabase, userId)) {
    await auditLog(supabase, userId, "chat_blacklist_fail", false);
    return json({ ok: false, error: "Нет доступа. Запросите доступ у администратора." }, 401);
  }
  
  const userRow = await getUser(supabase, userId);
  if (userRow == null) {
    await auditLog(supabase, userId, "chat_no_key", false);
    return json({ ok: false, error: "Укажи API-ключ в настройках" }, 401);
  }

  const dbKeys = buildUserProviderKeys(userRow);
  const providersToCheck = ["openrouter", "openai", "gemini", "groq", "huggingface", "venice"];
  const resolvedKeys = await Promise.all(providersToCheck.map((p) => resolveEffectiveApiKey(supabase, userRow, p)));
  const hasKey = resolvedKeys.some((k) => k && String(k).trim()) || Object.values(dbKeys).some((k: any) => k && String(k).trim());
  if (!hasKey) {
    await auditLog(supabase, userId, "chat_no_key", false);
    return json({ ok: false, error: "Укажи API-ключ в настройках" }, 401);
  }
  if (!userRow.selected_model) {
    await auditLog(supabase, userId, "chat_no_model", false);
    return json({ ok: false, error: "Выбери модель в настройках" }, 401);
  }

  const encryptedMessage = await encryptField(messageText);
  await supabase.from("messages").insert({ user_id: userId, role: "user", content: encryptedMessage, image_url: imageRaw });

  const currentMsg: any = { role: "user", content: messageText };
  if (imageRaw && typeof imageRaw === "string" && imageRaw.startsWith("data:")) {
    const comma = imageRaw.indexOf(",");
    if (comma >= 0) {
      currentMsg.image_bytes = imageRaw.slice(comma + 1);
      const mimeMatch = imageRaw.match(/^data:([^;]+);/);
      if (mimeMatch) currentMsg.image_mime = mimeMatch[1];
    }
  }

  let history: any[] = [];
  if (Array.isArray(payload.history) && payload.history.length > 0) {
    history = historyToMessages(payload.history);
  } else {
    const limit = payload.context_limit_full ? null : (userRow.context_limit || 10);
    const query = supabase
      .from("messages")
      .select("role, content, image_url")
      .eq("user_id", userId)
      .order("id", { ascending: false });
    if (limit) query.limit(limit);
    const { data: hist } = await query;
    const decrypted = await Promise.all((hist || []).reverse().map(async (m: any) => ({
      ...m,
      content: await decryptField(m.content || ""),
    })));
    history = historyToMessages(decrypted);
  }

  history.push(currentMsg);

  const model = userRow.selected_model;
  const provider = detectProvider(model);
  const normalizedModel = normalizeModelId(provider, model);
  const providerKey = await resolveEffectiveApiKey(supabase, userRow, provider);
  if (!providerKey || !String(providerKey).trim()) {
    await auditLog(supabase, userId, "chat_no_key", false);
    return json({ ok: false, error: `Не указан API-ключ для ${providerLabel(provider)}` }, 400);
  }
  
  const url = getProviderUrl(provider, normalizedModel);
  const headers = toHeaders(provider, providerKey);
  const serverHistory = history.length > 0 ? history : [];
  const systemPrompt = (payload.system_prompt || userRow.system_prompt || "").trim();
  let body = buildPayload(provider, normalizedModel, systemPrompt, serverHistory);
  let cacheName: string | null = null;

  // Gemini Prompt Caching
  if (provider === "gemini") {
    const { cacheName: cn, cachedHistory } = await getOrCreateGeminiCache(
      supabase,
      userId,
      normalizedModel,
      systemPrompt,
      serverHistory,
      providerKey
    );
    cacheName = cn;
    if (cacheName) {
      // Use cached content: only send recent history
      body = buildPayload(provider, normalizedModel, systemPrompt, cachedHistory);
      // Remove system_instruction to avoid conflict with cached content
      delete body.system_instruction;
      body.cachedContent = cacheName;
    }
  }

  const statsMode = (userRow.stats_display || "full").toLowerCase();

  console.log("[chat] provider=" + provider + " model=" + normalizedModel + " key_present=" + !!providerKey + " url=" + url + " cache=" + (cacheName || "none"));

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: any) => controller.enqueue(encoder.encode(JSON.stringify(obj) + "\n"));
      const finish = () => { try { controller.close(); } catch (_) {} };

      send({ type: "start" });
      let full = "";
      let usage: any = {};

      try {
        const bodyStr = JSON.stringify(body);
        console.log("[chat] fetch body=" + bodyStr.slice(0, 200));
        const resp = await fetch(url, { method: "POST", headers, body: bodyStr });
        if (!resp.ok) {
          const text = await resp.text();
          send({ type: "error", message: `Ошибка API ${provider.toUpperCase()} (${resp.status}): ${text.slice(0, 500)}` });
          return finish();
        }

        if (provider === "gemini") {
          const reader = resp.body!.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          let prevText = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let nl: number;
            while ((nl = buf.indexOf("\n")) >= 0) {
              const line = buf.slice(0, nl).trim();
              buf = buf.slice(nl + 1);
              if (!line || !line.startsWith("data:")) continue;
              const data = line.slice(5).trim();
              if (!data || data === "[DONE]") continue;
               try {
                 const obj = JSON.parse(data);
                 const textNow = extractGeminiContent(obj);
                 if (obj.usageMetadata) usage = extractUsage(obj, "gemini");
                 let delta = "";
                 if (textNow.startsWith(prevText)) {
                   delta = textNow.slice(prevText.length);
                   prevText = textNow;
                 } else if (textNow && !prevText) {
                   delta = textNow;
                   prevText = textNow;
                 } else {
                   delta = textNow;
                   prevText = prevText + delta;
                 }
                 if (delta) {
                   full += delta;
                   send({ type: "delta", text: delta });
                 }
               } catch { /* частичный/служебный чанк */ }
            }
          }
        } else {
          const reader = resp.body!.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let nl: number;
            while ((nl = buf.indexOf("\n")) >= 0) {
              const line = buf.slice(0, nl).trim();
              buf = buf.slice(nl + 1);
              if (!line || !line.startsWith("data:")) continue;
              const data = line.slice(5).trim();
              if (data === "[DONE]") break;
               try {
                 const obj = JSON.parse(data);
                 const choices = obj.choices || [];
                 let delta = choices.length ? (choices[0].delta?.content || "") : "";
                 if (obj.usage) usage = obj.usage;
                  if (delta) {
                    full += delta;
                    send({ type: "delta", text: delta });
                  }
               } catch { /* ignore partial */ }
            }
          }
        }
      } catch (e: any) {
        send({ type: "error", message: `Не удалось подключиться к API: ${e?.message || e}` });
        return finish();
      }

      try {
        const encryptedReply = await encryptField(full || "");
        await supabase.from("messages").insert({ user_id: userId, role: "assistant", content: encryptedReply });
        const total = usage.total_tokens || ((usage.prompt_tokens || 0) + (usage.completion_tokens || 0));
        if (total) await supabase.from("api_stats").insert({ user_id: userId, tokens_used: total, timestamp: Math.floor(Date.now() / 1000) });
      } catch (e: any) {
        send({ type: "error", message: `Ошибка сохранения: ${e?.message || e}` });
      }

const pt = usage.prompt_tokens ?? usage.promptTokenCount;
      const ct = usage.completion_tokens ?? usage.candidatesTokenCount;
      const tt = usage.total_tokens ?? usage.totalTokenCount;
      const thinking = usage.thinking_tokens ?? usage.thoughtsTokenCount;
      const cached = usage.cached_tokens ?? usage.cachedContentTokenCount;
      let statsStr = "";
      if (statsMode !== "disabled" && (pt != null || ct != null || tt != null)) {
        if (statsMode === "compact") {
          statsStr = `токенов: ${tt != null ? tt : ((pt || 0) + (ct || 0))}`;
        } else {
          const parts: string[] = [`модель: ${model}`];
          if (pt != null) parts.push(`prompt: ${pt}`);
          if (thinking != null && thinking > 0) parts.push(`thinking: ${thinking}`);
          if (ct != null) parts.push(`completion: ${ct}`);
          if (cached != null && cached > 0) parts.push(`cached: ${cached}`);
          if (tt != null) parts.push(`total: ${tt}`);
          statsStr = parts.join(" | ");
        }
      }
      send({ type: "result", ok: true, reply: full, markdown: full, model, usage, stats: statsStr });
      finish();
    }});

  const chatSupabase = getSupabase(true);return withCORS(new Response(stream, { headers: STREAM_HEADERS }));
 } catch (e: any) {
   const errSupabase = getSupabase(true);return json({ ok: false, crash: String(e?.message || e), stack: String(e?.stack || "").substring(0, 800) }, 500);
 }
});




