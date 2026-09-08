// Edge Function: img-proxy
// Проксирует внешние картинки, чтобы Telegram WebApp не блокировал чужие домены.
// GET /img-proxy?u=<url> -> отдаёт картинку с CORS-заголовками.
import { getSupabase, checkRateLimit, auditLog, corsPreflight, withCORS } from "../_shared/shared.ts";

const MAX_BYTES = 5 * 1024 * 1024; // 5 МБ

function isPrivateIpV4(ip: string): boolean {
  const parts = ip.split(".").map((p) => parseInt(p, 10));
  if (parts.length !== 4 || parts.some((p) => isNaN(p) || p < 0 || p > 255)) {
    return false;
  }
  const [a, b, c] = parts;
  // 0.0.0.0/8
  if (a === 0) return true;
  // 10.0.0.0/8
  if (a === 10) return true;
  // 127.0.0.0/8 (loopback)
  if (a === 127) return true;
  // 169.254.0.0/16 (link-local & cloud metadata 169.254.169.254)
  if (a === 169 && b === 254) return true;
  // 172.16.0.0/12
  if (a === 172 && b >= 16 && b <= 31) return true;
  // 192.168.0.0/16
  if (a === 192 && b === 168) return true;
  // 100.64.0.0/10 (carrier-grade NAT)
  if (a === 100 && b >= 64 && b <= 127) return true;
  // 192.0.0.0/24, 192.0.2.0/24
  if (a === 192 && b === 0 && (c === 0 || c === 2)) return true;
  // 198.18.0.0/15
  if (a === 198 && (b === 18 || b === 19)) return true;
  // 198.51.100.0/24
  if (a === 198 && b === 51 && c === 100) return true;
  // 203.0.113.0/24
  if (a === 203 && b === 0 && c === 113) return true;
  // 224.0.0.0/4 (multicast) & 240.0.0.0/4 (reserved)
  if (a >= 224) return true;

  return false;
}

function isPrivateIpV6(ip: string): boolean {
  const norm = ip.toLowerCase();
  if (norm === "::1" || norm === "::" || norm === "0:0:0:0:0:0:0:1") return true;
  // Unique local fc00::/7 or fe80::/10 (link-local)
  if (norm.startsWith("fc") || norm.startsWith("fd") || norm.startsWith("fe8") || norm.startsWith("fe9") || norm.startsWith("fea") || norm.startsWith("feb")) return true;
  return false;
}

async function isDisallowedHost(hostname: string): Promise<boolean> {
  const host = hostname.toLowerCase().trim().replace(/^\[|\]$/g, "");
  if (!host) return true;

  if (
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host.endsWith(".local") ||
    host.endsWith(".internal") ||
    host.endsWith(".arpa") ||
    host.endsWith(".lan") ||
    host === "metadata.google.internal"
  ) {
    return true;
  }

  // Check direct IP literals
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host)) {
    return isPrivateIpV4(host);
  }
  if (host.includes(":")) {
    return isPrivateIpV6(host);
  }

  // Resolve DNS to prevent DNS rebinding attacks (e.g. *.nip.io pointing to 127.0.0.1 or 169.254.169.254)
  try {
    const records = await Deno.resolveDns(host, "A");
    for (const ip of records) {
      if (isPrivateIpV4(ip)) return true;
    }
  } catch (_) {
    // If DNS resolution fails, allow fetch to handle or fail naturally
  }

  return false;
}

Deno.serve(async (req: Request) => {
  const pre = corsPreflight(req);
  if (pre) return pre;
  if (req.method !== "GET") return withCORS(new Response("Method not allowed", { status: 405 }));

  const clientIp = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || req.headers.get("cf-connecting-ip") || "unknown";
  const supabase = getSupabase(true);
  // Rate limit by client IP hash to prevent abuse
  const ipHash = clientIp.split(".").reduce((acc, part) => acc * 31 + parseInt(part || "0", 10), 0);
  if (!(await checkRateLimit(supabase, ipHash, 60, 60))) {
    return withCORS(new Response("Too many requests", { status: 429 }));
  }

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

  // Check SSRF protection
  if (await isDisallowedHost(parsed.hostname)) {
    return withCORS(new Response("Access to internal or private hosts is forbidden", { status: 403 }));
  }

  try {
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 10000);

    const upstream = await fetch(parsed.toString(), {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; ai-app-imgproxy/1.0)" },
      signal: ctrl.signal,
    });
    clearTimeout(timeout);

    if (!upstream.ok) return withCORS(new Response("Upstream error " + upstream.status, { status: 502 }));
    const ctype = upstream.headers.get("content-type") || "";
    if (!/^image\/(jpeg|png|webp|gif|svg\+xml|x-icon|bmp)/i.test(ctype)) {
      return withCORS(new Response("Not an image", { status: 415 }));
    }

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
    for (const c of chunks) {
      blob.set(c, off);
      off += c.byteLength;
    }
    return withCORS(new Response(blob, {
      status: 200,
      headers: {
        "Content-Type": ctype,
        "Cache-Control": "public, max-age=3600",
        "X-Content-Type-Options": "nosniff",
      },
    }));
  } catch (e: any) {
    return withCORS(new Response("Proxy error: " + (e?.message || e), { status: 502 }));
  }
});
