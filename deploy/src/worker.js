// ClipSift team demo Worker.
// Every request passes through here first (assets.run_worker_first), so the team-key gate covers
// the page, the sample files and the API. Secrets: TEAM_KEY. Bindings: ASSETS, FEEDBACK_DB (D1).

const COOKIE = "clipsift_team";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30;
const AREAS = ["Counting", "Video", "Timeline", "Help", "Layout", "Other"];
const TYPES = ["Bug", "Confusing", "Idea", "Like"];
const RATE_LIMIT = 30;                 // notes per sender per hour
const RATE_WINDOW_MS = 60 * 60 * 1000;
const MAX_BODY = 8192;
const ROBOTS = "User-agent: *\nDisallow: /\n";
const APP_CSP = "default-src 'self'; img-src 'self' data: blob:; media-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'";
const PAGE_CSP = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'";

const enc = new TextEncoder();

async function sha256(text) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(text)));
}
function hex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}
// Constant-time comparison. Hashing first makes both sides the same length, so length does not leak.
async function safeEqual(a, b) {
  const [x, y] = await Promise.all([sha256(String(a)), sha256(String(b))]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}
// The cookie holds a derived token, not the team key itself.
async function tokenFor(env) {
  return hex(await sha256("clipsift-demo-cookie:" + env.TEAM_KEY));
}
function readCookie(request, name) {
  for (const part of (request.headers.get("Cookie") || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return "";
}
function cookieHeader(token) {
  return `${COOKIE}=${token}; Path=/; Max-Age=${COOKIE_MAX_AGE}; HttpOnly; Secure; SameSite=Lax`;
}
function secure(headers) {
  headers.set("X-Robots-Tag", "noindex, nofollow");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "no-referrer");
  return headers;
}
function json(obj, status = 200, extra = {}) {
  const h = secure(new Headers({ "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra }));
  return new Response(JSON.stringify(obj), { status, headers: h });
}
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function gatePage(message, status = 401) {
  const note = message ? `<p class="err" role="alert">${esc(message)}</p>` : "";
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Team code needed</title>
<style>body{font:16px/1.5 system-ui,sans-serif;background:#15181b;color:#e8ecef;display:grid;place-items:center;min-height:100vh;margin:0}
main{max-width:360px;padding:24px}h1{font-size:20px;margin:0 0 8px}input,button{font:inherit;padding:8px 10px;border-radius:5px;border:1px solid #3a424a;margin-top:8px}
input{background:#101316;color:#e8ecef;width:100%;box-sizing:border-box}button{background:#2a5d44;color:#fff;cursor:pointer}.err{color:#ff8a80}p{margin:6px 0}</style></head>
<body><main><h1>ClipSift team demo</h1><p>This page is for the project team. Enter the team code to continue.</p>${note}
<form method="post" action="/_unlock"><label for="k">Team code</label><input id="k" name="key" type="password" autocomplete="off" required autofocus>
<button type="submit">Continue</button></form></main></body></html>`;
  return new Response(html, { status, headers: secure(new Headers({ "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "Content-Security-Policy": PAGE_CSP })) });
}
function redirect(location, token) {
  const h = secure(new Headers({ Location: location, "Cache-Control": "no-store" }));
  if (token) h.append("Set-Cookie", cookieHeader(token));
  return new Response(null, { status: 303, headers: h });
}

// ---- feedback -------------------------------------------------------------
function cleanText(v, max) {
  return String(v).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "").trim().slice(0, max + 1);
}
function validateFeedback(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { error: "Send a JSON object." };
  if (typeof body.message !== "string") return { error: "message is required." };
  const message = cleanText(body.message, 2000);
  if (message.length < 1) return { error: "message is required." };
  if (message.length > 2000) return { error: "message is too long (max 2000 characters)." };
  let name = "";
  if (body.name != null) {
    if (typeof body.name !== "string") return { error: "name must be text." };
    name = cleanText(body.name, 60);
    if (name.length > 60) return { error: "name is too long (max 60 characters)." };
  }
  if (!AREAS.includes(body.area)) return { error: "area must be one of: " + AREAS.join(", ") + "." };
  if (!TYPES.includes(body.type)) return { error: "type must be one of: " + TYPES.join(", ") + "." };
  let ctx = "";
  if (body.page_context != null) {
    if (typeof body.page_context !== "object" && typeof body.page_context !== "string") return { error: "page_context must be an object or text." };
    ctx = typeof body.page_context === "string" ? body.page_context : JSON.stringify(body.page_context);
    if (ctx.length > 1000) return { error: "page_context is too long." };
  }
  return { value: { name, area: body.area, type: body.type, message, page_context: ctx } };
}

async function handleFeedback(request, env) {
  if (request.method !== "POST") return json({ error: "Use POST." }, 405, { Allow: "POST" });
  const origin = request.headers.get("Origin");
  if (origin && origin !== new URL(request.url).origin) return json({ error: "Cross-site requests are not allowed." }, 403);
  if (!(request.headers.get("Content-Type") || "").toLowerCase().startsWith("application/json")) return json({ error: "Send JSON (Content-Type: application/json)." }, 415);
  const raw = await request.text();
  if (raw.length > MAX_BODY) return json({ error: "That note is too large." }, 413);
  let body;
  try { body = JSON.parse(raw); } catch (e) { return json({ error: "Body is not valid JSON." }, 400); }
  if (body && typeof body === "object" && typeof body.website === "string" && body.website.trim() !== "") {
    return json({ ok: true }, 201);  // honeypot filled: pretend it worked, store nothing
  }
  const v = validateFeedback(body);
  if (v.error) return json({ error: v.error }, 400);

  // Rate limit per sender (cookie token plus IP, hashed with the team key as salt). The raw IP is never stored.
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const rateKey = hex(await sha256(`rate:${env.TEAM_KEY}:${ip}:${readCookie(request, COOKIE)}`)).slice(0, 32);
  const since = new Date(Date.now() - RATE_WINDOW_MS).toISOString().replace(/\.\d+Z$/, "Z");
  try {
    const row = await env.FEEDBACK_DB.prepare("SELECT COUNT(*) AS n FROM feedback WHERE rate_key = ?1 AND created_at >= ?2").bind(rateKey, since).first();
    if (row && row.n >= RATE_LIMIT) return json({ error: "Too many notes from this browser in the last hour. Please try again later." }, 429, { "Retry-After": "3600" });
    const createdAt = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    await env.FEEDBACK_DB.prepare("INSERT INTO feedback (created_at, name, area, type, message, page_context, rate_key) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)")
      .bind(createdAt, v.value.name, v.value.area, v.value.type, v.value.message, v.value.page_context, rateKey).run();
  } catch (e) {
    return json({ error: "The note could not be saved. Please try again in a minute." }, 500);
  }
  return json({ ok: true }, 201);
}

// ---- main -----------------------------------------------------------------
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/robots.txt") {
      return new Response(ROBOTS, { headers: secure(new Headers({ "Content-Type": "text/plain; charset=utf-8" })) });
    }
    if (!env.TEAM_KEY) return json({ error: "The demo is not configured (TEAM_KEY is not set)." }, 500);
    const token = await tokenFor(env);

    // Unlock with the form, or with ?key=... (sets the cookie, then redirects to the clean URL).
    if (url.pathname === "/_unlock" && request.method === "POST") {
      let key = "";
      try { key = String((await request.formData()).get("key") || ""); } catch (e) { /* bad form */ }
      return (await safeEqual(key, env.TEAM_KEY)) ? redirect("/", token) : gatePage("That code did not work. Check it and try again.");
    }
    if (url.searchParams.has("key")) {
      const ok = await safeEqual(url.searchParams.get("key"), env.TEAM_KEY);
      url.searchParams.delete("key");
      return ok ? redirect(url.pathname + url.search, token) : gatePage("That code did not work. Check it and try again.");
    }

    const authed = await safeEqual(readCookie(request, COOKIE), token);
    if (!authed) {
      return url.pathname.startsWith("/api/") ? json({ error: "A team code is needed." }, 401) : gatePage("");
    }

    if (url.pathname === "/api/feedback") return handleFeedback(request, env);
    if (url.pathname.startsWith("/api/")) return json({ error: "Not found." }, 404);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: secure(new Headers({ Allow: "GET, HEAD" })) });
    }

    const resp = await env.ASSETS.fetch(request);   // static files; the platform handles Range for video
    const headers = secure(new Headers(resp.headers));
    headers.set("Cache-Control", "private, max-age=0, must-revalidate");
    if ((headers.get("Content-Type") || "").includes("text/html")) headers.set("Content-Security-Policy", APP_CSP);
    // The assets binding answers Range requests with the whole file, and Safari needs 206 to play video.
    // Demo clips are small, so slice in the Worker.
    const range = request.headers.get("Range");
    if (resp.status === 200 && (headers.get("Content-Type") || "").startsWith("video/")) {
      headers.set("Accept-Ranges", "bytes");
      if (range && request.method === "GET") {
        const buf = await resp.arrayBuffer();
        const r = parseRange(range, buf.byteLength);
        if (!r) {
          headers.set("Content-Range", `bytes */${buf.byteLength}`);
          headers.delete("Content-Length");
          return new Response(null, { status: 416, headers });
        }
        headers.set("Content-Range", `bytes ${r.start}-${r.end}/${buf.byteLength}`);
        headers.set("Content-Length", String(r.end - r.start + 1));
        return new Response(buf.slice(r.start, r.end + 1), { status: 206, headers });
      }
    }
    return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers });
  },
};

// One byte range ("bytes=a-b", "bytes=a-", "bytes=-n"); returns null if unsatisfiable or not understood.
function parseRange(value, size) {
  const m = /^bytes=(\d*)-(\d*)$/.exec(value.trim());
  if (!m || (m[1] === "" && m[2] === "") || size === 0) return null;
  if (m[1] === "") {
    const n = Math.min(Number(m[2]), size);
    return n > 0 ? { start: size - n, end: size - 1 } : null;
  }
  const start = Number(m[1]);
  const end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
  return start <= end && start < size ? { start, end } : null;
}
