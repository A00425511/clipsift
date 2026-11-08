/* ClipSift label page: shared, blind, label-only mode. No libraries, no network except the same-origin API.
 *
 * Blind: this page only ever asks for this person's own marks. Other people's marks and any model
 * suggestions are never sent to the browser.
 * Identity is a chosen name, not a login (see README, Labelling).
 *
 * The pure helpers at the top are also loaded by Node for tests (deploy/test/label.test.mjs).
 */
(function () {
  "use strict";

  const D = typeof module !== "undefined" && module.exports ? require("./display.js") : window.ClipSiftDisplay;
  const relTime = D.relTime;

  // ---------- pure helpers (no DOM) ----------
  const PRESET_NAMES = ["Jacob", "Ali", "Gina", "Wang", "Adrien"];
  const NEEDED = 2;            // labels wanted per frame
  const DOT_R = 8;             // dot radius on screen, in CSS pixels, whatever the zoom
  const MAX_K = 24;            // most zoom, relative to the fitted view
  const VIEWS = ["frame", "movement", "clip"];   // recorded per label: which views the person used
  const SPECIES_MAX = 80;
  const COUNT_WINDOW_S = 1;    // the designated count second starts at the frame's moment
  const COUNT_TOLERANCE_S = 0.5;   // a fish first seen this close either side may count
  const SPEEDS = [1, 0.5, 0.25];
  // Not fish: hard negatives, things that could fool a computer. Keep ids in step with worker.js and app/server.py.
  const NOT_FISH_CATEGORIES = [
    { id: "algae", label: "Algae or seaweed" }, { id: "debris", label: "Debris" },
    { id: "equipment", label: "Equipment (pole, pipe, tape, frame)" }, { id: "seabed", label: "Seabed or rock" },
    { id: "bubbles", label: "Bubbles or sediment" }, { id: "other", label: "Other" },
  ];
  const KINDS = ["fish", "invertebrate", "unsure", "not_fish"];   // unsure: might be an animal but does not meet the rule; never counted
  const NOT_FISH_SOFT_LIMIT = 3;   // the protocol asks for at most 3 Not fish marks per frame

  function cleanName(v) {
    const n = String(v == null ? "" : v).replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, 40);
    const preset = PRESET_NAMES.find((p) => p.toLowerCase() === n.toLowerCase());
    return preset || n;
  }
  // FNV-1a: a stable pseudo-random number from text, so the order is the same on every visit.
  function hash32(text) {
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h >>> 0;
  }
  // Next frame for this person: fewest labels so far (under 2), not done or skipped by them, then a shuffle
  // that depends on their name so five people do not all land on the same frame.
  // Calibration frames (a list of frame ids) come first, in that order, for everyone, whatever the two-label cap
  // says. They are never offered again as normal frames. After them, normal assignment.
  // `held` frames are never offered as normal frames, to anyone (see heldFrames).
  function pickNext(frames, counts, mine, name, exclude, calibration, calibrationOnly, held) {
    const cal = Array.isArray(calibration) ? calibration : [];
    const hold = Array.isArray(held) ? held : [];
    for (const id of cal) {
      if (id === exclude || mine[id]) continue;
      const f = frames.find((x) => x.frame_id === id);
      if (f) return f;
    }
    if (calibrationOnly) return null;     // the other frames are held back for now
    let best = null, bestKey = null;
    for (const f of frames) {
      const id = f.frame_id;
      if (id === exclude || mine[id] || cal.includes(id) || hold.includes(id)) continue;
      const n = counts[id] || 0;
      if (n >= NEEDED) continue;
      const key = [n, hash32(name.toLowerCase() + "|" + id)];
      if (!bestKey || key[0] < bestKey[0] || (key[0] === bestKey[0] && key[1] < bestKey[1])) { best = f; bestKey = key; }
    }
    return best;
  }
  // Extra frames for one named person, such as demo frames recorded for the team. `personal` is { "lower case name": [frame ids] }.
  // That person gets them after the shared calibration frames. Nobody else is offered them, so a recording cannot unblind a label.
  function calibrationFor(calibration, personal, name) {
    const extra = personal && typeof personal === "object" ? personal[String(name || "").toLowerCase()] : null;
    const list = Array.isArray(calibration) ? calibration : [];
    return Array.isArray(extra) ? list.concat(extra.filter((id) => !list.includes(id))) : list;
  }
  function heldFrames(personal) {
    return personal && typeof personal === "object" ? Object.values(personal).filter(Array.isArray).flat() : [];
  }
  function fitScale(sw, sh, w, h) { return Math.min(sw / w, sh / h); }
  // Keep the picture on screen: centred when smaller than the stage, no empty edge when larger.
  function clampView(v, sw, sh, w, h, fit) {
    const s = fit * v.k, iw = w * s, ih = h * s;
    const x = iw <= sw ? (sw - iw) / 2 : Math.min(0, Math.max(sw - iw, v.x));
    const y = ih <= sh ? (sh - ih) / 2 : Math.min(0, Math.max(sh - ih, v.y));
    return { k: v.k, x, y };
  }
  // Zoom by factor f keeping the image point under (px, py) where it is.
  function zoomAt(v, f, px, py, fit) {
    const k = Math.max(1, Math.min(MAX_K, v.k * f)), s0 = fit * v.k, s1 = fit * k;
    const ix = (px - v.x) / s0, iy = (py - v.y) / s0;
    return { k, x: px - ix * s1, y: py - iy * s1 };
  }
  function filterString(bright, contrast, enhance) {
    const extra = D.enhanceFilter(enhance);
    return "brightness(" + bright + "%) contrast(" + contrast + "%)" + (extra ? " " + extra : "");
  }
  function fmtTime(s) { s = Math.round(s); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); }
  // "Calibration frame 2 of 5" for a calibration frame, "" for any other frame.
  function calibrationText(calibration, frameId) {
    const i = Array.isArray(calibration) ? calibration.indexOf(frameId) : -1;
    return i < 0 ? "" : "Calibration frame " + (i + 1) + " of " + calibration.length;
  }
  // What must be looked at before a frame can be called empty. Only views this frame actually has.
  function missingChecks(views, hasClip, hasMovement) {
    const seen = Array.isArray(views) ? views : [], out = [];
    if (hasClip && !seen.includes("clip")) out.push("the clip");
    if (hasMovement && !seen.includes("movement")) out.push("the Movement view");
    return out;
  }
  function calibrationProgressText(calibration, mine) {
    const done = calibration.filter((id) => mine[id] && mine[id].state === "done").length;
    return "You: " + done + " of " + calibration.length + " calibration frames done.";
  }
  function progressText(myDone, team, total) {
    return "You: " + myDone + (myDone === 1 ? " frame" : " frames") + ". Team: " + team + " of " + total + " frames have two labels.";
  }

  // Species text: control characters out, spaces tidied, at most SPECIES_MAX characters. Empty means none.
  function cleanSpecies(v) {
    return String(v == null ? "" : v).replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, SPECIES_MAX);
  }
  function buildSpeciesIndex(list) {
    const out = [];
    for (const sp of Array.isArray(list) ? list : []) {
      if (!sp || typeof sp.scientific_name !== "string" || !sp.scientific_name) continue;
      const strs = (a) => (Array.isArray(a) ? a.filter((x) => typeof x === "string" && x) : []);
      const commons = strs(sp.common_names), alias = strs(sp.aliases);
      out.push({ sci: sp.scientific_name, common: commons[0] || "", kind: sp.kind || null, label: commons[0] ? commons[0] + " (" + sp.scientific_name + ")" : sp.scientific_name,
        terms: [sp.scientific_name, ...commons, ...alias].map((t) => t.toLowerCase()) });
    }
    return out;
  }
  // Type-ahead: names that start with the text (or a word in it) first, then names that contain it.
  function speciesMatches(index, query, limit) {
    const q = cleanSpecies(query).toLowerCase(), max = limit || 8;
    if (!q) return index.slice(0, max);
    const scored = [];
    for (const it of index) {
      let best = 9;
      for (const t of it.terms) {
        if (t.startsWith(q)) { best = 0; break; }
        if (t.includes(" " + q)) best = Math.min(best, 1);
        else if (t.includes(q)) best = Math.min(best, 2);
      }
      if (best < 9) scored.push([best, it.label, it]);
    }
    scored.sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    return scored.slice(0, max).map((x) => x[2]);
  }
  // Text that exactly matches a known name becomes the scientific name; anything else stays as typed (free text).
  function resolveSpecies(index, text) {
    const t = cleanSpecies(text), low = t.toLowerCase();
    if (!t) return "";
    const hit = index.find((it) => it.terms.includes(low));
    return hit ? hit.sci : t;
  }
  // Put a menu of size w x h at (x, y) but keep it fully inside a viewport of vw x vh.
  function clampMenu(x, y, w, h, vw, vh, margin) {
    const m = margin == null ? 6 : margin;
    return { x: Math.max(m, Math.min(x, vw - w - m)), y: Math.max(m, Math.min(y, vh - h - m)) };
  }
  // Whether a moment in the clip is inside the count second.
  function inCountWindow(t, countS) { return D.inCount(t, countS, COUNT_WINDOW_S); }
  function categoryLabel(id) { const c = NOT_FISH_CATEGORIES.find((x) => x.id === id); return c ? c.label : ""; }
  // A saved or drafted point made safe: known kind (fish if unknown), species only on animals, category only on not_fish.
  function cleanPoint(p) {
    if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) return null;
    const kind = KINDS.includes(p.kind) ? p.kind : "fish", out = { x: p.x, y: p.y, kind };
    if (kind === "unsure") { /* no species, no category */ }
    else if (kind === "not_fish") { if (categoryLabel(p.category)) out.category = p.category; }
    else { const sp = cleanSpecies(p.species); if (sp) out.species = sp; }
    return out;
  }
  // Unsure and Not fish marks are never counted as animals.
  function countMarks(points) {
    const c = { fish: 0, invertebrate: 0, unsure: 0, not_fish: 0 };
    for (const p of points || []) if (p && c[p.kind] != null) c[p.kind]++;
    return c;
  }
  function markCountText(points, noAnimals) {
    if (noAnimals) return "Marked: no animals";
    if (!points || !points.length) return "No marks yet";
    const c = countMarks(points);
    return "Marked: " + c.fish + " fish, " + c.invertebrate + " invertebrate" + (c.invertebrate === 1 ? "" : "s") + ", " + c.unsure + " unsure, " + c.not_fish + " not fish";
  }
  // A gentle one-line hint when there are more Not fish marks than the protocol asks for. "" otherwise.
  function notFishHint(points) {
    if (countMarks(points).not_fish <= NOT_FISH_SOFT_LIMIT) return "";
    return "That is more than " + NOT_FISH_SOFT_LIMIT + " Not fish marks. Keep them for things that truly look like a fish. The pipe and ordinary seabed are handled in software.";
  }
  // True when a frame has marks but none of them is an animal: it counts as a frame with no animals.
  function onlyNotFish(points) { return !!points && points.length > 0 && points.every((p) => p.kind === "not_fish"); }
  // True when none of the marks is a confident animal (only Unsure and Not fish): also a frame with no counted animals.
  function noConfidentAnimals(points) { return !!points && points.length > 0 && points.every((p) => p.kind === "not_fish" || p.kind === "unsure"); }
  function orderedViews(list) { return VIEWS.filter((v) => Array.isArray(list) && list.includes(v)); }

  const api = { calibrationFor, heldFrames, missingChecks, calibrationProgressText, KINDS, NOT_FISH_SOFT_LIMIT, notFishHint, noConfidentAnimals, calibrationText, NOT_FISH_CATEGORIES, categoryLabel, cleanPoint, countMarks, markCountText, onlyNotFish, VIEWS, SPEEDS, cleanSpecies, buildSpeciesIndex, speciesMatches, resolveSpecies, clampMenu, relTime, inCountWindow, orderedViews, PRESET_NAMES, cleanName, hash32, pickNext, fitScale, clampView, zoomAt, filterString, progressText, fmtTime, NEEDED };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  // ---------- page ----------
  const $ = (id) => document.getElementById(id);
  const LS = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage blocked: the page still works */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };
  const S = {
    set: null, frames: [], byId: {}, calibration: [], name: "", counts: {}, mine: {}, team: { frames_with_two: 0 }, total: 0,
    cur: null, points: [], noAnimals: false, seconds: 0, kind: "fish", category: "", undo: [],
    view: { k: 1, x: 0, y: 0 }, fit: 1, motion: false, loadToken: 0,
    saving: false, retryTimer: null, retries: 0, lastInput: Date.now(), draftTimer: null, raf: 0,
    bright: 100, contrast: 100, enhance: "off", restart: true, countOnly: false, stopAfterDrag: false, clip: null, names: "common",
    movement: false, diffOk: false, views: [], speed: 1, spaceStarted: false, hudRaf: 0, playMsg: false,
    speciesIndex: null, menuPoint: null, spChoices: [], spActive: -1, lastPos: [0, 0],
  };
  const pointers = new Map();
  let gesture = null;       // { type: "tap"|"pan"|"pinch", ... }
  let spaceDown = false;

  // ---------- messages ----------
  function msg(text, level, action) {
    const m = $("msg");
    m.textContent = "";
    if (!text) { m.hidden = true; return; }
    m.className = "message" + (level ? " " + level : "");
    m.append(document.createTextNode(text));
    if (action) { const b = document.createElement("button"); b.type = "button"; b.textContent = action.label; b.addEventListener("click", action.fn); m.append(b); }
    m.hidden = false;
  }

  // ---------- network ----------
  async function apiJson(path, init) {
    let r;
    try { r = await fetch(path, Object.assign({ credentials: "same-origin", cache: "no-store" }, init || {})); }
    catch (e) { const err = new Error("No connection to the server."); err.network = true; throw err; }
    let data = null;
    try { data = await r.json(); } catch (e) { /* not JSON */ }
    if (!r.ok) {
      const err = new Error((data && data.error) || ("The server answered " + r.status + "."));
      err.status = r.status; err.network = r.status >= 500 || r.status === 429; throw err;
    }
    return data;
  }
  const q = (o) => Object.entries(o).map(([k, v]) => encodeURIComponent(k) + "=" + encodeURIComponent(v)).join("&");
  async function refreshStatus() {
    const st = await apiJson("/api/labels/status?" + q({ set: S.set, name: S.name }));
    S.counts = st.counts || {}; S.mine = st.mine || {}; S.team = st.team || { frames_with_two: 0 }; S.total = st.total || S.frames.length;
    paintProgress();
  }
  function paintProgress() {
    const myDone = Object.values(S.mine).filter((m) => m.state === "done").length;
    $("progress").textContent = S.calibrationOnly ? calibrationProgressText(calList(), S.mine) : progressText(myDone, S.team.frames_with_two || 0, S.total);
  }

  // ---------- name ----------
  const nameKey = () => "clipsift.label.name";
  function askName() {
    const box = $("who-buttons"); box.textContent = "";
    for (const n of PRESET_NAMES) {
      const b = document.createElement("button"); b.type = "button"; b.textContent = n;
      b.addEventListener("click", () => chooseName(n)); box.append(b);
    }
    $("who-dialog").hidden = false;
  }
  function chooseName(n) {
    n = cleanName(n);
    if (!n) { $("who-text").focus(); return; }
    LS.set(nameKey(), n);
    $("who-dialog").hidden = true;
    if (S.name && S.name.toLowerCase() === n.toLowerCase()) return;
    S.name = n; $("btn-who").textContent = "Labelling as " + n + " (change)";
    start();
  }

  // ---------- drafts: autosave in this browser, so a refresh or a failed save loses nothing ----------
  const calList = () => calibrationFor(S.calibration, S.personal, S.name);
  const heldNow = () => heldFrames(S.personal).concat(S.archived || []);   // archived frames are finished with: nobody gets them, and they leave My frames
  const draftKey = (fid) => "clipsift.label.draft." + S.set + "." + S.name.toLowerCase() + "." + fid;
  const curKey = () => "clipsift.label.current." + S.set + "." + S.name.toLowerCase();
  function saveDraftSoon() {
    clearTimeout(S.draftTimer);
    S.draftTimer = setTimeout(saveDraftNow, 250);
  }
  function saveDraftNow() {
    if (!S.cur) return;
    if (!S.points.length && !S.noAnimals) { LS.del(draftKey(S.cur.frame_id)); return; }
    LS.set(draftKey(S.cur.frame_id), JSON.stringify({ points: S.points, views: orderedViews(S.views), no_animals: S.noAnimals, seconds: S.seconds }));
  }
  function readDraft(fid) {
    try {
      const d = JSON.parse(LS.get(draftKey(fid)) || "null");
      if (d && Array.isArray(d.points)) return d;
    } catch (e) { /* damaged draft: ignore */ }
    return null;
  }

  // ---------- frame loading ----------
  async function openFrame(frame) {
    const token = ++S.loadToken;
    saveDraftNow();
    clearTimeout(S.retryTimer); S.retries = 0;
    S.cur = frame; S.points = []; S.noAnimals = false; S.seconds = 0; S.undo = []; S.views = [];
    $("done-panel").hidden = true; $("loading").hidden = false; setMotion(false); closeMenu(false);
    LS.set(curKey(), frame.frame_id);
    const calText = calibrationText(calList(), frame.frame_id);
    $("frame-info").textContent = (calText ? calText + ". " : "") + "Frame at " + fmtTime(frame.time_s) + " in the video";
    const note = [];
    const draft = readDraft(frame.frame_id);
    if (draft) {
      S.points = draft.points; S.noAnimals = !!draft.no_animals; S.seconds = draft.seconds || 0; S.views = orderedViews(draft.views);
      note.push("Restored your unsaved marks.");
    } else if (S.mine[frame.frame_id]) {
      try {
        const m = await apiJson("/api/labels/mine?" + q({ set: S.set, frame: frame.frame_id, name: S.name }));
        if (token !== S.loadToken) return;
        if (m.exists) { S.points = m.points || []; S.noAnimals = !!m.no_animals; S.seconds = m.seconds || 0; S.views = orderedViews(m.views); note.push(m.skipped ? "You skipped this frame earlier." : "Showing your saved marks. Saving again replaces them."); }
      } catch (e) { msg("Could not load your saved marks: " + e.message, "error"); }
    }
    if (token !== S.loadToken) return;
    S.points = S.points.map(cleanPoint).filter(Boolean);
    const plane = $("plane"), img = $("frame");
    plane.style.width = frame.width + "px"; plane.style.height = frame.height + "px";
    await new Promise((resolve) => {
      img.onload = img.onerror = resolve;
      img.src = frame.frame_url;
    });
    if (token !== S.loadToken) return;
    const clip = $("clip"); clip.src = frame.clip_url || "";
    // Movement view: always starts on the plain frame. A missing or broken file just turns the button off.
    S.movement = false; S.diffOk = false;
    const dimg = $("diff"); dimg.hidden = true;
    dimg.onload = () => { if (token === S.loadToken) { S.diffOk = true; paintViewButtons(); } };
    dimg.onerror = () => { if (token === S.loadToken) { S.diffOk = false; paintViewButtons(); } };
    dimg.removeAttribute("src"); if (frame.diff_url) dimg.src = frame.diff_url;
    paintHudStatic(); paintViewButtons();
    markView("frame");
    $("loading").hidden = true;
    S.view = { k: 1, x: 0, y: 0 }; layout(true);
    paintCount(); paintButtons();
    if (note.length) msg(note.join(" "), "");
    else if ($("msg").classList.contains("error") === false) msg("");
    prefetchNext();
  }
  function prefetchNext() {
    const nxt = pickNext(S.frames, S.counts, S.mine, S.name, S.cur && S.cur.frame_id, calList(), S.calibrationOnly, heldNow());
    if (nxt) { const i = new Image(); i.src = nxt.frame_url; }
  }

  async function goNext() {
    try { await refreshStatus(); } catch (e) { /* use what we have */ }
    const nxt = pickNext(S.frames, S.counts, S.mine, S.name, null, calList(), S.calibrationOnly, heldNow());
    if (nxt) { await openFrame(nxt); return; }
    showDone();
  }
  function showDone() {
    S.loadToken++; saveDraftNow(); S.cur = null; setMotion(false);
    LS.del(curKey());
    $("loading").hidden = true;
    const myDone = Object.values(S.mine).filter((m) => m.state === "done").length;
    $("done-text").textContent = S.calibrationOnly ? "You have finished the calibration frames. Thank you. More frames open after the team debrief. You can look at these frames again and change them." : "Nothing is left for you. You labelled " + myDone + (myDone === 1 ? " frame" : " frames") +
      ". Every other frame already has two labels, or you skipped it. You can look at your own frames again and change them.";
    $("done-panel").hidden = false;
    $("frame-info").textContent = ""; $("mark-count").textContent = "";
    S.points = []; draw(); paintButtons(); paintViewButtons();
  }

  // ---------- view: zoom, pan, dots ----------
  function stageSize() { const st = $("stage"); return [st.clientWidth, st.clientHeight]; }
  function layout(reset) {
    if (!S.cur) return;
    const [sw, sh] = stageSize();
    S.fit = fitScale(sw, sh, S.cur.width, S.cur.height);
    if (reset) S.view = { k: 1, x: 0, y: 0 };
    S.view = clampView(S.view, sw, sh, S.cur.width, S.cur.height, S.fit);
    schedule();
  }
  function schedule() { if (!S.raf) S.raf = requestAnimationFrame(() => { S.raf = 0; render(); }); }
  function render() {
    if (!S.cur) { draw(); return; }
    const s = S.fit * S.view.k;
    const plane = $("plane");
    plane.style.transform = "translate(" + S.view.x + "px," + S.view.y + "px) scale(" + s + ")";
    plane.classList.toggle("zoomed", s > 3);
    draw();
  }
  function draw() {
    const cv = $("dots"), st = $("stage"), dpr = window.devicePixelRatio || 1;
    const w = st.clientWidth, h = st.clientHeight;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const c = cv.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, w, h);
    if (!S.cur) return;
    const s = S.fit * S.view.k;
    for (const p of S.points) {
      const x = S.view.x + p.x * s, y = S.view.y + p.y * s;
      if (x < -20 || y < -20 || x > w + 20 || y > h + 20) continue;
      const inv = p.kind === "invertebrate", nf = p.kind === "not_fish", uns = p.kind === "unsure", col = nf ? "#ff7ad9" : uns ? "#ffb04d" : inv ? "#6fd3ff" : "#ffe94d";
      c.lineJoin = "round"; c.lineCap = "round";
      for (const pass of [0, 1]) {
        c.lineWidth = pass ? 2 : 4.5; c.strokeStyle = pass ? col : "rgba(0,0,0,.85)";
        c.beginPath();
        c.setLineDash(uns ? [3.5, 3.5] : []);          // Unsure: a dashed ring with a question mark, not a solid shape
        if (nf) { const r = DOT_R * 0.9; c.moveTo(x - r, y - r); c.lineTo(x + r, y + r); c.moveTo(x + r, y - r); c.lineTo(x - r, y + r); }   // an X: not a circle or a square
        else if (inv) c.rect(x - DOT_R, y - DOT_R, DOT_R * 2, DOT_R * 2); else c.arc(x, y, uns ? DOT_R + 1.5 : DOT_R, 0, Math.PI * 2);
        c.stroke();
      }
      c.setLineDash([]);
      if (uns) {
        c.font = "bold 12px system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
        c.lineWidth = 3; c.strokeStyle = "rgba(0,0,0,.85)"; c.strokeText("?", x, y + 0.5); c.fillStyle = col; c.fillText("?", x, y + 0.5);
      } else if (!nf) { c.fillStyle = col; c.fillRect(x - 1, y - 1, 2, 2); }
      if (p.species) {      // small badge at the upper right: this mark has a species
        c.beginPath(); c.arc(x + DOT_R * 0.85, y - DOT_R * 0.85, 4, 0, Math.PI * 2);
        c.fillStyle = "#ffffff"; c.fill(); c.lineWidth = 1.5; c.strokeStyle = "#000"; c.stroke();
      }
    }
  }
  function toImage(px, py) { const s = S.fit * S.view.k; return [(px - S.view.x) / s, (py - S.view.y) / s]; }
  function stagePos(e) { const r = $("stage").getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }

  function pushUndo() { S.undo.push(S.points.map((p) => Object.assign({}, p))); if (S.undo.length > 200) S.undo.shift(); }
  function afterChange() { S.noAnimals = false; paintCount(); paintButtons(); saveDraftSoon(); schedule(); }
  function hitDot(px, py) {
    const s = S.fit * S.view.k;
    let hit = -1, best = DOT_R + 4;
    S.points.forEach((p, i) => { const d = Math.hypot(S.view.x + p.x * s - px, S.view.y + p.y * s - py); if (d <= best) { best = d; hit = i; } });
    return hit;
  }
  function clickAt(px, py) {
    if (!S.cur) return;
    if (S.motion) { msg("Stop the clip to add or remove dots. Let go of Space, or press Motion.", "warn"); S.playMsg = true; return; }
    const hit = hitDot(px, py);
    if (hit >= 0) { pushUndo(); S.points.splice(hit, 1); afterChange(); return; }
    const [ix, iy] = toImage(px, py);
    if (ix < 0 || iy < 0 || ix > S.cur.width || iy > S.cur.height) return;
    pushUndo();
    const np = { x: Math.round(ix * 10) / 10, y: Math.round(iy * 10) / 10, kind: S.kind };
    if (S.kind === "not_fish" && S.category) np.category = S.category;
    S.points.push(np);
    afterChange();
  }
  function undo() {
    if (S.motion) { msg("Stop the clip before you change dots.", "warn"); S.playMsg = true; return; }
    if (!S.undo.length) { msg("Nothing to undo.", ""); return; }
    S.points = S.undo.pop(); S.noAnimals = false; paintCount(); paintButtons(); saveDraftSoon(); schedule();
  }
  function clearAll() {
    if (!S.points.length) { msg("No marks to clear.", ""); return; }
    if (!confirm("Remove all " + S.points.length + " of your marks on this frame? Undo (Z) can bring them back until you leave the frame.")) return;
    pushUndo(); S.points = []; afterChange();
  }
  function setKind(k) {
    S.kind = k;
    $("k-fish").setAttribute("aria-pressed", k === "fish"); $("k-inv").setAttribute("aria-pressed", k === "invertebrate"); $("k-nf").setAttribute("aria-pressed", k === "not_fish"); $("k-uns").setAttribute("aria-pressed", k === "unsure");
    $("nf-picker").hidden = k !== "not_fish";
  }
  function setCategory(id) {
    if (!categoryLabel(id)) return;
    S.category = id; LS.set("clipsift.label.category", id);
    for (const b of document.querySelectorAll("#nf-picker [data-cat]")) b.setAttribute("aria-pressed", String(b.dataset.cat === id));
  }
  function buildPicker() {
    const box = $("nf-cats");
    NOT_FISH_CATEGORIES.forEach((c, i) => {
      const b = document.createElement("button"); b.type = "button"; b.dataset.cat = c.id; b.setAttribute("aria-pressed", "false");
      b.append(document.createTextNode(c.label + " "));
      const k = document.createElement("kbd"); k.textContent = String(i + 1); b.append(k);
      b.addEventListener("click", () => setCategory(c.id)); box.append(b);
    });
    const last = LS.get("clipsift.label.category");
    setCategory(categoryLabel(last) ? last : "algae");
  }
  function paintCount() {
    $("mark-count").textContent = markCountText(S.points, S.noAnimals) + (S.points.length && !S.noAnimals ? speciesNote() : "");
    const hint = $("nf-hint"), h = notFishHint(S.points);
    hint.textContent = h; hint.hidden = !h;
  }
  function speciesNote() { const n = S.points.filter((p) => p.species).length; return n ? ", " + n + " with a species" : ""; }
  function paintButtons() {
    const on = !!S.cur && !S.saving;
    for (const id of ["b-save", "b-skip", "b-none", "b-undo", "b-clear"]) $(id).disabled = !on;
  }

  function pointerDown(e) {
    if (e.button > 0 || !S.cur) return;
    $("stage").setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, stagePos(e));
    touched();
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      gesture = { type: "pinch", d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, cx: (a[0] + b[0]) / 2, cy: (a[1] + b[1]) / 2 };
    } else if (pointers.size === 1) {
      const [x, y] = pointers.get(e.pointerId);
      gesture = { type: "tap", x0: x, y0: y, x, y };
    }
  }
  function pointerMove(e) {
    if (!pointers.has(e.pointerId) || !gesture) return;
    const prev = pointers.get(e.pointerId), cur = stagePos(e);
    pointers.set(e.pointerId, cur);
    const [sw, sh] = stageSize();
    if (gesture.type === "pinch" && pointers.size >= 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, cx = (a[0] + b[0]) / 2, cy = (a[1] + b[1]) / 2;
      let v = zoomAt(S.view, d / gesture.d, cx, cy, S.fit);
      v = { k: v.k, x: v.x + (cx - gesture.cx), y: v.y + (cy - gesture.cy) };
      S.view = clampView(v, sw, sh, S.cur.width, S.cur.height, S.fit);
      gesture.d = d; gesture.cx = cx; gesture.cy = cy; schedule(); return;
    }
    if (gesture.type === "tap" && Math.hypot(cur[0] - gesture.x0, cur[1] - gesture.y0) > 5) { gesture.type = "pan"; $("stage").classList.add("panning"); }
    if (gesture.type === "pan") {
      S.view = clampView({ k: S.view.k, x: S.view.x + cur[0] - prev[0], y: S.view.y + cur[1] - prev[1] }, sw, sh, S.cur.width, S.cur.height, S.fit);
      schedule();
    }
  }
  function pointerUp(e) {
    if (!pointers.has(e.pointerId)) return;
    const pos = stagePos(e);
    pointers.delete(e.pointerId);
    const g = gesture;
    if (pointers.size === 0) { gesture = null; $("stage").classList.remove("panning"); }
    else if (pointers.size === 1 && g && g.type === "pinch") gesture = { type: "pan-after-pinch" };
    if (g && g.type === "tap" && e.type === "pointerup") clickAt(pos[0], pos[1]);
  }
  function wheel(e) {
    if (!S.cur) return;
    e.preventDefault(); touched();
    const [px, py] = stagePos(e), [sw, sh] = stageSize();
    const step = Math.exp(-Math.max(-300, Math.min(300, e.deltaY)) * 0.0016);   // smooth for wheels and trackpads
    S.view = clampView(zoomAt(S.view, step, px, py, S.fit), sw, sh, S.cur.width, S.cur.height, S.fit);
    schedule();
  }

  // ---------- display filters ----------
  function applyFilters() {
    const f = filterString(S.bright, S.contrast, S.enhance);
    $("frame").style.filter = f; $("clip").style.filter = f; $("diff").style.filter = f;
    $("s-bright").value = S.bright; $("s-contrast").value = S.contrast;
    for (const b of $("enhance-group").children) b.setAttribute("aria-pressed", String(b.dataset.enhance === S.enhance));
    LS.set("clipsift.label.filters", JSON.stringify({ b: S.bright, c: S.contrast, e: S.enhance }));
  }
  function resetFilters() { S.bright = 100; S.contrast = 100; S.enhance = "off"; applyFilters(); }
  function buildEnhance() {
    for (const p of D.ENHANCE_PRESETS) {
      const b = document.createElement("button"); b.type = "button"; b.dataset.enhance = p.id; b.textContent = p.label; b.title = p.title;
      b.addEventListener("click", () => { S.enhance = p.id; applyFilters(); });
      $("enhance-group").append(b);
    }
  }

  // ---------- views: frame, movement view, clip. Every view sits in the same zoomed and panned plane, so dots line up ----------
  function markView(v) {
    if (!S.cur || S.views.includes(v)) return;
    S.views.push(v); saveDraftSoon();
  }
  function paintViewButtons() {
    const mb = $("b-movement"), has = !!(S.cur && S.cur.diff_url);
    mb.setAttribute("aria-pressed", S.movement);
    mb.disabled = !S.cur || !has || (!S.diffOk && !S.movement);
    mb.title = !has && S.cur ? "No movement view for this frame." : "Black and white view of what changed. Bright areas moved. Marking works in either view. (M)";
    const hasClip = !!(S.cur && S.cur.clip_url);
    $("b-motion").disabled = !hasClip; $("b-jump").disabled = !hasClip;
  }
  function setMovement(on) {
    if (!S.cur || !S.cur.diff_url) return;
    if (on && !S.diffOk) { msg("The movement view is not ready yet or could not be loaded.", "warn"); return; }
    S.movement = on; $("diff").hidden = !on;
    markView(on ? "movement" : "frame");
    paintViewButtons();
  }

  // ---------- motion: the clip plays in the same pane, zoom and pan, with dots above it ----------
  function countS() { return S.cur && Number.isFinite(S.cur.clip_count_s) ? S.cur.clip_count_s : 5; }
  function clipLen() { const v = $("clip"); return v.duration && isFinite(v.duration) ? v.duration : (S.cur && S.cur.clip_length_s) || 10; }
  function paintHudStatic() {
    const len = clipLen(), c = countS();
    const w = $("hud-window");
    const bands = D.countBands(c, COUNT_WINDOW_S, COUNT_TOLERANCE_S, len), tol = $("hud-tol");
    w.style.left = bands.count.left + "%"; w.style.width = bands.count.width + "%";
    tol.style.left = bands.tolerance.left + "%"; tol.style.width = bands.tolerance.width + "%";
    $("hud-speed").textContent = S.speed + "x";
  }
  const playRange = () => D.clipRange(S.countOnly, countS(), COUNT_WINDOW_S, clipLen());
  function paintHud() {
    const v = $("clip"), t = (S.clip ? S.clip.time() : v.currentTime) || 0, len = clipLen(), c = countS();
    $("hud-time").textContent = relTime(t, c);
    $("hud-head").style.left = Math.min(100, t / len * 100) + "%";
    const inWin = inCountWindow(t, c);
    $("hud-count").hidden = !inWin; $("stage").classList.toggle("counting", inWin);
  }
  function hudLoop() { if (!S.motion) { S.hudRaf = 0; return; } S.clip.tick(); paintHud(); S.hudRaf = requestAnimationFrame(hudLoop); }
  function setMotion(on) {
    on = !!on && !!S.cur && !!S.cur.clip_url;
    if (on === S.motion) return;
    S.motion = on;
    const v = $("clip"), r = playRange();
    $("b-motion").setAttribute("aria-pressed", on);
    $("clip-hud").hidden = !on; $("stage").classList.toggle("playing", on);
    if (on) {
      closeMenu(false);
      v.playbackRate = S.speed; markView("clip"); paintHudStatic();
      const outside = v.currentTime < r.start - 0.05 || v.currentTime > r.end;
      if (outside || (S.restart && v.currentTime > r.start + 0.1)) v.currentTime = r.start;   // already rewound on release, so usually nothing to do
      v.play().catch(() => {});
      if (!S.hudRaf) S.hudRaf = requestAnimationFrame(hudLoop);
    } else {
      v.pause();     // back to the exact frame (or the movement view), nothing moved
      if (S.restart) v.currentTime = r.start;   // rewind now, so the next press starts at once
      $("stage").classList.remove("counting"); $("hud-count").hidden = true;
      if (S.playMsg) { S.playMsg = false; msg(""); }
    }
    schedule();
  }
  function setSpeed(r) {
    if (!SPEEDS.includes(r)) r = 1;
    S.speed = r; $("clip").playbackRate = r; $("hud-speed").textContent = r + "x";
    for (const b of document.querySelectorAll("[data-speed]")) b.setAttribute("aria-pressed", String(+b.dataset.speed === r));
    LS.set("clipsift.label.speed", String(r));
  }
  function setRestart(on) {
    S.restart = !!on; $("b-restart").setAttribute("aria-pressed", S.restart);
    LS.set("clipsift.label.restart", S.restart ? "1" : "0");
  }
  function setCountOnly(on) {
    S.countOnly = !!on; $("count-only").setAttribute("aria-pressed", S.countOnly);
    LS.set("clipsift.count_only", S.countOnly ? "1" : "0");
    if (S.cur && !S.motion && S.restart) $("clip").currentTime = playRange().start;
  }
  function jumpToCount() {
    if (!S.cur) return;
    setMotion(true);
    const v = $("clip");
    try { v.currentTime = Math.max(0, countS() - 2); } catch (e) { /* not loaded yet */ }
    paintHud();
  }

  // ---------- right-click menu on a dot ----------
  const menuEl = () => $("ctx-menu");
  const menuOpen = () => !menuEl().hidden;
  function menuItems() { return [...menuEl().querySelectorAll("#cm-main button, #cm-cat button")].filter((b) => !b.hidden && !b.closest("[hidden]")); }
  function placeMenu(x, y) {
    const m = menuEl(), r = m.getBoundingClientRect();
    const pos = clampMenu(x, y, r.width, r.height, document.documentElement.clientWidth, window.innerHeight);
    m.style.left = pos.x + "px"; m.style.top = pos.y + "px";
    m._at = [x, y];
  }
  function openMenu(point, cx, cy) {
    const m = menuEl();
    S.menuPoint = point;
    const nf = point.kind === "not_fish", uns = point.kind === "unsure";
    paintMenuTitle();
    $("cm-to-fish").hidden = point.kind === "fish"; $("cm-to-inv").hidden = point.kind === "invertebrate"; $("cm-to-nf").hidden = nf; $("cm-to-uns").hidden = uns;
    $("cm-category").hidden = !nf; $("cm-species").hidden = nf || uns;
    $("cm-clear").hidden = nf || uns || !point.species;
    $("cm-main").hidden = false; $("cm-sp").hidden = true; $("cm-cat").hidden = true;
    m.hidden = false;
    placeMenu(cx, cy);
    menuItems()[0].focus();
    loadSpecies();
  }
  function speciesItem(sci) { return (S.speciesIndex || []).find((it) => it.sci === sci) || null; }
  function speciesShown(sci) { const it = speciesItem(sci); return it ? D.speciesName(it, S.names) : sci; }
  function paintMenuTitle() {
    const p = S.menuPoint; if (!p) return;
    $("cm-title").textContent = p.kind === "not_fish" ? "Not fish: " + (categoryLabel(p.category) || "no category") : p.kind === "unsure" ? "Unsure" :
      (p.kind === "invertebrate" ? "Invertebrate" : "Fish") + (p.species ? ": " + speciesShown(p.species) : ", no species");
  }
  function setNames(mode) {
    const inp = $("cm-sp-input"), typed = resolveSpecies(S.speciesIndex || [], inp.value);
    S.names = D.cleanNameMode(mode); LS.set("clipsift.species_names", S.names);
    for (const b of document.querySelectorAll("[data-names]")) b.setAttribute("aria-pressed", String(b.dataset.names === S.names));
    if (speciesItem(typed)) inp.value = speciesShown(typed);
    paintMenuTitle();
    if (menuOpen() && !$("cm-sp").hidden) { paintSpChoices(); inp.focus(); }
  }
  function closeMenu(refocus) {
    if (!menuOpen()) { S.menuPoint = null; return; }
    menuEl().hidden = true; S.menuPoint = null;
    if (refocus !== false) { const st = $("stage"); if (st) st.focus({ preventScroll: true }); }
  }
  function editPoint(fn) {
    const p = S.menuPoint, i = p ? S.points.indexOf(p) : -1;
    if (i < 0) { closeMenu(); return; }
    pushUndo(); fn(p, i); afterChange(); closeMenu();
  }
  function showCategories() {
    const box = $("cm-cat-list"); box.textContent = "";
    for (const c of NOT_FISH_CATEGORIES) {
      const b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "menuitem"); b.textContent = c.label;
      if (S.menuPoint && S.menuPoint.category === c.id) b.setAttribute("aria-current", "true");
      b.addEventListener("click", () => editPoint((p) => { p.category = c.id; }));
      box.append(b);
    }
    $("cm-main").hidden = true; $("cm-cat").hidden = false; placeMenu(...menuEl()._at);
    (box.querySelector("[aria-current]") || box.firstChild).focus();
  }
  function showSpeciesBox() {
    $("cm-main").hidden = true; $("cm-sp").hidden = false;
    const inp = $("cm-sp-input"); inp.value = S.menuPoint && S.menuPoint.species ? speciesShown(S.menuPoint.species) : "";
    paintSpChoices(); placeMenu(...menuEl()._at); inp.focus(); inp.select();
  }
  function paintSpChoices() {
    const ul = $("cm-sp-list"), inp = $("cm-sp-input");
    const list = S.speciesIndex && S.menuPoint ? D.forKind(S.speciesIndex, S.menuPoint.kind) : [];
    S.spChoices = speciesMatches(list, inp.value, 50);
    if (!inp.value.trim() && !S.speciesIndex) S.spChoices = [];
    S.spActive = -1; ul.textContent = "";
    S.spChoices.forEach((it, i) => {
      const li = document.createElement("li"); li.id = "cm-sp-" + i; li.setAttribute("role", "option"); li.setAttribute("aria-selected", "false"); li.textContent = D.speciesLabel(it, S.names);
      li.addEventListener("mousedown", (e) => e.preventDefault());
      li.addEventListener("click", () => commitSpecies(it.sci));
      ul.append(li);
    });
    inp.setAttribute("aria-expanded", String(S.spChoices.length > 0)); inp.removeAttribute("aria-activedescendant");
    placeMenu(...menuEl()._at);
  }
  function moveSpActive(d) {
    const n = S.spChoices.length; if (!n) return;
    S.spActive = S.spActive < 0 ? (d > 0 ? 0 : n - 1) : (S.spActive + d + n) % n;
    [...$("cm-sp-list").children].forEach((li, i) => li.setAttribute("aria-selected", String(i === S.spActive)));
    const li = $("cm-sp-list").children[S.spActive]; $("cm-sp-input").setAttribute("aria-activedescendant", li.id); li.scrollIntoView({ block: "nearest" });
  }
  function commitSpecies(text) {
    const val = resolveSpecies(S.speciesIndex || [], text);
    editPoint((p) => { if (val) p.species = val; else delete p.species; });
  }
  async function loadSpecies() {
    if (S.speciesIndex) return;
    S.speciesIndex = [];            // free text still works if the list cannot be read
    for (const url of ["/api/species", "/species_list.json"]) {
      try {
        const r = await fetch(url, { credentials: "same-origin" });
        if (!r.ok) continue;
        const d = await r.json();
        S.speciesIndex = buildSpeciesIndex(Array.isArray(d) ? d : d && d.species);
        if (S.speciesIndex.length) break;
      } catch (e) { /* try the next place */ }
    }
    paintMenuTitle();
    if (menuOpen() && !$("cm-sp").hidden) paintSpChoices();
  }
  function onContextMenu(e) {
    e.preventDefault();                       // never the browser's menu on the frame
    if (!S.cur || S.motion) return;
    let cx = e.clientX, cy = e.clientY;
    if (!cx && !cy) { cx = S.lastPos[0]; cy = S.lastPos[1]; }   // opened from the keyboard: use the last pointer place
    const r = $("stage").getBoundingClientRect(), hit = hitDot(cx - r.left, cy - r.top);
    if (hit < 0) { closeMenu(false); return; }
    openMenu(S.points[hit], cx, cy);
  }
  function wireMenu() {
    const st = $("stage"), m = menuEl();
    st.addEventListener("contextmenu", onContextMenu);
    m.addEventListener("contextmenu", (e) => e.preventDefault());
    st.addEventListener("pointermove", (e) => { S.lastPos = [e.clientX, e.clientY]; });
    // A press anywhere outside the menu closes it. On the picture that press is swallowed, so it does not also place a dot.
    document.addEventListener("pointerdown", (e) => {
      if (!menuOpen() || m.contains(e.target)) return;
      closeMenu(false);
      if (st.contains(e.target)) { e.stopPropagation(); e.preventDefault(); }
    }, true);
    window.addEventListener("blur", () => closeMenu(false)); window.addEventListener("resize", () => closeMenu(false));
    st.addEventListener("wheel", () => closeMenu(false), { passive: true });
    const toKind = (k) => editPoint((p) => {
      const it = speciesItem(p.species);
      p.kind = k;
      if ((k !== "fish" && k !== "invertebrate") || (it && it.kind && it.kind !== k)) delete p.species;   // a crab name cannot stay on a fish mark
      if (k !== "not_fish") delete p.category;
    });
    $("cm-to-fish").addEventListener("click", () => toKind("fish"));
    $("cm-to-inv").addEventListener("click", () => toKind("invertebrate"));
    $("cm-to-nf").addEventListener("click", () => toKind("not_fish"));
    $("cm-to-uns").addEventListener("click", () => toKind("unsure"));
    $("cm-category").addEventListener("click", showCategories);
    $("cm-cat-back").addEventListener("click", () => { $("cm-cat").hidden = true; $("cm-main").hidden = false; placeMenu(...m._at); menuItems()[0].focus(); });
    $("cm-remove").addEventListener("click", () => editPoint((p, i) => { S.points.splice(i, 1); }));
    $("cm-clear").addEventListener("click", () => editPoint((p) => { delete p.species; }));
    $("cm-species").addEventListener("click", showSpeciesBox);
    $("cm-sp-back").addEventListener("click", () => { $("cm-sp").hidden = true; $("cm-main").hidden = false; placeMenu(...m._at); menuItems()[0].focus(); });
    $("cm-sp-ok").addEventListener("click", () => commitSpecies($("cm-sp-input").value));
    $("cm-sp-input").addEventListener("input", paintSpChoices);
    for (const b of document.querySelectorAll("[data-names]")) b.addEventListener("click", () => setNames(b.dataset.names));
    m.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeMenu(); return; }
      if (e.key === "Tab") { closeMenu(false); return; }
      if (e.target.id === "cm-sp-input") {
        if (e.key === "ArrowDown") { e.preventDefault(); moveSpActive(1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); moveSpActive(-1); }
        else if (e.key === "Enter") { e.preventDefault(); commitSpecies(S.spActive >= 0 ? S.spChoices[S.spActive].sci : e.target.value); }
        e.stopPropagation(); return;
      }
      const items = menuItems(), i = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
      else if (e.key === "Home") { e.preventDefault(); items[0].focus(); }
      else if (e.key === "End") { e.preventDefault(); items[items.length - 1].focus(); }
      e.stopPropagation();
    });
  }

  // ---------- saving ----------
  function payload(kind) {
    return { set: S.set, frame: S.cur.frame_id, name: S.name, points: kind === "done" ? S.points : [], views: orderedViews(S.views),
      no_animals: kind === "none", skipped: kind === "skip", seconds: Math.round(S.seconds * 10) / 10 };
  }
  async function commit(kind) {
    if (!S.cur || S.saving) return;
    if (kind === "done" && !S.points.length) { msg("No marks yet. Click each animal you are sure about. If the frame is empty press No animals (N); to leave it, press Skip (S).", "warn"); return; }
    if (kind === "none") {
      const missing = missingChecks(S.views, !!S.cur.clip_url, !!S.cur.diff_url && S.diffOk);
      if (missing.length) { msg("Check " + missing.join(" and ") + " first. Animals are easy to miss in the still.", "warn"); return; }
    }
    if (kind === "none" && noConfidentAnimals(S.points)) kind = "done";   // only Unsure and Not fish marks: the same as no counted animals, saved with the marks kept
    if (kind === "none" && S.points.length) { msg("You have marks on this frame. Clear them first if it really has no animals.", "warn"); return; }
    if (kind === "skip" && S.points.length && !confirm("Skipping throws away your marks on this frame. Skip anyway?")) return;
    clearTimeout(S.retryTimer); setMotion(false); closeMenu(false);
    S.saving = true; paintButtons(); msg("Saving...", "");
    const fid = S.cur.frame_id, body = payload(kind);
    try {
      await apiJson("/api/labels", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    } catch (e) {
      S.saving = false; paintButtons();
      if (e.status && e.status >= 400 && e.status < 500 && e.status !== 429) { msg("Not saved: " + e.message + " Your marks are kept on screen.", "error"); return; }
      scheduleRetry(kind, e.message);
      return;
    }
    S.saving = false; S.retries = 0;
    LS.del(draftKey(fid));
    clearTimeout(S.draftTimer); S.points = []; S.noAnimals = false; S.undo = [];   // so leaving the frame does not write the draft back
    S.mine[fid] = { state: kind === "skip" ? "skipped" : "done", no_animals: kind === "none", n_points: body.points.length };
    msg(kind === "skip" ? "Skipped." : "Saved.", "ok");
    await goNext();
  }
  function scheduleRetry(kind, why) {
    S.retries++;
    const wait = Math.min(30, 3 * S.retries);
    const again = () => { clearTimeout(S.retryTimer); commit(kind); };
    if (S.retries > 6) { msg("Not saved (" + why + "). Your marks are kept in this browser. Check your connection, then press Try again.", "error", { label: "Try again", fn: again }); return; }
    msg("Not saved (" + why + "). Your marks are kept. Trying again in " + wait + " s.", "error", { label: "Try now", fn: again });
    S.retryTimer = setTimeout(again, wait * 1000);
  }

  // ---------- my frames ----------
  function showMine() {
    const list = $("mine-list"); list.textContent = "";
    const rows = S.frames.filter((f) => S.mine[f.frame_id] && !(S.archived || []).includes(f.frame_id) && (!S.calibrationOnly || calList().includes(f.frame_id)));
    if (!rows.length) { const li = document.createElement("li"); li.className = "hint"; li.textContent = "You have not saved any frames yet."; list.append(li); }
    for (const f of rows) {
      const m = S.mine[f.frame_id], li = document.createElement("li"), b = document.createElement("button");
      b.type = "button";
      const what = m.state === "skipped" ? "skipped" : m.no_animals ? "no animals" : m.n_points + (m.n_points === 1 ? " mark" : " marks");
      b.append(document.createTextNode(fmtTime(f.time_s) + "  "));
      const tag = document.createElement("span"); tag.className = "tag" + (m.state === "skipped" ? " skipped" : ""); tag.textContent = what; b.append(tag);
      b.addEventListener("click", () => { $("mine-panel").hidden = true; openFrame(f); });
      li.append(b); list.append(li);
    }
    $("mine-panel").hidden = false;
    $("mine-panel").scrollIntoView({ block: "nearest" });
  }

  // ---------- time on frame: counts only while the tab is visible and the person is active ----------
  function touched() { S.lastInput = Date.now(); }
  setInterval(() => {
    if (S.cur && document.visibilityState === "visible" && Date.now() - S.lastInput < 30000 && !S.saving) S.seconds += 1;
  }, 1000);

  // ---------- keys ----------
  function typing(t) { return t && (t.tagName === "TEXTAREA" || (t.tagName === "INPUT" && t.type !== "range" && t.type !== "checkbox")); }
  document.addEventListener("keydown", (e) => {
    touched();
    if (e.key === "Escape" && menuOpen()) { e.preventDefault(); closeMenu(); return; }
    if (!$("who-dialog").hidden || typing(e.target) || menuEl().contains(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (e.key === " ") { e.preventDefault(); if (!e.repeat && !spaceDown) { spaceDown = true; if (!S.motion) { S.spaceStarted = true; setMotion(true); } } return; }
    if (e.key === "Enter") { if (e.target.tagName === "BUTTON" && e.target.id !== "b-save") return; e.preventDefault(); commit("done"); }
    else if (k === "f") setKind("fish");
    else if (k === "i") setKind("invertebrate");
    else if (k === "x") setKind("not_fish");
    else if (k === "u") setKind("unsure");
    else if (S.kind === "not_fish" && /^[1-9]$/.test(e.key) && NOT_FISH_CATEGORIES[+e.key - 1]) setCategory(NOT_FISH_CATEGORIES[+e.key - 1].id);
    else if (k === "z") undo();
    else if (k === "m") setMovement(!S.movement);
    else if (k === "r") setRestart(!S.restart);
    else if (k === "o") setCountOnly(!S.countOnly);
    else if (k === "c") { S.enhance = D.nextEnhance(S.enhance); applyFilters(); }
    else if (k === "n") commit("none");
    else if (k === "s") commit("skip");
    else if (e.key === "Escape") { $("help-panel").hidden = true; $("btn-help").setAttribute("aria-expanded", "false"); $("mine-panel").hidden = true; }
  });
  function spaceUp() {
    spaceDown = false;
    if (!S.spaceStarted) return;
    S.spaceStarted = false;
    if (S.clip.dragging()) S.stopAfterDrag = true; else setMotion(false);   // let go mid-drag: stop when the mouse lets go too
  }
  document.addEventListener("keyup", (e) => {
    if (e.key !== " ") return;
    if (!typing(e.target) && !menuEl().contains(e.target) && $("who-dialog").hidden) e.preventDefault();   // a focused button must not also "click"
    if (spaceDown) spaceUp();
  });
  window.addEventListener("blur", () => { if (spaceDown) spaceUp(); });
  window.addEventListener("beforeunload", saveDraftNow);

  // ---------- start ----------
  async function loadSet() {
    const params = new URLSearchParams(location.search);
    let setId = params.get("set");
    if (!setId) {
      const idx = await apiJson("/label_sets/index.json").catch(() => null);
      setId = idx && idx.sets && idx.sets[0];
    }
    if (!setId) throw new Error("No label set is installed here yet.");
    const mf = await apiJson("/label_sets/" + encodeURIComponent(setId) + "/manifest.json");
    S.set = setId; S.frames = (mf.frames || []).slice().sort((a, b) => a.time_s - b.time_s); S.total = S.frames.length;
    S.byId = {}; for (const f of S.frames) S.byId[f.frame_id] = f;
    const seen = new Set();
    S.calibrationOnly = mf.calibration_only === true;
    S.archived = (Array.isArray(mf.archived) ? mf.archived : []).filter((id) => S.byId[id]);
    S.personal = {};
    for (const [who, ids] of Object.entries(mf.personal || {})) if (Array.isArray(ids)) S.personal[who.toLowerCase()] = ids.filter((id) => S.byId[id]);
    S.calibration = (Array.isArray(mf.calibration) ? mf.calibration : []).filter((id) => typeof id === "string" && S.byId[id] && !seen.has(id) && seen.add(id));
  }
  async function start() {
    try {
      if (!S.set) await loadSet();
      await refreshStatus();
    } catch (e) { msg("Could not start: " + e.message, "error", { label: "Try again", fn: () => start() }); $("progress").textContent = ""; return; }
    const saved = LS.get(curKey()), f = saved && S.byId[saved];
    const allowed = f && !(S.archived || []).includes(f.frame_id) && (!S.calibrationOnly || calList().includes(f.frame_id));
    if (allowed && (!S.mine[f.frame_id] || readDraft(f.frame_id))) { await openFrame(f); return; }
    await goNext();
  }

  function wire() {
    const st = $("stage");
    st.addEventListener("pointerdown", pointerDown); st.addEventListener("pointermove", pointerMove);
    st.addEventListener("pointerup", pointerUp); st.addEventListener("pointercancel", pointerUp);
    st.addEventListener("wheel", wheel, { passive: false });
    window.addEventListener("resize", () => layout(false));
    if (window.ResizeObserver) new ResizeObserver(() => layout(false)).observe(st);
    $("k-fish").addEventListener("click", () => setKind("fish")); $("k-inv").addEventListener("click", () => setKind("invertebrate")); $("k-nf").addEventListener("click", () => setKind("not_fish")); $("k-uns").addEventListener("click", () => setKind("unsure"));
    buildPicker();
    $("b-undo").addEventListener("click", undo); $("b-clear").addEventListener("click", clearAll);
    $("b-fit").addEventListener("click", () => layout(true));
    $("b-motion").addEventListener("click", () => { S.spaceStarted = false; setMotion(!S.motion); });
    $("b-movement").addEventListener("click", () => setMovement(!S.movement));
    $("b-jump").addEventListener("click", () => { S.spaceStarted = false; jumpToCount(); });
    for (const b of document.querySelectorAll("[data-speed]")) b.addEventListener("click", () => setSpeed(+b.dataset.speed));
    $("clip").addEventListener("loadedmetadata", paintHudStatic);
    wireMenu();
    setSpeed(+LS.get("clipsift.label.speed") || 1);
    $("b-save").addEventListener("click", () => commit("done")); $("b-none").addEventListener("click", () => commit("none")); $("b-skip").addEventListener("click", () => commit("skip"));
    $("s-bright").addEventListener("input", (e) => { S.bright = +e.target.value; applyFilters(); });
    $("s-contrast").addEventListener("input", (e) => { S.contrast = +e.target.value; applyFilters(); });
    buildEnhance();
    $("b-restart").addEventListener("click", () => setRestart(!S.restart));
    $("count-only").addEventListener("click", () => setCountOnly(!S.countOnly));
    S.clip = D.clipControl({ video: $("clip"), track: document.querySelector("#clip-hud .lb-track"), range: playRange, active: () => S.motion, paint: paintHud,
      release: () => { if (S.stopAfterDrag) { S.stopAfterDrag = false; setMotion(false); } else $("clip").play().catch(() => {}); } });
    setCountOnly(LS.get("clipsift.count_only") === "1");
    setRestart(LS.get("clipsift.label.restart") !== "0");
    setNames(LS.get("clipsift.species_names"));
    $("b-reset").addEventListener("click", resetFilters);
    $("btn-help").addEventListener("click", () => { const p = $("help-panel"); p.hidden = !p.hidden; $("btn-help").setAttribute("aria-expanded", String(!p.hidden)); });
    $("help-close").addEventListener("click", () => { $("help-panel").hidden = true; $("btn-help").setAttribute("aria-expanded", "false"); LS.set("clipsift.label.help_seen", "1"); });
    $("btn-mine").addEventListener("click", showMine); $("done-review").addEventListener("click", showMine);
    $("mine-close").addEventListener("click", () => { $("mine-panel").hidden = true; });
    $("btn-who").addEventListener("click", askName);
    $("who-other").addEventListener("submit", (e) => { e.preventDefault(); chooseName($("who-text").value); });
    try { const f = JSON.parse(LS.get("clipsift.label.filters") || "null"); if (f) { S.bright = +f.b || 100; S.contrast = +f.c || 100; S.enhance = f.e === true ? "light" : D.cleanEnhance(f.e); } } catch (e) { /* ignore */ }
    applyFilters(); paintButtons();
  }

  wire();
  if (!LS.get("clipsift.label.help_seen")) { $("help-panel").hidden = false; $("btn-help").setAttribute("aria-expanded", "true"); }
  const remembered = cleanName(LS.get(nameKey()) || "");
  if (remembered) { S.name = remembered; $("btn-who").textContent = "Labelling as " + remembered + " (change)"; start(); }
  else { $("progress").textContent = ""; askName(); }
})();
