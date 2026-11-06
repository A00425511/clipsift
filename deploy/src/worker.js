// ClipSift team demo Worker.
// Every request passes through here first (assets.run_worker_first), so the team-key gate covers
// the page, the sample files and the API. Secrets: TEAM_KEY. Bindings: ASSETS, FEEDBACK_DB (D1: feedback and labels tables).

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

// ---- blind labelling ------------------------------------------------------
// Shared, label-only mode (label.html). Two people label each frame on their own. Blind means no route
// here ever returns another person's marks: status gives counts only, and /mine reads the caller's own row.
// IDENTITY IS A CHOSEN NAME, NOT A LOGIN. Anyone who has the team code can type any name, including a
// teammate's, and read or overwrite that name's marks. The team code is the only gate. That is fine for
// five people in a weekend and not fine for anything with real stakes.
const LABEL_MAX_POINTS = 2000;
const LABEL_MAX_BODY = 400000;          // 2000 points with species names is about 250 KB as JSON
const LABEL_NAME_MAX = 40;
const LABEL_MAX_SECONDS = 86400;
const LABEL_RATE_BURST = 120;           // saves in a quick run
const LABEL_RATE_PER_SEC = 10;          // then 600 a minute; a fast labeller saves about once every 3 seconds
const SET_RE = /^[A-Za-z0-9_][A-Za-z0-9_-]{0,39}$/;
const FRAME_RE = /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}$/;
const KINDS = ["fish", "invertebrate", "unsure", "not_fish"];   // unsure: might be an animal, never counted; no species or category
const NOT_FISH_CATEGORIES = ["algae", "debris", "equipment", "seabed", "bubbles", "other"];   // keep in step with label.js and app/server.py
const VIEWS = ["frame", "movement", "clip"];   // which views the labeller used on this frame, in this order
const SPECIES_MAX = 80;
const PRESET_NAMES = ["Jacob", "Ali", "Gina", "Wang", "Adrien"];
const MANIFEST_TTL_MS = 10 * 60 * 1000;
const manifestCache = new Map();        // set id -> { at, frames: Map(frame_id -> {width, height}) }
const rateBuckets = new Map();          // best effort, per isolate: the team code is the real gate

function cleanLabeller(v) {
  if (typeof v !== "string") return { error: "name is required." };
  const name = v.replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim();
  if (name.length < 1) return { error: "name is required." };
  if (name.length > LABEL_NAME_MAX) return { error: `name is too long (max ${LABEL_NAME_MAX} characters).` };
  const preset = PRESET_NAMES.find((n) => n.toLowerCase() === name.toLowerCase());
  return { value: preset || name };
}
// Species typed or picked by a person: control characters removed, spaces tidied, at most SPECIES_MAX characters.
function cleanSpecies(v) {
  return String(v).replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim();
}
function checkIds(setId, frameId) {
  if (typeof setId !== "string" || !SET_RE.test(setId)) return "set is missing or not a plain id.";
  if (frameId !== undefined && (typeof frameId !== "string" || !FRAME_RE.test(frameId))) return "frame is missing or not a plain id.";
  return null;
}
async function loadManifest(env, origin, setId) {
  const hit = manifestCache.get(setId);
  if (hit && Date.now() - hit.at < MANIFEST_TTL_MS) return hit.frames;
  let data;
  try {
    const r = await env.ASSETS.fetch(new Request(`${origin}/label_sets/${setId}/manifest.json`));
    if (!r.ok) return null;
    data = JSON.parse(await r.text());
  } catch (e) { return null; }
  if (!data || !Array.isArray(data.frames)) return null;
  const frames = new Map();
  for (const f of data.frames) {
    if (f && typeof f.frame_id === "string" && FRAME_RE.test(f.frame_id) && Number.isFinite(f.width) && Number.isFinite(f.height)) {
      frames.set(f.frame_id, { width: f.width, height: f.height });
    }
  }
  manifestCache.set(setId, { at: Date.now(), frames });
  return frames;
}
// Token bucket per sender: a burst of 120, then 10 a second. Marks are saved once per frame, so a human never gets near it.
function rateAllowed(key) {
  const now = Date.now();
  let b = rateBuckets.get(key);
  if (!b) {
    if (rateBuckets.size > 2000) rateBuckets.clear();
    b = { tokens: LABEL_RATE_BURST, at: now };
    rateBuckets.set(key, b);
  }
  b.tokens = Math.min(LABEL_RATE_BURST, b.tokens + ((now - b.at) / 1000) * LABEL_RATE_PER_SEC);
  b.at = now;
  if (b.tokens < 1) return false;
  b.tokens -= 1;
  return true;
}
function validateLabel(body, frames) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { error: "Send a JSON object." };
  const bad = checkIds(body.set, body.frame);
  if (bad) return { error: bad };
  const who = cleanLabeller(body.name);
  if (who.error) return who;
  const frame = frames.get(body.frame);
  if (!frame) return { error: "That frame is not in this label set." };
  if (body.skipped != null && typeof body.skipped !== "boolean") return { error: "skipped must be true or false." };
  if (body.no_animals != null && typeof body.no_animals !== "boolean") return { error: "no_animals must be true or false." };
  const skipped = body.skipped === true, noAnimals = body.no_animals === true;
  const pts = body.points == null ? [] : body.points;
  if (!Array.isArray(pts)) return { error: "points must be a list." };
  if (pts.length > LABEL_MAX_POINTS) return { error: `Too many points (max ${LABEL_MAX_POINTS}).` };
  const points = [];
  for (const p of pts) {
    if (!p || typeof p !== "object" || Array.isArray(p)) return { error: "Each point needs x, y and kind." };
    if (typeof p.x !== "number" || typeof p.y !== "number" || !Number.isFinite(p.x) || !Number.isFinite(p.y)) return { error: "Point coordinates must be numbers." };
    if (p.x < 0 || p.y < 0 || p.x > frame.width || p.y > frame.height) return { error: `A point is outside the image (${frame.width} x ${frame.height}).` };
    if (!KINDS.includes(p.kind)) return { error: "kind must be fish, invertebrate, unsure or not_fish." };
    const out = { x: Math.round(p.x * 10) / 10, y: Math.round(p.y * 10) / 10, kind: p.kind };
    if (p.kind === "not_fish") {
      // A not-fish mark has a category (or none) and never a species.
      if (p.category != null && p.category !== "") {
        if (typeof p.category !== "string" || !NOT_FISH_CATEGORIES.includes(p.category)) return { error: "category must be one of: " + NOT_FISH_CATEGORIES.join(", ") + " (or empty)." };
        out.category = p.category;
      }
    } else if (p.kind === "unsure") {
      // An unsure mark carries no species and no category: anything sent is dropped.
    } else if (p.species != null) {
      if (typeof p.species !== "string") return { error: "species must be text." };
      const sp = cleanSpecies(p.species);
      if (sp.length > SPECIES_MAX) return { error: `species is too long (max ${SPECIES_MAX} characters).` };
      if (sp) out.species = sp;
    }
    points.push(out);
  }
  let views = [];
  if (body.views != null) {
    if (!Array.isArray(body.views) || body.views.length > 10 || body.views.some((v) => !VIEWS.includes(v))) return { error: "views must be a list made of: " + VIEWS.join(", ") + "." };
    views = VIEWS.filter((v) => body.views.includes(v));
  }
  if ((noAnimals || skipped) && points.length) return { error: "A skipped frame or a No animals frame cannot have points." };
  if (noAnimals && skipped) return { error: "A frame cannot be both skipped and No animals." };
  let seconds = 0;
  if (body.seconds != null) {
    if (typeof body.seconds !== "number" || !Number.isFinite(body.seconds) || body.seconds < 0) return { error: "seconds must be a number, 0 or more." };
    seconds = Math.min(Math.round(body.seconds * 10) / 10, LABEL_MAX_SECONDS);
  }
  return { value: { set: body.set, frame: body.frame, name: who.value, points, noAnimals, skipped, seconds, views } };
}

async function handleLabels(request, env, url) {
  if (!env.FEEDBACK_DB) return json({ error: "The label database is not set up." }, 500);
  const path = url.pathname;
  const q = url.searchParams;
  try {
    if (path === "/api/labels/status" || path === "/api/labels/mine") {
      if (request.method !== "GET") return json({ error: "Use GET." }, 405, { Allow: "GET" });
      const setId = q.get("set"), frameId = path.endsWith("/mine") ? q.get("frame") : undefined;
      const bad = checkIds(setId, frameId === null ? "" : frameId);
      if (bad) return json({ error: bad }, 400);
      const who = cleanLabeller(q.get("name"));
      if (who.error) return json({ error: who.error }, 400);
      const frames = await loadManifest(env, url.origin, setId);
      if (!frames) return json({ error: "Unknown label set." }, 404);
      if (path.endsWith("/mine")) {
        if (!frames.has(frameId)) return json({ error: "That frame is not in this label set." }, 404);
        const row = await env.FEEDBACK_DB.prepare("SELECT points_json, views_json, no_animals, seconds, skipped, updated_at FROM labels WHERE set_id = ?1 AND frame_id = ?2 AND labeller = ?3").bind(setId, frameId, who.value).first();
        if (!row) return json({ exists: false });
        let points = [];
        try { points = JSON.parse(row.points_json); } catch (e) { /* damaged row: show it as empty */ }
        let views = [];
        try { views = JSON.parse(row.views_json || "[]").filter((v) => VIEWS.includes(v)); } catch (e) { /* damaged row: no views */ }
        return json({ exists: true, frame: frameId, points, views, no_animals: !!row.no_animals, skipped: !!row.skipped, seconds: row.seconds, updated_at: row.updated_at });
      }
      // Counts of finished labels per frame (no names, no marks), and this person's own state.
      const [all, mine] = await Promise.all([
        env.FEEDBACK_DB.prepare("SELECT frame_id, COUNT(*) AS n FROM labels WHERE set_id = ?1 AND skipped = 0 GROUP BY frame_id").bind(setId).all(),
        env.FEEDBACK_DB.prepare("SELECT frame_id, skipped, no_animals, json_array_length(points_json) AS n_points, seconds, updated_at FROM labels WHERE set_id = ?1 AND labeller = ?2").bind(setId, who.value).all(),
      ]);
      const counts = {};
      let two = 0, any = 0;
      for (const r of all.results || []) {
        if (!frames.has(r.frame_id)) continue;
        counts[r.frame_id] = r.n;
        any++;
        if (r.n >= 2) two++;
      }
      const mineOut = {};
      for (const r of mine.results || []) {
        if (frames.has(r.frame_id)) mineOut[r.frame_id] = { state: r.skipped ? "skipped" : "done", no_animals: !!r.no_animals, n_points: r.n_points || 0, seconds: r.seconds, updated_at: r.updated_at };
      }
      return json({ set: setId, total: frames.size, counts, mine: mineOut, team: { frames_with_any: any, frames_with_two: two } });
    }

    if (path === "/api/labels") {
      if (request.method !== "POST") return json({ error: "Use POST." }, 405, { Allow: "POST" });
      const origin = request.headers.get("Origin");
      if (origin && origin !== url.origin) return json({ error: "Cross-site requests are not allowed." }, 403);
      if (!(request.headers.get("Content-Type") || "").toLowerCase().startsWith("application/json")) return json({ error: "Send JSON (Content-Type: application/json)." }, 415);
      const raw = await request.text();
      if (raw.length > LABEL_MAX_BODY) return json({ error: "That save is too large." }, 413);
      let body;
      try { body = JSON.parse(raw); } catch (e) { return json({ error: "Body is not valid JSON." }, 400); }
      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      const who = typeof (body && body.name) === "string" ? body.name.toLowerCase().slice(0, 80) : "";
      if (!rateAllowed(`${ip}|${who}`)) return json({ error: "Saving too fast. Wait a moment and it will retry." }, 429, { "Retry-After": "5" });
      const setId = body && typeof body === "object" ? body.set : undefined;
      const badSet = checkIds(setId);
      if (badSet) return json({ error: badSet }, 400);
      const frames = await loadManifest(env, url.origin, setId);
      if (!frames) return json({ error: "Unknown label set." }, 404);
      const v = validateLabel(body, frames);
      if (v.error) return json({ error: v.error }, 400);
      const x = v.value;
      const updatedAt = new Date().toISOString().replace(/\.\d+Z$/, "Z");
      await env.FEEDBACK_DB.prepare(
        "INSERT INTO labels (set_id, frame_id, labeller, points_json, views_json, no_animals, seconds, skipped, updated_at) VALUES (?1, ?2, ?3, ?4, ?9, ?5, ?6, ?7, ?8) " +
        "ON CONFLICT (set_id, frame_id, labeller) DO UPDATE SET points_json = excluded.points_json, views_json = excluded.views_json, no_animals = excluded.no_animals, seconds = excluded.seconds, skipped = excluded.skipped, updated_at = excluded.updated_at"
      ).bind(x.set, x.frame, x.name, JSON.stringify(x.points), x.noAnimals ? 1 : 0, x.seconds, x.skipped ? 1 : 0, updatedAt, JSON.stringify(x.views)).run();
      return json({ ok: true, updated_at: updatedAt, n_points: x.points.length });
    }
  } catch (e) {
    return json({ error: "The labels could not be read or saved. Please try again in a moment." }, 500);
  }
  return json({ error: "Not found." }, 404);
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
    if (url.pathname === "/api/labels" || url.pathname.startsWith("/api/labels/")) return handleLabels(request, env, url);
    if (url.pathname.startsWith("/api/")) return json({ error: "Not found." }, 404);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: secure(new Headers({ Allow: "GET, HEAD" })) });
    }

    const resp = await env.ASSETS.fetch(request);   // static files; the platform handles Range for video
    const headers = secure(new Headers(resp.headers));
    // Label frames and clips never change once a set id is published (new data gets a new id), so let the browser keep them.
    const stable = /^\/label_sets\/[^/]+\/(frames|clips|diff)\//.test(url.pathname);
    headers.set("Cache-Control", stable ? "private, max-age=86400" : "private, max-age=0, must-revalidate");
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
