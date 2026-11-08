/* ClipSift review UI. Plain JavaScript, no libraries, no network except this server.
   All text from files is inserted with textContent (never innerHTML). */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const D = window.ClipSiftDisplay;
  const DEFAULT_PROTOCOL = { count_window_s: 1, count_tolerance_s: 0.5, qc_share: 0.10, qc_min: 6, qc_max: 12 };
  const STATUS = {
    known: "Species identified by model", fish_unknown: "Fish, species unknown", unclear: "Unclear",
    movement_unidentified: "Movement, unidentified", none: "Nothing detected",
  };
  const DECISION_TEXT = { confirm: "Confirmed", reject: "Rejected", unknown: "Unknown", needs_second_look: "Needs second look" };
  const DECISION_KEYS = { "1": "confirm", "2": "reject", "3": "unknown", "4": "needs_second_look" };
  const CHAR_KEYS = { "1": 0, "2": 1, "3": 2, "4": 3 };

  const S = {
    runId: null, results: null, saved: null, species: [], aliases: [], index: [],
    mode: "sub", selId: null, qc: false, recount: false, step: "count", who: "", whoSet: false,
    guess: { on: false, ready: false, seen: {}, boxes: {} },
    diff: false, grid: false, watch: { species: [], points: false }, big: localStorage.getItem("clipsift.big") === "1", wantStep: null,
    seg: { species: null }, ss: { rows: [] },
    filters: { brightness: 100, contrast: 100, saturation: 100 }, enhance: "off",
    markHistory: [], motion: false, restart: true, countOnly: false, spaceDown: false, spaceStarted: false, held: false, hudRaf: 0, names: "common",
    zoom: { k: 1, x: 0, y: 0 }, tool: "pan", drag: null,
    more: localStorage.getItem("clipsift.moretools") === "1",   // "More tools" toggle, remembered
  };

  // ---------- small helpers ----------
  function el(tag, props, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k === "on") for (const [ev, fn] of Object.entries(v)) e.addEventListener(ev, fn);
      else if (v === true) e.setAttribute(k, "");
      else if (v !== false && v != null) e.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(kid));
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function fmtTime(s) {
    if (s == null || isNaN(s)) return "n/a";
    const m = Math.floor(s / 60), r = s - m * 60;
    return m + ":" + (r < 10 ? "0" : "") + r.toFixed(r % 1 ? 1 : 0);
  }
  const statText = (v) => (/^stat/i.test(String(v)) ? String(v) : "STAT " + v);
  function fmtNum(v, d) { return v == null ? "not computed" : (d != null ? Number(v).toFixed(d) : String(v)); }
  function proto() { return Object.assign({}, DEFAULT_PROTOCOL, (S.results && S.results.protocol) || {}); }
  function message(text, kind) {
    const m = $("message");
    m.textContent = text || "";
    m.className = "message " + (kind || "");
    m.hidden = !text;
    clearTimeout(m._t); if (text && kind !== "error") m._t = setTimeout(() => { m.hidden = true; }, 5000);
  }
  // ---------- data layer: every call to a server or store goes through `Data` ----------
  // Two implementations. FlaskData talks to the local Flask API. DemoData reads static files and keeps
  // all writes in this browser's localStorage (set window.CLIPSIFT_DEMO to turn it on).
  const DEMO = window.CLIPSIFT_DEMO || null;
  async function api(path, opts) {
    let resp;
    try { resp = await fetch(path, opts); } catch (e) { throw new Error(DEMO ? "Cannot reach the server. Check your connection." : "Cannot reach the ClipSift server. Is it still running?"); }
    let body = null;
    try { body = await resp.json(); } catch (e) { /* not JSON */ }
    if (!resp.ok) throw new Error((body && body.error) || ("Request failed (" + resp.status + ")"));
    return body;
  }
  function post(path, data) {
    return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  }
  const enc = encodeURIComponent;
  const FlaskData = {
    demo: false,
    runs: () => api("/api/runs"),
    species: () => api("/api/species"),
    results: (id) => api("/api/runs/" + enc(id) + "/results"),
    saved: (id) => api("/api/runs/" + enc(id) + "/saved"),
    profiles: async () => (await api("/api/profiles")).profiles,
    addProfile: (name) => post("/api/profiles", { name }),
    home: async () => { const [p, r] = await Promise.all([api("/api/progress"), api("/api/interrater")]); return { videos: p.videos, rater: r }; },
    save: (id, kind, data) => post("/api/runs/" + enc(id) + "/" + kind, data),  // reviews, grid_tags, subsample_reviews, recording_notes, point_labels
    addAlias: (data) => post("/api/species/aliases", data),
    feedback: (data) => post("/api/feedback", data),
    mediaUrl: (id, folder, unitId, kind) => "/api/runs/" + enc(id) + "/" + folder + "/" + enc(unitId) + "/" + kind,
    windowUrl: (id) => "/api/runs/" + enc(id) + "/window",
    exportHref: (id, name) => "/api/runs/" + enc(id) + "/" + name,
    download: null,
  };

  const DEMO_FILES = { still: "still.jpg", diff: "diff.jpg", loop: "loop.mp4", context: "context.mp4" };
  const DEMO_PERCENT_DIFF_MAX = 6, DEMO_AGREEMENT = 95;
  // Frames for the blind check on a run made before the pick was recorded: same every time for one run.
  function pickSample(results, runId) {
    const all = (results.subsamples || []).filter((s) => s && s.subsample_id).sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0));
    const marked = all.filter((s) => s.qc_sample).map((s) => s.subsample_id);
    if (marked.length || !all.length) return marked;
    const p = Object.assign({}, DEFAULT_PROTOCOL, results.protocol || {});
    const n = Math.min(all.length, Math.max(p.qc_min, Math.min(p.qc_max, Math.round(p.qc_share * all.length))));
    let seed = 0;
    for (const ch of runId) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    const ids = all.map((s) => s.subsample_id);
    for (let i = ids.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [ids[i], ids[j]] = [ids[j], ids[i]]; }
    const pick = new Set(ids.slice(0, n));
    return all.map((s) => s.subsample_id).filter((id) => pick.has(id));
  }
  const DemoData = (function () {
    const root = (DEMO && DEMO.base) || "/";
    const cache = new Map();
    const key = (id, kind) => "clipsift.demo." + id + "." + kind;
    function load(id, kind) {
      try { const v = JSON.parse(localStorage.getItem(key(id, kind)) || "[]"); return Array.isArray(v) ? v : []; } catch (e) { return []; }
    }
    function store(id, kind, rows) {
      try { localStorage.setItem(key(id, kind), JSON.stringify(rows)); }
      catch (e) { throw new Error("This browser could not store your counts (storage may be full or blocked)."); }
    }
    async function getJson(url) {
      let resp;
      try { resp = await fetch(url); } catch (e) { throw new Error("Cannot reach the server. Check your connection."); }
      if (!resp.ok) throw new Error("Could not load " + url + " (" + resp.status + ")");
      return resp.json();
    }
    const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
    function activeLabels(rows) {
      const live = new Map();
      for (const r of rows) { if (r.op === "remove") live.delete(r.label_id); else if (typeof r.label_id === "string") live.set(r.label_id, r); }
      return [...live.values()];
    }
    function qcAndMeans(results, subReviews, runId) {
      const proto = Object.assign({ qc_max_percent_diff: DEMO_PERCENT_DIFF_MAX, qc_agreement: DEMO_AGREEMENT }, results.protocol || {});
      const limit = proto.qc_max_percent_diff, primary = {}, seconds = {}, qc = {}, final = {};
      for (const r of subReviews) {
        if (r.pass === "primary") primary[r.subsample_id] = r;
        else if (r.pass === "qc_blind" || r.pass === "recount") (seconds[r.subsample_id] = seconds[r.subsample_id] || {})[(r.counter || "").toLowerCase()] = r;
      }
      for (const [sid, rows] of Object.entries(seconds)) if (primary[sid]) qc[sid] = D.assessPoint([primary[sid], ...Object.values(rows)], limit, proto.qc_small_gap);
      const check = D.qcVerdict(pickSample(results, runId), new Set(Object.keys(primary)), qc, limit, proto.qc_agreement);
      for (const [sid, r] of Object.entries(primary)) final[sid] = qc[sid] ? qc[sid].average_fish : r.total_fish_count;
      const mean = (v) => (v.length ? Math.round((v.reduce((x, y) => x + y, 0) / v.length) * 1000) / 1000 : null);
      const fish = Object.values(primary).map((r) => r.total_fish_count).filter((v) => v != null);
      return { latest_primary: primary, qc, qc_check: check, qc_agreement: check.agreement, qc_agreement_target: proto.qc_agreement, n_counted: Object.keys(primary).length,
        n_subsamples: (results.subsamples || []).length, mean_count_reviewed: mean(fish), final_fish: final, mean_count_final: mean(Object.values(final).filter((v) => v != null)) };
    }
    // ---- CSV exports, generated in the browser (mirror app/server.py) ----
    const SEG_COLS = [["recording_id", "Recording folder name."], ["segment_id", "Segment id from results.json."], ["start_s", "Segment start, seconds from the start of the recording."], ["end_s", "Segment end, seconds."], ["kind", "active, or set_aside (no activity found, time is kept)."], ["audit_sample", "true if this set-aside segment was picked at random as a check."], ["status", "Model status: known, fish_unknown, unclear, movement_unidentified, none."], ["motion_score", "Motion score from the pipeline. Blank means not computed."], ["visibility_score", "Visibility score from the pipeline. Blank means not computed."], ["flag_shake", "true if camera shake was flagged."], ["flag_low_visibility", "true if low visibility was flagged."], ["review_priority", "Higher means it was shown earlier in the queue."], ["model_maxn", "Model MaxN: the most fish seen in one frame. A relative index, not abundance."], ["model_mean_count", "Model mean fish per sampled frame. A relative index, not abundance."], ["model_unique_tracks", "Number of separate fish tracks. A relative index, not abundance."], ["decision", "Reviewer decision: confirm, reject, unknown, needs_second_look."], ["species", "Species the reviewer entered. Blank if none."], ["species_free_text", "true if the species was typed and is not in the species list. Check these."], ["count", "Fish count the reviewer entered. A relative index, not abundance."], ["note", "Reviewer note."], ["reviewer", "Reviewer name as typed."], ["reviewed_at", "When the latest decision was saved (UTC)."], ["n_decisions", "How many decisions were saved for this segment. Only the latest is shown here."], ["n_grid_tags", "How many grid cell tags were saved for this segment."]];
    const SUB_COLS = [["Video ID", "Video ID from results.json. Must match the Coastal Action spreadsheet."], ["Subsample", "Subsample point id."], ["Time (s)", "Seconds from the start of the recording."], ["Counter", "Who counted."], ["Pass", "primary, qc_blind (second blind count) or recount."], ["Total fish count", "Fish counted in the designated second. A relative index, not abundance."], ["Invertebrate count", "Invertebrates counted in the designated second. A relative index."], ["Number of species", "Species in this subsample."], ["Unknown/Unable to ID due to visibility", "Count that could not be identified because of visibility."], ["Visibility category", "Water clarity category for this point."], ["Visibility change >= 0.5 m", "yes if visibility changed by 0.5 m or more."], ["Visibility direction", "increasing or decreasing, when it changed."], ["Characteristics ticked", "Of shape, anatomical features, colour or flashes, swimming behaviour."], ["Model guess shown", "after: the model's guess was shown once this count was saved. seen: it was seen before this count was saved."], ["Possible animals not confirmed", "yes if the counter ticked that there may be animals they couldn't confirm. Never counted."], ["Notes", "Reviewer notes."], ["Saved at (UTC)", "When the count was saved."], ["QC percent difference", "Primary vs second count difference. Formula is provisional."], ["QC recount needed", "yes if the difference is over the configured limit."]];
    const csvText = D.csvText;
    async function csvFor(id, name) {
      const results = await this.results(id);
      const rec = results.recording || {};
      const revs = load(id, "subsample_reviews"), info = qcAndMeans(results, revs, id);
      if (name === "export_columns.csv") return csvText(["column", "meaning"], SUB_COLS.concat([["Video summary: MeanCount", "Mean of Total fish count over latest primary counts. A relative index, not abundance."]], SEG_COLS));
      if (name === "export.csv") {
        const vid = rec.video_id || rec.recording_id || id;
        const times = {}; for (const s of results.subsamples || []) times[s.subsample_id] = s.t_s;
        const names = [...new Set(revs.flatMap((r) => Object.keys(r.species_counts || {})))].sort();
        const rows = revs.map((r) => {
          const q = r.pass !== "primary" ? info.qc[r.subsample_id] : null, sc = r.species_counts || {};
          return [vid, r.subsample_id, times[r.subsample_id], r.counter, r.pass, r.total_fish_count, r.invertebrate_count, r.total_species, r.unknown_count, r.visibility_category,
            r.visibility_change == null ? "" : (r.visibility_change ? "yes" : "no"), r.visibility_direction, (r.characteristics || []).join(";"), r.model_guess, D.noteParts(r).possible ? "yes" : "", D.noteParts(r).text, r.at,
            q && q.percent_diff != null ? q.percent_diff : "", q ? (q.recount_needed ? "yes" : "no") : ""].concat(names.map((n) => (n in sc ? sc[n] : "")));
        });
        return csvText(SUB_COLS.map((c) => c[0]).concat(names.map((n) => "Count: " + n)), rows);
      }
      if (name === "export_summary.csv") {
        const notes = load(id, "recording_notes"), n = notes[notes.length - 1] || {}, proto = results.protocol || {};
        const species = new Set(n.species_observed || []);
        for (const r of Object.values(info.latest_primary)) for (const k of Object.keys(r.species_counts || {})) species.add(k);
        const vis = latestVisibility(load(id, "visibility")).map((v) => v.observer + ": " + v.category).join("; ");
        const qcs = Object.values(info.qc);
        const header = ["Video ID", "Transect", "STAT", "Year", "Season", "Window start (s)", "Window end (s)", "Subsamples counted", "Subsamples planned", "MeanCount (fish per subsample, reviewed)", "Species observed", "Number of species", "Juveniles present (1/0)", "Visibility by observer", "QC pairs", "QC recounts needed", "QC agreement (%) (provisional)", "Note"];
        const row = [rec.video_id || rec.recording_id || id, rec.transect, rec.stat, rec.year, rec.season, n.window_start_s != null ? n.window_start_s : proto.window_start_s, n.window_end_s != null ? n.window_end_s : proto.window_end_s,
          info.n_counted, info.n_subsamples, info.mean_count_reviewed, [...species].sort().join("; "), species.size, n.juveniles, vis, qcs.length, qcs.filter((q) => q.recount_needed).length, info.qc_agreement, "Counts are a relative index, not abundance."];
        return csvText(header, [row]);
      }
      if (name === "export_segments.csv") {
        const reviews = load(id, "reviews"), tags = load(id, "grid_tags"), by = {}, nDec = {}, nTags = {};
        for (const r of reviews) { by[r.segment_id] = r; nDec[r.segment_id] = (nDec[r.segment_id] || 0) + 1; }
        for (const t of tags) if (t.segment_id) nTags[t.segment_id] = (nTags[t.segment_id] || 0) + 1;
        const rows = [];
        for (const seg of results.segments || []) {
          const rev = by[seg.segment_id]; if (!rev) continue;
          const f = seg.flags || {}, c = seg.counts || {};
          rows.push([rec.recording_id || id, seg.segment_id, seg.start_s, seg.end_s, seg.kind, seg.audit_sample, seg.status, seg.motion_score, seg.visibility_score, f.shake, f.low_visibility, seg.review_priority, c.maxn, c.mean_count, c.unique_tracks,
            rev.decision, rev.species, rev.species_free_text, rev.count, rev.note, rev.reviewer, rev.at, nDec[seg.segment_id] || 0, nTags[seg.segment_id] || 0]);
        }
        return csvText(SEG_COLS.map((c) => c[0]), rows);
      }
      throw new Error("Unknown export");
    }
    function latestVisibility(rows) { const m = {}; for (const r of rows) m[r.observer] = r; return Object.values(m); }
    return {
      demo: true,
      async profiles() { try { return JSON.parse(localStorage.getItem("clipsift.demo.profiles") || "[]"); } catch (e) { return []; } },
      async addProfile(name) { const list = await this.profiles(); if (!list.some((n) => n.toLowerCase() === name.toLowerCase())) { list.push(name); list.sort(); try { localStorage.setItem("clipsift.demo.profiles", JSON.stringify(list)); } catch (e) { /* storage may be blocked */ } } return { name }; },
      async home() { return { videos: [], rater: { pairs: [], people: [] } }; },
      async runs() { const m = await getJson(root + (DEMO.manifest || "manifest.json")); return { runs: Array.isArray(m.runs) ? m.runs : [] }; },
      async species() {
        let species = [];
        try { const d = await getJson(root + (DEMO.species || "species_list.json")); species = Array.isArray(d) ? d.filter((x) => x && typeof x === "object") : []; } catch (e) { /* the app works with free text */ }
        let aliases = []; try { aliases = JSON.parse(localStorage.getItem("clipsift.demo.aliases") || "[]"); } catch (e) { /* ignore */ }
        return { species, local_aliases: aliases, note: null };
      },
      async results(id) {
        if (!cache.has(id)) cache.set(id, await getJson(root + "runs/" + enc(id) + "/results.json"));
        return cache.get(id);
      },
      async saved(id) {
        const results = await this.results(id);
        const reviews = load(id, "reviews"), sub = load(id, "subsample_reviews"), notes = load(id, "recording_notes"), latest = {};
        for (const r of reviews) if (typeof r.segment_id === "string") latest[r.segment_id] = r;
        return Object.assign({ reviews, latest_review: latest, grid_tags: load(id, "grid_tags"), subsample_reviews: sub, point_labels: activeLabels(load(id, "point_labels")),
          recording_notes: notes, latest_recording_notes: notes.length ? notes[notes.length - 1] : null, visibility: latestVisibility(load(id, "visibility")), review_set: null }, qcAndMeans(results, sub, id));
      },
      async save(id, kind, data) {
        const results = await this.results(id);
        const rec = Object.assign({}, data, { at: nowIso() });
        if (kind === "reviews" || kind === "subsample_reviews") rec.model_version = (results.run || {}).model_version || null;
        if (kind === "subsample_reviews" && !rec.counter) throw new Error("counter is required");
        if (kind === "reviews" && !["confirm", "reject", "unknown", "needs_second_look"].includes(rec.decision)) throw new Error("decision is not valid");
        if (kind === "point_labels" && (rec.op || "add") === "add") { rec.op = "add"; rec.label_id = "pl_" + Math.random().toString(16).slice(2, 14); }
        const rows = load(id, kind); rows.push(rec); store(id, kind, rows);
        return rec;
      },
      async addAlias(d) {
        let a = []; try { a = JSON.parse(localStorage.getItem("clipsift.demo.aliases") || "[]"); } catch (e) { /* ignore */ }
        const rec = Object.assign({}, d, { at: nowIso() }); a.push(rec);
        try { localStorage.setItem("clipsift.demo.aliases", JSON.stringify(a)); } catch (e) { throw new Error("This browser could not store the name."); }
        return rec;
      },
      feedback: (d) => post("/api/feedback", d),
      mediaUrl: (id, folder, unitId, kind) => root + "runs/" + enc(id) + "/" + folder + "/" + enc(unitId) + "/" + DEMO_FILES[kind],
      windowUrl: () => null,
      exportHref: () => "#",
      async download(id, name) {
        const text = await csvFor.call(this, id, name);
        const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
        const a = document.createElement("a"); a.href = url; a.download = id + "_" + name; document.body.append(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
      },
      clearAll() {
        for (const k of Object.keys(localStorage)) if (k.startsWith("clipsift.demo.")) localStorage.removeItem(k);
      },
    };
  })();
  const Data = DEMO ? DemoData : FlaskData;
  const segs = () => (S.results.segments || []).filter((s) => s && s.segment_id);
  const subs = () => (S.results.subsamples || []).filter((s) => s && s.subsample_id);
  const reviewer = () => S.who;
  const isTyping = (t) => t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT") && t.type !== "checkbox" && t.type !== "range";

  // ---------- startup ----------
  async function init() {
    S.who = localStorage.getItem("clipsift.reviewer") || ""; paintWho();
    try {
      const f = JSON.parse(localStorage.getItem("clipsift.filters") || "null");
      if (f) for (const k of Object.keys(S.filters)) if (typeof f[k] === "number") S.filters[k] = f[k];
      const g = JSON.parse(localStorage.getItem("clipsift.grid") || "null");
      if (g) { $("grid-rows").value = g.rows; $("grid-cols").value = g.cols; }
      S.enhance = D.cleanEnhance(localStorage.getItem("clipsift.enhance"));
      S.restart = localStorage.getItem("clipsift.restart") !== "0";
      S.countOnly = localStorage.getItem("clipsift.count_only") === "1";
      S.names = D.cleanNameMode(localStorage.getItem("clipsift.species_names"));
    } catch (e) { /* ignore bad saved settings */ }
    wireStatic();
    paintRestart(); paintNames();
    $("new-video").hidden = !!DEMO;
    $("demo-banner").hidden = !DEMO;
    if (DEMO) $("label-link").classList.remove("adv");   // the team site is where people tag frames
    applyView();
    await loadSpecies();
    try {
      const runs = await fillRuns();
      const want = new URLSearchParams(location.search).get("run");
      S.wantStep = new URLSearchParams(location.search).get("step");
      if (want && runs.some((r) => r.run_id === want)) { $("run-select").value = want; loadRun(want); return; }
      if (DEMO) {
        if (!runs.length) { showEmpty("The demo recordings did not load. Try refreshing the page. If it keeps happening, tell the team with the Feedback button."); return; }
        const first = runs.find((r) => !r.fixture) || runs[0]; $("run-select").value = first.run_id; loadRun(first.run_id); return;
      }
      showHome();
    } catch (e) { showEmpty(e.message); }
  }
  async function fillRuns() {
    const { runs } = await Data.runs(), sel = $("run-select"), keep = sel.value;
    clear(sel);
    if (!runs.length) { sel.append(el("option", { value: "", text: "No runs found" })); return runs; }
    sel.append(el("option", { value: "", text: "Choose a run..." }));
    for (const r of runs) sel.append(el("option", { value: r.run_id, text: r.run_id + (r.fixture ? " (fixture)" : "") + (r.error ? " (unreadable)" : "") }));
    sel.value = keep;
    return runs;
  }
  const PANELS = ["workspace", "summary", "timeline-wrap", "steps", "step-visibility", "step-watch", "step-qc", "step-verify"];
  function showEmpty(text) {
    $("empty").textContent = text; $("empty").hidden = !text;
    if (text) { for (const id of PANELS) $(id).hidden = true; $("home").hidden = true; }
  }

  // ---------- home: open a video, or carry on with one ----------
  async function showHome() {
    setMotion(false);
    for (const id of PANELS) $(id).hidden = true;
    $("empty").hidden = true; $("progress-wrap").hidden = true; $("fixture-badge").hidden = true;
    S.results = null; S.runId = null; S.selId = null; S.whoSet = false; $("run-select").value = "";
    if (DEMO) return;
    $("home").hidden = false; $("run-pick").hidden = true; $("new-video").hidden = true;
    let d;
    try { d = await Data.home(); } catch (e) { message(e.message, "error"); return; }
    const list = $("home-videos"); clear(list);
    const STATUS_WORDS = { no_sample: "", counting: "", waiting_second: "Waiting for a second count", review: "Quality check done, some frames worth a look", pass: "Quality check done" };
    const stage = (v) => ["Visibility " + v.n_visibility + " rated", "Counted " + v.n_counted + " of " + v.n_subsamples, STATUS_WORDS[v.qc_status], v.review_total ? "Model flags " + v.review_done + " of " + v.review_total : ""].filter(Boolean).join(". ");
    const real = d.videos.filter((v) => !v.fixture);
    if (!real.length) list.append(el("li", { class: "hint", text: "No videos yet. Open one to begin." }));
    const ready = (v) => ["pass", "review"].includes(v.qc_status) && v.n_counted >= v.n_subsamples;
    for (const v of real) list.append(el("li", {}, el("button", { type: "button", on: { click: () => { $("run-select").value = v.run_id; loadRun(v.run_id); } } },
      el("span", { text: v.video_id }), el("span", { class: ready(v) ? "hint ready" : "hint", text: ready(v) ? "Ready to sign off" : "In progress" }),
      el("span", { class: "sub", text: stage(v) + (v.mean_count != null ? ". MeanCount " + v.mean_count.toFixed(2) : "") }))));
    const box = $("home-rater"); clear(box);
    if (!d.rater.pairs.length) { box.append(el("p", { class: "hint", text: "Nothing yet. This fills in after the first blind check." })); return; }
    box.append(el("table", { class: "rater-table" },
      el("thead", {}, el("tr", {}, ["People", "Frames", "Within " + d.rater.limit + "%", "Mean difference", "Who counts higher"].map((t) => el("th", { text: t })))),
      el("tbody", {}, d.rater.pairs.map((p) => el("tr", {}, [p.a + " and " + p.b, p.frames, p.within + " of " + p.frames, p.mean_percent_diff + "%",
        p.mean_fish_gap === 0 ? "Level" : (p.mean_fish_gap > 0 ? p.a : p.b) + " by " + Math.abs(p.mean_fish_gap).toFixed(1) + " fish per frame"].map((t) => el("td", { text: String(t) })))))));
  }

  // ---------- who is working: a saved name, asked for each time a video opens ----------
  function paintWho() { $("who-name").textContent = S.who ? "Working as " + S.who : "Choose your name"; }
  function setWho(name) {
    const theirs = S.results && name !== S.who && (S.saved.subsample_reviews || []).some((r) => r.counter === name);
    if (theirs && !confirm(name + " already has counts on this video. Choose this name only if you are " + name + ", because their counts can be changed under it.")) return;
    const opening = !S.whoSet;
    if (S.who && name !== S.who) { resetFilters(); if (S.big) toggleBig(); }   // display settings belong to the person who set them
    S.who = name; S.whoSet = true; S.watch.reveal = false; paintWho();
    try { localStorage.setItem("clipsift.reviewer", name); localStorage.setItem("bank-reviewer", name); } catch (e) { /* storage may be blocked */ }
    $("who-dlg").close();
    if (S.results) { const back = S.qc ? "qc" : S.step; S.selId = null; refreshSaved().then(() => { const go = opening ? firstStep() : back; setStep(locked() && ["count", "report", "verify"].includes(go) ? "qc" : go); if (S.step === "count") maybeTour(); }); }
  }
  async function askWho() {
    const list = await Data.profiles().catch(() => []), box = $("who-list"); clear(box);
    for (const n of list) box.append(el("button", { type: "button", class: n === S.who ? "primary" : "", text: n, on: { click: () => setWho(n) } }));
    $("who-status").textContent = list.length ? "" : "No one is set up yet. Add your name.";
    $("who-cancel").hidden = !S.whoSet;
    if (!$("who-dlg").open) $("who-dlg").showModal();
    if (!list.length) $("who-new").focus();
  }
  async function addWho(e) {
    e.preventDefault();
    const name = $("who-new").value.trim(); if (!name) return;
    try { const r = await Data.addProfile(name); $("who-new").value = ""; setWho(r.name); }
    catch (err) { $("who-status").textContent = err.message; }
  }
  async function loadSpecies() {
    try {
      const d = await Data.species();
      S.species = d.species || []; S.aliases = d.local_aliases || [];
      if (d.note) message(d.note, "warn");
    } catch (e) { S.species = []; S.aliases = []; }
    buildIndex();
  }
  function buildIndex() {
    const idx = [], seen = new Set();
    for (const sp of S.species) {
      const sci = typeof sp.scientific_name === "string" ? sp.scientific_name : "";
      const commons = Array.isArray(sp.common_names) ? sp.common_names.filter((x) => typeof x === "string") : [];
      const alias = Array.isArray(sp.aliases) ? sp.aliases.filter((x) => typeof x === "string") : [];
      for (const a of S.aliases) if (a.maps_to && a.maps_to.toLowerCase() === sci.toLowerCase()) alias.push(a.alias);
      idx.push({ rec: sp, sci, common: commons[0] || "", kind: sp.kind || null, terms: [sci, ...commons, ...alias].filter(Boolean), aliasTerms: alias });
      seen.add(sci.toLowerCase());
    }
    S.index = idx;
  }

  // ---------- load a run ----------
  async function loadRun(id) {
    if (!id) { showHome(); return; }
    message(""); S.whoSet = false; S.watch.reveal = false; S.guess = { on: false, ready: S.guess.ready, seen: {}, boxes: {} };   // the guess starts off for every video
    if (!DEMO && !S.guess.checked) { S.guess.checked = true; api("/api/videos").then((d) => { S.guess.ready = !!d.detector_ready; }).catch(() => {}); } $("home").hidden = true; $("run-pick").hidden = false; $("new-video").hidden = !!DEMO;
    try {
      const [results, saved] = await Promise.all([Data.results(id), Data.saved(id)]);
      S.runId = id; S.results = results; S.saved = saved; S.selId = null;
    } catch (e) { showEmpty(e.message); return; }
    $("empty").hidden = true;
    $("fixture-badge").hidden = !S.results.fixture;
    paintReportBtn();
    for (const id2 of ["export-link", "export-summary-link", "export-dict-link"]) {
      $(id2).href = Data.exportHref(S.runId, $(id2).dataset.export); $(id2).hidden = false;
    }
    S.mode = "sub"; S.qc = false;
    S.grid = true;  // totals per cell are part of counting a school
    setPressed("toggle-grid", S.grid);
    applyView();
    if (S.tool === "pan") setTool("dot");  // new people mark straight away; wheel still zooms
    S.selId = null;
    renderAll();
    fillNotes();
    setStep(firstStep());
    await askWho();
  }
  // Where to pick up: the first step that still needs doing.
  function firstStep() {
    if (S.wantStep) { const s = S.wantStep; if (S.whoSet) S.wantStep = null; return s; }   // kept until the name is chosen
    const rated = (S.saved.visibility || []).map((r) => r.observer);
    if (S.whoSet && rated.length < 3 && !rated.includes(reviewer())) return "visibility";   // each person rates on their own, before anything else
    if (!(S.saved.visibility || []).length) return "visibility";
    if (!S.saved.latest_recording_notes) return "watch";
    return S.saved.n_counted < subs().length ? "count" : "qc";
  }
  async function refreshSaved() {
    S.saved = await Data.saved(S.runId);
    renderChrome();
  }

  // ---------- queue ----------
  function byPriority(a, b) {
    const pa = a.review_priority, pb = b.review_priority;
    if (pa == null && pb == null) return (a.t_s ?? a.start_s ?? 0) - (b.t_s ?? b.start_s ?? 0);
    if (pa == null) return 1;
    if (pb == null) return -1;
    return pb - pa;
  }
  function qcSample() {
    const ids = new Set((S.saved && S.saved.qc_check && S.saved.qc_check.sample) || pickSample(S.results, S.runId));
    return { items: subs().filter((s) => ids.has(s.subsample_id)).sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0)) };
  }
  function queue() {
    if (S.mode === "sub") {
      if (S.qc) return S.recount ? check().recount.slice() : qcSample().items.map((s) => s.subsample_id);
      return subs().slice().sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0)).map((s) => s.subsample_id);   // systematic: time order, never by activity
    }
    return [];
  }
  function unit(id, mode) {
    mode = mode || S.mode;
    return mode === "sub" ? subs().find((s) => s.subsample_id === id) : segs().find((s) => s.segment_id === id);
  }
  const primaryOf = (id) => (S.saved.latest_primary || {})[id];
  const secondOf = (id) => { let r = null; for (const x of S.saved.subsample_reviews || []) if (x.subsample_id === id && x.pass !== "primary" && x.counter === reviewer()) r = x; return r; };
  const check = () => S.saved.qc_check || { sample: [], recount: [], status: "no_sample", n_sample: 0, n_done: 0 };
  const firstCounters = () => new Set(Object.values(S.saved.latest_primary || {}).map((r) => r.counter));
  // Someone who still owes a blind count can't see the first counts, so the steps that show them stay closed.
  function locked() {
    if (!S.saved) return false;
    const c = check(), me = reviewer();
    return c.status === "waiting_second" && !firstCounters().has(me);
  }
  // Someone new to a flagged frame may be about to recount it, so its earlier counts stay folded away until they ask.
  function freshToRecount() {
    const c = check();
    return c.status === "review" && !c.recount.some((id) => S.saved.qc[id].counters.includes(reviewer()));
  }
  function isDone(id) {
    if (S.mode === "sub") return S.qc ? !!secondOf(id) : !!primaryOf(id);
    return !!(S.saved.latest_review || {})[id];
  }

  // ---------- chrome: summary, progress, timeline, queue ----------
  function renderAll() {
    $("steps").hidden = false;
    renderChrome();
  }
  function renderChrome() {
    renderSummary(); renderProgress(); renderTimeline(); renderQueue(); paintSteps();
  }
  // Re-cut a video already set up: same file, new window or spacing.
  async function openRecut() {
    const r = S.results, rec = r.recording || {}, p = r.protocol || {}, src = (rec.source_files || [])[0];
    if (!src) { message("This video's original file isn't recorded, so it can't be re-cut here.", "error"); return; }
    const counted = (S.saved.subsample_reviews || []).length > 0 || (S.saved.point_labels || []).length > 0;
    await setupVideo({ path: src, recutOf: S.runId });
    const set = (id, v) => { if (v != null) $(id).value = v; };
    set("nv-id", rec.video_id); set("nv-start", p.window_start_s); set("nv-end", p.window_end_s);
    set("nv-transect", rec.transect); set("nv-stat", rec.stat); set("nv-year", rec.year); set("nv-season", rec.season); set("nv-date", rec.date);
    const every = p.interval_s;
    if (every && every !== 60) { if (every === 15) $("nv-points").value = "15"; else { $("nv-points").value = "custom"; $("nv-every").value = every; } }
    paintPointCount();
    nvStatus(counted ? "Counting has started on this video, so this makes a new version beside it. The original and its counts stay as they are. Visibility ratings and watch notes carry over."
      : "The new points replace the current ones. Visibility ratings and watch notes carry over.", "");
  }
  function renderSummary() {
    const r = S.results, sm = r.summary || {}, rec = r.recording || {};
    const box = $("summary"); clear(box); box.hidden = false;
    const item = (label, value, adv) => el("div", { class: "stat" + (adv ? " adv" : "") }, el("span", { class: "stat-v", text: value }), el("span", { class: "stat-l", text: label }));
    box.append(
      item("Video", rec.video_id || rec.recording_id || S.runId),
      item("Length", fmtTime(rec.duration_s)),
      item("Analysis window", r.protocol && r.protocol.window_start_s != null ? fmtTime(r.protocol.window_start_s) + " to " + fmtTime(r.protocol.window_end_s) : "n/a"),
      item("Count points", fmtNum(sm.n_subsamples ?? subs().length)),
    );
    const hide = S.qc || locked() || !S.whoSet;
    box.append(item("MeanCount (index)", !S.whoSet ? "hidden until you choose your name" : hide ? "hidden until your blind count is done" : fmtNum(S.saved.mean_count_final ?? S.saved.mean_count_reviewed, 2)));
    const meta = [rec.transect && "Transect " + rec.transect, rec.stat && statText(rec.stat), rec.year, rec.season].filter(Boolean).join(", ");
    if (meta) box.append(el("div", { class: "stat meta", text: meta }));
    if (!DEMO && !S.qc && !locked() && (rec.source_files || []).length) box.append(el("button", { type: "button", class: "quiet", text: "Change window or spacing", title: "Cut new count points from the same video", on: { click: openRecut } }));
  }
  function renderProgress() {
    const wrap = $("progress-wrap"); wrap.hidden = false;
    const ids = queue(), done = ids.filter(isDone).length;
    let t = (S.mode === "sub" ? (S.qc ? "QC counted " : "Counted ") : "Reviewed ") + done + " of " + ids.length;
    if (S.mode === "sub" && !S.qc && !locked() && S.whoSet && S.saved.mean_count_reviewed != null) t += ". MeanCount " + (S.saved.mean_count_final ?? S.saved.mean_count_reviewed).toFixed(2);
    $("progress-text").textContent = t;
    $("progress-bar").max = Math.max(1, ids.length); $("progress-bar").value = done;
  }
  function renderTimeline() {
    const wrap = $("timeline-wrap"), tl = $("timeline"); clear(tl);
    const rec = S.results.recording || {}, list = segs(), ss = subs();
    let dur = rec.duration_s;
    if (!dur) dur = Math.max(1, ...list.map((s) => s.end_s || 0), ...ss.map((s) => s.t_s || 0));
    wrap.hidden = !ss.length || !["count", "blind"].includes(S.step);
    const pct = (v) => Math.max(0, Math.min(100, (v / dur) * 100));
    const p = S.results.protocol || {};
    if (p.window_start_s != null && p.window_end_s != null) {
      const w = el("div", { class: "tl-window", title: "Analysis window " + fmtTime(p.window_start_s) + " to " + fmtTime(p.window_end_s) });
      w.style.left = pct(p.window_start_s) + "%"; w.style.width = pct(p.window_end_s - p.window_start_s) + "%";
      tl.append(w);
    }
    for (const s of []) {
      if (s.start_s == null || s.end_s == null) continue;
      const flagged = !!(s.flags && (s.flags.shake || s.flags.low_visibility));
      const done = !!(S.saved.latest_review || {})[s.segment_id];
      const cls = ["tl-block", s.kind === "set_aside" ? "set" : "active"];
      if (s.audit_sample) cls.push("audit"); if (flagged) cls.push("flagged"); if (done) cls.push("done");
      if (S.mode === "seg" && s.segment_id === S.selId) cls.push("current");
      const label = s.segment_id + ", " + fmtTime(s.start_s) + " to " + fmtTime(s.end_s) + ", " + (s.kind === "set_aside" ? "set aside" : "active") + (s.audit_sample ? ", random check" : "") + (flagged ? ", flagged" : "") + (done ? ", reviewed" : "");
      const b = el("button", { type: "button", class: cls.join(" "), title: label, "aria-label": label, on: { click: () => { S.mode = "seg"; modeChanged(); select(s.segment_id); } } },
        el("span", { class: "tl-mark", text: (s.audit_sample ? "A" : "") + (flagged ? "!" : "") + (done ? "✓" : "") }));
      b.style.left = pct(s.start_s) + "%"; b.style.width = "max(6px," + (pct(s.end_s) - pct(s.start_s)) + "%)";
      tl.append(b);
    }
    for (const s of ss) {
      if (s.t_s == null) continue;
      const done = !!primaryOf(s.subsample_id);
      const label = s.subsample_id + " at " + fmtTime(s.t_s) + (done ? ", counted" : ", not counted");
      const cls = "tl-tick" + (done ? " done" : "") + (S.mode === "sub" && s.subsample_id === S.selId ? " current" : "");
      const b = el("button", { type: "button", class: cls, title: label, "aria-label": label, on: { click: () => { S.mode = "sub"; modeChanged(); select(s.subsample_id); } } });
      b.style.left = pct(s.t_s) + "%";
      tl.append(b);
    }
    const ax = $("timeline-axis"); clear(ax);
    for (let i = 0; i <= 6; i++) { const t = el("span", { text: fmtTime((dur * i) / 6) }); t.style.left = (i / 6) * 100 + "%"; ax.append(t); }
  }
  function badge(text, cls) { return el("span", { class: "badge " + (cls || ""), text }); }
  function renderQueue() {
    const list = $("queue-list"); clear(list);
    const note = $("qc-note");
    note.hidden = !(S.mode === "sub" && S.qc);
    if (!note.hidden) {
      const q = qcSample();
      note.textContent = (S.recount ? "Recount: " + queue().length + (queue().length === 1 ? " frame" : " frames") + " where the counts differ." : "Blind count: " + q.items.length + " frames, picked at random.") + " Earlier counts are hidden.";
    }
    const ids = queue();
    if (!ids.length) {
      list.append(el("li", { class: "empty-li", text: S.mode === "sub" ? "Nothing to count in this recording yet. Try another recording from the Run menu." : "No motion segments to review in this run." }));
      return;
    }
    ids.forEach((id) => {
      const u = unit(id); if (!u) return;
      const done = isDone(id);
      const b = el("button", { type: "button", class: "q-item" + (id === S.selId ? " current" : ""), "aria-current": id === S.selId ? "true" : null, on: { click: () => select(id) } });
      b.append(el("span", { class: "q-id", text: id }));
      if (S.mode === "sub") {
        b.append(el("span", { class: "q-time", text: fmtTime(u.t_s) }));
      } else {
        b.append(el("span", { class: "q-time", text: fmtTime(u.start_s) + " to " + fmtTime(u.end_s) }));
        if (u.audit_sample) b.append(badge("Random check", "audit"));
        else if (u.kind === "set_aside") b.append(badge("Set aside"));
        if (u.status === "movement_unidentified") b.append(badge("Movement, unidentified", "move"));
        else if (u.status) b.append(badge(STATUS[u.status] || u.status));
        if (u.flags && u.flags.shake) b.append(badge("Shake", "flag"));
        if (u.flags && u.flags.low_visibility) b.append(badge("Low visibility", "flag"));
      }
      const r = done && S.mode === "sub" && !S.qc ? primaryOf(id) : null;
      b.append(el("span", { class: "q-done", text: !done ? "" : r && S.whoSet && r.counter === reviewer() ? "✓ " + r.total_fish_count + " fish, " + r.invertebrate_count + " inv" : "✓ done" }));
      list.append(el("li", {}, b));
    });
  }
  function modeChanged() {
    S.selId = null; renderChrome();
  }

  // ---------- selection and media ----------
  function showNoSelection() {
    $("seg-head").textContent = "Nothing to review here yet. Pick another recording from the Run menu, or open More tools to look at motion segments.";
    for (const id of ["audit-banner", "movement-banner", "side-sub", "side-seg"]) $(id).hidden = true;
    $("stage").hidden = true;
  }
  function select(id) {
    const u = unit(id);
    if (!u) return;
    S.selId = id;
    $("workspace").dataset.mode = S.mode;
    $("stage").hidden = false;
    $("side-sub").hidden = S.mode !== "sub"; $("side-seg").hidden = S.mode !== "seg";
    renderQueue(); renderTimeline();
    const cur = $("queue-list").querySelector(".current"); if (cur) cur.scrollIntoView({ block: "nearest" });
    S.diff = false; setPressed("toggle-diff", false); $("movement-hint").hidden = true;
    setMotion(false);
    if (isTyping(document.activeElement)) document.activeElement.blur();   // otherwise Space and the other keys do nothing on the new point
    if (markKind() === "unsure") setMarkKind("fish");   // later marks must not silently go uncounted
    $("p-species").value = "";   // a species from the last point mustn't ride along
    const top = $("stage-wrap").getBoundingClientRect().top;
    if (top < 0 || top > window.innerHeight * 0.5) $("stage-wrap").scrollIntoView({ block: "start" });
    loadMedia(u);
    S.zoom = { k: 1, x: 0, y: 0 }; applyZoom(); $("z-level").textContent = "";   // every point starts at the whole picture
    S.ss.fromMarks = false; S.ss.markSpecies = [];
    $("save-point").textContent = id + " at " + fmtTime(u.t_s);
    $("point-tools").hidden = S.mode !== "sub";
    if (S.mode === "sub") renderSubsample(u); else renderSegment(u);
    renderGrid();
    if (S.mode === "sub") renderLabels(true); else clear($("labels"));
  }
  function mediaUrl(kind) {
    return Data.mediaUrl(S.runId, S.mode === "sub" ? "subsamples" : "segments", S.selId, kind);
  }
  function loadMedia(u) {
    const rec = S.results.recording || {};
    const stage = $("stage");
    if (rec.width && rec.height) stage.style.aspectRatio = rec.width + " / " + rec.height; else stage.style.aspectRatio = "16 / 9";
    showStill();
    const sc = $("stage-clip");
    sc.dataset.ok = "1"; sc.onerror = () => { sc.dataset.ok = ""; setMotion(false); };
    sc.src = mediaUrl(S.mode === "sub" ? "context" : "loop"); sc.load(); sc.playbackRate = currentSpeed();
    applyFilters();
  }
  function showStill() {
    const img = $("still"), miss = $("media-missing");
    miss.hidden = true; img.hidden = false;
    img.onerror = () => { img.hidden = true; miss.hidden = false; miss.textContent = S.diff ? "No movement view for this " + (S.mode === "sub" ? "point" : "segment") + "." : "No still image for this " + (S.mode === "sub" ? "point" : "segment") + "."; };
    img.onload = () => { if (S.mode === "sub") renderLabels(false); };
    img.src = mediaUrl(S.diff ? "diff" : "still");
    img.alt = S.diff ? "Movement view: bright areas changed between frames" : "Still frame";
  }
  function setPressed(id, on) { $(id).setAttribute("aria-pressed", on ? "true" : "false"); }
  function applyFilters() {
    const f = S.filters, extra = D.enhanceFilter(S.enhance);
    const v = "brightness(" + f.brightness + "%) contrast(" + f.contrast + "%) saturate(" + f.saturation + "%)" + (extra ? " " + extra : "");
    $("still").style.filter = v; $("stage-clip").style.filter = v;
    for (const b of $("enhance-group").children) b.setAttribute("aria-pressed", b.dataset.enhance === S.enhance ? "true" : "false");
    for (const k of Object.keys(f)) { $("f-" + k).value = f[k]; $("f-" + k).nextElementSibling.textContent = f[k] + "%"; }
    try { localStorage.setItem("clipsift.filters", JSON.stringify(f)); localStorage.setItem("clipsift.enhance", S.enhance); } catch (e) { /* private mode: keep going */ }
  }
  function resetFilters() {
    S.filters.brightness = 100; S.filters.contrast = 100; S.filters.saturation = 100;  // same object the sliders write to
    S.enhance = "off";
    applyFilters();
    try { localStorage.removeItem("clipsift.filters"); } catch (e) { /* storage may be blocked */ }
  }
  const settingsPayload = () => Object.assign({}, S.filters, { enhance: S.enhance });

  // ---------- motion: hold Space and the clip plays in the picture, same zoom, marks on top ----------
  const countSec = () => proto().count_window_s;   // see docs/PROTOCOL_WORKFLOW.md: this starts at the point
  function clipLen() { const v = $("stage-clip"); return v.duration && isFinite(v.duration) ? v.duration : 10; }
  const clipRange = () => D.clipRange(S.countOnly, S.mode === "sub" ? countOffset() : null, countSec(), clipLen());
  function paintHud() {
    const v = $("stage-clip"), t = (S.clip ? S.clip.time() : v.currentTime) || 0, len = clipLen(), off = S.mode === "sub" ? countOffset() : null;
    const w = $("hud-window"), tol = $("hud-tol"); w.hidden = tol.hidden = off == null;
    if (off != null) {
      const b = D.countBands(off, countSec(), proto().count_tolerance_s, len);
      w.style.left = b.count.left + "%"; w.style.width = b.count.width + "%"; tol.style.left = b.tolerance.left + "%"; tol.style.width = b.tolerance.width + "%";
    }
    $("hud-time").textContent = off != null ? D.relTime(t, off) : t.toFixed(1) + " s";
    $("motion-btn").firstChild.textContent = !S.motion ? "Play clip " : (v.paused ? "Back to still " : "Stop clip ");
    $("hud-speed").textContent = currentSpeed() + "x";
    $("hud-head").style.left = Math.min(100, (t / len) * 100) + "%";
    const inWin = off != null && D.inCount(t, off, countSec());
    $("hud-count").hidden = !inWin; $("stage").classList.toggle("counting", inWin);
  }
  function hudLoop() { if (!S.motion) { S.hudRaf = 0; return; } S.clip.tick(); paintHud(); S.hudRaf = requestAnimationFrame(hudLoop); }
  function setMotion(on) {
    const v = $("stage-clip");
    on = !!on && !!S.selId && v.dataset.ok === "1";
    S.held = false;
    if (on === S.motion) return;
    S.motion = on;
    $("clip-hud").hidden = !on; $("stage").classList.toggle("playing", on); setPressed("motion-btn", on);
    $("motion-btn").firstChild.textContent = on ? "Stop clip " : "Play clip ";
    const r = clipRange();
    if (on) {
      v.playbackRate = currentSpeed();
      const outside = v.currentTime < r.start - 0.05 || v.currentTime > r.end;
      if (outside || (S.restart && v.currentTime > r.start + 0.1)) v.currentTime = r.start;   // already rewound on release, so usually nothing to do
      v.play().catch(() => {});
      if (!S.hudRaf) S.hudRaf = requestAnimationFrame(hudLoop);
    } else {
      v.pause();     // back to the exact still, nothing moved
      if (S.restart) v.currentTime = r.start;   // rewind now, so the next press starts at once
      $("stage").classList.remove("counting"); $("hud-count").hidden = true;
    }
  }
  function paintRestart() { setPressed("hold-restart", S.restart); }
  function setRestart(on) {
    S.restart = !!on; paintRestart();
    try { localStorage.setItem("clipsift.restart", S.restart ? "1" : "0"); } catch (e) { /* storage may be blocked */ }
  }
  function setCountOnly(on) {
    S.countOnly = !!on; setPressed("count-only", S.countOnly);
    try { localStorage.setItem("clipsift.count_only", S.countOnly ? "1" : "0"); } catch (e) { /* storage may be blocked */ }
    if (S.selId) { const v = $("stage-clip"), r = clipRange(); if (!S.motion && S.restart) v.currentTime = r.start; }
  }
  function spaceUp() {
    if (!S.spaceDown) return;
    S.spaceDown = false;
    if (!S.spaceStarted) return;
    S.spaceStarted = false;
    if (!S.clip.dragging() && !S.held) setMotion(false);   // a scrubbed or stepped frame stays put until Space is pressed again
  }

  // ---------- species names: shown as common or scientific, always saved as scientific ----------
  const shownName = (sci) => { const it = S.index.find((x) => x.sci === sci); return it ? D.speciesName(it, S.names) : sci; };
  const markKind = () => document.querySelector("input[name=pkind]:checked").value;
  function paintNames() { for (const b of document.querySelectorAll("[data-names]")) b.setAttribute("aria-pressed", b.dataset.names === S.names ? "true" : "false"); }
  function setNames(mode) {
    S.names = D.cleanNameMode(mode); paintNames();
    try { localStorage.setItem("clipsift.species_names", S.names); } catch (e) { /* storage may be blocked */ }
    for (const id of ["p-species", "species"]) { const r = resolve($(id).value); if (r) $(id).value = D.speciesName(r, S.names); }
    if (S.results && S.selId) { if (S.mode === "sub") paintSpeciesRows(); else paintSpeciesStatus(); }
  }
  // A species from the other list must not ride along on the next mark.
  function kindChanged() {
    const k = markKind(), r = resolve($("p-species").value), box = $("p-species");
    if (k === "unsure" || (r && r.kind && r.kind !== k)) box.value = "";
    box.disabled = k === "unsure";
    box.placeholder = k === "unsure" ? "No species for Unsure" : (k === "invertebrate" ? "Invertebrate" : "Fish") + " species (optional)";
  }
  function setMarkKind(k) { document.querySelector('input[name=pkind][value="' + k + '"]').checked = true; kindChanged(); }

  // ---------- grid (optional tool) ----------
  function gridSize() {
    const c = (id) => Math.max(1, Math.min(20, parseInt($(id).value, 10) || 1));
    return [c("grid-rows"), c("grid-cols")];
  }
  function tagsFor() {
    const key = S.mode === "sub" ? "subsample_id" : "segment_id";
    return (S.saved.grid_tags || []).filter((t) => t[key] === S.selId);
  }
  function renderGrid() {
    const g = $("grid"); clear(g);
    g.hidden = !S.grid;
    g.classList.toggle("passive", S.mode === "sub");
    setPressed("toggle-grid", S.grid);
    $("grid-hint").textContent = S.grid ? (S.mode === "sub" ? "Totals per cell update as you mark animals." : "Click a cell to tag it. Tags save at once and cannot be undone here.") : "";
    if (!S.grid) return;
    const [rows, cols] = gridSize();
    localStorage.setItem("clipsift.grid", JSON.stringify({ rows, cols }));
    g.style.gridTemplateRows = "repeat(" + rows + ",1fr)"; g.style.gridTemplateColumns = "repeat(" + cols + ",1fr)";
    if (S.mode === "sub") {
      const totals = cellTotals(rows, cols);
      for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
        const n = totals[r][c];
        g.append(el("div", { class: "cell" + (n ? " tagged" : ""), "aria-label": "Row " + (r + 1) + ", column " + (c + 1) + ", " + n + " marked" }, el("span", { class: "cell-n", text: n ? String(n) : "" })));
      }
      return;
    }
    const tags = tagsFor().filter((t) => t.grid && t.grid[0] === rows && t.grid[1] === cols);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const n = tags.filter((t) => t.cell[0] === r && t.cell[1] === c).reduce((a, t) => a + (t.count || 1), 0);
      g.append(el("button", { type: "button", class: "cell" + (n ? " tagged" : ""), "aria-label": "Row " + (r + 1) + ", column " + (c + 1) + ", " + n + " tagged", on: { click: () => tagCell(r, c, rows, cols) } },
        el("span", { class: "cell-n", text: n ? String(n) : "" })));
    }
  }
  async function tagCell(r, c, rows, cols) {
    const payload = { grid: [rows, cols], cell: [r, c], count: 1, reviewer: reviewer() || null };
    if (S.mode === "sub") { payload.subsample_id = S.selId; payload.species = null; }
    else { payload.segment_id = S.selId; payload.species = S.seg.species ? S.seg.species.value : null; }
    const u = unit(S.selId);
    payload.time_s = S.mode === "sub" ? u.t_s : u.still_time_s;
    try {
      const rec = await Data.save(S.runId, "grid_tags", payload);
      S.saved.grid_tags.push(rec); renderGrid();
    } catch (e) { message("Tag not saved: " + e.message, "error"); }
  }

  // ---------- point tool (main counting tool for schools) ----------
  const NS = "http://www.w3.org/2000/svg";
  function dims() {
    const r = S.results.recording || {}, im = $("still");
    return [r.width || im.naturalWidth || 1600, r.height || im.naturalHeight || 900];
  }
  function myLabels() {
    const me = reviewer();
    return (S.saved.point_labels || []).filter((l) => l.subsample_id === S.selId && l.counter === me);
  }
  function labelCenter(l) { return l.w != null && l.h != null ? [l.x + l.w / 2, l.y + l.h / 2] : [l.x, l.y]; }
  function cellTotals(rows, cols) {
    const [W, H] = dims(), t = Array.from({ length: rows }, () => new Array(cols).fill(0));
    for (const l of myLabels().filter((x) => x.kind !== "unsure")) {
      const [cx, cy] = labelCenter(l);
      t[Math.min(rows - 1, Math.max(0, Math.floor((cy / H) * rows)))][Math.min(cols - 1, Math.max(0, Math.floor((cx / W) * cols)))] += 1;
    }
    return t;
  }
  function qcBlocked() {
    const f = primaryOf(S.selId);
    return S.qc && !S.recount && f && f.counter === reviewer();
  }
  function renderLabels(feed) {
    const svg = $("labels"); clear(svg);
    if (S.mode !== "sub" || !S.selId) return;
    const [W, H] = dims();
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    const blocked = qcBlocked();
    const labels = blocked ? [] : myLabels();
    const rad = (6 * W) / Math.max(200, $("stage").clientWidth) / S.zoom.k;
    const g = !S.qc && S.guess.boxes[S.selId];
    if (g) for (const b of g.boxes) {
      const n = document.createElementNS(NS, "rect");
      n.setAttribute("x", b[0]); n.setAttribute("y", b[1]); n.setAttribute("width", b[2]); n.setAttribute("height", b[3]);
      n.setAttribute("class", "mark guess"); n.setAttribute("vector-effect", "non-scaling-stroke");
      const t = document.createElementNS(NS, "title"); t.textContent = "Model guess, score " + b[4]; n.append(t); svg.append(n);
    }
    if (S.showOthers && othersVisible()) for (const l of (S.saved.point_labels || []).filter((x) => x.subsample_id === S.selId && x.counter !== reviewer() && x.kind !== "unsure")) {
      const [cx, cy] = labelCenter(l), n = document.createElementNS(NS, "circle");
      n.setAttribute("cx", cx); n.setAttribute("cy", cy); n.setAttribute("r", rad * 1.6); n.setAttribute("class", "mark other"); n.setAttribute("vector-effect", "non-scaling-stroke");
      const t = document.createElementNS(NS, "title"); t.textContent = l.counter + ": " + l.kind; n.append(t); svg.append(n);
    }
    for (const l of labels) {
      const inv = l.kind === "invertebrate", cls = "mark " + (l.kind === "unsure" ? "uns" : inv ? "inv" : "fish");
      let n;
      if (l.w != null && l.h != null) {
        n = document.createElementNS(NS, l.shape === "ellipse" ? "ellipse" : "rect");
        if (l.shape === "ellipse") { n.setAttribute("cx", l.x + l.w / 2); n.setAttribute("cy", l.y + l.h / 2); n.setAttribute("rx", l.w / 2); n.setAttribute("ry", l.h / 2); }
        else { n.setAttribute("x", l.x); n.setAttribute("y", l.y); n.setAttribute("width", l.w); n.setAttribute("height", l.h); }
      } else if (inv) {
        n = document.createElementNS(NS, "rect");
        n.setAttribute("x", l.x - rad); n.setAttribute("y", l.y - rad); n.setAttribute("width", rad * 2); n.setAttribute("height", rad * 2);
      } else {
        n = document.createElementNS(NS, "circle"); n.setAttribute("cx", l.x); n.setAttribute("cy", l.y); n.setAttribute("r", rad);
      }
      n.setAttribute("class", cls + (l.w != null ? " big" : "")); n.setAttribute("vector-effect", "non-scaling-stroke");
      svg.append(n);
    }
    const fish = labels.filter((l) => l.kind === "fish").length, inv = labels.filter((l) => l.kind === "invertebrate").length, uns = labels.length - fish - inv;
    $("p-totals").textContent = blocked ? "Use a different name for the blind second count." : (labels.length ? "Marked: " + fish + " fish, " + inv + " invertebrates" + (uns ? ", " + uns + " Unsure (not counted)" : "") : "No marks yet. Click an animal on the picture to place a dot.");
    if (feed && !blocked && (labels.length || S.ss.fromMarks)) {   // once marks set the totals, they keep them in step, down to 0
      S.ss.fromMarks = labels.length > 0 || S.ss.fromMarks;
      if (!labels.length) S.ss.rows = S.ss.rows.filter((r) => !S.ss.markSpecies || !S.ss.markSpecies.includes(r.name));
      $("c-fish").value = fish; $("c-inv").value = inv;
      const withSp = labels.filter((l) => l.species);
      S.ss.markSpecies = [...new Set(withSp.map((l) => l.species))];
      if (withSp.length) {
        const m = {}; for (const l of withSp) m[l.species] = (m[l.species] || 0) + 1;
        S.ss.rows = Object.entries(m).map(([name, n2]) => ({ name, n: n2, free: !resolve(name) })); paintSpeciesRows();
      }
      paintCharsWarn(); paintSpeciesSum();
    }
    if (S.grid) renderGrid();
  }
  function applyZoom() {
    const z = S.zoom, st = $("stage");
    if (z.k <= 1) { z.k = 1; z.x = 0; z.y = 0; }
    z.x = Math.min(0, Math.max(st.clientWidth * (1 - z.k), z.x)); z.y = Math.min(0, Math.max(st.clientHeight * (1 - z.k), z.y));
    $("zoom").style.transform = "translate(" + z.x + "px," + z.y + "px) scale(" + z.k + ")";
  }
  function zoomBy(f, cx, cy) {
    const st = $("stage"), z = S.zoom, nk = Math.max(1, Math.min(12, z.k * f));
    cx = cx ?? st.clientWidth / 2; cy = cy ?? st.clientHeight / 2;
    z.x = cx - (cx - z.x) * (nk / z.k); z.y = cy - (cy - z.y) * (nk / z.k); z.k = nk;
    applyZoom(); renderLabels(false);
    $("z-level").textContent = S.zoom.k > 1.01 ? S.zoom.k.toFixed(1) + "x" : "";
  }
  function setTool(t) {
    S.tool = t;
    document.querySelectorAll("[data-tool]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.tool === t ? "true" : "false"));
    $("stage").classList.remove("tool-pan", "tool-dot", "tool-ellipse", "tool-box"); $("stage").classList.add("tool-" + t);
  }
  function toImage(e) {
    const r = $("zoom").getBoundingClientRect(), [W, H] = dims();
    return [Math.max(0, Math.min(W, ((e.clientX - r.left) / r.width) * W)), Math.max(0, Math.min(H, ((e.clientY - r.top) / r.height) * H))];
  }
  async function addLabel(shape, x, y, w, h) {
    if (!reviewer()) { askWho(); return; }
    if (qcBlocked()) { message("Use a different name for the blind second count.", "error"); return; }
    const typed = $("p-species").value.trim(), known = resolve(typed);
    const payload = { subsample_id: S.selId, counter: reviewer(), op: "add", shape, kind: markKind(), species: (known ? known.sci : typed) || null, x, y };
    const u = unit(S.selId, "sub");   // marked on a paused clip frame: keep the moment it was seen
    if (S.motion && u && u.context_start_s != null) payload.time_s = Math.round((u.context_start_s + $("stage-clip").currentTime) * 100) / 100;
    if (shape !== "point") { payload.w = w; payload.h = h; }
    try {
      const rec = await Data.save(S.runId, "point_labels", payload);
      S.saved.point_labels = (S.saved.point_labels || []).concat([rec]);
      S.markHistory.push({ type: "add", label: rec });
      renderLabels(true);
    } catch (err) { message("Mark not saved: " + err.message, "error"); }
  }
  // Which of my marks is under this image point? Dots use their on-screen size so zoomed-in clicks stay easy.
  function labelAt(x, y) {
    const [W] = dims(), rad = (6 * W) / Math.max(200, $("stage").clientWidth) / S.zoom.k, reach = rad * 1.6;
    let best = null, bestD = Infinity;
    for (const l of myLabels()) {
      if (l.w != null && l.h != null) {
        if (x >= l.x && x <= l.x + l.w && y >= l.y && y <= l.y + l.h) { const d = Math.hypot(x - (l.x + l.w / 2), y - (l.y + l.h / 2)); if (d < bestD) { best = l; bestD = d; } }
      } else {
        const d = Math.hypot(x - l.x, y - l.y);
        if (d <= reach && d < bestD) { best = l; bestD = d; }
      }
    }
    return best;
  }
  async function removeLabel(l) {
    try {
      await Data.save(S.runId, "point_labels", { subsample_id: S.selId, counter: reviewer(), op: "remove", label_id: l.label_id });
      S.saved.point_labels = (S.saved.point_labels || []).filter((x) => x.label_id !== l.label_id);
      S.markHistory.push({ type: "remove", label: l });
      renderLabels(true);
      message("Mark removed. Press Z to bring it back.", "");
    } catch (err) { message("Could not remove that mark: " + err.message, "error"); }
  }
  async function clearAllLabels() {
    if (S.mode !== "sub") return;
    const mine = myLabels(); if (!mine.length) { message("No marks to clear.", ""); return; }
    if (!confirm("Remove all " + mine.length + " of your marks on this picture? Undo will not bring them back.")) return;
    try {
      for (const l of mine) {
        await Data.save(S.runId, "point_labels", { subsample_id: S.selId, counter: reviewer(), op: "remove", label_id: l.label_id });
        S.saved.point_labels = S.saved.point_labels.filter((x) => x.label_id !== l.label_id);
      }
      message("Cleared " + mine.length + " marks. The totals follow the marks.", "ok");
    } catch (err) { message("Clearing stopped partway: " + err.message, "error"); }
    renderLabels(true);
  }
  async function undoLabel() {
    if (S.mode !== "sub") return;
    // The latest add or removal on this point, by this person, in this session.
    let at = S.markHistory.length - 1;
    while (at >= 0 && !(S.markHistory[at].label.subsample_id === S.selId && S.markHistory[at].label.counter === reviewer())) at--;
    const step = at >= 0 ? S.markHistory.splice(at, 1)[0] : null;
    if (step && step.type === "remove") {
      const { subsample_id, counter, shape, kind, species, x, y, w, h } = step.label;
      try {
        const rec = await Data.save(S.runId, "point_labels", Object.assign({ subsample_id, counter, op: "add", shape, kind, species, x, y }, w != null ? { w, h } : {}));
        S.saved.point_labels = (S.saved.point_labels || []).concat([rec]);
        renderLabels(true); message("Mark brought back.", "");
      } catch (err) { message("Undo failed: " + err.message, "error"); }
      return;
    }
    const mine = myLabels(); if (!mine.length) { message("Nothing to undo.", ""); return; }
    const last = step ? (mine.find((l) => l.label_id === step.label.label_id) || mine[mine.length - 1]) : mine[mine.length - 1];
    try {
      await Data.save(S.runId, "point_labels", { subsample_id: S.selId, counter: reviewer(), op: "remove", label_id: last.label_id });
      S.saved.point_labels = S.saved.point_labels.filter((l) => l.label_id !== last.label_id);
      renderLabels(true);
    } catch (err) { message("Undo failed: " + err.message, "error"); }
  }
  function wireTools() {
    const st = $("stage");
    st.addEventListener("pointerdown", (e) => {
      if (S.mode !== "sub" || e.button > 1 || (e.button === 0 && e.ctrlKey) || !$("still").complete) return;   // Ctrl+click is a right-click on a Mac
      const middle = e.button === 1;
      if (S.motion && S.tool !== "pan" && !middle && !$("stage-clip").paused) { message("Pause the clip, or let go of Space, to add or remove marks.", "warn"); return; }
      if (S.tool === "pan" || middle) { S.drag = { type: "pan", x: e.clientX, y: e.clientY }; st.setPointerCapture(e.pointerId); e.preventDefault(); return; }
      const [x, y] = toImage(e);
      S.drag = { type: S.tool, x, y, x2: x, y2: y, sx: e.clientX, sy: e.clientY };
      st.setPointerCapture(e.pointerId); e.preventDefault();
    });
    st.addEventListener("pointermove", (e) => {
      const d = S.drag; if (!d) return;
      if (d.type === "pan") { S.zoom.x += e.clientX - d.x; S.zoom.y += e.clientY - d.y; d.x = e.clientX; d.y = e.clientY; applyZoom(); return; }
      if (d.type === "dot") {   // a drag in Dot mode moves the picture, so it never places a mark by accident
        if (!d.panning && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < 6) return;
        if (!d.panning) { d.panning = true; d.px = d.sx; d.py = d.sy; st.classList.add("panning"); }
        S.zoom.x += e.clientX - d.px; S.zoom.y += e.clientY - d.py; d.px = e.clientX; d.py = e.clientY; applyZoom(); return;
      }
      [d.x2, d.y2] = toImage(e);
      let pv = $("labels").querySelector(".preview"); if (pv) pv.remove();
      const x = Math.min(d.x, d.x2), y = Math.min(d.y, d.y2), w = Math.abs(d.x2 - d.x), h = Math.abs(d.y2 - d.y);
      pv = document.createElementNS(NS, d.type === "ellipse" ? "ellipse" : "rect");
      if (d.type === "ellipse") { pv.setAttribute("cx", x + w / 2); pv.setAttribute("cy", y + h / 2); pv.setAttribute("rx", w / 2); pv.setAttribute("ry", h / 2); }
      else { pv.setAttribute("x", x); pv.setAttribute("y", y); pv.setAttribute("width", w); pv.setAttribute("height", h); }
      pv.setAttribute("class", "mark preview big"); pv.setAttribute("vector-effect", "non-scaling-stroke"); $("labels").append(pv);
    });
    const end = (e) => {
      const d = S.drag; S.drag = null; if (!d) return;
      const pv = $("labels").querySelector(".preview"); if (pv) pv.remove();
      if (d.type === "pan") return;
      if (d.type === "dot") {
        st.classList.remove("panning");
        if (d.panning) { renderLabels(false); return; }
        addLabel("point", Math.round(d.x), Math.round(d.y));   // a click only ever adds. Right-click or Undo removes
        return;
      }
      const [W] = dims(), minPx = (8 * W) / Math.max(200, st.clientWidth) / S.zoom.k;
      const w = Math.abs(d.x2 - d.x), h = Math.abs(d.y2 - d.y);
      if (w < minPx || h < minPx) { message("Drag to draw the " + d.type + ". It was too small, so nothing was saved.", ""); return; }
      addLabel(d.type, Math.round(Math.min(d.x, d.x2)), Math.round(Math.min(d.y, d.y2)), Math.round(w), Math.round(h));
    };
    st.addEventListener("pointerup", end); st.addEventListener("pointercancel", () => { S.drag = null; });
    st.addEventListener("contextmenu", (e) => {   // right-click removes the mark under the pointer, whichever tool is on
      if (S.mode !== "sub") return;
      e.preventDefault();
      if (S.motion || qcBlocked() || !$("still").complete) return;
      const [x, y] = toImage(e), hit = labelAt(x, y);
      if (hit) removeLabel(hit);
    });
    st.addEventListener("wheel", (e) => {
      if (S.mode !== "sub") return;
      e.preventDefault();
      const r = st.getBoundingClientRect();
      S.lastPointer = [e.clientX - r.left, e.clientY - r.top];
      zoomBy(Math.pow(1.0018, -e.deltaY * (e.deltaMode === 1 ? 33 : 1)), e.clientX - r.left, e.clientY - r.top);   // about 1.2x per wheel notch, smooth on a trackpad
    }, { passive: false });
    document.querySelectorAll("[data-tool]").forEach((b) => b.addEventListener("click", () => setTool(b.dataset.tool)));
    $("p-undo").addEventListener("click", undoLabel);
    $("p-clear").addEventListener("click", clearAllLabels);
    st.addEventListener("pointermove", (e) => { const r = st.getBoundingClientRect(); S.lastPointer = [e.clientX - r.left, e.clientY - r.top]; });
    const atPointer = (f) => zoomBy(f, ...(S.lastPointer || []));   // + and - zoom where the mouse last was
    $("z-in").addEventListener("click", () => atPointer(2)); $("z-out").addEventListener("click", () => atPointer(0.5));
    $("z-reset").addEventListener("click", () => { S.zoom = { k: 1, x: 0, y: 0 }; applyZoom(); renderLabels(false); });
    window.addEventListener("resize", () => { applyZoom(); if (S.mode === "sub") renderLabels(false); });
  }

  // ---------- species combo ----------
  function matches(text, opts) {
    const q = text.trim().toLowerCase(), base = opts.kind ? D.forKind(S.index, opts.kind()) : S.index;
    if (!q) return opts.showAll ? base.map((it) => ({ it, via: null })) : [];
    const out = [];
    for (const it of base) {
      let best = -1, via = null;
      for (const t of it.terms) {
        const l = t.toLowerCase(), pos = l.indexOf(q);
        if (pos < 0) continue;
        const score = pos === 0 ? 2 : (l.split(/[\s-]+/).some((w) => w.startsWith(q)) ? 1 : 0);
        if (score > best) { best = score; via = t; }
      }
      if (best >= 0) out.push({ it, best, via });
    }
    out.sort((a, b) => b.best - a.best || a.it.sci.localeCompare(b.it.sci));
    return out.slice(0, 12);
  }
  function resolve(text) {
    const l = text.trim().toLowerCase();
    return S.index.find((it) => it.terms.some((t) => t.toLowerCase() === l)) || null;
  }
  function flagBadges(rec) {
    const f = (rec && rec.flags) || {}, out = [];
    if (f.at_risk) out.push(badge("At risk", "risk"));
    if (f.invasive) out.push(badge("Invasive", "invasive"));
    if (f.range_expander) out.push(badge("Range expander", "info"));
    return out;
  }
  function makeCombo(input, list, onChoose, opts) {
    opts = opts || {};
    let items = [], active = -1;
    const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; };
    function paint() {
      clear(list);
      const text = input.value.trim();
      items = matches(text, opts).map((m) => ({ kind: "list", it: m.it, via: m.via }));
      if (text && !resolve(text)) items.push({ kind: "free", text });
      if (!items.length) { close(); return; }
      items.forEach((x, i) => {
        const li = el("li", { role: "option", id: list.id + "-" + i, "aria-selected": i === active ? "true" : "false", class: i === active ? "active" : "", on: { mousedown: (e) => { e.preventDefault(); choose(i); } } });
        if (x.kind === "list") {
          const main = D.speciesName(x.it, S.names), other = main === x.it.sci ? x.it.common : x.it.sci;
          li.append(el("span", { class: "opt-main", text: main }), el("span", { class: "opt-sci", text: other ? " " + other : "" }));
          if (x.via && x.via !== x.it.sci && x.via !== x.it.common) li.append(el("span", { class: "opt-via", text: " (also called " + x.via + ")" }));
          li.append(...flagBadges(x.it.rec));
        } else li.append(el("span", { class: "opt-main", text: "Use \"" + x.text + "\" as free text" }), badge("Not in the list, flagged", "warn"));
        list.append(li);
      });
      list.hidden = false; input.setAttribute("aria-expanded", "true");
      if (active >= 0) input.setAttribute("aria-activedescendant", list.id + "-" + active); else input.removeAttribute("aria-activedescendant");
    }
    function choose(i) {
      const x = items[i]; if (!x) return;
      close();
      if (x.kind === "list") onChoose({ value: x.it.sci, free: false, item: x.it });
      else onChoose({ value: x.text, free: true, item: null });
    }
    input.addEventListener("input", () => { active = -1; paint(); onChoose && combo.onType && combo.onType(input.value); });
    input.addEventListener("blur", close);
    if (opts.showAll) for (const ev of ["focus", "click"]) input.addEventListener(ev, () => { if (list.hidden) paint(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && !list.hidden) { e.preventDefault(); active = Math.min(items.length - 1, active + 1); paint(); }
      else if (e.key === "ArrowUp" && !list.hidden) { e.preventDefault(); active = Math.max(0, active - 1); paint(); }
      else if (e.key === "Enter") {
        e.preventDefault();
        if (!list.hidden && items.length && (active >= 0 || items[0].kind === "list")) choose(active >= 0 ? active : 0);   // Enter takes the top match
        else if (input.value.trim()) { const r = resolve(input.value); onChoose(r ? { value: r.sci, free: false, item: r } : { value: input.value.trim(), free: true, item: null }); close(); }
      } else if (e.key === "Escape") { close(); input.blur(); }
    });
    const combo = { onType: null, close };
    return combo;
  }

  // ---------- segment review (supporting pass) ----------
  function renderSegment(u) {
    const head = $("seg-head"); clear(head);
    head.append(el("h2", { text: u.segment_id }), el("span", { text: fmtTime(u.start_s) + " to " + fmtTime(u.end_s) }));
    head.append(badge(u.kind === "set_aside" ? "Set aside" : "Active", u.kind === "set_aside" ? "" : "info"));
    if (u.audit_sample) head.append(badge("Random check", "audit"));
    head.append(badge(u.status === "movement_unidentified" ? "Movement, unidentified" : (STATUS[u.status] || "Status not set"), u.status === "movement_unidentified" ? "move" : ""));
    if (u.flags && u.flags.shake) head.append(badge("Camera shake", "flag"));
    if (u.flags && u.flags.low_visibility) head.append(badge("Low visibility", "flag"));
    if (u.review_priority != null) head.append(el("span", { class: "hint", text: "Priority " + Number(u.review_priority).toFixed(2) }));
    const ab = $("audit-banner");
    ab.hidden = !u.audit_sample;
    ab.textContent = "Random check. This stretch was set aside because no activity was found. It was picked at random to test that nothing was missed. Look closely before you decide.";
    const mb = $("movement-banner");
    mb.hidden = u.status !== "movement_unidentified";
    mb.textContent = "Movement, unidentified. Something moved here but no fish was found. It is kept for you to look at, not dropped.";
    renderCountsPanel(u);
    // previous decision
    const prev = (S.saved.latest_review || {})[u.segment_id];
    $("last-decision").textContent = prev ? "Last saved: " + (DECISION_TEXT[prev.decision] || prev.decision) + (prev.reviewer ? " by " + prev.reviewer : "") + " at " + prev.at + ". A new decision adds a new line. Earlier ones are kept." : "Not reviewed yet.";
    S.seg.species = null; $("species").value = prev && prev.species ? shownName(prev.species) : ""; $("count").value = ""; $("note").value = "";
    if (prev && prev.species) { const r = resolve(prev.species); S.seg.species = { value: prev.species, free: !r }; }
    paintSpeciesStatus();
  }
  function renderCountsPanel(u) {
    const c = u.counts || {}, d = $("counts"); clear(d);
    const row = (k, v) => d.append(el("dt", { text: k }), el("dd", { text: v }));
    row("MaxN", fmtNum(c.maxn) + (c.maxn != null && c.maxn_time_s != null ? " at " + fmtTime(c.maxn_time_s) : ""));
    row("MeanCount", fmtNum(c.mean_count, 2));
    row("Unique tracks", fmtNum(c.unique_tracks));
    const t = $("tracks"); clear(t);
    const tracks = Array.isArray(u.tracks) ? u.tracks : [];
    if (tracks.length) {
      t.append(el("h3", { text: "Model suggestions" }));
      tracks.forEach((tr) => {
        const top = Array.isArray(tr.species_topk) && tr.species_topk[0];
        const line = el("div", { class: "track" }, el("span", { text: "Track " + tr.track_id + ": " }));
        if (top) line.append(el("button", { type: "button", class: "linkish", text: top.name + (top.score != null ? " (" + Math.round(top.score * 100) + "%)" : ""), on: { click: () => setSegSpecies(top.name) } }));
        else line.append("no species suggestion");
        t.append(line);
      });
    }
  }
  function setSegSpecies(text) {
    $("species").value = text;
    const r = resolve(text);
    S.seg.species = text.trim() ? { value: r ? r.sci : text.trim(), free: !r } : null;
    paintSpeciesStatus();
  }
  function paintSpeciesStatus() {
    const sp = S.seg.species, st = $("species-status"); clear(st);
    $("alias-row").hidden = !(sp && !sp.free);
    if (!sp) { st.textContent = S.index.length ? "No species chosen." : "No species list found. Free text is fine."; return; }
    if (sp.free) { st.append(badge("Free text, not in the list: flagged for checking", "warn")); return; }
    const it = S.index.find((x) => x.sci === sp.value);
    st.append(el("span", { text: (it ? D.speciesLabel(it, S.names) : sp.value) + " " }), ...(it ? flagBadges(it.rec) : []));
  }
  async function saveDecision(decision) {
    if (S.mode !== "seg" || !S.selId) return;
    const cnt = $("count").value.trim();
    const payload = {
      segment_id: S.selId, decision, species: S.seg.species ? S.seg.species.value : null,
      species_free_text: !!(S.seg.species && S.seg.species.free),
      count: cnt === "" ? null : parseInt(cnt, 10), note: $("note").value, reviewer: reviewer(),
      contrast_settings: settingsPayload(),
    };
    try {
      await Data.save(S.runId, "reviews", payload);
      await refreshSaved();
      message("Saved: " + DECISION_TEXT[decision] + " for " + S.selId + ".", "ok");
      step(1);
    } catch (e) { message("Not saved: " + e.message, "error"); }
  }

  // ---------- subsample review (main pass) ----------
  function renderSubsample(u) {
    const head = $("seg-head"); clear(head);
    head.append(el("h2", { text: u.subsample_id }), el("span", { text: "at " + fmtTime(u.t_s) }));
    if (S.qc) head.append(badge(S.recount ? "Recount" : "Blind second count", "audit"));
    head.append(el("button", { type: "button", class: "quiet", text: S.qc ? "Back to the quality check" : "", hidden: !S.qc, on: { click: () => setStep("qc") } }));
    $("audit-banner").hidden = !S.qc;
    $("movement-banner").hidden = true;
    // form: prefill only from this person's own latest count, of any kind
    const prev = ownCount(u.subsample_id);
    renderOthers(u); renderGuess();
    $("audit-banner").textContent = prev ? "Your earlier count is loaded. Other people's counts are hidden." : "Count this frame fresh. Earlier counts are hidden on purpose.";
    $("c-fish").value = prev ? prev.total_fish_count : ""; $("c-inv").value = prev ? prev.invertebrate_count : "";
    $("c-unk").value = prev && prev.unknown_count ? prev.unknown_count : "";
    S.ss.rows = prev ? Object.entries(prev.species_counts || {}).map(([name, n]) => ({ name, n, free: !resolve(name) })) : [];
    // A saved Unknown that differs from "total minus species" was typed on purpose, so it isn't recalculated.
    S.ss.unkTouched = !!prev && (prev.unknown_count || 0) !== Math.max(0, (prev.total_fish_count || 0) + (prev.invertebrate_count || 0) - S.ss.rows.reduce((a, r) => a + r.n, 0));
    S.carriedVis = !S.qc ? carriedVisibility(u) : null;
    $("c-vis").value = prev && prev.visibility_direction ? prev.visibility_category || "" : "";
    document.querySelector('input[name=vdir][value="' + ((prev && prev.visibility_direction) || "") + '"]').checked = true;
    paintVisDir();
    document.querySelector("#c-vdir legend").textContent = S.qc ? "Visibility since the last frame you counted" : "Visibility since the last point";
    $("c-notes").value = prev ? D.noteParts(prev).text : "";
    $("c-move").checked = !!(prev && D.noteParts(prev).possible);
    for (const cb of $("chars").querySelectorAll("input")) cb.checked = !!(prev && (prev.characteristics || []).includes(cb.value));
    $("ss-species").value = "";
    paintSpeciesRows(); paintCharsWarn();
    const r = prev ? "Your earlier count is loaded. Saving adds a new row; earlier rows are kept." : "";
    $("sub-result").textContent = r;
  }
  // Visibility from the nearest earlier counted point, so it is only typed when it changes. Never in a blind count.
  function ownCount(id) { let r = null; for (const x of S.saved.subsample_reviews || []) if (x.subsample_id === id && x.counter === reviewer()) r = x; return r; }
  const visChange = () => document.querySelector("input[name=vdir]:checked").value;
  function paintVisDir() { $("c-vis-row").hidden = !visChange(); }
  // Visibility before this point: the video's rating, then the changes recorded at earlier points. Never a stored copy.
  function carriedVisibility(u) {
    const earlier = subs().filter((s) => (s.t_s ?? 0) < (u.t_s ?? 0));
    const vis = D.pointVisibility(earlier, S.saved.latest_primary || {}, S.saved.visibility || []);
    const last = earlier.filter((s) => vis[s.subsample_id]).sort((a, b) => (b.t_s ?? 0) - (a.t_s ?? 0))[0];
    return last ? vis[last.subsample_id] : D.visibilitySummary(S.saved.visibility || []).usual;
  }
  // Everyone else's count of this point, read only. Hidden from anyone counting blind or about to recount it.
  function othersVisible() {
    if (S.qc || locked() || !S.whoSet) return false;
    const c = check();
    return !(c.status === "review" && c.recount.includes(S.selId) && !((S.saved.qc[S.selId] || {}).counters || []).includes(reviewer()));
  }
  function renderOthers(u) {
    const latest = {}; for (const r of S.saved.subsample_reviews || []) if (r.subsample_id === u.subsample_id && r.counter !== reviewer()) latest[r.counter + "|" + r.pass] = r;
    const rows = Object.values(latest), box = $("others-list"); clear(box);
    $("others-panel").hidden = !rows.length || !othersVisible();
    const PASS = { primary: "first count", qc_blind: "blind count", recount: "recount" }, CH = { shape: "shape", anatomical_features: "anatomy", colouration_or_flashes: "colour", swimming_behaviour: "movement" };
    const vis = D.pointVisibility(subs(), S.saved.latest_primary || {}, S.saved.visibility || []);
    for (const r of rows) {
      const np = D.noteParts(r), sp = Object.entries(r.species_counts || {}).map(([k, n]) => shownName(k) + " " + n).join(", ");
      const bits = [r.total_fish_count + " fish, " + r.invertebrate_count + (r.invertebrate_count === 1 ? " invertebrate" : " invertebrates") + (r.unknown_count ? ", " + r.unknown_count + " unknown" : ""), sp,
        (r.characteristics || []).length ? "Features: " + r.characteristics.map((c) => CH[c] || c).join(", ") : "",
        r.pass === "primary" ? "Visibility " + (r.visibility_direction ? (r.visibility_direction === "increasing" ? "better, " : "worse, ") : "") + (vis[r.subsample_id] || "not recorded") : "",
        np.possible ? "Possible animals, not confirmed" : "", np.text].filter(Boolean);
      box.append(el("div", { class: "others-row" }, el("b", { text: r.counter + ", " + (PASS[r.pass] || r.pass) }), el("span", { text: bits.map((b) => b.replace(/\.+$/, "")).join(". ") + "." })));
    }
  }
  function paintSpeciesRows() {
    const ul = $("species-rows"); clear(ul);
    S.ss.rows.forEach((row, i) => {
      const it = S.index.find((x) => x.sci === row.name);
      const li = el("li", {}, el("span", { class: "sp-name", text: it ? D.speciesLabel(it, S.names) : row.name }),
        ...(row.free ? [badge("Free text, flagged", "warn")] : []), ...(it ? flagBadges(it.rec) : []),
        el("input", { type: "number", min: "0", max: "100000", value: String(row.n), "aria-label": "Count for " + row.name, on: { input: (e) => { row.n = parseInt(e.target.value, 10) || 0; paintSpeciesSum(); } } }),
        el("button", { type: "button", class: "quiet", text: "Remove", "aria-label": "Remove " + row.name, on: { click: () => { S.ss.rows.splice(i, 1); paintSpeciesRows(); } } }));
      ul.append(li);
    });
    paintSpeciesSum();
  }
  function paintSpeciesSum() {
    const sum = S.ss.rows.reduce((a, r) => a + r.n, 0), p = $("species-sum");
    const fish = parseInt($("c-fish").value, 10), inv = parseInt($("c-inv").value, 10) || 0;
    if (!S.ss.unkTouched) { const unk = Math.max(0, (isNaN(fish) ? 0 : fish) + inv - sum); $("c-unk").value = unk || ""; }   // the animals with no species yet
    p.textContent = S.ss.rows.length ? S.ss.rows.length + " species, " + sum + " counted by species." + (!isNaN(fish) && sum > fish + inv ? " That is more than your fish and invertebrate totals. Check the numbers." : "") : "";
  }
  function paintCharsWarn() {
    const n = $("chars").querySelectorAll("input:checked").length;
    const anyCount = (parseInt($("c-fish").value, 10) || 0) + (parseInt($("c-inv").value, 10) || 0) > 0;
    $("chars-warn").classList.toggle("ghost", !(anyCount && n < 2));   // keeps its space, so the boxes never jump
  }
  function addSpecies(sel) {
    if (!sel || !sel.value) return;
    const ex = S.ss.rows.find((r) => r.name === sel.value);
    const total = (parseInt($("c-fish").value, 10) || 0) + (parseInt($("c-inv").value, 10) || 0), used = S.ss.rows.reduce((a, r) => a + r.n, 0);
    if (ex) ex.n += 1; else S.ss.rows.push({ name: sel.value, n: Math.max(1, total - used), free: sel.free });   // starts with whatever isn't assigned yet
    $("ss-species").value = ""; paintSpeciesRows();
  }
  async function saveSubsample() {
    if (S.mode !== "sub" || !S.selId) return;
    const num = (id) => { const v = $(id).value.trim(); return v === "" ? null : parseInt(v, 10); };
    const fish = num("c-fish"), inv = num("c-inv");
    if (!reviewer()) { askWho(); return; }
    if (fish == null || inv == null || fish < 0 || inv < 0) { const say = "Enter fish and invertebrate counts. Use 0 if there were none, or press No animals."; message(say, "error"); $("sub-result").textContent = say; (fish == null ? $("c-fish") : $("c-inv")).focus(); return; }
    const move = $("c-move").checked, notes = $("c-notes").value.trim();
    if (visChange() && !$("c-vis").value) {
      const say = "You said visibility got " + (visChange() === "increasing" ? "better" : "worse") + ". Choose what it is now, just above.";
      message(say, "error"); $("sub-result").textContent = say; $("c-vis").scrollIntoView({ block: "center" }); $("c-vis").focus(); return;
    }
    const sc = {}; for (const r of S.ss.rows) sc[r.name] = (sc[r.name] || 0) + r.n;
    const payload = {
      subsample_id: S.selId, counter: reviewer(), pass: S.qc ? (S.recount ? "recount" : "qc_blind") : "primary",
      total_fish_count: fish, invertebrate_count: inv, species_counts: sc, unknown_count: num("c-unk") || 0,
      total_species: Object.keys(sc).length, visibility_category: visChange() ? $("c-vis").value : (S.carriedVis || null),
      visibility_change: visChange() ? true : null, visibility_direction: visChange() || null,
      characteristics: [...$("chars").querySelectorAll("input:checked")].map((c) => c.value),
      free_text_species: S.ss.rows.filter((r) => r.free).map((r) => r.name),
      possible_animals: move, notes, contrast_settings: settingsPayload(),
      model_guess: S.qc ? null : (S.guess.seen[S.selId] ? "seen" : (S.guess.on ? "after" : null)),
    };
    const id = S.selId, first = primaryOf(id);
    if (!S.qc && first && first.counter !== reviewer()) {
      if (!confirm("This point was counted by " + first.counter + ". Saving makes your count the first count, in place of theirs. Save anyway?")) return;
      payload.replace = true;
    }
    try {
      await Data.save(S.runId, "subsample_reviews", payload);
      await refreshSaved();
      message("Saved count for " + id + ".", "ok");
      $("sub-result").textContent = "Saved count for " + id + ".";
      if (!S.qc && S.guess.on && !S.guess.boxes[id]) { await showGuess(id, fish); return; }   // compare with the model, then move on
      advanceAfter(id);
    } catch (e) { message("Not saved: " + e.message, "error"); }
  }
  function advanceAfter(id) {
      if (S.qc && queue().every(isDone)) { S.recount = false; setStep("qc"); return; }
      const ids = queue(), skipped = ids.filter((x) => !isDone(x));
      if (ids.indexOf(id) === ids.length - 1 && skipped.length) {   // the end, with a point still to do
        message((skipped.length > 3 ? skipped.length + " points" : skipped.join(", ")) + (skipped.length === 1 ? " isn't" : " aren't") + " counted yet. Opening " + skipped[0] + ".", "warn");
        select(skipped[0]); return;
      }
      if (!S.qc && S.saved.n_counted >= subs().length && queue().indexOf(id) === queue().length - 1) { setStep("qc"); return; }
      step(1);
  }
  // The model's guess for a point already counted: boxes on the frame and its number beside yours. Changes nothing.
  async function showGuess(id, mine) {
    const box = $("guess-box"); box.hidden = false; box.textContent = "Getting the model's guess...";
    try {
      const d = await post("/api/runs/" + enc(S.runId) + "/model_guess", { subsample_id: id });
      S.guess.boxes[id] = d; S.guess.seen[id] = true; S.guess.mine = Object.assign(S.guess.mine || {}, { [id]: mine });
    } catch (e) { box.textContent = "No guess: " + e.message; }
    if (S.selId === id) { renderGuess(); renderLabels(false); }
    box.append(el("button", { type: "button", class: "primary", text: "Next point", on: { click: () => advanceAfter(id) } }));
  }
  function renderGuess() {
    const row = $("guess-row"), box = $("guess-box"), d = S.guess.boxes[S.selId];
    row.hidden = !!DEMO || S.qc || !S.guess.ready; $("guess-on").checked = S.guess.on;
    box.hidden = !d || S.qc; clear(box);
    if (!d || S.qc) return;
    const mine = (S.guess.mine || {})[S.selId] ?? (ownCount(S.selId) || {}).total_fish_count;
    box.append(el("b", { text: "Model guess: " + d.fish + " fish" + (mine != null ? ". You counted " + mine + " fish." : ".") }),
      el("div", { class: "hint", text: "Pink boxes. A prototype that isn't trained on Coastal footage, and it misses most fish in murky water. Your count stays as saved. If you change it now, the app notes that you'd seen the guess." }));
  }

  function noAnimals() {
    if (S.mode !== "sub" || !S.selId) return;
    if (myLabels().some((l) => l.kind !== "unsure")) { message("This point has marks on it. Clear them first if nothing is really there.", "warn"); return; }
    $("c-fish").value = 0; $("c-inv").value = 0; $("c-unk").value = ""; paintCharsWarn();
    saveSubsample();
  }
  function paintBig() { document.body.classList.toggle("big-view", S.big); setPressed("big-view", S.big); }
  function toggleBig() {
    S.big = !S.big; paintBig();
    try { localStorage.setItem("clipsift.big", S.big ? "1" : "0"); } catch (e) { /* storage may be blocked */ }
    requestAnimationFrame(() => { applyZoom(); renderLabels(false); });
  }

  // ---------- navigation and keys ----------
  function step(dir) {
    const ids = queue(); if (!ids.length) return;
    const i = ids.indexOf(S.selId);
    let j = i < 0 ? (dir > 0 ? 0 : ids.length - 1) : i + dir;
    if (j < 0 || j >= ids.length) { message(dir > 0 ? "That is the last item in the queue." : "That is the first item in the queue.", ""); return; }
    select(ids[j]);
  }
  function frameStep(dir) {
    const v = $("stage-clip"), fromStill = !S.motion;
    if (fromStill) setMotion(true);
    v.pause();
    if (fromStill && countOffset() != null) { v.currentTime = countOffset(); S.held = true; paintHud(); return; }   // the first step shows the count second itself
    const fps = (S.results.recording && S.results.recording.fps) || 30;
    v.currentTime = Math.max(0, Math.min(v.duration || 1e9, v.currentTime + dir / fps));
    S.held = true;
    paintHud();
  }
  const currentSpeed = () => { const b = document.querySelector("[data-speed][aria-pressed=true]"); return b ? parseFloat(b.dataset.speed) : 1; };
  function countOffset() { const u = unit(S.selId, "sub"); return u && u.t_s != null && u.context_start_s != null ? Math.max(0, u.t_s - u.context_start_s) : null; }
  function toggle(which) {
    if (which === "grid") { S.grid = !S.grid; renderGrid(); }
    if (which === "diff") { S.diff = !S.diff; setPressed("toggle-diff", S.diff); $("movement-hint").hidden = !S.diff; showStill(); }
  }
  function onKey(e) {
    if (e.altKey || e.metaKey) return;
    if (tourOn() || document.querySelector("dialog[open]")) return;   // help, feedback and the tour own the keyboard
    if (e.key === "?" && !isTyping(e.target)) { e.preventDefault(); openHelp(); return; }
    if ((e.ctrlKey) && e.key === "Enter") { e.preventDefault(); if (S.mode === "sub") saveSubsample(); return; }
    if (e.ctrlKey) return;
    if (e.key === "/" && !isTyping(e.target)) { e.preventDefault(); (S.mode === "sub" ? $("ss-species") : $("species")).focus(); return; }
    if (isTyping(e.target) || e.target.tagName === "SELECT" || e.target.tagName === "SUMMARY") return;
    if (!S.results || $("workspace").hidden) return;
    const k = e.key.toLowerCase();
    if (k === "arrowright" || k === "arrowdown" || k === "j") { e.preventDefault(); step(1); }
    else if (k === "arrowleft" || k === "arrowup" || k === "k") { e.preventDefault(); step(-1); }
    else if (k === "g") toggle("grid");
    else if (k === "n") noAnimals();
    else if (k === "v") toggleBig();
    else if (k === "d") toggle("diff");
    else if (S.mode === "sub" && k === "p") setTool("dot");
    else if (S.mode === "sub" && k === "e") setTool("ellipse");
    else if (S.mode === "sub" && k === "b") setTool("box");
    else if (S.mode === "sub" && k === "z") undoLabel();
    else if (S.mode === "sub" && k === "f") setMarkKind("fish");
    else if (S.mode === "sub" && k === "i") setMarkKind("invertebrate");
    else if (S.mode === "sub" && k === "u") setMarkKind("unsure");
    else if (S.mode === "seg" && DECISION_KEYS[k]) saveDecision(DECISION_KEYS[k]);
    else if (S.mode === "sub" && k in CHAR_KEYS) { const cb = $("chars").querySelectorAll("input")[CHAR_KEYS[k]]; cb.checked = !cb.checked; paintCharsWarn(); }
    else if (k === "," ) frameStep(-1);
    else if (k === ".") frameStep(1);
    else if (k === "r") setRestart(!S.restart);
    else if (k === "o") setCountOnly(!S.countOnly);
    else if (k === "c") { S.enhance = D.nextEnhance(S.enhance); applyFilters(); }
    else if (k === " " && !e.target.closest("button, a, input[type=checkbox], input[type=radio]")) {   // a control reached with Tab keeps its own Space
      e.preventDefault();
      if (!e.repeat && !S.spaceDown) {
        S.spaceDown = true;
        if (S.held || (S.motion && !S.spaceStarted)) setMotion(false);   // paused on a scrubbed frame, or started with the button: back to the still
        else if (!S.motion) { S.spaceStarted = true; setMotion(true); }
      }
    }
  }

  // ---------- step 2: what is present in the window. Counting happens in step 3 ----------
  function fillNotes() {
    const n = S.saved.latest_recording_notes || {};
    S.watch.species = (n.species_observed || []).slice();
    document.querySelector('input[name=juv][value="' + (n.juveniles == null ? "" : n.juveniles) + '"]').checked = true;
    $("rn-none").checked = !!n.none_seen;
    $("rn-notes").value = n.notes || ""; $("rn-status").textContent = ""; S.watch.dirty = false;
    $("rn-who").textContent = n.reviewer ? "Recorded by " + n.reviewer + (n.at ? ", " + new Date(n.at).toLocaleString() : "") + "." + (n.reviewer !== reviewer() ? " Saving replaces it with yours. Theirs stays in the history." : "") : "";
    paintWatchSpecies();
  }
  function paintWatchSpecies() {
    const ul = $("rn-chips"); clear(ul);
    S.watch.species.forEach((name, i) => ul.append(el("li", {}, el("span", { text: shownName(name) }),
      el("button", { type: "button", "aria-label": "Remove " + name, text: "×", on: { click: () => { S.watch.species.splice(i, 1); paintWatchSpecies(); } } }))));
    $("rn-none").disabled = S.watch.species.length > 0;
    if (S.watch.species.length) $("rn-none").checked = false;
  }
  async function saveNotes(auto) {
    const p = S.results.protocol || {}, say = (t) => { $("rn-status").textContent = t; };
    if (!reviewer()) { askWho(); return; }
    if (!auto && !S.watch.species.length && !$("rn-none").checked) { say("Add the species you saw, or tick that none were seen. Your notes are kept if you leave this step."); return; }
    const juv = document.querySelector("input[name=juv]:checked").value, was = (S.saved.latest_recording_notes || {}).reviewer;
    if (was && was !== reviewer() && (auto || !confirm(was + " recorded this step. Save your entries in place of theirs? Theirs stays in the history."))) return;
    const payload = {
      window_start_s: p.window_start_s ?? null, window_end_s: p.window_end_s ?? null, species_observed: S.watch.species,
      none_seen: $("rn-none").checked, juveniles: juv === "" ? null : Number(juv), notes: $("rn-notes").value, reviewer: reviewer(),
    };
    try {
      await Data.save(S.runId, "recording_notes", payload);
      S.watch.dirty = false;
      if (auto) { S.saved = await Data.saved(S.runId); paintSteps(); return; }
      S.saved = await Data.saved(S.runId); setStep("count");
    } catch (e) { say("Not saved: " + e.message); }
  }
  // The first counter's notes say when the fish pass, so they stay hidden from anyone about to count blind.
  function paintWatchForm() {
    const shut = locked(), fresh = !shut && freshToRecount() && !S.watch.reveal;
    $("watch-form").hidden = shut || fresh; $("watch-hidden").hidden = !(shut || fresh); $("watch-reveal").hidden = !fresh;
    $("watch-hidden-text").textContent = shut ? "Earlier notes stay hidden until your blind count is done. You can still watch the video." : "Earlier notes are hidden in case you're about to recount.";
  }
  function setWatch(points) {
    const v = $("watch-video"), url = Data.windowUrl(S.runId);
    if (!url) points = true;
    S.watch.points = points;
    setPressed("watch-whole", !points); setPressed("watch-points", points);
    $("watch-whole").disabled = !url; $("watch-missing").hidden = !!url; $("watch-chips").hidden = !points;
    const chips = $("watch-chips"); clear(chips);
    if (!points) { v.onerror = () => { $("watch-missing").hidden = false; setWatch(true); }; if (!v.src.endsWith(url)) { v.src = url; v.load(); v.playbackRate = watchSpeed(); } return; }
    v.onerror = null;
    const list = subs().slice().sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0));
    const open = (s, b) => {
      v.src = Data.mediaUrl(S.runId, "subsamples", s.subsample_id, "context"); v.loop = true; v.load(); v.playbackRate = watchSpeed(); v.play().catch(() => {});
      for (const c of chips.children) c.setAttribute("aria-pressed", c === b ? "true" : "false");
    };
    for (const s of list) { const b = el("button", { type: "button", "aria-pressed": "false", text: fmtTime(s.t_s), title: "Play 5 seconds either side of " + fmtTime(s.t_s), on: { click: (e) => open(s, e.currentTarget) } }); chips.append(b); }
    if (list.length) open(list[0], chips.firstChild);
  }
  const watchSpeed = () => { const b = document.querySelector("[data-wspeed][aria-pressed=true]"); return b ? parseFloat(b.dataset.wspeed) : 1; };

  // ---------- step 1: one rating per person, for the whole video ----------
  function renderVisibility() {
    const rows = S.saved.visibility || [], mine = rows.find((r) => r.observer === reviewer()), box = $("vis-choice");
    while (box.children.length > 1) box.lastChild.remove();
    $("vis-legend").textContent = "How far can you see" + (reviewer() ? ", " + reviewer() : "") + "?";
    for (const c of D.VIS_ORDER) box.append(el("label", {}, el("input", { type: "radio", name: "vis", value: c, checked: !!mine && mine.category === c }), " " + c));
    $("vis-status").textContent = "";
    const out = $("vis-others"); clear(out);
    const sum = D.visibilitySummary(rows), others = rows.length - (mine ? 1 : 0);
    out.append(el("p", { class: "hint", text: (rows.length === 1 ? "1 person has" : rows.length + " people have") + " rated this video." + (rows.length < 2 ? " The protocol asks for 2 to 3, so ask someone else to rate it under their own name." : "") }));
    if (!mine) { if (others) out.append(el("p", { class: "hint", text: "Their ratings stay hidden until you've saved yours." })); }
    else {
      out.append(el("ul", { class: "plain" }, rows.map((r) => el("li", { text: r.observer + ": " + r.category + (r.at_s != null ? ", judged at " + fmtTime(r.at_s) : "") }))));
      if (sum.spread > 1) out.append(el("p", { class: "warn-text", text: "These ratings are more than one category apart. Look at the video together and agree whether conditions changed." }));
      if (sum.low) out.append(el("p", { class: "hint", text: "Rated under 0.5 m. One study left out videos this poor (Baker 2022). Whether to analyse them is Coastal Action's call." }));
    }
    if (rows.length) { const b = el("button", { type: "button", class: "quiet", text: "Next: watch the window", on: { click: () => setStep("watch") } }); out.append(b); }
    paintVisVideo();
  }
  // Judge visibility at the first count point, or scrub the whole window to the clearest view of the pole.
  function paintVisVideo() {
    const first = subs().slice().sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0))[0], v = $("vis-video"), win = Data.windowUrl(S.runId);
    if (!win) S.visWhole = false;
    setPressed("vis-first", !S.visWhole); setPressed("vis-whole", !!S.visWhole); $("vis-whole").disabled = !win;
    const url = S.visWhole ? win : first && Data.mediaUrl(S.runId, "subsamples", first.subsample_id, "context");
    v.loop = !S.visWhole;
    if (url && !v.src.endsWith(url)) { v.src = url; v.load(); }
    $("vis-where").textContent = S.visWhole ? "The whole analysis window. Scrub to the clearest view of the pole, then rate. The time is saved with your rating."
      : "The first count point. Use the pole here if there is one. If this video has its own visibility video, use that instead.";
  }
  function visTime() {
    const v = $("vis-video"), p = S.results.protocol || {}, first = subs().slice().sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0))[0];
    if (S.visWhole) return (p.window_start_s || 0) + v.currentTime;
    return first && first.context_start_s != null ? first.context_start_s + v.currentTime : null;
  }
  async function saveVisibility() {
    if (!reviewer()) { askWho(); return; }
    const pick = document.querySelector("input[name=vis]:checked");
    if (!pick) { $("vis-status").textContent = "Choose a category first."; return; }
    try {
      const at = visTime();
      await Data.save(S.runId, "visibility", Object.assign({ observer: reviewer(), category: pick.value }, at != null && isFinite(at) ? { at_s: Math.round(at * 10) / 10 } : {}));
      S.saved = await Data.saved(S.runId); renderVisibility(); paintSteps();
    } catch (e) { $("vis-status").textContent = "Not saved: " + e.message; }
  }

  // ---------- step 4: the app holds the frames, compares the counts and recommends ----------
  function startBlind(recount) { S.recount = recount; setStep("blind"); }
  function renderQc() {
    const c = check(), me = reviewer(), [title, detail] = D.qcMessage(c), v = $("qc-verdict");
    const act = $("qc-actions"), res = $("qc-results"); clear(act); clear(res); clear(v);
    if (!S.whoSet) return;   // nothing shows until the person is known
    v.className = "verdict " + c.status; v.append(el("b", { text: title }), el("span", { text: detail }));
    const isFirst = firstCounters().has(me);
    if (c.status === "counting") act.append(el("button", { type: "button", text: "Go to counting", on: { click: () => setStep("count") } }));
    if (c.status === "waiting_second") {
      if (isFirst) act.append(el("span", { class: "hint", text: "You counted this video, so someone else needs to do this. They open this video on this computer and choose their own name." }),
        el("button", { type: "button", text: "Switch person", on: { click: askWho } }));
      else {
        const mine = qcSample().items.filter((s) => secondOf(s.subsample_id)).length;
        act.append(el("button", { type: "button", class: "primary", text: (mine ? "Carry on with" : "Start") + " the blind count (" + (c.n_sample - mine) + " frames)", on: { click: () => startBlind(false) } }));
      }
    }
    if (c.status === "review") act.append(el("button", { type: "button", class: "primary", text: "Go to the report", on: { click: () => setStep("report") } }), el("button", { type: "button", text: "Recount " + c.recount.length + (c.recount.length === 1 ? " frame" : " frames") + " as " + me, on: { click: () => startBlind(true) } }), el("button", { type: "button", text: "Switch person", on: { click: askWho } }));
    if (c.status === "pass") act.append(el("button", { type: "button", class: "primary", text: "Go to the report", on: { click: () => setStep("report") } }));
    const p = proto();
    $("qc-formula").textContent = "Percent difference is the gap between two counts divided by their mean. Agreement is 100 minus the mean of those differences. The protocol leaves both formulas out, so these are provisional until Coastal Action confirms them. The numbers are for information and never hold up a video. With fewer than 17 fish in a frame, one fish is already over 6%, so a frame is only flagged if it's also more than " + (p.qc_small_gap ?? 1) + " apart.";
    if (!c.n_done || c.status === "waiting_second" || c.status === "counting" || locked()) return;
    const ids = c.sample.filter((id) => S.saved.qc[id]);
    // Someone new may be about to recount, so the first counts don't show until they ask.
    const fresh = freshToRecount();
    const wrap = fresh ? el("details", {}, el("summary", { text: "Show the comparison. Leave this closed if you're about to recount." })) : res;
    if (fresh) res.append(wrap);
    wrap.append(el("div", { class: "qc-stats" }, el("span", { text: c.n_within + " of " + c.n_done + " frames within " + p.qc_max_percent_diff + "%" }), el("span", { text: "Agreement " + c.agreement + "%, target " + c.target + "%" }), el("span", { text: c.n_animal_frames ? "On the " + c.n_animal_frames + " with animals: " + c.animal_agreement + "%" : "No frames with animals" })));
    wrap.append(el("table", { class: "qc-table" },
      el("thead", {}, el("tr", {}, ["Frame", "Time", "People", "Fish", "Average", "Difference", "Invertebrates", "Difference", "Marks in both", "Result", ""].map((t) => el("th", { text: t })))),
      el("tbody", {}, ids.map((id) => {
        const q = S.saved.qc[id], u = unit(id, "sub"), m = marksFor(id, q), all = D.qcCounts(q);
        return el("tr", {}, [id, fmtTime(u.t_s), all.people, all.fish, q.average_fish, pct(q.fish_diff, q.first_fish, q.second_fish),
          all.inv, pct(q.inv_diff, q.first_inv, q.second_inv), m.both.length + " of " + (m.both.length + m.onlyA.length + m.onlyB.length), qcWord(q)].map((t) => el("td", { text: String(t) })),
          el("td", {}, el("button", { type: "button", class: "quiet", text: "Compare", on: { click: () => compareMarks(id, q) } })));
      }))));
    for (const id of ids) { const rule = D.qcCounts(S.saved.qc[id]).rule; if (rule) wrap.append(el("p", { class: "hint", text: id + ": " + rule })); }
    wrap.append(el("div", { id: "qc-compare", class: "qc-compare" }));
  }
  const pct = (d, a, b) => (!a && !b ? "both 0" : d.toFixed(1) + "%");   // 0 against 0 has no percent difference
  const qcWord = (q) => (q.recount_needed ? "Worth a look" : q.small_gap ? "Small gap" : "Close");
  function marksFor(id, q) {
    const of = (who) => (S.saved.point_labels || []).filter((l) => l.subsample_id === id && l.counter === who && l.kind !== "unsure");
    return D.matchMarks(of(q.first_counter), of(q.second_counter), (dims()[0] * 60) / 3840);
  }
  // Both people's marks on one frame: green where they agree, yellow and blue where only one marked.
  function compareMarks(id, q) {
    const box = $("qc-compare"), m = marksFor(id, q), img = new Image(); clear(box);
    let showMarks = true;
    const toggle = el("button", { type: "button", class: "quiet", text: "Hide marks", on: { click: () => { showMarks = !showMarks; toggle.textContent = showMarks ? "Hide marks" : "Show marks"; draw(); } } });
    box.append(el("p", { class: "hint", text: id + ": green marked by both, yellow only by " + q.first_counter + ", blue only by " + q.second_counter + ". " }, toggle));
    let c = null, g = null, k = 1, w = 1100, h = 0;
    const draw = () => {
      if (!c) return;
      g.drawImage(img, 0, 0, w, h); g.lineWidth = 2;
      if (!showMarks) return;
      const dot = (l, col) => { const x = (l.w != null ? l.x + l.w / 2 : l.x) * k, y = (l.w != null ? l.y + l.h / 2 : l.y) * k; g.strokeStyle = col; g.beginPath(); g.arc(x, y, 8, 0, Math.PI * 2); g.stroke(); };
      m.both.forEach((p) => dot(p[0], "#7fd8a0")); m.onlyA.forEach((l) => dot(l, "#ffe94d")); m.onlyB.forEach((l) => dot(l, "#6fd3ff"));
    };
    img.onload = () => {
      h = Math.round((w * img.naturalHeight) / img.naturalWidth); c = el("canvas", { width: w, height: h }); g = c.getContext("2d"); k = w / dims()[0];
      draw(); box.append(c); box.scrollIntoView({ block: "start", behavior: "smooth" });
    };
    img.src = Data.mediaUrl(S.runId, "subsamples", id, "still");
  }

  // ---------- step 6: model flags for a person to check, after everything else ----------
  const SOURCE_WORDS = { agree: "Model and counter agreed", model_only: "Model only, at a count point", elsewhere: "Model only, between count points" };
  async function renderVerify() {
    const box = $("vf-body"); clear(box);
    if (DEMO) { box.append(el("p", { class: "hint", text: "This step runs the model, so it needs the app on your own computer." })); return; }
    const st = S.saved.review_set, c = check();
    if (!S.saved.n_counted) { box.append(el("p", { class: "hint", text: "Count the points first. Model flags can sway a count." })); return; }
    if (["counting", "waiting_second"].includes(c.status)) box.append(el("p", { class: "hint", text: "This is best left until the quality check is done, so the flags can't sway a count." }));
    if (!st) {
      const job = NV.jobs.find((j) => j.kind === "review_set" && j.name === S.runId && (j.status === "queued" || j.status === "running"));
      if (job) { box.append(el("p", { text: (job.progress || "Waiting") + "..." }), el("progress", { max: "100", value: String(job.percent) })); return; }
      const failed = NV.jobs.filter((j) => j.kind === "review_set" && j.name === S.runId && j.status === "failed").pop();
      if (failed) box.append(el("p", { class: "warn-text", text: failed.error || "That run failed." }));
      let ready = false; try { ready = (await api("/api/videos")).detector_ready; } catch (e) { /* shown as not installed */ }
      if (!ready) { box.append(el("p", { class: "hint", text: "The fish detector isn't installed on this computer, so this optional step isn't available." })); return; }
      const size = el("select", { "aria-label": "Items to check" }, [30, 36, 40].map((n) => el("option", { value: n, text: n + " items", selected: n === 36 })));
      box.append(el("div", { class: "qc-actions" }, size, el("button", { type: "button", class: "primary", text: "Find items to check", on: { click: async () => {
        try { await post("/api/runs/" + enc(S.runId) + "/review_set", { count: Number(size.value) }); await pollJobs(); renderVerify(); } catch (e) { message(e.message, "error"); }
      } } })), el("p", { class: "hint", text: "This runs the model over the count points and between them. It can take several minutes on a computer without a graphics card." }));
      return;
    }
    box.append(el("p", { text: st.done + " of " + st.total + " items checked." + (st.requested && st.total < st.requested ? " The model flagged only " + st.total + " on this video, fewer than the " + st.requested + " asked for. It's set to flag few false alarms." : "") }));
    box.append(el("div", { class: "qc-actions" }, el("a", { class: "btn primary", href: "/species_bank.html?run=" + enc(S.runId) + "&set=review", text: st.done >= st.total ? "Look through the items" : st.done ? "Carry on checking" : "Start checking" }),
      el("a", { class: "btn", href: "/api/runs/" + enc(S.runId) + "/review_set.csv", text: "Download results as CSV" })));
    const rows = Object.entries(st.by_source);
    if (rows.length) box.append(el("table", { class: "qc-table" }, el("thead", {}, el("tr", {}, ["Where it came from", "Animal", "Not an animal", "Unclear"].map((t) => el("th", { text: t })))),
      el("tbody", {}, rows.map(([k, r]) => el("tr", {}, [SOURCE_WORDS[k] || k, r.animal, r.not_animal, r.unclear].map((t) => el("td", { text: String(t) })))))));
    if (st.missed && st.missed.length) box.append(el("p", { text: "Animals the counter hadn't marked, as judged here. Open a frame to look. Nothing changes unless someone recounts it." }),
      el("div", { class: "qc-actions" }, st.missed.map((m) => el("button", { type: "button", text: m.subsample_id + " at " + fmtTime(m.time_s) + (m.n > 1 ? " (" + m.n + ")" : ""), on: { click: () => { setStep("count"); select(m.subsample_id); } } }))));
    if (st.model) box.append(el("p", { class: "hint", text: "Model: " + st.model + ". These answers don't change any count." }));
  }

  // ---------- simple view ("More tools") ----------
  const isSimple = () => !S.more;
  function applyView() {
    document.body.classList.toggle("simple", isSimple());
    setPressed("more-tools", S.more);
  }
  function toggleMore() {
    S.more = !S.more; localStorage.setItem("clipsift.moretools", S.more ? "1" : "0");
    applyView();
  }

  // ---------- protocol steps: visibility, watch, count, quality check, report ----------
  function paintSteps() {
    if (!S.results) return;
    const here = S.step === "blind" ? "qc" : S.step;
    for (const b of document.querySelectorAll("#steps [data-step]")) b.setAttribute("aria-current", b.dataset.step === here ? "step" : "false");
    const notes = S.saved.latest_recording_notes || {}, tag = (k, t) => { document.querySelector('[data-state="' + k + '"]').textContent = t; };
    const seen = (S.saved.visibility || []).length, all = subs().length, counted = subs().filter((s) => primaryOf(s.subsample_id)).length, c = check(), rs = S.saved.review_set;
    tag("visibility", seen ? seen + " rated" : "");
    tag("watch", locked() || !S.whoSet ? "" : (notes.species_observed || []).length ? notes.species_observed.length + " species" : (S.saved.latest_recording_notes ? (S.saved.latest_recording_notes.none_seen ? "done" : "notes only") : ""));
    tag("count", counted + " of " + all);
    tag("qc", { pass: "done", review: "done, see notes" }[c.status] || (c.n_done + " of " + c.n_sample));
    tag("verify", rs ? rs.done + " of " + rs.total : "");
    paintReportBtn();
  }
  function setStep(step) {
    if (S.step === "watch" && step !== "watch" && S.watch.dirty) saveNotes(true);   // never lose typed notes by leaving the step
    if (locked() && ["count", "report", "verify"].includes(step)) { message("These stay closed until your blind count is done, so earlier counts can't sway it.", "warn"); step = "qc"; } else if (S.step !== step) message("");
    if (step === "report") { openReport(); return; }
    const was = S.qc, wasRecount = S.recount;
    S.step = step; S.qc = step === "blind";
    if (!S.qc) S.recount = false;
    const counting = step === "count" || step === "blind";
    $("workspace").hidden = !counting;
    for (const [id, name] of [["step-visibility", "visibility"], ["step-watch", "watch"], ["step-qc", "qc"], ["step-verify", "verify"]]) $(id).hidden = step !== name;
    setMotion(false);
    const wv = $("watch-video");
    if (step === "watch") { wv.loop = false; setWatch(S.watch.points); fillNotes(); paintWatchForm(); } else wv.pause();
    if (step !== "visibility") $("vis-video").pause();
    if (step === "visibility") renderVisibility();
    if (step === "qc") renderQc();
    if (step === "verify") { if (DEMO) renderVerify(); else pollJobs().then(renderVerify); }
    if (counting && (was !== S.qc || wasRecount !== S.recount || !S.selId)) {
      S.selId = null; renderChrome();
      if (step === "count") maybeTour();
      const q = queue(), next = q.find((id) => !isDone(id));
      if (q.length) select(next || q[0]); else showNoSelection();
    } else renderChrome();
  }

  // ---------- new video: choose, process in the background, open ----------
  const NV = { videos: [], jobs: [], timer: null, seen: {}, uploading: false, previewAsk: 0, autoOpen: null };
  const JOB_TEXT = { queued: "Waiting", running: "Processing", done: "Ready", failed: "Failed", cancelled: "Cancelled" };
  const fmtSize = (b) => (b >= 1e9 ? (b / 1e9).toFixed(1) + " GB" : Math.max(1, Math.round(b / 1e6)) + " MB");
  const fmtSpan = (s) => (s >= 3600 ? Math.floor(s / 3600) + " h " : "") + Math.floor((s % 3600) / 60) + " min " + (s % 60) + " s";
  function nvStatus(text, kind) { const p = $("nv-status"); p.textContent = text || ""; p.className = "fb-status " + (kind || ""); }
  async function loadVideos(pick) {
    const d = await api("/api/videos");
    NV.videos = d.videos;
    $("nv-folder").textContent = d.folder;
    const sel = $("nv-video"), keep = pick || sel.value; clear(sel);
    sel.append(el("option", { value: "", text: d.videos.length ? "Choose a video..." : "No videos here yet" }));
    for (const v of d.videos) sel.append(el("option", { value: v.id, text: v.id + (v.files.length > 1 ? " (" + v.files.length + " parts)" : "") + ", " + fmtSize(v.size) }));
    sel.value = keep; suggestName();
  }
  function suggestName() {
    const v = NV.videos.find((x) => x.id === $("nv-video").value);
    if (v) { $("nv-name").value = v.suggested_name; $("nv-path").value = ""; $("nv-chosen").textContent = v.id + (v.files.length > 1 ? ", " + v.files.length + " parts" : ""); }
    loadPreview();
  }
  // Frames at each minute, so a person can choose when the sediment has settled.
  async function loadPreview() {
    const video = $("nv-video").value || null, path = $("nv-path").value.trim(), box = $("nv-preview"), wrap = $("nv-preview-wrap");
    clear(box); wrap.hidden = true;
    if (!video && !path) return;
    const ask = ++NV.previewAsk;
    nvStatus("Getting frames from the video...");
    try {
      const d = await post("/api/videos/preview", { video, path });
      if (ask !== NV.previewAsk) return;
      nvStatus(""); wrap.hidden = !d.frames.length;
      NV.duration = d.duration_s;
      const n = d.names || {};
      for (const [id, v] of [["nv-id", n.video_id], ["nv-transect", n.transect], ["nv-stat", n.stat], ["nv-year", n.year], ["nv-season", n.season], ["nv-name", d.suggested_name]]) if (v != null && !$(id).value) $(id).value = v;
      paintPointCount();
      if (path) $("nv-chosen").textContent = path + (d.parts && d.parts.length > 1 ? ", joined from " + d.parts.length + " parts" : "");
      for (const f of d.frames) box.append(el("button", { type: "button", "aria-pressed": "false", title: "Start the window at " + fmtTime(f.t_s), on: { click: (e) => {
        $("nv-start").value = f.t_s; paintPointCount();
        const limit = (NV.duration || 0) > 1800 ? 900 : (NV.duration || 0) > 1500 ? 600 : 300;
        $("nv-window-hint").textContent = f.t_s > limit ? "That removes more than the protocol allows for a video this long. The start time is recorded in the report." : "The protocol starts at 1:00 and allows up to 4 more minutes.";
        for (const b of box.children) b.setAttribute("aria-pressed", b === e.currentTarget ? "true" : "false");
      } } }, el("img", { src: f.url, alt: "Frame at " + fmtTime(f.t_s) }), el("span", { text: fmtTime(f.t_s) })));
    } catch (e) { if (ask === NV.previewAsk) nvStatus(e.message, "error"); }
  }
  // The real number of points for the chosen window, so "every 15 s" doesn't surprise anyone.
  // The spacing chosen in setup: the protocol's, a preset, or a custom number of seconds.
  function chosenSpacing() {
    const v = $("nv-points").value;
    if (v === "custom") { const s = Number($("nv-every").value); return s >= 5 && s <= 600 ? s : null; }
    return v === "" ? null : Number(v);
  }
  function nvWindow() {
    const d = NV.duration, num = (id) => { const v = $(id).value; return v === "" ? null : Number(v); };
    const start = num("nv-start") ?? 60;
    return { start, end: num("nv-end") ?? Math.min(d - 60, start + 900) };
  }
  function paintPointCount() {
    const d = NV.duration;
    $("nv-custom").hidden = $("nv-points").value !== "custom";
    if (!d) { $("nv-count").textContent = ""; return; }
    if ($("nv-points").value === "custom" && chosenSpacing() == null) { $("nv-count").textContent = "Type the seconds between points (5 to 600), or how many points you want."; return; }
    const { start, end } = nvWindow(), every = chosenSpacing() ?? 60;
    const n = end > start ? Math.floor((end - start - 1) / every) + 1 : 0;
    $("nv-count").textContent = n ? "This gives " + n + (n === 1 ? " count point" : " count points") + ", one every " + every + " s." + (every !== 60 ? " The protocol uses one every 60 s, and the report will say this differs." : "") : "This window is too short for any count points. Check Window start and end under More options.";
  }
  function uploadVideo(file) {
    return new Promise((resolve, reject) => {
      const bar = $("home-upload"); bar.hidden = false; bar.value = 0;
      homeStatus("Copying " + file.name + " into ClipSift...");
      const x = new XMLHttpRequest(), done = () => { bar.hidden = true; };
      x.open("PUT", "/api/videos/upload?name=" + enc(file.name));
      x.setRequestHeader("X-ClipSift-Upload", "1");
      x.upload.onprogress = (e) => { if (e.lengthComputable) { bar.max = e.total; bar.value = e.loaded; } };
      x.onerror = () => { done(); reject(new Error("The copy stopped. Is ClipSift still running?")); };
      x.onload = () => {
        done();
        let b = null; try { b = JSON.parse(x.responseText); } catch (e) { /* not JSON */ }
        if (x.status >= 300) reject(new Error((b && b.error) || "The copy failed.")); else resolve(b);
      };
      x.send(file);
    });
  }
  function homeStatus(text, kind) { const p = $("home-status"); p.textContent = text || ""; p.className = "fb-status " + (kind || ""); }
  async function addFiles(files) {
    if (NV.uploading || !files.length) return;
    NV.uploading = true;
    try {
      let last = null;
      for (const f of files) last = await uploadVideo(f);
      homeStatus(""); await setupVideo({ id: last.id });
    } catch (e) { homeStatus(e.message, "error"); }
    NV.uploading = false; $("file-pick").value = "";
  }
  async function browse() {
    try {
      const d = await post("/api/videos/browse", {});
      if (d.unavailable) { $("file-pick").click(); return; }
      if (d.path) await setupVideo({ path: d.path });
    } catch (e) { homeStatus(e.message, "error"); }
  }
  // The setup window, for one chosen video.
  async function setupVideo(pick) {
    closeDialogs(); nvStatus("");
    NV.duration = null; $("nv-count").textContent = ""; NV.recutOf = pick.recutOf || null;
    $("nv-points").value = ""; $("nv-every").value = ""; $("nv-howmany").value = ""; $("nv-custom").hidden = true;
    $("nv-h").textContent = NV.recutOf ? "Change window or spacing" : "Set up this video";
    $("nv-start-btn").textContent = NV.recutOf ? "Cut new points" : "Start";
    for (const id of ["nv-path", "nv-name", "nv-id", "nv-start", "nv-end", "nv-transect", "nv-stat", "nv-year", "nv-season", "nv-date"]) $(id).value = "";
    $("nv-chosen").textContent = pick.path || pick.id || "Choose a video below"; $("nv-preview-wrap").hidden = true;
    $("nv-folder-wrap").hidden = !!pick.path; $("new-dlg").showModal();
    try {
      await loadVideos(pick.id);
      if (pick.path) { $("nv-video").value = ""; $("nv-path").value = pick.path; await loadPreview(); }
      await pollJobs();
    } catch (e) { nvStatus(e.message, "error"); }
  }
  async function startJob() {
    const num = (id) => { const v = $(id).value.trim(); return v === "" ? null : Number(v); };
    const body = { video: $("nv-video").value || null, path: $("nv-path").value, name: $("nv-name").value.trim(), layer: 0, window_start: num("nv-start"), window_end: num("nv-end"), video_id: $("nv-id").value.trim(), interval: chosenSpacing(),
      transect: $("nv-transect").value.trim(), stat: $("nv-stat").value.trim(), year: num("nv-year"), season: $("nv-season").value.trim(), date: $("nv-date").value };
    if ($("nv-points").value === "custom" && body.interval == null) { nvStatus("Type the seconds between points, from 5 to 600.", "error"); $("nv-every").focus(); return; }
    if (!NV.recutOf && !body.year && !body.season && !body.date && !confirm("There's no survey date, year or season. These appear on the report. Carry on without them?")) return;
    try {
      const job = NV.recutOf ? await post("/api/runs/" + enc(NV.recutOf) + "/recut", body) : await post("/api/jobs", body);
      NV.autoOpen = job.opens || job.name;
      nvStatus("Getting the count points ready. It will open when it's done.", "ok");
      await pollJobs();
    } catch (e) { nvStatus(e.message, "error"); }
  }
  function paintJobs() {
    const ul = $("nv-jobs"); clear(ul);
    $("nv-jobs-h").hidden = !NV.jobs.length;
    for (const j of NV.jobs.slice().reverse()) {
      if (j.kind === "review_set") continue;
      const live = j.status === "queued" || j.status === "running";
      const line = el("li", {}, el("span", { class: "nv-name", text: j.name.replace(/__recut$/, " (new points)") }), badge(JOB_TEXT[j.status] || j.status, j.status === "failed" ? "flag" : j.status === "done" ? "info" : ""));
      if (j.status === "running") line.append(el("span", { class: "hint", text: j.progress + ", " + fmtSpan(j.elapsed_s) }), el("progress", { max: "100", value: String(j.percent) }));
      if (j.status === "done") line.append(el("span", { class: "hint", text: "Took " + fmtSpan(j.elapsed_s) }), el("button", { type: "button", class: "primary", text: "Open", on: { click: () => openRun(j.name) } }));
      if (live) line.append(el("button", { type: "button", class: "quiet", text: "Cancel", on: { click: async () => { if (!confirm("Stop processing " + j.name + "?")) return; try { await post("/api/jobs/" + enc(j.id) + "/cancel", {}); await pollJobs(); } catch (e) { nvStatus(e.message, "error"); } } } }));
      if (j.error) line.append(el("p", { class: "warn-text", text: j.error }));
      ul.append(line);
    }
    const videoJobs = NV.jobs.filter((j) => j.kind !== "review_set");   // step 6 shows its own progress
    const run = videoJobs.find((j) => j.status === "running"), waiting = videoJobs.filter((j) => j.status === "queued").length, b = $("job-badge");
    b.hidden = !run && !waiting;
    b.textContent = run ? "Processing " + run.name.replace(/__recut$/, " (new points)") + ": " + run.progress + (waiting ? ", " + waiting + " waiting" : "") : waiting + " waiting";
  }
  async function pollJobs() {
    clearTimeout(NV.timer);
    try { NV.jobs = (await api("/api/jobs")).jobs; } catch (e) { return; }
    let finished = null;
    for (const j of NV.jobs) { if (NV.seen[j.id] && NV.seen[j.id] !== "done" && j.status === "done") finished = j; NV.seen[j.id] = j.status; }
    paintJobs();
    if (finished && finished.kind === "review_set") { if (S.runId === finished.name) { await refreshSaved(); if (S.step === "verify") renderVerify(); } }
    else if (finished) {
      await fillRuns();
      if (NV.autoOpen === finished.name) { NV.autoOpen = null; await openRun(finished.name); }
      else if (!S.results) showHome();
    }
    if (S.step === "verify" && S.results && NV.jobs.some((j) => j.kind === "review_set" && j.name === S.runId && j.status === "running")) renderVerify();
    if (NV.jobs.some((j) => j.status === "queued" || j.status === "running")) NV.timer = setTimeout(pollJobs, 2000);
  }
  async function openRun(name) { closeDialogs(); await fillRuns(); $("run-select").value = name; await loadRun(name); }

  // ---------- summary report: print it, or save it as a PDF from the print window ----------
  function paintReportBtn() {
    const shut = S.qc || locked(), b = $("report-btn"); b.disabled = shut;
    b.title = shut ? "The report shows first counts, so it stays closed until your blind count is done" : "Counts, times and species for this video, to print or save as a PDF";
  }
  function reportName(n) { const r = resolve(n); return r ? D.speciesLabel(r, S.names) : n; }
  function openReport() {
    if (S.qc || !S.results || locked()) return;
    closeDialogs();
    const rep = D.buildReport(S.results, S.saved), box = $("report-body"); clear(box);
    const dec = (v, d) => (v == null ? null : v.toFixed(d));
    const table = (cols, rows) => el("table", { class: "rp-table" }, el("thead", {}, el("tr", {}, cols.map((c) => el("th", { text: c })))), el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) => el("td", { text: c == null ? "" : String(c) }))))));
    const stat = (l, v) => el("div", { class: "rp-stat" }, el("b", { text: v == null ? "n/a" : String(v) }), el("span", { text: l }));
    const meta = [rep.transect && "Transect " + rep.transect, rep.stat && statText(rep.stat), rep.year, rep.season].filter(Boolean).join(", ");
    const qcDone = rep.qcCheck && ["pass", "review"].includes(rep.qcCheck.status);
    if (!qcDone) box.append(el("p", { class: "rp-draft", text: "DRAFT: the quality check isn't finished, so these counts aren't final." }));
    box.append(el("h1", { text: "ClipSift count report" }), el("p", { class: "rp-meta", text: "Video " + rep.video + (rep.fileName ? " (" + rep.fileName + ")" : "") + (meta ? ". " + meta : "") + "." + (rep.surveyDate ? " Surveyed " + rep.surveyDate + "." : "") + (rep.windowStart != null ? " Analysis window " + fmtTime(rep.windowStart) + " to " + fmtTime(rep.windowEnd) + "." : "") }),
      el("div", { class: "rp-stats" }, stat("Points counted", rep.counted + " of " + rep.planned), stat(rep.qcPairs ? "MeanCount, using QC averages" : "MeanCount (fish per point)", dec(rep.meanCount, 2)), stat("Standard deviation (sample)", dec(rep.sd, 2)), stat("Standard error", dec(rep.se, 2)), stat("Points with no fish", rep.zeroPoints), stat("Invertebrate MeanCount", rep.counted ? dec(rep.totalInv / rep.counted, 2) : null), stat("Fish", rep.totalFish), stat("Invertebrates", rep.totalInv), stat("Unknown", rep.totalUnknown), stat("Species identified", rep.speciesObserved.filter(D.isSpeciesName).length), stat("Unidentified or broader groups", rep.speciesObserved.filter((n) => !D.isSpeciesName(n)).length)));
    const vis = rep.visibility.map((v) => v.observer + ": " + v.category + (v.at_s != null ? " (at " + fmtTime(v.at_s) + ")" : "")).join("; "), vsum = D.visibilitySummary(rep.visibility);
    box.append(el("p", { class: "rp-meta", text: "One point every " + (rep.interval ?? "?") + " s. Visibility: " + (vis || "not recorded") + (vsum.n > 1 ? " (most common: " + vsum.usual + ")" : "") + ". Juveniles: " + (rep.juveniles == null ? "not recorded" : rep.juveniles ? "present" : "absent") + "." }));
    if (rep.interval && rep.interval !== 60) box.append(el("p", { class: "warn-text", text: "Count points are every " + rep.interval + " s here. The protocol uses every 60 s, so MeanCount isn't directly comparable with videos counted the standard way." }));
    if (rep.visibilityChanges.length) box.append(el("p", { class: "rp-meta", text: "Visibility changed by 0.5 m or more at " + rep.visibilityChanges.map((c) => fmtTime(c.t) + " (" + (c.direction === "increasing" ? "better" : "worse") + (c.category ? ", " + c.category : "") + ")").join("; ") + "." }));
    if (vsum.spread > 1) box.append(el("p", { class: "warn-text", text: "Observers' visibility ratings are more than one category apart." }));
    if (vsum.n) box.append(el("p", { class: "rp-meta", text: "Visibility limits what can be seen, so counts from clearer and poorer water aren't directly comparable." }));
    if (rep.watchNotes) box.append(el("p", { class: "rp-meta", text: "Watch window notes" + (rep.watchBy ? " (" + rep.watchBy + ")" : "") + ": " + rep.watchNotes }));
    if (rep.counted < rep.planned) box.append(el("p", { class: "warn-text", text: "Not finished: " + (rep.planned - rep.counted) + " of " + rep.planned + " points have no count yet." }));
    box.append(el("h2", { text: "Species observed in the window" }), el("p", { text: rep.speciesObserved.length ? rep.speciesObserved.map(reportName).join("; ") : (rep.noneSeen ? "None seen in the watch window." + (rep.totalFish + rep.totalInv ? " Animals were counted at points, listed below." : "") : "Not recorded yet.") }));
    box.append(el("h2", { text: "Species in counted points" }));
    box.append(rep.species.length ? table(["Species", "Count", "Points seen at", "MeanCount"], rep.species.map((s) => [reportName(s.name), s.total, s.points, s.meanCount.toFixed(2)])) : el("p", { text: "No species recorded yet." }));
    box.append(el("h2", { text: "Points" }), table(["Point", "Time", "Fish", "Used in MeanCount", "Invertebrates", "Unknown", "Species", "Features", "Visibility", "Counter", "Notes"],
      rep.points.map((p) => [p.id, fmtTime(p.t), p.counted ? p.fish : "not counted", p.finalFish, p.inv, p.unknown, Object.entries(p.species).map(([n, c]) => reportName(n) + ": " + c).join("; "), p.features, p.visibility, p.counter, p.notes])));
    if (rep.qcCheck && rep.qcPairs) {
      const [title, detail] = D.qcMessage(rep.qcCheck);
      box.append(el("h2", { text: "Quality check" }), el("p", { text: title + ". " + detail + " Formulas are provisional until Coastal Action confirms them." }),
        table(["Point", "People", "Fish", "Average", "Difference", "Invertebrates", "Average", "Difference", "Result"], Object.entries(rep.qcPoints).map(([id, q]) => { const all = D.qcCounts(q); return [id, all.people, all.fish, q.average_fish, pct(q.fish_diff, q.first_fish, q.second_fish), all.inv, q.average_inv, pct(q.inv_diff, q.first_inv, q.second_inv), qcWord(q)]; })));
      for (const [id, q] of Object.entries(rep.qcPoints)) { const rule = D.qcCounts(q).rule; if (rule) box.append(el("p", { class: "rp-meta", text: id + ": " + rule })); }
      if (rep.qcNotes.length) box.append(el("h3", { text: "Notes from quality check counts" }), table(["Point", "Counter", "Fish", "Species", "Notes"], rep.qcNotes.map((n) => [n.id, n.counter, n.fish, Object.entries(n.species).map(([k, c]) => reportName(k) + ": " + c).join("; "), n.notes])));
      if (rep.meanFirst != null) box.append(el("p", { class: "rp-meta", text: "MeanCount from first counts only: " + rep.meanFirst.toFixed(2) + "." }));
    }
    if (rep.guessAfter || rep.guessSeen) box.append(el("p", { class: "rp-meta", text: "The model's guess was shown after counting on " + rep.guessAfter + (rep.guessAfter === 1 ? " point" : " points") + (rep.guessSeen ? ", and seen before a later change to the count on " + rep.guessSeen + (rep.guessSeen === 1 ? " point" : " points") : "") + ". It never fills in a count." }));
    if (rep.reviewSet) box.append(el("p", { class: "rp-meta", text: "Model flags: " + rep.reviewSet.done + " of " + rep.reviewSet.total + " checked by a person. These do not affect any count." }));
    box.append(el("h2", { text: "Sign-off" }), el("p", { class: "rp-meta", text: "First count: " + (rep.counters.join(", ") || "none") + ". Second counts: " + (rep.secondCounters.join(", ") || "none") + ". Report opened by: " + (reviewer() || "not recorded") + "." }),
      el("p", { class: "rp-sign", text: "Reviewed by ______________________    Date ______________" }));
    box.append(el("p", { class: "rp-note", text: "Counts are a relative index, not abundance. Every count here was made by a person, with no model suggestions. Created " + new Date().toLocaleString() + "." }));
    S.report = rep;
    const shots = el("div", { class: "rp-shots" });
    if (rep.counted) box.insertBefore(el("h2", { text: "Screenshots" }), box.lastChild), box.insertBefore(shots, box.lastChild);
    $("report-dlg").showModal();
    for (const p of rep.points.filter((x) => x.counted)) addShot(shots, p);
  }
  // A counted frame with its counter's marks drawn on, like Coastal Action's marked screenshots.
  function addShot(box, p) {
    const img = new Image(), fig = el("figure", {}, el("figcaption", { text: p.id + " at " + fmtTime(p.t) + ": " + p.fish + " fish, " + (p.inv || 0) + " invertebrates. Marks by " + p.counter }));
    box.append(fig);
    img.onload = () => {
      const w = 900, h = Math.round((w * img.naturalHeight) / img.naturalWidth), c = el("canvas", { width: w, height: h }), g = c.getContext("2d");
      const rec = S.results.recording || {}, k = w / (rec.width || img.naturalWidth);
      g.drawImage(img, 0, 0, w, h); g.lineWidth = 2;
      for (const l of (S.saved.point_labels || []).filter((x) => x.subsample_id === p.id && x.counter === p.counter)) {
        g.strokeStyle = l.kind === "unsure" ? "#ffb04d" : l.kind === "invertebrate" ? "#6fd3ff" : "#ffe94d"; g.setLineDash(l.kind === "unsure" ? [4, 3] : []); g.beginPath();
        if (l.w != null && l.h != null) g.ellipse((l.x + l.w / 2) * k, (l.y + l.h / 2) * k, (l.w / 2) * k, (l.h / 2) * k, 0, 0, Math.PI * 2);
        else g.arc(l.x * k, l.y * k, 7, 0, Math.PI * 2);
        g.stroke();
      }
      fig.prepend(el("img", { src: c.toDataURL("image/jpeg", 0.8), alt: "Frame at " + fmtTime(p.t) }));
    };
    img.src = Data.mediaUrl(S.runId, "subsamples", p.id, "still");
  }
  function downloadReportCsv() {
    const url = URL.createObjectURL(new Blob([D.reportCsv(S.report, fmtTime)], { type: "text/csv" }));
    const a = el("a", { href: url, download: S.runId + "_report.csv" }); document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  // ---------- dialogs: help and feedback ----------
  function openHelp() { closeDialogs(); $("help-dlg").showModal(); $("help-dlg").querySelector(".drawer-body").scrollTop = 0; }
  function closeDialogs() { document.querySelectorAll("dialog[open]").forEach((d) => d.close()); }
  function feedbackContext() {
    const ctx = { run: S.runId || null, view: (isSimple() ? "simple" : "more tools") + ", " + "step " + S.step, demo: !!DEMO };
    if (S.selId) ctx[S.mode === "sub" ? "subsample_id" : "segment_id"] = S.selId;
    return ctx;
  }
  function openFeedback() {
    closeDialogs();
    $("fb-name").value = localStorage.getItem("clipsift.feedback_name") || reviewer() || "";
    $("fb-status").textContent = ""; $("fb-status").className = "fb-status";
    const c = feedbackContext();
    $("fb-context").textContent = "Sent with your note: run " + (c.run || "none chosen") + (c.subsample_id || c.segment_id ? ", " + (c.subsample_id || c.segment_id) : "") + ", view " + c.view + ".";
    $("feedback-dlg").showModal(); $("fb-message").focus();
  }
  async function sendFeedback(e) {
    e.preventDefault();
    const st = $("fb-status"), msg = $("fb-message").value.trim();
    if (!msg) { st.className = "fb-status error"; st.textContent = "Write a short note first."; $("fb-message").focus(); return; }
    const name = $("fb-name").value.trim();
    localStorage.setItem("clipsift.feedback_name", name);
    $("fb-send").disabled = true; st.className = "fb-status"; st.textContent = "Sending...";
    try {
      await Data.feedback({ name, area: $("fb-area").value, type: $("fb-type").value, message: msg, page_context: feedbackContext(), website: $("fb-website").value });
      $("fb-message").value = ""; st.className = "fb-status ok"; st.textContent = "Thank you. Your note was sent to the team.";
    } catch (err) {
      st.className = "fb-status error"; st.textContent = "Your note was not sent: " + err.message + " Your text is still here. Please try again, or tell the team in person.";
    } finally { $("fb-send").disabled = false; }
  }

  // ---------- first-visit tour (hand written, no library) ----------
  const TOUR = [
    { target: "steps", title: "Follow the steps", body: "These steps follow Coastal Action's protocol, in order. Each one shows its progress. The ? button at the top has more help." },
    { target: "timeline-wrap", title: "The whole recording", body: "Each tick is a point to count. Grey means not counted yet, green means done. Click a tick to jump to it." },
    { target: "stage-wrap", title: "Play, then mark", body: "Hold Space to play 5 seconds either side in the picture. The yellow border shows the count second. Then click each animal to place a dot. Not sure about one? Leave it out." },
    { target: "side-sub", title: "Check your count", body: "The totals fill in from your dots. Tick which features you can see, and note any change in visibility." },
    { target: "save-sub", title: "Save and go to the next", body: "Press Save to keep your count and open the next point. The ? button at the top has help and can replay this tour." },
  ];
  const tour = { i: 0, on: false, opener: null };
  const tourOn = () => tour.on;
  function maybeTour() {
    if (localStorage.getItem("clipsift.tour_done") === "1" || tour.on) return;
    setTimeout(() => { if (!tour.on && localStorage.getItem("clipsift.tour_done") !== "1") startTour(); }, 400);
  }
  function startTour() {
    closeDialogs();
    if (!S.results || $("workspace").hidden) { openHelp(); return; }
    tour.on = true; tour.i = 0; tour.opener = document.activeElement; $("tour").hidden = false; showTourStep();
  }
  function endTour() {
    if (!tour.on) return;
    tour.on = false; $("tour").hidden = true; localStorage.setItem("clipsift.tour_done", "1");
    if (tour.opener && tour.opener.focus) tour.opener.focus();
  }
  function showTourStep() {
    // skip steps whose part of the screen is not showing (for example a run with no subsample points)
    while (tour.i < TOUR.length && !visible($(TOUR[tour.i].target))) tour.i++;
    if (tour.i >= TOUR.length) { endTour(); return; }
    const n = TOUR.filter((t) => visible($(t.target))), pos = n.indexOf(TOUR[tour.i]);
    const step = TOUR[tour.i], target = $(step.target);
    target.scrollIntoView({ block: "center", behavior: "auto" });
    $("tour-step").textContent = "Step " + (pos + 1) + " of " + n.length;
    $("tour-title").textContent = step.title; $("tour-body").textContent = step.body;
    $("tour-back").hidden = pos === 0; $("tour-next").textContent = pos === n.length - 1 ? "Done" : "Next";
    placeTour(); $("tour-next").focus();
  }
  function visible(node) { return !!node && !node.hidden && !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length); }
  function placeTour() {
    if (!tour.on) return;
    const t = $(TOUR[tour.i].target).getBoundingClientRect(), hole = $("tour-hole"), card = $("tour-card"), pad = 6;
    const vw = window.innerWidth, vh = window.innerHeight;
    const top = Math.max(0, t.top - pad), bottom = Math.min(vh, t.bottom + pad);
    hole.style.left = Math.max(0, t.left - pad) + "px"; hole.style.top = top + "px";
    hole.style.width = Math.min(vw, t.right + pad) - Math.max(0, t.left - pad) + "px"; hole.style.height = bottom - top + "px";
    const ch = card.offsetHeight, cw = card.offsetWidth;
    let y = bottom + 12;
    if (y + ch > vh) y = top - ch - 12;
    if (y < 8) y = Math.max(8, Math.min(vh - ch - 8, vh / 2 - ch / 2));  // target fills the screen: float the card over it
    card.style.top = y + "px"; card.style.left = Math.max(8, Math.min(vw - cw - 8, t.left)) + "px";
  }
  function tourMove(d) {
    const n = TOUR.filter((t) => visible($(t.target)));
    let pos = n.indexOf(TOUR[tour.i]) + d;
    if (pos >= n.length) { endTour(); return; }
    if (pos < 0) pos = 0;
    tour.i = TOUR.indexOf(n[pos]); showTourStep();
  }
  function onTourKey(e) {
    if (!tour.on) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); endTour(); return; }
    if (e.key === "Tab") {  // keep Tab inside the tour card
      const f = [...$("tour-card").querySelectorAll("button")].filter((b) => !b.hidden);
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      else if (!$("tour-card").contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    }
    else if (e.key === "ArrowRight") { e.preventDefault(); tourMove(1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); tourMove(-1); }
  }

  // ---------- wiring ----------
  function wireStatic() {
    $("run-select").addEventListener("change", (e) => loadRun(e.target.value));
    $("more-tools").addEventListener("click", toggleMore);
    $("help-btn").addEventListener("click", openHelp);
    $("help-close").addEventListener("click", () => $("help-dlg").close());
    $("help-tour").addEventListener("click", startTour);
    $("feedback-btn").addEventListener("click", openFeedback);
    $("new-video").addEventListener("click", showHome);
    $("home-btn").addEventListener("click", () => { if (DEMO) return; closeDialogs(); showHome(); });
    $("who-btn").addEventListener("click", askWho);
    $("who-form").addEventListener("submit", addWho);
    $("who-cancel").addEventListener("click", () => $("who-dlg").close());
    $("browse-btn").addEventListener("click", browse);
    $("file-pick").addEventListener("change", (e) => addFiles([...e.target.files]));
    $("home-path-go").addEventListener("click", () => { const p = $("home-path").value.trim(); if (p) setupVideo({ path: p }); });
    const drop = $("drop");
    for (const ev of ["dragenter", "dragover"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); });
    for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); });
    drop.addEventListener("drop", (e) => addFiles([...e.dataTransfer.files]));
    for (const ev of ["dragover", "drop"]) window.addEventListener(ev, (e) => e.preventDefault());   // a missed drop must not navigate away
    $("vis-save").addEventListener("click", saveVisibility);
    $("vis-first").addEventListener("click", () => { S.visWhole = false; paintVisVideo(); });
    $("vis-whole").addEventListener("click", () => { S.visWhole = true; paintVisVideo(); });
    $("watch-whole").addEventListener("click", () => { $("watch-video").loop = false; setWatch(false); });
    $("watch-points").addEventListener("click", () => setWatch(true));
    for (const b of document.querySelectorAll("[data-wspeed]")) b.addEventListener("click", () => {
      document.querySelectorAll("[data-wspeed]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
      $("watch-video").playbackRate = parseFloat(b.dataset.wspeed);
    });
    for (const id of ["rn-notes", "rn-none"]) $(id).addEventListener("input", () => { S.watch.dirty = true; });
    for (const r of document.querySelectorAll("input[name=juv]")) r.addEventListener("change", () => { S.watch.dirty = true; });
    $("watch-reveal").addEventListener("click", () => { S.watch.reveal = true; paintWatchForm(); });
    $("who-dlg").addEventListener("cancel", (e) => { if (!S.whoSet && S.results) e.preventDefault(); });
    $("who-dlg").addEventListener("close", () => { if (!S.whoSet && S.results) $("who-dlg").showModal(); });   // the name can't be skipped
    $("rn-none").addEventListener("change", () => { if ($("rn-none").checked) { S.watch.species = []; paintWatchSpecies(); } });
    for (const r of document.querySelectorAll("input[name=vdir]")) r.addEventListener("change", paintVisDir);
    $("nv-close").addEventListener("click", () => $("new-dlg").close());
    $("nv-start-btn").addEventListener("click", startJob);
    $("nv-video").addEventListener("change", suggestName);
    for (const b of document.querySelectorAll("#steps [data-step]")) b.addEventListener("click", () => setStep(b.dataset.step));
    for (const b of document.querySelectorAll("[data-note]")) b.addEventListener("click", () => {
      const box = $("c-notes"), text = b.dataset.note;
      if (!box.value.includes(text)) box.value = (box.value.trim() + " " + text).trim();
    });
    makeCombo($("rn-sp-input"), $("rn-sp-list"), (sel) => {
      if (sel.value && !S.watch.species.includes(sel.value)) { S.watch.species.push(sel.value); S.watch.dirty = true; }
      $("rn-sp-input").value = ""; paintWatchSpecies();
    });
    $("report-close").addEventListener("click", () => $("report-dlg").close());
    $("report-print").addEventListener("click", () => window.print());
    $("report-csv").addEventListener("click", downloadReportCsv);
    $("feedback-form").addEventListener("submit", sendFeedback);
    $("fb-cancel").addEventListener("click", () => $("feedback-dlg").close());
    $("help-dlg").addEventListener("click", (e) => { if (e.target === $("help-dlg")) $("help-dlg").close(); });
    $("tour-next").addEventListener("click", () => tourMove(1)); $("tour-back").addEventListener("click", () => tourMove(-1));
    $("tour-skip").addEventListener("click", endTour);
    document.addEventListener("keydown", onTourKey, true);
    window.addEventListener("resize", placeTour); window.addEventListener("scroll", placeTour, true);
    for (const a of document.querySelectorAll("[data-export]")) a.addEventListener("click", (e) => {
      if (!Data.download) return;
      e.preventDefault();
      Data.download(S.runId, a.dataset.export).catch((err) => message("Could not make the file: " + err.message, "error"));
    });
    $("demo-reset").addEventListener("click", () => {
      if (!confirm("Clear all the counts and marks you saved in this browser for the demo?")) return;
      Data.clearAll(); if (S.runId) loadRun(S.runId);
    });
    $("toggle-diff").addEventListener("click", () => toggle("diff"));
    $("toggle-grid").addEventListener("click", () => toggle("grid"));
    $("grid-rows").addEventListener("change", renderGrid); $("grid-cols").addEventListener("change", renderGrid);
    for (const k of ["brightness", "contrast", "saturation"]) $("f-" + k).addEventListener("input", (e) => { S.filters[k] = parseInt(e.target.value, 10); applyFilters(); });
    $("filter-reset").addEventListener("click", resetFilters);
    for (const k of ["brightness", "contrast", "saturation"]) {
      $("f-" + k).addEventListener("change", (e) => { S.filters[k] = parseInt(e.target.value, 10); applyFilters(); });  // some browsers only fire change
      $("f-" + k).addEventListener("dblclick", () => { S.filters[k] = 100; applyFilters(); });
    }
    for (const b of document.querySelectorAll("[data-speed]")) b.addEventListener("click", () => {
      document.querySelectorAll("[data-speed]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
      $("stage-clip").playbackRate = parseFloat(b.dataset.speed);
    });
    $("step-back").addEventListener("click", () => frameStep(-1)); $("step-fwd").addEventListener("click", () => frameStep(1));
    for (const b of document.querySelectorAll("[data-decision]")) b.addEventListener("click", () => saveDecision(b.dataset.decision));
    // segment species combo
    const segCombo = makeCombo($("species"), $("species-list"), (sel) => { $("species").value = shownName(sel.value); S.seg.species = sel.value ? sel : null; paintSpeciesStatus(); });
    segCombo.onType = (text) => { const t = text.trim(); S.seg.species = t ? (resolve(t) ? { value: resolve(t).sci, free: false } : { value: t, free: true }) : null; paintSpeciesStatus(); };
    $("alias-add").addEventListener("click", async () => {
      const a = $("alias-input").value.trim(), sp = S.seg.species;
      if (!a || !sp || sp.free) return;
      try { await Data.addAlias({ alias: a, maps_to: sp.value }); $("alias-input").value = ""; await loadSpecies(); paintSpeciesStatus(); message("Added \"" + a + "\" as a local name for " + sp.value + ". The species list file is unchanged.", "ok"); }
      catch (e) { message("Not saved: " + e.message, "error"); }
    });
    makeCombo($("ss-species"), $("ss-species-list"), addSpecies);
    makeCombo($("p-species"), $("p-species-list"), (sel) => { $("p-species").value = shownName(sel.value); }, { kind: markKind, showAll: true });
    for (const r of document.querySelectorAll("input[name=pkind]")) r.addEventListener("change", kindChanged);
    for (const b of document.querySelectorAll("[data-names]")) b.addEventListener("click", () => setNames(b.dataset.names));
    for (const p of D.ENHANCE_PRESETS) $("enhance-group").append(el("button", { type: "button", "data-enhance": p.id, title: p.title, text: p.label, on: { click: () => { S.enhance = p.id; applyFilters(); } } }));
    $("hold-restart").addEventListener("click", () => setRestart(!S.restart));
    $("count-only").addEventListener("click", () => setCountOnly(!S.countOnly));
    $("motion-btn").addEventListener("click", () => { S.spaceStarted = false; setMotion(!S.motion); });
    setPressed("count-only", S.countOnly);
    S.clip = D.clipControl({ video: $("stage-clip"), track: document.querySelector("#clip-hud .lb-track"), range: clipRange, active: () => S.motion, paint: paintHud,
      release: () => { S.held = true; paintHud(); } });   // stays paused where it was dropped
    document.addEventListener("keyup", (e) => { if (e.key === " " && S.spaceDown) { e.preventDefault(); spaceUp(); } });
    window.addEventListener("blur", spaceUp);
    // After a mouse click, hand the keyboard back to the page, so Space plays the clip instead of pressing that control again.
    document.addEventListener("click", (e) => {
      if (!e.detail) return;
      setTimeout(() => { const a = document.activeElement; if (a && a.matches("button, input[type=checkbox], input[type=radio]") && !a.closest("dialog, .tour")) a.blur(); });
    });
    for (const id of ["c-fish", "c-inv"]) $(id).addEventListener("input", () => { paintCharsWarn(); paintSpeciesSum(); });
    $("chars").addEventListener("change", paintCharsWarn);
    $("save-sub").addEventListener("click", saveSubsample);
    $("no-animals").addEventListener("click", noAnimals);
    $("guess-on").addEventListener("change", (e) => { S.guess.on = e.target.checked; });
    $("c-unk").addEventListener("input", () => { S.ss.unkTouched = true; });
    $("others-marks").addEventListener("change", (e) => { S.showOthers = e.target.checked; renderLabels(false); });
    $("big-view").addEventListener("click", toggleBig);
    paintBig();
    $("watch-video").addEventListener("timeupdate", () => {
      const p = (S.results && S.results.protocol) || {}, v = $("watch-video");
      $("watch-clock").textContent = S.watch.points || p.window_start_s == null ? "" : "Video time " + fmtTime(Math.floor(p.window_start_s + v.currentTime)) + ". Use this time in notes, because it matches the count points.";
    });
    for (const id of ["nv-start", "nv-end", "nv-points", "nv-every"]) $(id).addEventListener("input", paintPointCount);
    $("nv-howmany").addEventListener("input", () => {   // a number of points becomes the spacing that fits them in the window
      const n = Number($("nv-howmany").value); if (!NV.duration || !(n >= 1)) return;
      const { start, end } = nvWindow();
      $("nv-every").value = Math.max(5, Math.min(600, n > 1 ? Math.floor((end - start - 1) / (n - 1)) : 600));
      paintPointCount();
    });
    $("nv-points").addEventListener("change", paintPointCount);
    $("rn-save").addEventListener("click", saveNotes);
    wireTools();
    document.addEventListener("keydown", onKey);
  }
  init().then(() => { if (!DEMO) pollJobs(); });
})();
