// Run with:  node deploy/test/worker.test.mjs   (Node 18+; no packages needed)
// Exercises the Worker with a fake ASSETS binding and an in-memory fake D1.
import assert from "node:assert/strict";
import worker from "../src/worker.js";

const KEY = "correct-horse";
const rows = [];
const db = {
  prepare(sql) {
    return {
      args: [],
      bind(...a) { this.args = a; return this; },
      async first() { const [rk, since] = this.args; return { n: rows.filter((r) => r.rate_key === rk && r.created_at >= since).length }; },
      async run() { const [created_at, name, area, type, message, page_context, rate_key] = this.args; rows.push({ created_at, name, area, type, message, page_context, rate_key }); return {}; },
    };
  },
};
const env = {
  TEAM_KEY: KEY, FEEDBACK_DB: db,
  ASSETS: { async fetch(req) { return new Response("<html>app</html>", { status: 200, headers: { "Content-Type": "text/html", "Cache-Control": "public, max-age=999" } }); } },
};
const call = (path, init = {}) => worker.fetch(new Request("https://demo.example" + path, init), env);
let cookie = "";
let n = 0;
async function t(name, fn) { await fn(); n++; console.log("ok - " + name); }

await t("no key shows the gate with noindex", async () => {
  const r = await call("/");
  assert.equal(r.status, 401);
  assert.match(await r.text(), /team code/i);
  assert.match(r.headers.get("X-Robots-Tag"), /noindex/);
  assert.equal(r.headers.get("Set-Cookie"), null);
});
await t("assets and api are gated", async () => {
  assert.equal((await call("/static/app.js")).status, 401);
  assert.equal((await call("/runs/_fixture/results.json")).status, 401);
  const r = await call("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  assert.equal(r.status, 401);
  assert.equal(rows.length, 0);
});
await t("robots.txt disallows everything and needs no key", async () => {
  const r = await call("/robots.txt");
  assert.equal(r.status, 200);
  assert.match(await r.text(), /Disallow: \//);
});
await t("wrong key is refused", async () => {
  const r = await call("/?key=nope");
  assert.equal(r.status, 401);
  assert.equal(r.headers.get("Set-Cookie"), null);
});
await t("right key sets a secure cookie and redirects to the clean URL", async () => {
  const r = await call("/some/page?key=" + KEY + "&x=1");
  assert.equal(r.status, 303);
  assert.equal(r.headers.get("Location"), "/some/page?x=1");
  const sc = r.headers.get("Set-Cookie");
  assert.match(sc, /HttpOnly/); assert.match(sc, /Secure/); assert.match(sc, /SameSite=Lax/);
  assert.ok(!sc.includes(KEY), "cookie must not hold the raw key");
  cookie = sc.split(";")[0];
});
await t("the form unlock works too", async () => {
  const r = await call("/_unlock", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "key=" + KEY });
  assert.equal(r.status, 303);
  const bad = await call("/_unlock", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "key=wrong" });
  assert.equal(bad.status, 401);
});
await t("with the cookie, assets are served with noindex and private caching", async () => {
  const r = await call("/", { headers: { Cookie: cookie } });
  assert.equal(r.status, 200);
  assert.match(r.headers.get("X-Robots-Tag"), /noindex/);
  assert.match(r.headers.get("Cache-Control"), /private/);
  assert.match(r.headers.get("Content-Security-Policy"), /script-src 'self'/);
});
await t("a forged cookie is refused", async () => {
  assert.equal((await call("/", { headers: { Cookie: "clipsift_team=" + KEY } })).status, 401);
});
const good = { name: "Sam", area: "Counting", type: "Confusing", message: "I was not sure what COUNT NOW meant.", page_context: { run: "synthetic_demo", subsample_id: "ss_01" } };
const send = (body, extra = {}) => call("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json", Cookie: cookie, ...extra }, body: typeof body === "string" ? body : JSON.stringify(body) });
await t("valid feedback is stored", async () => {
  const r = await send(good);
  assert.equal(r.status, 201);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].area, "Counting");
  assert.equal(JSON.parse(rows[0].page_context).subsample_id, "ss_01");
  assert.ok(rows[0].rate_key);
});
await t("validation rejects bad input", async () => {
  for (const bad of [{ ...good, message: "" }, { ...good, message: "   " }, { ...good, message: "x".repeat(2001) }, { ...good, name: "n".repeat(61) },
    { ...good, area: "Nope" }, { ...good, type: "Rant" }, { ...good, message: 5 }, [1], "not json"]) {
    const r = await send(bad);
    assert.equal(r.status, 400, JSON.stringify(bad).slice(0, 60));
  }
  assert.equal((await send(good, { "Content-Type": "text/plain" })).status, 415);
  assert.equal((await send(good, { Origin: "https://evil.example" })).status, 403);
  assert.equal(rows.length, 1);
});
await t("limits are inclusive: 2000 chars and 60-char name pass", async () => {
  assert.equal((await send({ ...good, message: "m".repeat(2000), name: "n".repeat(60) })).status, 201);
});
await t("honeypot is accepted quietly and stores nothing", async () => {
  const before = rows.length;
  assert.equal((await send({ ...good, website: "spam" })).status, 201);
  assert.equal(rows.length, before);
});
await t("rate limit stops the 31st note in an hour", async () => {
  let last = 0;
  for (let i = 0; i < 40; i++) last = (await send(good)).status;
  assert.equal(last, 429);
  assert.equal(rows.length, 30);
});
await t("no way to read feedback back", async () => {
  assert.equal((await call("/api/feedback", { headers: { Cookie: cookie } })).status, 405);
  assert.equal((await call("/api/feedback/mine", { headers: { Cookie: cookie } })).status, 404);
});
console.log(n + " checks passed");
