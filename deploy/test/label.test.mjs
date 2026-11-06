// Run with:  node deploy/test/label.test.mjs   (Node 18+)
// Tests the pure helpers in app/static/label.js: next-frame choice, zoom and pan maths, names.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const L = createRequire(import.meta.url)("../../app/static/label.js");

let n = 0;
const t = (name, fn) => { fn(); n++; console.log("ok - " + name); };
const frames = Array.from({ length: 100 }, (_, i) => ({ frame_id: "f" + i, time_s: 60 + i * 20 }));

t("names: presets keep their spelling, others are trimmed and capped", () => {
  assert.equal(L.cleanName("  jacob "), "Jacob");
  assert.equal(L.cleanName("ADRIEN"), "Adrien");
  assert.equal(L.cleanName("Sam\n  Lee"), "Sam Lee");
  assert.equal(L.cleanName("x".repeat(80)).length, 40);
  assert.equal(L.cleanName(null), "");
});
t("next frame: fewest labels first, never done or skipped by this person, never two-label frames", () => {
  const counts = { f0: 1, f1: 1, f2: 2, f3: 0 };
  const mine = { f3: { state: "done" }, f4: { state: "skipped" } };
  const seen = new Set();
  for (let i = 0; i < 200; i++) {
    const f = L.pickNext(frames, counts, mine, "Jacob", null);
    if (!f) break;
    assert.ok(!mine[f.frame_id] && (counts[f.frame_id] || 0) < 2);
    seen.add(f.frame_id);
    mine[f.frame_id] = { state: "done" };       // pretend it was saved
    counts[f.frame_id] = (counts[f.frame_id] || 0) + 1;
  }
  assert.ok(!seen.has("f2") && !seen.has("f3") && !seen.has("f4"));
  assert.equal(L.pickNext(frames, counts, mine, "Jacob", null), null);   // nothing left
});
t("next frame: zero-label frames come before one-label frames", () => {
  const counts = {}; for (let i = 0; i < 100; i++) counts[frames[i].frame_id] = i === 7 ? 0 : 1;
  assert.equal(L.pickNext(frames, counts, {}, "Ali", null).frame_id, "f7");
});
t("next frame: stable for one person, different between people", () => {
  const a1 = L.pickNext(frames, {}, {}, "Jacob", null).frame_id, a2 = L.pickNext(frames, {}, {}, "jacob", null).frame_id;
  assert.equal(a1, a2);
  const firsts = new Set(["Jacob", "Ali", "Gina", "Wang", "Adrien"].map((p) => L.pickNext(frames, {}, {}, p, null).frame_id));
  assert.ok(firsts.size >= 4, "five people should mostly start on different frames, got " + [...firsts]);
});
t("next frame: skips the frame being left", () => {
  const first = L.pickNext(frames, {}, {}, "Gina", null).frame_id;
  assert.notEqual(L.pickNext(frames, {}, {}, "Gina", first).frame_id, first);
});
t("fit and clamp: centred when smaller, no empty edge when larger", () => {
  const fit = L.fitScale(1000, 500, 3840, 2160);
  assert.ok(Math.abs(fit - 500 / 2160) < 1e-9);
  let v = L.clampView({ k: 1, x: 500, y: 500 }, 1000, 500, 3840, 2160, fit);
  assert.ok(Math.abs(v.y) < 1e-9 && v.x > 0);                         // centred sideways, full height
  v = L.clampView({ k: 4, x: 100, y: 100 }, 1000, 500, 3840, 2160, fit);
  assert.equal(v.x, 0); assert.equal(v.y, 0);                          // dragged past the edge: pinned
  v = L.clampView({ k: 4, x: -99999, y: -99999 }, 1000, 500, 3840, 2160, fit);
  assert.ok(Math.abs(v.x - (1000 - 3840 * fit * 4)) < 1e-6);
});
t("zoom keeps the point under the cursor fixed and stops at the limits", () => {
  const fit = 0.25, v0 = { k: 1, x: 10, y: 20 };
  const before = [(300 - v0.x) / (fit * v0.k), (200 - v0.y) / (fit * v0.k)];
  const v1 = L.zoomAt(v0, 3, 300, 200, fit);
  const after = [(300 - v1.x) / (fit * v1.k), (200 - v1.y) / (fit * v1.k)];
  assert.ok(Math.abs(before[0] - after[0]) < 1e-9 && Math.abs(before[1] - after[1]) < 1e-9);
  assert.equal(L.zoomAt(v0, 0.01, 0, 0, fit).k, 1);
  assert.equal(L.zoomAt(v0, 1e6, 0, 0, fit).k, 24);
});
t("filters and progress text", () => {
  assert.equal(L.filterString(100, 100, false), "brightness(100%) contrast(100%)");
  assert.match(L.filterString(120, 150, true), /saturate/);
  assert.equal(L.progressText(12, 34, 100), "You: 12 frames. Team: 34 of 100 frames have two labels.");
  assert.equal(L.progressText(1, 0, 100), "You: 1 frame. Team: 0 of 100 frames have two labels.");
  assert.equal(L.fmtTime(125), "2:05");
});
t("species text: cleaned and capped; type-ahead ranks starts first, finds common names and aliases", () => {
  assert.equal(L.cleanSpecies("  Gadus \u0007  morhua\n"), "Gadus morhua");
  assert.equal(L.cleanSpecies("x".repeat(100)).length, 80);
  assert.equal(L.cleanSpecies(null), "");
  const idx = L.buildSpeciesIndex([
    { scientific_name: "Gadus morhua", common_names: ["Atlantic cod", "cod"], aliases: ["Morhua vulgaris"] },
    { scientific_name: "Pollachius virens", common_names: ["Pollock", "coalfish"], aliases: [] },
    { scientific_name: "Scomber scombrus", common_names: ["Atlantic mackerel"], aliases: [] },
    { common_names: ["broken"] }, null,
  ]);
  assert.equal(idx.length, 3);
  assert.equal(L.speciesMatches(idx, "cod")[0].sci, "Gadus morhua");          // starts with "cod"
  assert.equal(L.speciesMatches(idx, "atl").length, 2);                         // "Atlantic cod" and "Atlantic mackerel"
  assert.equal(L.speciesMatches(idx, "coal")[0].sci, "Pollachius virens");
  assert.equal(L.speciesMatches(idx, "vulgaris")[0].sci, "Gadus morhua");       // alias, inside the name
  assert.equal(L.speciesMatches(idx, "zzz").length, 0);
  assert.equal(L.speciesMatches(idx, "").length, 3);
  assert.equal(L.resolveSpecies(idx, "Atlantic Cod"), "Gadus morhua");          // a known name becomes the scientific name
  assert.equal(L.resolveSpecies(idx, "juvenile flatfish?"), "juvenile flatfish?");   // free text stays as typed
  assert.equal(L.resolveSpecies(idx, "   "), "");
});
t("menu placement stays inside the viewport", () => {
  assert.deepEqual(L.clampMenu(100, 100, 190, 140, 1024, 768), { x: 100, y: 100 });
  assert.deepEqual(L.clampMenu(1000, 760, 190, 140, 1024, 768), { x: 1024 - 190 - 6, y: 768 - 140 - 6 });
  assert.deepEqual(L.clampMenu(-50, -50, 190, 140, 1024, 768), { x: 6, y: 6 });
  assert.deepEqual(L.clampMenu(10, 10, 2000, 2000, 1024, 768), { x: 6, y: 6 });   // bigger than the window: top left
});
t("clip time is relative to the count frame, and the count second is half a second either side", () => {
  assert.equal(L.relTime(0, 5), "-5.0 s"); assert.equal(L.relTime(5, 5), "0.0 s"); assert.equal(L.relTime(7.34, 5), "+2.3 s");
  assert.ok(L.inCountWindow(4.5, 5) && L.inCountWindow(5.5, 5) && L.inCountWindow(5, 5));
  assert.ok(!L.inCountWindow(4.49, 5) && !L.inCountWindow(5.51, 5));
  assert.deepEqual(L.SPEEDS, [1, 0.5, 0.25]);
});
t("views are kept in a fixed order with unknown names dropped", () => {
  assert.deepEqual(L.orderedViews(["clip", "frame", "bogus", "movement", "frame"]), ["frame", "movement", "clip"]);
  assert.deepEqual(L.orderedViews(null), []);
});
t("not fish: counts leave them out and the text shows them", () => {
  const pts = [{ kind: "fish" }, { kind: "fish" }, { kind: "invertebrate" }, { kind: "not_fish", category: "algae" }, { kind: "not_fish" }];
  assert.deepEqual(L.countMarks(pts), { fish: 2, invertebrate: 1, unsure: 0, not_fish: 2 });
  assert.equal(L.markCountText(pts, false), "Marked: 2 fish, 1 invertebrate, 0 unsure, 2 not fish");
  assert.equal(L.markCountText([{ kind: "not_fish" }], false), "Marked: 0 fish, 0 invertebrates, 0 unsure, 1 not fish");
  assert.equal(L.markCountText([], false), "No marks yet");
  assert.equal(L.markCountText([], true), "Marked: no animals");
});
t("not fish: only not fish marks counts as no animals", () => {
  assert.ok(L.onlyNotFish([{ kind: "not_fish" }, { kind: "not_fish" }]));
  assert.ok(!L.onlyNotFish([{ kind: "not_fish" }, { kind: "fish" }]));
  assert.ok(!L.onlyNotFish([]));
});
t("not fish: points are cleaned, old points still load", () => {
  assert.deepEqual(L.cleanPoint({ x: 1, y: 2, kind: "not_fish", category: "debris", species: "x" }), { x: 1, y: 2, kind: "not_fish", category: "debris" });
  assert.deepEqual(L.cleanPoint({ x: 1, y: 2, kind: "not_fish", category: "nope" }), { x: 1, y: 2, kind: "not_fish" });
  assert.deepEqual(L.cleanPoint({ x: 1, y: 2, kind: "fish", species: " Gadus  morhua", category: "algae" }), { x: 1, y: 2, kind: "fish", species: "Gadus morhua" });
  assert.deepEqual(L.cleanPoint({ x: 1, y: 2, kind: "invertebrate" }), { x: 1, y: 2, kind: "invertebrate" });
  assert.equal(L.cleanPoint({ x: "a", y: 2 }), null);
  assert.deepEqual(L.NOT_FISH_CATEGORIES.map((c) => c.id), ["algae", "debris", "equipment", "seabed", "bubbles", "other"]);
});

// ---- Unsure ----
t("unsure: its own count, left out of fish and invertebrate, running text matches the brief", () => {
  const pts = [...Array(12).fill({ kind: "fish" }), { kind: "invertebrate" }, ...Array(4).fill({ kind: "unsure" }), ...Array(2).fill({ kind: "not_fish" })];
  assert.deepEqual(L.countMarks(pts), { fish: 12, invertebrate: 1, unsure: 4, not_fish: 2 });
  assert.equal(L.markCountText(pts, false), "Marked: 12 fish, 1 invertebrate, 4 unsure, 2 not fish");
});
t("unsure: stored as kind unsure with no species or category, and old kinds still load", () => {
  assert.ok(L.KINDS.includes("unsure") && L.KINDS.includes("fish"));
  assert.deepEqual(L.cleanPoint({ x: 1, y: 2, kind: "unsure", species: "Gadus", category: "algae" }), { x: 1, y: 2, kind: "unsure" });
  assert.deepEqual(L.cleanPoint({ x: 1, y: 2, kind: "fish", species: "Gadus" }), { x: 1, y: 2, kind: "fish", species: "Gadus" });
});
t("unsure: only unsure and not fish marks count as no confident animals; a fish does not", () => {
  assert.ok(L.noConfidentAnimals([{ kind: "unsure" }, { kind: "not_fish" }]));
  assert.ok(L.noConfidentAnimals([{ kind: "unsure" }]));
  assert.ok(!L.noConfidentAnimals([{ kind: "unsure" }, { kind: "invertebrate" }]));
  assert.ok(!L.noConfidentAnimals([]));
});
t("not fish hint: quiet up to 3, one gentle line above 3", () => {
  const nf = (n) => Array(n).fill({ kind: "not_fish" });
  assert.equal(L.notFishHint(nf(3)), "");
  assert.equal(L.notFishHint([...nf(3), { kind: "unsure" }, { kind: "fish" }]), "");
  const h = L.notFishHint(nf(4));
  assert.ok(h.includes("more than 3") && !h.includes("\n") && !h.includes("\u2014"));
});

// ---- Calibration ----
t("calibration: everyone gets those frames first, in order, whatever the two-label cap says", () => {
  const cal = ["f9", "f3", "f5"];
  const counts = { f9: 2, f3: 5, f5: 0 };            // already over the cap: still offered
  const mine = {};
  const order = [];
  for (let i = 0; i < 3; i++) { const f = L.pickNext(frames, counts, mine, "Ali", null, cal); order.push(f.frame_id); mine[f.frame_id] = { state: "done" }; }
  assert.deepEqual(order, cal);
  const next = L.pickNext(frames, counts, mine, "Ali", null, cal);   // then normal assignment
  assert.ok(next && !cal.includes(next.frame_id) && (counts[next.frame_id] || 0) < 2);
  assert.deepEqual(["Jacob", "Gina"].map((p) => L.pickNext(frames, counts, {}, p, null, cal).frame_id), ["f9", "f9"]);   // same first frame for all
});
t("calibration: not assigned again as normal frames, and an empty list changes nothing", () => {
  const cal = ["f0", "f1"];
  const seen = new Set(); const mine = { f0: { state: "done" }, f1: { state: "done" } };
  for (let i = 0; i < 300; i++) { const f = L.pickNext(frames, {}, mine, "Wang", null, cal); if (!f) break; seen.add(f.frame_id); mine[f.frame_id] = { state: "done" }; }
  assert.ok(!seen.has("f0") && !seen.has("f1") && seen.size === 98);
  assert.equal(L.pickNext(frames, {}, { f0: { state: "done" } }, "Wang", null, ["f0"]) !== null, true);
  assert.equal(L.pickNext(frames, {}, {}, "Jacob", null, []).frame_id, L.pickNext(frames, {}, {}, "Jacob", null).frame_id);
  const skipThis = L.pickNext(frames, {}, {}, "Ali", "f2", ["f2", "f4"]);
  assert.equal(skipThis.frame_id, "f4");               // the exclude rule still works for the prefetch
});
t("calibration: the on-screen label", () => {
  assert.equal(L.calibrationText(["a", "b", "c", "d", "e"], "b"), "Calibration frame 2 of 5");
  assert.equal(L.calibrationText(["a"], "zz"), "");
  assert.equal(L.calibrationText([], "a"), "");
  assert.equal(L.calibrationText(undefined, "a"), "");
});
console.log(n + " checks passed");
