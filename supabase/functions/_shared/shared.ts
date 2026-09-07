// РћР±С‰РёР№ РєРѕРґ РґР»СЏ РІСЃРµС… Edge Functions: РїСЂРѕРІРµСЂРєР° initData Telegram, РґРѕСЃС‚СѓРї Рє Р‘Р”,
// СѓС‚РёР»РёС‚С‹ РїСЂРѕРІР°Р№РґРµСЂРѕРІ. РџРѕРІС‚РѕСЂСЏРµС‚ Р»РѕРіРёРєСѓ src/web/auth.py Рё src/ai/providers.py.

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

// --- CORS (С„СЂРѕРЅС‚РµРЅРґ РЅР° GitHub Pages -> *.supabase.co) ---
const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-requested-with",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Max-Age": "86400",
};

// Р’РѕР·РІСЂР°С‰Р°РµС‚ РѕС‚РІРµС‚ РЅР° preflight OPTIONS (РёР»Рё null, РµСЃР»Рё РјРµС‚РѕРґ РЅРµ OPTIONS).
function corsPreflight(req: Request): Response | null {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }
  return null;
}

// Р”РѕРїРёСЃС‹РІР°РµС‚ CORS-Р·Р°РіРѕР»РѕРІРєРё РІ Р»СЋР±РѕР№ РѕС‚РІРµС‚.
function withCORS(res: Response): Response {
  const h = new Headers(res.headers);
  for (const [k, v] of Object.entries(CORS_HEADERS)) h.set(k, v);
  return new Response(res.body, { status: res.status, headers: h });
}
const PROVIDER_LABELS: Record<string, string> = {
  openrouter: "OpenRouter",
  openai: "OpenAI",
  gemini: "Gemini",
  groq: "Groq",
  huggingface: "HuggingFace",
  venice: "Venice AI",
};

interface ApiEndpoints {
  openrouter_chat: string;
  openrouter_models: string;
  openai_chat: string;
  openai_models: string;
  gemini_chat: string;
  gemini_models: string;
  gemini_cached_contents: string;
  groq_chat: string;
  groq_models: string;
  huggingface_models: string;
  venice_chat: string;
  venice_models: string;
}

const API_ENDPOINTS: ApiEndpoints = {
  openrouter_chat: "https://openrouter.ai/api/v1/chat/completions",
  openrouter_models: "https://openrouter.ai/api/v1/models",
  openai_chat: "https://api.openai.com/v1/chat/completions",
  openai_models: "https://api.openai.com/v1/models",
  gemini_chat: "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
  gemini_models: "https://generativelanguage.googleapis.com/v1beta/models",
  gemini_cached_contents: "https://generativelanguage.googleapis.com/v1beta/cachedContents",
  groq_chat: "https://api.groq.com/openai/v1/chat/completions",
  groq_models: "https://api.groq.com/openai/v1/models",
  huggingface_models: "https://router.huggingface.co/api/models",
  venice_chat: "https://api.venice.ai/api/v1/chat/completions",
  venice_models: "https://api.venice.ai/api/v1/models",
};

// --- РђСѓС‚РµРЅС‚РёС„РёРєР°С†РёСЏ Telegram initData ---

// РђСЃРёРЅС…СЂРѕРЅРЅР°СЏ РїСЂРѕРІРµСЂРєР° initData (HMAC-SHA256, РєР»СЋС‡ = HMAC_SHA256("WebAppData", bot_token))
async function verifyInitData(initData: string, botToken: string): Promise<boolean> {
  if (!initData || !botToken) return false;
  const params = new URLSearchParams(initData);
  const hash = params.get("hash");
  if (!hash) return false;
  params.delete("hash");

  const dataCheckString = [...params.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");

  const authDate = params.get("auth_date");
  if (authDate) {
    const ts = Number(authDate);
    if (Number.isFinite(ts) && Date.now() / 1000 - ts > 86400) return false;
  }

  const keyBuf = new TextEncoder().encode("WebAppData");
  const tokenBuf = new TextEncoder().encode(botToken);
  const secretKey = await crypto.subtle.importKey(
    "raw",
    keyBuf,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const secretBytes = new Uint8Array(
    await crypto.subtle.sign("HMAC", secretKey, tokenBuf),
  );

  const secretKey2 = await crypto.subtle.importKey(
    "raw",
    secretBytes,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    secretKey2,
    new TextEncoder().encode(dataCheckString),
  );
  const hex = [...new Uint8Array(sig)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  if (hex.length !== hash.length) return false;
  let diff = 0;
  for (let i = 0; i < hex.length; i++) {
    diff |= hex.charCodeAt(i) ^ hash.charCodeAt(i);
  }
  return diff === 0;
}

function extractUser(initData: string): { id: number } | null {
  const params = new URLSearchParams(initData);
  const raw = params.get("user");
  if (!raw) return null;
  try {
    const u = JSON.parse(raw);
    if (u && u.id) return { id: Number(u.id) };
  } catch {
    /* ignore */
  }
  return null;
}

function getEnv(key: string): string {
  return (Deno.env.get(key) || "").trim();
}

function getSupabase(useServiceRole = true): SupabaseClient {
  const url = getEnv("SUPABASE_URL");
  const key = useServiceRole ? getEnv("SUPABASE_SERVICE_ROLE_KEY") : getEnv("SUPABASE_ANON_KEY");
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

// --- Р Р°Р±РѕС‚Р° СЃ Р‘Р” (Р°РЅР°Р»РѕРі repository.py) ---
async function isBlacklisted(supabase: SupabaseClient, userId: number): Promise<boolean> {
  const adminId = getEnv("ADMIN_ID");
  console.log("[isBlacklisted] userId=" + userId + " adminId=" + adminId + " match=" + (adminId && String(userId) === String(adminId)));
  if (adminId && String(userId) === String(adminId)) return false;
  const { data: setting } = await supabase.from("site_settings").select("value").eq("key", "blacklist_enabled").maybeSingle();
  const enabled = setting?.value !== "false";
  console.log("[isBlacklisted] blacklist_enabled=" + enabled);
  if (!enabled) return false;
  const { data } = await supabase
    .from("blacklist")
    .select("user_id")
    .eq("user_id", userId)
    .maybeSingle();
  console.log("[isBlacklisted] db result=" + (data != null));
  return data != null;
}

async function ensureUser(supabase: SupabaseClient, userId: number): Promise<void> {
  await supabase.from("users").upsert({ user_id: userId }, { onConflict: "user_id" });
}

async function getUser(supabase: SupabaseClient, userId: number): Promise<any> {
  const { data } = await supabase
    .from("users")
    .select("*")
    .eq("user_id", userId)
    .maybeSingle();
  if (!data) return null;
  for (const col of Object.values(PROVIDER_KEY_COLS)) {
    const raw = data[col];
    if (raw && typeof raw === "string" && !/^[вЂў]+$/.test(raw)) {
      data[col] = await decryptApiKey(raw);
    } else if (raw && /^[вЂў]+$/.test(raw)) {
      data[col] = "";
    }
  }
  if (data.api_key && typeof data.api_key === "string" && !/^[вЂў]+$/.test(data.api_key)) {
    data.api_key = await decryptApiKey(data.api_key);
  } else if (data.api_key && /^[вЂў]+$/.test(data.api_key)) {
    data.api_key = "";
  }
  if (data.system_prompt && typeof data.system_prompt === "string") {
    data.system_prompt = await decryptField(data.system_prompt);
  }
  return data;
}

const PROVIDER_KEY_COLS: Record<string, string> = {
  openrouter: "api_key_openrouter",
  openai: "api_key_openai",
  gemini: "api_key_gemini",
  groq: "api_key_groq",
  huggingface: "api_key_huggingface",
  venice: "api_key_venice",
};

function buildUserProviderKeys(user: any): Record<string, string> {
  if (!user) return {};
  return {
    openrouter: user.api_key_openrouter || "",
    openai: user.api_key_openai || "",
    gemini: user.api_key_gemini || "",
    groq: user.api_key_groq || "",
    huggingface: user.api_key_huggingface || "",
    venice: user.api_key_venice || "",
  };
}

function detectProvider(modelId: string): string {
  const lower = (modelId || "").toLowerCase();
  if (lower.startsWith("openai:")) return "openai";
  // Только явный префикс gemini: или models/gemini- означают прямой Google API.
  // ID вида google/gemini-... идут через OpenRouter (возвращаем openrouter).
  if (lower.startsWith("gemini:") || lower.startsWith("models/gemini-")) return "gemini";
  if (lower.startsWith("groq:")) return "groq";
  if (lower.startsWith("hf:")) return "huggingface";
  if (lower.startsWith("venice:")) return "venice";
  if (lower.startsWith("gpt-") || lower.startsWith("o1") || lower.startsWith("o3") || lower.startsWith("chatgpt-")) return "openai";
  return "openrouter";
}

function normalizeModelId(provider: string, modelId: string): string {
  const prefixes: Record<string, string> = {
    openai: "openai:",
    gemini: "gemini:",
    groq: "groq:",
    huggingface: "hf:",
    venice: "venice:",
  };
  const prefix = prefixes[provider];
  let id = modelId || "";
  if (prefix && id.toLowerCase().startsWith(prefix)) id = id.slice(prefix.length);
  if (provider === "gemini" && id.toLowerCase().startsWith("models/")) id = id.slice(7);
  return id;
}

function modelIdForProvider(provider: string, modelId: string): string {
  const prefixes: Record<string, string> = {
    openai: "openai:",
    gemini: "gemini:",
    groq: "groq:",
    huggingface: "hf:",
    venice: "venice:",
  };
  const prefix = prefixes[provider];
  if (prefix && modelId.toLowerCase().startsWith(prefix)) return modelId;
  if (prefix) return `${prefix}${modelId}`;
  return modelId;
}

async function resolveEffectiveApiKey(supabase: SupabaseClient, userRow: any, provider: string): Promise<string> {
  const dbKeys = buildUserProviderKeys(userRow);
  return getProviderApiKey(provider, userRow?.api_key || "", userRow?.api_key_provider || "openrouter", dbKeys);
}

function getProviderApiKey(
  provider: string,
  userApiKey: string,
  userApiKeyProvider: string,
  dbProviderKeys: Record<string, string>,
): string {
  // РљР»СЋС‡Рё СЃС‚СЂРѕРіРѕ РїРµСЂСЃРѕРЅР°Р»СЊРЅС‹Рµ: Р±РµСЂС‘Рј РёР· Р‘Р” РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ, env-РєР»СЋС‡Рё РќР•
  // РёСЃРїРѕР»СЊР·СѓРµРј (РёРЅР°С‡Рµ РєР»СЋС‡ Р°РґРјРёРЅР° РїСЂРёРјРµРЅСЏР»СЃСЏ Р±С‹ РєРѕ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј).
  const dbKey = dbProviderKeys?.[provider] || "";
  if (dbKey) return dbKey;
  if (userApiKey && userApiKeyProvider === provider) return userApiKey;
  return "";
}

function buildOpenAIMessages(systemPrompt: string, messages: any[], provider: string, modelId: string): any[] {
  const converted: any[] = [{ role: "system", content: systemPrompt }];
  for (const m of messages) {
    const content = m.content || "";
    const imageBytes = m.image_bytes || m.image_url;
    const role = m.role === "bot" ? "assistant" : (m.role || "user");
    if (imageBytes) {
      const mime = m.image_mime || "image/jpeg";
      converted.push({
        role,
        content: [
          { type: "text", text: content },
          { type: "image_url", image_url: { url: `data:${mime};base64,${imageBytes}` } },
        ],
      });
    } else if (content) {
      converted.push({ role, content });
    }
  }
  return converted;
}

function modelSupportsVision(provider: string, modelId: string): boolean {
  const lower = modelId.toLowerCase();
  let clean = lower;
  for (const p of ["openrouter:", "openai:", "gemini:", "groq:", "hf:", "venice:", "models/"]) {
    clean = clean.replace(p, "");
  }
  for (const p of ["openai/", "anthropic/", "google/", "meta/", "mistralai/", "qwen/"]) {
    clean = clean.replace(p, "");
  }
  const imageGen = ["flux", "sd-xl", "sd3", "dall-e", "gptimage", "imagen", "anything-v", "kandinsky", "playground", "grok-imagine"];
  if (imageGen.some((p) => lower.includes(p))) return false;
  if (provider === "openrouter" || provider === "openai") {
    const vp = ["gpt-4-vision", "gpt-4o", "gpt-4-turbo", "claude-3", "gemini-1.5", "gemini-2.0", "gemini-flash", "gemini-pro", "gemma-3", "qwen-vl", "qwen2-vl", "pixtral", "mistral-vision"];
    return vp.some((p) => clean.includes(p));
  }
  if (provider === "venice") {
    return ["claude", "gpt", "gemini", "kimi", "llama", "mistral", "qwen", "pixtral", "llava"].some((p) => clean.includes(p));
  }
  if (provider === "gemini") return true;
  if (provider === "groq") return clean.includes("llama-3.2");
  if (provider === "huggingface") {
    return ["llava", "qwen-vl", "qwen2-vl", "bakllava", "cogvlm", "deepseek-vl", "pixtral"].some((p) => clean.includes(p));
  }
  return false;
}

function buildGeminiContents(messages: any[], provider: string, modelId: string): any[] {
  const supportsVision = modelSupportsVision(provider, modelId);
  const contents: any[] = [];
  for (const m of messages) {
    const role = m.role === "assistant" || m.role === "bot" ? "model" : "user";
    const content = m.content || "";
    const imageBytes = m.image_bytes || m.image_url;
    const parts: any[] = [];
    if (imageBytes && supportsVision) {
      if (content) parts.push({ text: content });
      const mime = m.image_mime || "image/jpeg";
      parts.push({ inline_data: { mime_type: mime, data: imageBytes } });
    } else if (imageBytes && !supportsVision) {
      let c = content ? `${content}\n\n[РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ СЂР°РЅРµРµ РѕС‚РїСЂР°РІРёР» РёР·РѕР±СЂР°Р¶РµРЅРёРµ]` : "[РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РѕС‚РїСЂР°РІРёР» РёР·РѕР±СЂР°Р¶РµРЅРёРµ Р±РµР· РїРѕРґРїРёСЃРё]";
      parts.push({ text: c });
    } else if (content) {
      parts.push({ text: content });
    }
    if (parts.length) contents.push({ role, parts });
  }
  return contents;
}

function extractOpenAIContent(data: any): [string | null, string[]] {
  const choices = data.choices || [];
  if (!choices.length) return ["", []];
  const message = choices[0].message || {};
  const content = message.content;
  const images: string[] = [];
  const raw = message.images || [];
  for (const img of raw) {
    if (img && img.image_url && img.image_url.url && img.image_url.url.startsWith("data:image/")) {
      images.push(img.image_url.url.split(",", 2)[1]);
    }
  }
  const text = typeof content === "string" ? content : (content ? String(content) : "");
  return [text, images];
}

function extractGeminiContent(data: any): string {
  const cands = data.candidates || [];
  if (!cands.length) return "";
  const parts = cands[0]?.content?.parts || [];
  const texts: string[] = [];
  for (const p of parts) {
    // РџСЂРѕРїСѓСЃРєР°РµРј "СЂР°Р·РјС‹С€Р»РµРЅРёСЏ" РјРѕРґРµР»Рё (thought: true) вЂ” РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ РѕРЅРё РЅРµ РЅСѓР¶РЅС‹.
    if (p && p.thought) continue;
    if (p && typeof p.text === "string") texts.push(p.text);
    else if (typeof p === "string") texts.push(p);
  }
  return texts.join("\n").trim();
}

function extractUsage(data: any, provider: string): any {
  if (provider === "gemini") {
    const m = data.usageMetadata || {};
    return {
      prompt_tokens: m.promptTokenCount,
      completion_tokens: m.candidatesTokenCount,
      total_tokens: m.totalTokenCount,
      thinking_tokens: m.thoughtsTokenCount,
      cached_tokens: m.cachedContentTokenCount,
    };
  }
  return data.usage || {};
}

function isOpenrouterFreeModel(raw: any): boolean {
  if (raw == null) return false;
  if (typeof raw.id === "string" && raw.id.endsWith(":free")) return true;
  const pricing = raw.pricing;
  if (pricing) {
    const prompt = pricing.prompt;
    const completion = pricing.completion;
    // Handle both string and number pricing
    const promptCost = typeof prompt === "string" ? parseFloat(prompt) : (typeof prompt === "number" ? prompt : NaN);
    const completionCost = typeof completion === "string" ? parseFloat(completion) : (typeof completion === "number" ? completion : NaN);
    if (!isNaN(promptCost) && promptCost === 0 && !isNaN(completionCost) && completionCost === 0) return true;
  }
  return false;
}

function normalizeProviderModel(provider: string, raw: any): any {
  if (!raw) return null;
  if (provider === "openrouter") {
    const id = raw.id;
    if (!id) return null;
    const p = raw.pricing || {};
    const prompt = p.prompt != null ? String(p.prompt) : null;
    const completion = p.completion != null ? String(p.completion) : null;
    const ctx = raw.context_length || null;
    const arch = ((raw.architecture && raw.architecture.input_modalities) || []).join(",");
    const archOut = ((raw.architecture && raw.architecture.output_modalities) || []).join(",");
    return {
      id,
      model_id: id,
      name: raw.name || id,
      display_name: raw.name || id,
      is_free: isOpenrouterFreeModel(raw),
      context: ctx,
      mod_in: arch || "text",
      mod_out: archOut || "text",
      price_prompt: prompt,
      price_completion: completion,
      description: raw.description || "",
      meta: raw.id,
    };
  }
  if (provider === "openai" || provider === "groq" || provider === "huggingface") {
    const id = typeof raw === "string" ? raw : raw.id;
    if (!id) return null;
    const name = (raw.name && raw.name !== id) ? raw.name : id;
    return {
      id,
      model_id: id,
      name,
      display_name: name,
      is_free: false,
      context: raw.context_length || null,
      mod_in: raw.mod_in || "text",
      mod_out: raw.mod_out || "text",
      price_prompt: raw.price_prompt || null,
      price_completion: raw.price_completion || null,
      description: raw.description || "",
      meta: id,
    };
  }
  if (provider === "venice") {
    const rawId = typeof raw === "string" ? raw : raw.id;
    if (!rawId) return null;
    // РџСЂРµС„РёРєСЃ venice: РѕР±СЏР·Р°С‚РµР»РµРЅ, С‡С‚РѕР±С‹ detectProvider/С‡Р°С‚ РїРѕРЅРёРјР°Р»Рё РїСЂСЏРјРѕР№ Venice API
    // Рё РєР°СЂС‚РѕС‡РєР° РїРѕРєР°Р·С‹РІР°Р»Р° РїСЂР°РІРёР»СЊРЅРѕРіРѕ РїСЂРѕРІР°Р№РґРµСЂР° (Р° РЅРµ openrouter/gemini РїРѕ detectProvider).
    const id = rawId.toLowerCase().startsWith("venice:") ? rawId : `venice:${rawId}`;
    const spec = raw.model_spec || {};
    const caps = spec.capabilities || {};
    const pr = spec.pricing || {};
    const inMods = ["text"];
    if (caps.supportsVision) inMods.push("image");
    if (caps.supportsAudioInput) inMods.push("audio");
    const name = spec.name || raw.name || rawId;
    return {
      id,
      model_id: id,
      name,
      display_name: name,
      is_free: false,
      context: spec.availableContextTokens || raw.context_length || null,
      mod_in: inMods.join(","),
      mod_out: "text",
      // Venice model_spec.pricing.*.usd вЂ” СѓР¶Рµ С†РµРЅР° Р—Рђ 1Рњ С‚РѕРєРµРЅРѕРІ (РЅРµ СѓРјРЅРѕР¶Р°РµРј РїРѕРІС‚РѕСЂРЅРѕ).
      price_prompt: pr.input && pr.input.usd != null ? String(pr.input.usd) : null,
      price_completion: pr.output && pr.output.usd != null ? String(pr.output.usd) : null,
      price_cache: pr.cache_input && pr.cache_input.usd != null ? String(pr.cache_input.usd) : null,
      price_unit: "per_1m",
      description: spec.description || "",
      vision: !!caps.supportsVision,
      reasoning: !!caps.supportsReasoning,
      function_calling: !!caps.supportsFunctionCalling,
      max_output: spec.maxCompletionTokens || null,
      quantization: caps.quantization || null,
      type: raw.type || "text",
      meta: id,
    };
  }
  if (provider === "gemini") {
    const rawId = typeof raw === "string" ? raw : (raw.id || raw.name || raw.baseModelId);
    if (!rawId) return null;
    // РџСЂРµС„РёРєСЃ gemini: РѕР±СЏР·Р°С‚РµР»РµРЅ, С‡С‚РѕР±С‹ detectProvider/chat РїРѕРЅРёРјР°Р»Рё РїСЂСЏРјРѕР№ Google API.
    const id = rawId.toLowerCase().startsWith("gemini:") ? rawId : `gemini:${rawId}`;
    const name = (raw.name && raw.name !== rawId) ? raw.name : rawId;
    // Р”РµС‚Р°Р»Рё (context/description/vision) РґРѕС‚СЏРіРёРІР°СЋС‚СЃСЏ С‡РµСЂРµР· getModel РІ fetchProviderModels.
    const d = raw._detail || {};
    const methods: string[] = d.supportedGenerationMethods || [];
    const isEmbedding = /embedding|^aqa/.test(id.toLowerCase());
    const vision = methods.includes("generateContent") && !isEmbedding;
    return {
      id,
      model_id: id,
      name,
      display_name: name,
      is_free: true,
      context: d.inputTokenLimit || raw.context_length || null,
      mod_in: vision ? "text,image" : "text",
      mod_out: "text",
      price_prompt: null,
      price_completion: null,
      description: d.description || raw.description || "",
      meta: id,
    };
  }
  return null;
}

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] || provider;
}

async function auditLog(supabase: SupabaseClient, userId: number | null, action: string, ok: boolean, detail?: string): Promise<void> {
  try {
    await supabase.from("audit_log").insert({
      user_id: userId || 0,
      action,
      ok,
      detail: detail ? String(detail).slice(0, 500) : null,
      ts: Math.floor(Date.now() / 1000),
    });
  } catch (_) { /* never fail the request because of audit */ }
}

const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 30;
const rateLimitCache = new Map<number, number[]>();

async function checkRateLimit(supabase: SupabaseClient, userId: number): Promise<boolean> {
  const now = Date.now();
  const hits = rateLimitCache.get(userId) || [];
  const recent = hits.filter((t) => now - t < RATE_LIMIT_WINDOW_MS);
  if (recent.length >= RATE_LIMIT_MAX) return false;
  recent.push(now);
  rateLimitCache.set(userId, recent);
  return true;
}

let cachedCryptoKey: CryptoKey | null = null;
let cachedRawKey = "";

function getCryptoKey(): { key: CryptoKey | null; raw: string } {
  const raw = getEnv("AUDIT_ENCRYPTION_KEY");
  if (!raw || raw.length < 32) return { key: null, raw: "" };
  if (cachedCryptoKey && cachedRawKey === raw) return { key: cachedCryptoKey, raw };
  cachedRawKey = raw;
  return { key: null, raw: cachedRawKey };
}

async function importCryptoKey(raw: string): Promise<CryptoKey | null> {
  try {
    let keyBytes: Uint8Array;
    if (raw.length === 64 && /^[0-9a-fA-F]+$/.test(raw)) {
      keyBytes = new Uint8Array(32);
      for (let i = 0; i < 32; i++) {
        keyBytes[i] = parseInt(raw.slice(i * 2, i * 2 + 2), 16);
      }
    } else {
      keyBytes = new TextEncoder().encode(raw);
    }
    return await crypto.subtle.importKey("raw", keyBytes, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
  } catch (_) {
    return null;
  }
}

async function encryptField(plaintext: string): Promise<string> {
  const { raw } = getCryptoKey();
  if (!raw) return plaintext;
  try {
    const keyMaterial = await importCryptoKey(raw);
    if (!keyMaterial) return plaintext;
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, keyMaterial, new TextEncoder().encode(plaintext));
    const buf = new Uint8Array(iv.byteLength + encrypted.byteLength);
    buf.set(iv);
    buf.set(new Uint8Array(encrypted), iv.byteLength);
    return btoa(String.fromCharCode(...buf));
  } catch (_) {
    return plaintext;
  }
}

async function decryptField(ciphertext: string): Promise<string> {
  const { raw } = getCryptoKey();
  if (!raw) return ciphertext;
  try {
    const keyMaterial = await importCryptoKey(raw);
    if (!keyMaterial) return ciphertext;
    const data = Uint8Array.from(atob(ciphertext), (c) => c.charCodeAt(0));
    const iv = data.slice(0, 12);
    const payload = data.slice(12);
    const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, keyMaterial, payload);
    return new TextDecoder().decode(decrypted);
  } catch (_) {
    return ciphertext;
  }
}

async function tryDecryptField(ciphertext: string): Promise<string | null> {
  const { raw } = getCryptoKey();
  if (!raw) return null;
  try {
    const keyMaterial = await importCryptoKey(raw);
    if (!keyMaterial) return null;
    const data = Uint8Array.from(atob(ciphertext), (c) => c.charCodeAt(0));
    if (data.length < 13) return null;
    const iv = data.slice(0, 12);
    const payload = data.slice(12);
    const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, keyMaterial, payload);
    return new TextDecoder().decode(decrypted);
  } catch (_) {
    return null;
  }
}

async function encryptApiKey(plaintext: string): Promise<string> {
  return encryptField(plaintext);
}

async function decryptApiKey(ciphertext: string): Promise<string> {
  return decryptField(ciphertext);
}

// --- Gemini Prompt Caching ---------------------------------------------

const CACHE_TRIGGER_TOKENS = 32000; // Create cache when history exceeds this
const CACHE_TTL_SECONDS = 300; // 5 minutes

function estimateTokenCount(text: string): number {
  if (!text) return 0;
  // Rough estimation: ~3.5 chars per token for mixed text
  return Math.ceil(text.length / 3.5);
}

async function getOrCreateGeminiCache(
  supabase: any,
  userId: number,
  modelId: string,
  systemPrompt: string,
  history: any[],
  apiKey: string
): Promise<{ cacheName: string | null; cachedHistory: any[] }> {
  // Estimate tokens in the static prefix (system prompt + older history)
  const staticPrefix = [
    { role: "user", parts: [{ text: systemPrompt }] },
    ...history.slice(0, -10).map((m) => ({
      role: m.role === "user" ? "user" : "model",
      parts: [{ text: m.content || "" }]
    }))
  ];
  
  const estimatedTokens = staticPrefix.reduce((sum, m) => {
    const text = m.parts?.[0]?.text || m.content || "";
    return sum + estimateTokenCount(text);
  }, 0);

  if (estimatedTokens < CACHE_TRIGGER_TOKENS) {
    return { cacheName: null, cachedHistory: history };
  }

  // Check if we have a valid cache for this user/model
  const { data: cacheData } = await supabase
    .from("gemini_cache")
    .select("*")
    .eq("user_id", userId)
    .eq("model_id", modelId)
    .gt("expires_at", new Date().toISOString())
    .single();

  if (cacheData?.cache_name) {
    // Cache exists and is valid - use it
    return { 
      cacheName: cacheData.cache_name, 
      cachedHistory: history.slice(-10) // Only send recent messages
    };
  }

  // Create new cache
  try {
    const cachePayload = {
      model: `models/${modelId}`,
      contents: staticPrefix,
      ttl: `${CACHE_TTL_SECONDS}s`
    };

    const resp = await fetch(`${API_ENDPOINTS.gemini_cached_contents}?key=${apiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cachePayload)
    });

    if (resp.ok) {
      const data = await resp.json();
      const cacheName = data.name; // e.g., "cachedContents/abc123"
      
      // Store in DB
      const expiresAt = new Date(Date.now() + CACHE_TTL_SECONDS * 1000).toISOString();
      await supabase.from("gemini_cache").upsert({
        user_id: userId,
        model_id: modelId,
        cache_name: cacheName,
        expires_at: expiresAt,
        token_count: estimatedTokens
      }, { onConflict: "user_id,model_id" });

      return { 
        cacheName, 
        cachedHistory: history.slice(-10) 
      };
    }
  } catch (e) {
    console.warn("[gemini cache] failed to create cache:", e);
  }

  return { cacheName: null, cachedHistory: history };
}

export {
  verifyInitData,
  extractUser,
  getEnv,
  getSupabase,
  API_ENDPOINTS,
  PROVIDER_KEY_COLS,
  isBlacklisted,
  ensureUser,
  getUser,
  buildUserProviderKeys,
  detectProvider,
  normalizeModelId,
  modelIdForProvider,
  getProviderApiKey,
  resolveEffectiveApiKey,
  buildOpenAIMessages,
  buildGeminiContents,
  extractOpenAIContent,
  extractGeminiContent,
  extractUsage,
  normalizeProviderModel,
  isOpenrouterFreeModel,
  providerLabel,
  CORS_HEADERS,
  corsPreflight,
  withCORS,
  auditLog,
  checkRateLimit,
  encryptField,
  decryptField,
  tryDecryptField,
  encryptApiKey,
  decryptApiKey,
  getOrCreateGeminiCache,
};




