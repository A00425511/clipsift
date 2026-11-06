// Run with:  node deploy/test/worker.test.mjs   (Node 18+; no packages needed)
// Exercises the Worker with a fake ASSETS binding, a fake D1 for feedback and real SQLite for labels.
import assert from "node:assert/strict";
import worker from "../src/worker.js";

const KEY = "correct-horse";
const rows = [];
// Labels use a real SQLite database (node:sqlite, Node 22.5+) loaded from schema.sql, so the SQL itself is tested.
let sqlite = null;
try { const { DatabaseSync } = await import("node:sqlite"); sqlite = new DatabaseSync(":memory:"); const { readFileSync } = await import("node:fs"); sqlite.exec(readFileSync(new URL("../schema.sql", import.meta.url), "utf8")); } catch (e) { sqlite = null; }
const labelSql = (sql) => /\blabels\b/.test(sql);
function d1Over(sql) {
  return {
    args: [],
    bind(...a) { this.args = a; return this; },
    async first() { return sqlite.prepare(sql).get(...this.args) || null; },
    async all() { return { results: sqlite.prepare(sql).all(...this.args) }; },
    async run() { sqlite.prepare(sql).run(...this.args); return {}; },
  };
}
const db = {
  prepare(sql) {
    if (sqlite && labelSql(sql)) return d1Over(sql);
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
  ASSETS: {
    async fetch(req) {
      const path = new URL(req.url).pathname;
      if (path === "/label_sets/t1/manifest.json") return new Response(JSON.stringify({ set_id: "t1", frames: [
        { frame_id: "f1", width: 3840, height: 2160 }, { frame_id: "f2", width: 3840, height: 2160 }, { frame_id: "f3", width: 1000, height: 500 }] }), { status: 200, headers: { "Content-Type": "application/json" } });
      if (path === "/label_sets/t1/clips/f1.mp4") return new Response(new Uint8Array(100).map((_, i) => i), { status: 200, headers: { "Content-Type": "video/mp4" } });
      if (path === "/label_sets/t1/diff/f1.jpg") return new Response("jpg", { status: 200, headers: { "Content-Type": "image/jpeg" } });
      if (path.startsWith("/label_sets/")) return new Response("missing", { status: 404 });
      return new Response("<html>app</html>", { status: 200, headers: { "Content-Type": "text/html", "Cache-Control": "public, max-age=999" } });
    },
  },
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

// ---- blind labelling ----
const L = (path, init = {}) => call(path, { ...init, headers: { Cookie: cookie, ...(init.headers || {}) } });
const post = (body, extra = {}) => L("/api/labels", { method: "POST", headers: { "Content-Type": "application/json", ...extra }, body: typeof body === "string" ? body : JSON.stringify(body) });
const lab = { set: "t1", frame: "f1", name: "Jacob", points: [{ x: 100, y: 200, kind: "fish" }, { x: 3840, y: 2160, kind: "invertebrate" }], no_animals: false, skipped: false, seconds: 12.34 };
if (!sqlite) console.log("skip - label tests need node:sqlite (Node 22.5+)");
else {
  await t("label routes are behind the team gate", async () => {
    assert.equal((await call("/api/labels/status?set=t1&name=Jacob")).status, 401);
    assert.equal((await call("/api/labels", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lab) })).status, 401);
  });
  await t("a label is saved and read back by its owner only", async () => {
    const r = await post(lab);
    assert.equal(r.status, 200);
    const mine = await (await L("/api/labels/mine?set=t1&frame=f1&name=jacob")).json();  // case-insensitive name
    assert.equal(mine.exists, true);
    assert.equal(mine.points.length, 2);
    assert.equal(mine.seconds, 12.3);
    const other = await (await L("/api/labels/mine?set=t1&frame=f1&name=Ali")).json();
    assert.equal(other.exists, false);
    assert.equal((await (await L("/api/labels/mine?set=t1&frame=f2&name=Jacob")).json()).exists, false);
  });
  await t("saving again replaces the row (upsert), it never adds a second one", async () => {
    assert.equal((await post({ ...lab, name: "JACOB", points: [{ x: 5, y: 6, kind: "fish" }], seconds: 20 })).status, 200);
    const n = sqlite.prepare("SELECT COUNT(*) AS n FROM labels").get().n;
    assert.equal(n, 1);
    const mine = await (await L("/api/labels/mine?set=t1&frame=f1&name=Jacob")).json();
    assert.deepEqual(mine.points, [{ x: 5, y: 6, kind: "fish" }]);
    assert.equal(sqlite.prepare("SELECT labeller FROM labels").get().labeller, "Jacob");  // preset names keep their spelling
  });
  await t("status gives counts and own state, and no marks or names of others", async () => {
    await post({ ...lab, name: "Ali", frame: "f1", points: [{ x: 1, y: 1, kind: "fish" }] });
    await post({ ...lab, name: "Ali", frame: "f2", points: [], no_animals: true });
    await post({ ...lab, name: "Jacob", frame: "f2", points: [], skipped: true });
    const text = await (await L("/api/labels/status?set=t1&name=Jacob")).text();
    const st = JSON.parse(text);
    assert.equal(st.total, 3);
    assert.deepEqual(st.counts, { f1: 2, f2: 1 });          // Jacob's skip of f2 is not a label
    assert.equal(st.mine.f1.state, "done");
    assert.equal(st.mine.f2.state, "skipped");
    assert.deepEqual(st.team, { frames_with_any: 2, frames_with_two: 1 });
    assert.ok(!/Ali/.test(text) && !text.includes('"x"'), "no names or coordinates in status");
    const aliMine = JSON.parse(await (await L("/api/labels/status?set=t1&name=Ali")).text()).mine;
    assert.equal(aliMine.f2.no_animals, true);
  });
  await t("no route lets a browser list rows or read others", async () => {
    for (const path of ["/api/labels", "/api/labels/all", "/api/labels/export", "/api/labels/mine?set=t1&frame=f1"]) {
      const r = await L(path);
      assert.ok([400, 404, 405].includes(r.status), path + " gave " + r.status);
    }
  });
  await t("not fish: category must be listed or empty, species is dropped, other kinds unchanged", async () => {
    const pts = [{ x: 1, y: 2, kind: "not_fish", category: "algae" }, { x: 3, y: 4, kind: "not_fish" }, { x: 5, y: 6, kind: "not_fish", category: "", species: "Gadus" }, { x: 7, y: 8, kind: "fish" }];
    assert.equal((await post({ ...lab, frame: "f2", points: pts })).status, 200);
    const mine = await (await L("/api/labels/mine?set=t1&frame=f2&name=Jacob")).json();
    assert.deepEqual(mine.points, [{ x: 1, y: 2, kind: "not_fish", category: "algae" }, { x: 3, y: 4, kind: "not_fish" }, { x: 5, y: 6, kind: "not_fish" }, { x: 7, y: 8, kind: "fish" }]);
    for (const category of ["Algae", "weed", 5, ["algae"]]) assert.equal((await post({ ...lab, frame: "f2", points: [{ x: 1, y: 1, kind: "not_fish", category }] })).status, 400);
    assert.equal((await post({ ...lab, frame: "f2", points: [{ x: 1, y: 1, kind: "rock" }] })).status, 400);
    assert.equal((await post({ ...lab, frame: "f2", points: [pts[0]], no_animals: true })).status, 400);
    assert.equal((await post({ ...lab, frame: "f2", points: [pts[0]] })).status, 200);   // only not fish is an ordinary labelled frame
  });
  await t("species and views: cleaned, limited, stored, read back", async () => {
    const pts = [{ x: 1, y: 2, kind: "fish", species: "  Gadus \u0007 morhua\n " }, { x: 3, y: 4, kind: "invertebrate", species: "   " }, { x: 5, y: 6, kind: "fish", species: null }, { x: 7, y: 8, kind: "fish" }];
    assert.equal((await post({ ...lab, frame: "f2", points: pts, views: ["clip", "frame", "movement", "frame"] })).status, 200);
    const mine = await (await L("/api/labels/mine?set=t1&frame=f2&name=Jacob")).json();
    assert.deepEqual(mine.points[0], { x: 1, y: 2, kind: "fish", species: "Gadus morhua" });
    assert.ok(mine.points.slice(1).every((p) => !("species" in p)));
    assert.deepEqual(mine.views, ["frame", "movement", "clip"]);
    assert.equal((await post({ ...lab, frame: "f2", points: [{ x: 1, y: 1, kind: "fish", species: "x".repeat(80) }] })).status, 200);   // inclusive
    assert.deepEqual((await (await L("/api/labels/mine?set=t1&frame=f2&name=Jacob")).json()).views, []);                                  // no views sent
    const before = sqlite.prepare("SELECT COUNT(*) AS n FROM labels").get().n;
    const bads = [
      { ...lab, points: [{ x: 1, y: 1, kind: "fish", species: "x".repeat(81) }] }, { ...lab, points: [{ x: 1, y: 1, kind: "fish", species: 5 }] },
      { ...lab, points: [{ x: 1, y: 1, kind: "fish", species: ["a"] }] }, { ...lab, views: ["frame", "zoom"] }, { ...lab, views: "frame" }, { ...lab, views: [1] },
      { ...lab, views: Array(11).fill("frame") },
    ];
    for (const b of bads) assert.equal((await post(b)).status, 400, JSON.stringify(b).slice(0, 90));
    assert.equal(sqlite.prepare("SELECT COUNT(*) AS n FROM labels").get().n, before);
    assert.equal((await post({ ...lab, frame: "f2" })).status, 200);   // put f2 back as it was for the tests below
  });
  await t("validation rejects bad labels", async () => {
    const before = sqlite.prepare("SELECT COUNT(*) AS n FROM labels").get().n;
    const bads = [
      { ...lab, frame: "nope" }, { ...lab, set: "../x" }, { ...lab, frame: "a/b" }, { ...lab, name: "" }, { ...lab, name: "n".repeat(41) }, { ...lab, name: 5 },
      { ...lab, points: [{ x: 3841, y: 5, kind: "fish" }] }, { ...lab, points: [{ x: -1, y: 5, kind: "fish" }] }, { ...lab, frame: "f3", points: [{ x: 5, y: 501, kind: "fish" }] },
      { ...lab, points: [{ x: 1, y: 1, kind: "crab" }] }, { ...lab, points: [{ x: "1", y: 1, kind: "fish" }] }, { ...lab, points: [{ x: NaN, y: 1, kind: "fish" }] }, { ...lab, points: "x" },
      { ...lab, no_animals: true }, { ...lab, skipped: true }, { ...lab, points: [], no_animals: true, skipped: true }, { ...lab, seconds: -1 }, { ...lab, seconds: "5" },
      { ...lab, points: Array.from({ length: 2001 }, () => ({ x: 1, y: 1, kind: "fish" })) }, [1], "not json",
    ];
    for (const b of bads) assert.equal((await post(b)).status, 400, JSON.stringify(b).slice(0, 80));
    assert.equal((await post({ ...lab, set: "zzz" })).status, 404);  // set with no manifest
    assert.equal((await post(lab, { "Content-Type": "text/plain" })).status, 415);
    assert.equal((await post(lab, { Origin: "https://evil.example" })).status, 403);
    assert.equal((await post({ ...lab, pad: "x".repeat(410000) })).status, 413);
    assert.equal(sqlite.prepare("SELECT COUNT(*) AS n FROM labels").get().n, before);
  });
  await t("limits are inclusive: 2000 points, 40-char name, points on the image edge", async () => {
    const pts = Array.from({ length: 2000 }, (_, i) => ({ x: i % 3841, y: 2160, kind: "fish" }));
    assert.equal((await post({ ...lab, frame: "f2", name: "n".repeat(40), points: pts })).status, 200);
  });
  await t("a hostile name is stored as plain text and returned only as itself", async () => {
    const evil = "=cmd|'/c calc'!A1 <img src=x onerror=1>";
    assert.equal((await post({ ...lab, frame: "f3", name: evil.slice(0, 40), points: [{ x: 1, y: 1, kind: "fish" }] })).status, 200);
    const st = JSON.parse(await (await L("/api/labels/status?set=t1&name=Jacob")).text());
    assert.ok(!JSON.stringify(st).includes("calc"));
  });
  await t("SQL in a name or id does nothing", async () => {
    const before = sqlite.prepare("SELECT COUNT(*) AS n FROM labels").get().n;
    assert.equal((await post({ ...lab, name: "x'); DROP TABLE labels;--", frame: "f2" })).status, 200);
    assert.ok(sqlite.prepare("SELECT COUNT(*) AS n FROM labels").get().n >= before);
    assert.equal((await L("/api/labels/status?set=t1' OR '1'='1&name=Jacob")).status, 400);
  });
  await t("a fast labeller is not rate limited, a flood is", async () => {
    for (let i = 0; i < 40; i++) assert.equal((await post({ ...lab, name: "Gina", frame: "f1", seconds: i })).status, 200);
    let limited = 0;
    for (let i = 0; i < 300; i++) if ((await post({ ...lab, name: "Wang", frame: "f1", seconds: i })).status === 429) limited++;
    assert.ok(limited > 0, "flood should hit the limit");
  });
  await t("a database error is a 500 with a plain message and no details", async () => {
    const saved = env.FEEDBACK_DB;
    env.FEEDBACK_DB = { prepare() { throw new Error("secret detail"); } };
    const r = await L("/api/labels/status?set=t1&name=Jacob");
    env.FEEDBACK_DB = saved;
    assert.equal(r.status, 500);
    assert.ok(!(await r.text()).includes("secret"));
  });
}
await t("label clips are served with Range support, and frames are cached", async () => {
  const r = await L("/label_sets/t1/clips/f1.mp4", { headers: { Range: "bytes=10-19" } });
  assert.equal(r.status, 206);
  assert.equal(r.headers.get("Content-Range"), "bytes 10-19/100");
  assert.deepEqual([...new Uint8Array(await r.arrayBuffer())], [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]);
  assert.match(r.headers.get("Cache-Control"), /max-age=86400/);
  assert.equal((await call("/label_sets/t1/clips/f1.mp4")).status, 401);
  assert.match((await L("/label_sets/t1/diff/f1.jpg")).headers.get("Cache-Control"), /max-age=86400/);   // Movement view images are cached like frames
});
console.log(n + " checks passed");
