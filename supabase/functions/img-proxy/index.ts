// Edge Function: img-proxy
// РџСЂРѕРєСЃРёСЂСѓРµС‚ РІРЅРµС€РЅРёРµ РєР°СЂС‚РёРЅРєРё, С‡С‚РѕР±С‹ Telegram WebApp РЅРµ Р±Р»РѕРєРёСЂРѕРІР°Р» С‡СѓР¶РёРµ РґРѕРјРµРЅС‹.
// GET /img-proxy?u=<url>  ->  РѕС‚РґР°С‘С‚ РєР°СЂС‚РёРЅРєСѓ СЃ CORS-Р·Р°РіРѕР»РѕРІРєР°РјРё.
import { getSupabase, checkRateLimit, auditLog, corsPreflight, withCORS } from "../_shared/shared.ts";

const MAX_BYTES = 15 * 1024 * 1024; // 15 РњР‘

Deno.serve(async (req: Request) => {
  const pre = corsPreflight(req);
  if (pre) return pre;
  if (req.method !== "GET") return withCORS(new Response("Method not allowed", { status: 405 }));

  const url = new URL(req.url);
  const target = url.searchParams.get("u") || "";
  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    return withCORS(new Response("Bad url", { status: 400 }));
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return withCORS(new Response("Unsupported protocol", { status: 400 }));
  }

  try {
    const upstream = await fetch(parsed.toString(), {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; ai-app-imgproxy/1.0)" }});
    if (!upstream.ok) return withCORS(new Response("Upstream error " + upstream.status, { status: 502 }));
    const ctype = upstream.headers.get("content-type") || "";
    if (!/^image\//i.test(ctype)) return withCORS(new Response("Not an image", { status: 415 }));

    const reader = upstream.body!.getReader();
    const chunks: Uint8Array[] = [];
    let total = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_BYTES) return withCORS(new Response("Image too large", { status: 413 }));
      chunks.push(value);
    }
    const blob = new Uint8Array(total);
    let off = 0;
    for (const c of chunks) { blob.set(c, off); off += c.byteLength; }
    return withCORS(new Response(blob, {
      status: 200,
      headers: {
        "Content-Type": ctype,
        "Cache-Control": "public, max-age=3600",
        "Access-Control-Allow-Origin": "*"}}));
  } catch (e: any) {
    return withCORS(new Response("Proxy error: " + (e?.message || e), { status: 502 }));
  }
});




