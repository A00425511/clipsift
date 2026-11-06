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
    mode: "sub", selId: null, qc: false, step: "count",
    diff: false, grid: false, boxes: false,   // boxes = "Show model suggestions"; always off at run load, never stored
   
    seg: { species: null }, ss: { rows: [] },
    filters: { brightness: 100, contrast: 100, saturation: 100 }, enhance: "off",
    markHistory: [], motion: false, restart: true, countOnly: false, spaceDown: false, spaceStarted: false, stopAfterDrag: false, loopWasPlaying: false, hudRaf: 0, names: "common",
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
  function percentDifference(a, b) {  // same placeholder formula as app/server.py
    if (a == null || b == null) return null;
    if (a === 0 && b === 0) return 0;
    return Math.abs(a - b) / ((a + b) / 2) * 100;
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
    function qcAndMeans(results, subReviews) {
      const proto = Object.assign({ qc_max_percent_diff: DEMO_PERCENT_DIFF_MAX, qc_agreement: DEMO_AGREEMENT }, results.protocol || {});
      const primary = {}, second = {};
      for (const r of subReviews) { if (r.pass === "primary") primary[r.subsample_id] = r; else if (r.pass === "qc_blind" || r.pass === "recount") second[r.subsample_id] = r; }
      const qc = {};
      for (const [sid, sec] of Object.entries(second)) {
        const first = primary[sid]; if (!first) continue;
        const a = (first.total_fish_count || 0) + (first.invertebrate_count || 0), b = (sec.total_fish_count || 0) + (sec.invertebrate_count || 0);
        const diff = percentDifference(a, b);
        qc[sid] = { first_total: a, second_total: b, percent_diff: diff, first_counter: first.counter, second_counter: sec.counter, recount_needed: diff != null && diff > proto.qc_max_percent_diff };
      }
      const diffs = Object.values(qc).map((q) => q.percent_diff).filter((d) => d != null);
      const fish = Object.values(primary).map((r) => r.total_fish_count).filter((v) => v != null);
      return {
        latest_primary: primary, qc, qc_agreement: diffs.length ? Math.round((100 - diffs.reduce((x, y) => x + y, 0) / diffs.length) * 10) / 10 : null,
        qc_agreement_target: proto.qc_agreement, n_counted: Object.keys(primary).length, n_subsamples: (results.subsamples || []).length,
        mean_count_reviewed: fish.length ? Math.round((fish.reduce((x, y) => x + y, 0) / fish.length) * 1000) / 1000 : null,
      };
    }
    // ---- CSV exports, generated in the browser (mirror app/server.py) ----
    const SEG_COLS = [["recording_id", "Recording folder name."], ["segment_id", "Segment id from results.json."], ["start_s", "Segment start, seconds from the start of the recording."], ["end_s", "Segment end, seconds."], ["kind", "active, or set_aside (no activity found, time is kept)."], ["audit_sample", "true if this set-aside segment was picked at random as a check."], ["status", "Model status: known, fish_unknown, unclear, movement_unidentified, none."], ["motion_score", "Motion score from the pipeline. Blank means not computed."], ["visibility_score", "Visibility score from the pipeline. Blank means not computed."], ["flag_shake", "true if camera shake was flagged."], ["flag_low_visibility", "true if low visibility was flagged."], ["review_priority", "Higher means it was shown earlier in the queue."], ["model_maxn", "Model MaxN: the most fish seen in one frame. A relative index, not abundance."], ["model_mean_count", "Model mean fish per sampled frame. A relative index, not abundance."], ["model_unique_tracks", "Number of separate fish tracks. A relative index, not abundance."], ["decision", "Reviewer decision: confirm, reject, unknown, needs_second_look."], ["species", "Species the reviewer entered. Blank if none."], ["species_free_text", "true if the species was typed and is not in the species list. Check these."], ["count", "Fish count the reviewer entered. A relative index, not abundance."], ["note", "Reviewer note."], ["reviewer", "Reviewer name as typed."], ["reviewed_at", "When the latest decision was saved (UTC)."], ["n_decisions", "How many decisions were saved for this segment. Only the latest is shown here."], ["n_grid_tags", "How many grid cell tags were saved for this segment."]];
    const SUB_COLS = [["Video ID", "Video ID from results.json. Must match the Coastal Action spreadsheet."], ["Subsample", "Subsample point id."], ["Time (s)", "Seconds from the start of the recording."], ["Counter", "Who counted."], ["Pass", "primary, qc_blind (second blind count) or recount."], ["Total fish count", "Fish counted in the designated second. A relative index, not abundance."], ["Invertebrate count", "Invertebrates counted in the designated second. A relative index."], ["Number of species", "Species in this subsample."], ["Unknown/Unable to ID due to visibility", "Count that could not be identified because of visibility."], ["Visibility category", "Water clarity category for this point."], ["Visibility change >= 0.5 m", "yes if visibility changed by 0.5 m or more."], ["Characteristics ticked", "Of shape, anatomical features, colour or flashes, swimming behaviour."], ["Notes", "Reviewer notes. Movement noted as unidentified is a note, never counted."], ["Saved at (UTC)", "When the count was saved."], ["QC percent difference", "Primary vs second count difference. Formula is provisional."], ["QC recount needed", "yes if the difference is over the configured limit."]];
    const csvText = D.csvText;
    async function csvFor(id, name) {
      const results = await this.results(id);
      const rec = results.recording || {};
      const revs = load(id, "subsample_reviews"), info = qcAndMeans(results, revs);
      if (name === "export_columns.csv") return csvText(["column", "meaning"], SUB_COLS.concat([["Video summary: MeanCount", "Mean of Total fish count over latest primary counts. A relative index, not abundance."]], SEG_COLS));
      if (name === "export.csv") {
        const vid = rec.video_id || rec.recording_id || id;
        const times = {}; for (const s of results.subsamples || []) times[s.subsample_id] = s.t_s;
        const names = [...new Set(revs.flatMap((r) => Object.keys(r.species_counts || {})))].sort();
        const rows = revs.map((r) => {
          const q = r.pass !== "primary" ? info.qc[r.subsample_id] : null, sc = r.species_counts || {};
          return [vid, r.subsample_id, times[r.subsample_id], r.counter, r.pass, r.total_fish_count, r.invertebrate_count, r.total_species, r.unknown_count, r.visibility_category,
            r.visibility_change == null ? "" : (r.visibility_change ? "yes" : "no"), (r.characteristics || []).join(";"), r.notes, r.at,
            q && q.percent_diff != null ? q.percent_diff : "", q ? (q.recount_needed ? "yes" : "no") : ""].concat(names.map((n) => (n in sc ? sc[n] : "")));
        });
        return csvText(SUB_COLS.map((c) => c[0]).concat(names.map((n) => "Count: " + n)), rows);
      }
      if (name === "export_summary.csv") {
        const notes = load(id, "recording_notes"), n = notes[notes.length - 1] || {}, proto = results.protocol || {};
        const species = new Set(n.species_observed || []);
        for (const r of Object.values(info.latest_primary)) for (const k of Object.keys(r.species_counts || {})) species.add(k);
        const vis = (n.visibility_by_observer || []).map((v) => v.observer + ": " + v.category).join("; ");
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
    return {
      demo: true,
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
          recording_notes: notes, latest_recording_notes: notes.length ? notes[notes.length - 1] : null }, qcAndMeans(results, sub));
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
  const reviewer = () => $("reviewer").value.trim();
  const isTyping = (t) => t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT") && t.type !== "checkbox" && t.type !== "range";

  // ---------- startup ----------
  async function init() {
    $("reviewer").value = localStorage.getItem("clipsift.reviewer") || "";
    $("reviewer").addEventListener("change", () => localStorage.setItem("clipsift.reviewer", reviewer()));
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
    applyView(); nameHint();
    await loadSpecies();
    try {
      const runs = await fillRuns();
      if (!runs.length) {
        showEmpty(DEMO ? "The demo recordings did not load. Try refreshing the page. If it keeps happening, tell the team with the Feedback button."
          : "No recordings to review yet. Press New video at the top to add one.");
        return;
      }
      const sel = $("run-select");
      showEmpty("Pick a recording from the Run menu at the top to begin. New here? Press the ? button for a quick guide.");
      const want = new URLSearchParams(location.search).get("run");
      if (want && runs.some((r) => r.run_id === want)) { sel.value = want; loadRun(want); }
      else if (runs.length === 1 || DEMO) { const first = (DEMO && runs.find((r) => !r.fixture)) || runs[0]; sel.value = first.run_id; loadRun(first.run_id); }
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
  function showEmpty(text) {
    $("empty").textContent = text; $("empty").hidden = !text;
    if (text) for (const id of ["workspace", "summary", "timeline-wrap", "steps", "step-visibility", "step-watch"]) $(id).hidden = true;
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
    if (!id) { showEmpty("Pick a recording from the Run menu at the top to begin."); return; }
    message("");
    try {
      const [results, saved] = await Promise.all([Data.results(id), Data.saved(id)]);
      S.runId = id; S.results = results; S.saved = saved; S.selId = null;
      S.boxes = false; paintSuggestToggle();
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
    const started = Object.keys(S.saved.latest_primary || {}).length || S.saved.latest_recording_notes;
    setStep(started ? "count" : "visibility");
    nameHint();
    maybeTour();
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
    const all = subs();
    let marked = all.filter((s) => s.qc_sample);
    let chosenByApp = false;
    if (!marked.length && all.length) {
      const p = proto();
      let n = Math.round(p.qc_share * all.length);
      n = Math.min(all.length, Math.max(p.qc_min, Math.min(p.qc_max, n)));
      let seed = 0;
      for (const ch of S.runId) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
      const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
      const ids = all.map((s) => s.subsample_id);
      for (let i = ids.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [ids[i], ids[j]] = [ids[j], ids[i]]; }
      const pick = new Set(ids.slice(0, n));
      marked = all.filter((s) => pick.has(s.subsample_id));
      chosenByApp = true;
    }
    return { items: marked.slice().sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0)), chosenByApp };
  }
  function queue() {
    if (S.mode === "sub") {
      if (S.qc) return qcSample().items.map((s) => s.subsample_id);
      return subs().slice().sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0)).map((s) => s.subsample_id);   // systematic: time order, never by activity
    }
    return [];
  }
  function unit(id, mode) {
    mode = mode || S.mode;
    return mode === "sub" ? subs().find((s) => s.subsample_id === id) : segs().find((s) => s.segment_id === id);
  }
  const primaryOf = (id) => (S.saved.latest_primary || {})[id];
  const secondOf = (id) => { let r = null; for (const x of S.saved.subsample_reviews || []) if (x.subsample_id === id && x.pass !== "primary") r = x; return r; };
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
    box.append(item("MeanCount, by hand (index)", S.qc ? "hidden in QC mode" : fmtNum(S.saved.mean_count_reviewed, 2)));
    const meta = [rec.transect && "Transect " + rec.transect, rec.stat && statText(rec.stat), rec.year, rec.season, S.results.run && S.results.run.layer != null && "Layer " + S.results.run.layer].filter(Boolean).join(" . ");
    if (meta) box.append(el("div", { class: "stat meta", text: meta }));
  }
  function renderProgress() {
    const wrap = $("progress-wrap"); wrap.hidden = false;
    const ids = queue(), done = ids.filter(isDone).length;
    let t = (S.mode === "sub" ? (S.qc ? "QC counted " : "Counted ") : "Reviewed ") + done + " of " + ids.length;
    if (S.mode === "sub" && !S.qc && S.saved.mean_count_reviewed != null) t += " . MeanCount so far " + S.saved.mean_count_reviewed.toFixed(2);
    $("progress-text").textContent = t;
    $("progress-bar").max = Math.max(1, ids.length); $("progress-bar").value = done;
  }
  function renderTimeline() {
    const wrap = $("timeline-wrap"), tl = $("timeline"); clear(tl);
    const rec = S.results.recording || {}, list = segs(), ss = subs();
    let dur = rec.duration_s;
    if (!dur) dur = Math.max(1, ...list.map((s) => s.end_s || 0), ...ss.map((s) => s.t_s || 0));
    wrap.hidden = !ss.length || !["count", "qc"].includes(S.step);
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
      const withFirst = q.items.filter((s) => primaryOf(s.subsample_id)).length;
      note.textContent = "QC sample: " + q.items.length + " points" + (q.chosenByApp ? " (picked at random by this app, same every time)" : "") + ". " + withFirst + " already have a first count. Earlier counts and model suggestions are hidden.";
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
      b.append(el("span", { class: "q-done", text: done ? "✓ done" : "" }));
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
    $("clip-tools").querySelector("#to-count").hidden = S.mode !== "sub";
    renderQueue(); renderTimeline();
    const cur = $("queue-list").querySelector(".current"); if (cur) cur.scrollIntoView({ block: "nearest" });
    S.diff = false; setPressed("toggle-diff", false); $("movement-hint").hidden = true;
    setMotion(false);
    loadMedia(u);
    S.zoom = { k: 1, x: 0, y: 0 }; applyZoom();
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
    $("boxes").setAttribute("viewBox", "0 0 " + (rec.width || 1600) + " " + (rec.height || 900));
    showStill();
    const v = $("loop"); v.pause();
    $("loop-missing").hidden = true; v.hidden = false;
    v.onerror = () => { v.hidden = true; $("loop-missing").hidden = false; $("loop-missing").textContent = "No clip file for this " + (S.mode === "sub" ? "point" : "segment") + ". You can still use the still image."; };
    v.src = mediaUrl(S.mode === "sub" ? "context" : "loop");
    v.load();
    v.playbackRate = currentSpeed();
    v.play().catch(() => { /* autoplay may be blocked; the controls still work */ });
    const sc = $("stage-clip");
    sc.dataset.ok = "1"; sc.onerror = () => { sc.dataset.ok = ""; setMotion(false); };
    sc.src = v.src; sc.load();
    applyFilters();
  }
  function showStill() {
    const img = $("still"), miss = $("media-missing");
    miss.hidden = true; img.hidden = false;
    img.onerror = () => { img.hidden = true; miss.hidden = false; miss.textContent = S.diff ? "No movement view for this " + (S.mode === "sub" ? "point" : "segment") + "." : "No still image for this " + (S.mode === "sub" ? "point" : "segment") + "."; };
    img.onload = () => { if (S.mode === "sub") renderLabels(false); };
    img.src = mediaUrl(S.diff ? "diff" : "still");
    img.alt = S.diff ? "Movement view: bright areas changed between frames" : "Still frame";
    drawBoxes();
  }
  // Model suggestions (boxes and numbers) show only when asked for, and never in QC mode.
  const suggestionsOn = () => S.boxes && !(S.mode === "sub" && S.qc);
  function paintSuggestToggle() {
    const cb = $("show-suggest"), blocked = S.mode === "sub" && S.qc;
    cb.checked = suggestionsOn(); cb.disabled = blocked;
    cb.title = blocked ? "Model suggestions stay hidden in QC mode" : "Show or hide the model's boxes and numbers";
    $("suggest-caution").hidden = !cb.checked;
  }
  function drawBoxes() {
    const svg = $("boxes"); clear(svg);
    const u = unit(S.selId);
    svg.hidden = true;
    if (!u || !suggestionsOn() || S.diff) return;
    const dets = (S.mode === "sub" ? (u.auto && u.auto.detections) : u.detections || []).filter((d) => !d.static);  // static = pipe, pole or seabed
    if (!Array.isArray(dets) || !dets.length) return;
    svg.hidden = false;
    const NS = "http://www.w3.org/2000/svg";
    dets.forEach((d, i) => {
      if (!d || !Array.isArray(d.box) || d.box.length < 4 || d.box.some((n) => typeof n !== "number")) return;
      const r = document.createElementNS(NS, "rect");
      r.setAttribute("x", d.box[0]); r.setAttribute("y", d.box[1]); r.setAttribute("width", d.box[2]); r.setAttribute("height", d.box[3]);
      r.setAttribute("class", "det-box"); r.setAttribute("vector-effect", "non-scaling-stroke");
      const t = document.createElementNS(NS, "title");
      t.textContent = "Detection " + (i + 1) + (d.score != null ? ", score " + d.score : "") + (d.track_id != null ? ", track " + d.track_id : "");
      r.append(t); svg.append(r);
    });
  }
  function setPressed(id, on) { $(id).setAttribute("aria-pressed", on ? "true" : "false"); }
  function applyFilters() {
    const f = S.filters, extra = D.enhanceFilter(S.enhance);
    const v = "brightness(" + f.brightness + "%) contrast(" + f.contrast + "%) saturate(" + f.saturation + "%)" + (extra ? " " + extra : "");
    $("still").style.filter = v; $("loop").style.filter = v; $("stage-clip").style.filter = v;
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
    $("hud-speed").textContent = currentSpeed() + "x";
    $("hud-head").style.left = Math.min(100, (t / len) * 100) + "%";
    const inWin = off != null && D.inCount(t, off, countSec());
    $("hud-count").hidden = !inWin; $("stage").classList.toggle("counting", inWin);
  }
  function hudLoop() { if (!S.motion) { S.hudRaf = 0; return; } S.clip.tick(); paintHud(); S.hudRaf = requestAnimationFrame(hudLoop); }
  function setMotion(on) {
    const v = $("stage-clip"), loop = $("loop");
    on = !!on && !!S.selId && v.dataset.ok === "1";
    if (on === S.motion) return;
    S.motion = on;
    $("clip-hud").hidden = !on; $("stage").classList.toggle("playing", on); setPressed("motion-btn", on);
    const r = clipRange();
    if (on) {
      S.loopWasPlaying = !loop.paused; loop.pause();
      v.playbackRate = currentSpeed();
      const outside = v.currentTime < r.start - 0.05 || v.currentTime > r.end;
      if (outside || (S.restart && v.currentTime > r.start + 0.1)) v.currentTime = r.start;   // already rewound on release, so usually nothing to do
      v.play().catch(() => {});
      if (!S.hudRaf) S.hudRaf = requestAnimationFrame(hudLoop);
    } else {
      v.pause();     // back to the exact still, nothing moved
      if (S.restart) v.currentTime = r.start;   // rewind now, so the next press starts at once
      $("stage").classList.remove("counting"); $("hud-count").hidden = true;
      if (S.loopWasPlaying) loop.play().catch(() => {});
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
    if (S.clip.dragging()) S.stopAfterDrag = true; else setMotion(false);   // let go mid-drag: stop when the mouse lets go too
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
    return S.qc && f && f.counter === reviewer();
  }
  function renderLabels(feed) {
    const svg = $("labels"); clear(svg);
    if (S.mode !== "sub" || !S.selId) return;
    const [W, H] = dims();
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    const blocked = qcBlocked();
    const labels = blocked ? [] : myLabels();
    const rad = (6 * W) / Math.max(200, $("stage").clientWidth) / S.zoom.k;
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
    if (feed && labels.length && !blocked) {
      $("c-fish").value = fish; $("c-inv").value = inv;
      const withSp = labels.filter((l) => l.species);
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
    if (!reviewer()) { message("Type your name in the Reviewer box first. Marks are saved under your name.", "error"); $("reviewer").focus(); return; }
    if (qcBlocked()) { message("Use a different name for the blind second count.", "error"); return; }
    const typed = $("p-species").value.trim(), known = resolve(typed);
    const payload = { subsample_id: S.selId, counter: reviewer(), op: "add", shape, kind: markKind(), species: (known ? known.sci : typed) || null, x, y };
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
      if (!myLabels().length) $("p-totals").textContent += " Count fields were not changed; edit them by hand.";
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
      message("Cleared " + mine.length + " marks. Count fields were not changed; edit them by hand.", "ok");
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
      if (!myLabels().length) $("p-totals").textContent += ". Count fields were not changed; edit them by hand.";
    } catch (err) { message("Undo failed: " + err.message, "error"); }
  }
  function wireTools() {
    const st = $("stage");
    st.addEventListener("pointerdown", (e) => {
      if (S.mode !== "sub" || e.button > 1 || (e.button === 0 && e.ctrlKey) || !$("still").complete) return;   // Ctrl+click is a right-click on a Mac
      const middle = e.button === 1;
      if (S.motion && S.tool !== "pan" && !middle) { message("Let go of Space to add or remove marks.", "warn"); return; }
      if (S.tool === "pan" || middle) { S.drag = { type: "pan", x: e.clientX, y: e.clientY }; st.setPointerCapture(e.pointerId); e.preventDefault(); return; }
      const [x, y] = toImage(e);
      S.drag = { type: S.tool, x, y, x2: x, y2: y };
      st.setPointerCapture(e.pointerId); e.preventDefault();
    });
    st.addEventListener("pointermove", (e) => {
      const d = S.drag; if (!d) return;
      if (d.type === "pan") { S.zoom.x += e.clientX - d.x; S.zoom.y += e.clientY - d.y; d.x = e.clientX; d.y = e.clientY; applyZoom(); return; }
      if (d.type === "dot") return;
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
        const hit = labelAt(d.x, d.y);
        if (hit) removeLabel(hit); else addLabel("point", Math.round(d.x), Math.round(d.y));
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
      zoomBy(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });
    document.querySelectorAll("[data-tool]").forEach((b) => b.addEventListener("click", () => setTool(b.dataset.tool)));
    $("p-undo").addEventListener("click", undoLabel);
    $("p-clear").addEventListener("click", clearAllLabels);
    $("z-in").addEventListener("click", () => zoomBy(1.4)); $("z-out").addEventListener("click", () => zoomBy(1 / 1.4));
    $("z-reset").addEventListener("click", () => { S.zoom = { k: 1, x: 0, y: 0 }; applyZoom(); renderLabels(false); });
    $("reviewer").addEventListener("change", () => { if (S.mode === "sub" && S.selId) renderLabels(true); });
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
        if (!list.hidden && active >= 0) choose(active);
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
  function paintSuggest(u) {
    const auto = u.auto || {};
    const showSug = !S.qc;
    $("suggest-panel").hidden = !showSug;
    paintSuggestToggle();
    const sugOn = showSug && suggestionsOn();
    $("sug-hint").hidden = !sugOn; $("sug-off").hidden = sugOn;
    $("movement-banner").hidden = true;
    const d = $("suggest"); clear(d);
    if (sugOn) {
      const row = (k, v) => d.append(el("dt", { text: k }), el("dd", { text: v }));
      row("Fish (model)", fmtNum(auto.fish_count)); row("Invertebrates (model)", fmtNum(auto.invertebrate_count));
    }
  }
  function renderSubsample(u) {
    const head = $("seg-head"); clear(head);
    head.append(el("h2", { text: u.subsample_id }), el("span", { text: "at " + fmtTime(u.t_s) }));
    if (S.qc) head.append(badge("QC mode: blind second count", "audit"));
    $("audit-banner").hidden = !S.qc;
    $("audit-banner").textContent = "QC mode. Count this point fresh. The first count and the model suggestion are hidden on purpose.";
    paintSuggest(u);
    $("pass-row").hidden = !S.qc;
    // form: prefill only from the reviewer's own saved primary count, never from the model
    const prev = S.qc ? null : primaryOf(u.subsample_id);
    $("c-fish").value = prev ? prev.total_fish_count : ""; $("c-inv").value = prev ? prev.invertebrate_count : "";
    $("c-unk").value = prev && prev.unknown_count ? prev.unknown_count : "";
    S.ss.rows = prev ? Object.entries(prev.species_counts || {}).map(([name, n]) => ({ name, n, free: !resolve(name) })) : [];
    const carried = !prev && !S.qc ? carriedVisibility(u) : null;
    $("c-vis").value = prev && prev.visibility_category ? prev.visibility_category : (carried || "");
    $("c-vis-hint").hidden = !carried;
    $("c-vchange").checked = !!(prev && prev.visibility_change);
    $("c-notes").value = prev ? (prev.notes || "").replace(/^Movement, unidentified\. ?/, "") : "";
    $("c-move").checked = !!(prev && /^Movement, unidentified/.test(prev.notes || ""));
    for (const cb of $("chars").querySelectorAll("input")) cb.checked = !!(prev && (prev.characteristics || []).includes(cb.value));
    $("ss-species").value = "";
    paintSpeciesRows(); paintCharsWarn();
    const r = !S.qc && prev ? "Your earlier count is loaded. Saving adds a new row; earlier rows are kept." : "";
    $("sub-result").textContent = r;
  }
  // Visibility from the nearest earlier counted point, so it is only typed when it changes. Never in a blind count.
  function carriedVisibility(u) {
    const earlier = subs().filter((s) => (s.t_s ?? 0) < (u.t_s ?? 0)).sort((a, b) => (b.t_s ?? 0) - (a.t_s ?? 0));
    for (const s of earlier) { const r = primaryOf(s.subsample_id); if (r && r.visibility_category) return r.visibility_category; }
    return null;
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
    p.textContent = S.ss.rows.length ? S.ss.rows.length + " species, " + sum + " counted by species." + (!isNaN(fish) && sum > fish + inv ? " That is more than your fish and invertebrate totals. Check the numbers." : "") : "";
  }
  function paintCharsWarn() {
    const n = $("chars").querySelectorAll("input:checked").length;
    const anyCount = (parseInt($("c-fish").value, 10) || 0) + (parseInt($("c-inv").value, 10) || 0) > 0;
    $("chars-warn").hidden = !(anyCount && n < 2);
  }
  function addSpecies(sel) {
    if (!sel || !sel.value) return;
    const ex = S.ss.rows.find((r) => r.name === sel.value);
    if (ex) ex.n += 1; else S.ss.rows.push({ name: sel.value, n: 1, free: sel.free });
    $("ss-species").value = ""; paintSpeciesRows();
  }
  async function saveSubsample() {
    if (S.mode !== "sub" || !S.selId) return;
    const num = (id) => { const v = $(id).value.trim(); return v === "" ? null : parseInt(v, 10); };
    const fish = num("c-fish"), inv = num("c-inv");
    if (!reviewer()) { message("Type your name in the Reviewer box first. It is saved with each count.", "error"); $("reviewer").focus(); return; }
    if (fish == null || inv == null || fish < 0 || inv < 0) { message("Enter fish and invertebrate counts. Use 0 if there were none.", "error"); (fish == null ? $("c-fish") : $("c-inv")).focus(); return; }
    const move = $("c-move").checked, notes = $("c-notes").value.trim();
    const sc = {}; for (const r of S.ss.rows) sc[r.name] = (sc[r.name] || 0) + r.n;
    const payload = {
      subsample_id: S.selId, counter: reviewer(), pass: S.qc ? $("c-pass").value : "primary",
      total_fish_count: fish, invertebrate_count: inv, species_counts: sc, unknown_count: num("c-unk") || 0,
      total_species: Object.keys(sc).length, visibility_category: $("c-vis").value || null,
      visibility_change: $("c-vchange").checked ? true : null,
      characteristics: [...$("chars").querySelectorAll("input:checked")].map((c) => c.value),
      free_text_species: S.ss.rows.filter((r) => r.free).map((r) => r.name),
      notes: (move ? "Movement, unidentified. " : "") + notes, contrast_settings: settingsPayload(),
    };
    const id = S.selId;
    try {
      await Data.save(S.runId, "subsample_reviews", payload);
      await refreshSaved();
      let msg = "Saved count for " + id + ".";
      const q = (S.saved.qc || {})[id];
      if (S.qc && q) msg += " Difference from the first count: " + (q.percent_diff == null ? "n/a" : q.percent_diff.toFixed(1) + "%") + (q.recount_needed ? ". Recount needed, preferably by a different counter." : ". Within the set limit.");
      if (S.qc && q && q.first_counter && q.first_counter === reviewer()) msg += " Note: the first count was also by " + q.first_counter + ".";
      message(msg, q && q.recount_needed ? "warn" : "ok");
      $("sub-result").textContent = msg;
      step(1);
    } catch (e) { message("Not saved: " + e.message, "error"); }
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
    const v = $("loop"); if (v.hidden) return;
    v.pause();
    const fps = (S.results.recording && S.results.recording.fps) || 30;
    v.currentTime = Math.max(0, Math.min(v.duration || 1e9, v.currentTime + dir / fps));
  }
  const currentSpeed = () => { const b = document.querySelector("[data-speed][aria-pressed=true]"); return b ? parseFloat(b.dataset.speed) : 1; };
  function countOffset() { const u = unit(S.selId, "sub"); return u && u.t_s != null && u.context_start_s != null ? Math.max(0, u.t_s - u.context_start_s) : null; }
  function onTime() {
    const v = $("loop"), off = S.mode === "sub" ? countOffset() : null;
    $("to-count").hidden = off == null;
    $("clip-time").textContent = v.hidden ? "" : "Clip " + v.currentTime.toFixed(2) + " s" + (off != null ? ". Count point at " + off.toFixed(2) + " s. A fish within " + proto().count_tolerance_s + " s either side at 0.25x may count." : "");
    $("count-now").hidden = !(off != null && D.inCount(v.currentTime, off, countSec()));
  }
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
    if (!S.results || $("workspace").hidden || !["count", "qc"].includes(S.step)) return;
    const k = e.key.toLowerCase();
    if (k === "arrowright" || k === "arrowdown" || k === "j") { e.preventDefault(); step(1); }
    else if (k === "arrowleft" || k === "arrowup" || k === "k") { e.preventDefault(); step(-1); }
    else if (k === "g") toggle("grid");
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
      if (!e.repeat && !S.spaceDown) { S.spaceDown = true; if (!S.motion) { S.spaceStarted = true; setMotion(true); } }
    }
  }

  // ---------- recording notes ----------
  function fillNotes() {
    const n = S.saved.latest_recording_notes || {};
    $("rn-juv").value = n.juveniles == null ? "" : String(n.juveniles);
    $("rn-species").value = (n.species_observed || []).join("\n");
    $("rn-notes").value = n.notes || "";
    const box = $("rn-vis"); clear(box);
    const rows = n.visibility_by_observer && n.visibility_by_observer.length ? n.visibility_by_observer : [{}, {}, {}];
    rows.forEach((r, i) => {
      const sel = el("select", { "aria-label": "Visibility category, observer " + (i + 1) }, el("option", { value: "", text: "Not recorded" }), ...["<0.5 m", "0.5-1.0 m", "1.0-1.5 m", ">1.5 m"].map((c) => el("option", { value: c, text: c })));
      sel.value = r.category || "";
      box.append(el("div", { class: "vis-row" }, el("input", { type: "text", maxlength: "100", placeholder: "Observer " + (i + 1), value: r.observer || "", "aria-label": "Observer " + (i + 1) + " name" }), sel));
    });
  }
  async function saveNotes() {
    const p = S.results.protocol || {}, say = (t) => { $("rn-status").textContent = t; $("rn-status-vis").textContent = t; };
    const vis = [...$("rn-vis").querySelectorAll(".vis-row")].map((r) => ({ observer: r.querySelector("input").value.trim(), category: r.querySelector("select").value })).filter((r) => r.category || r.observer);
    if (vis.some((r) => !r.observer || !r.category)) { say("Each visibility entry needs a name and a category."); return; }
    const payload = {
      window_start_s: p.window_start_s ?? null, window_end_s: p.window_end_s ?? null,
      species_observed: $("rn-species").value.split("\n").map((x) => x.trim()).filter(Boolean),
      juveniles: $("rn-juv").value === "" ? null : Number($("rn-juv").value),
      visibility_by_observer: vis, notes: $("rn-notes").value, reviewer: reviewer(),
    };
    try {
      await Data.save(S.runId, "recording_notes", payload);
      say("Saved. A new version is added each time; earlier ones are kept.");
      S.saved = await Data.saved(S.runId); paintSteps();
    } catch (e) { say("Not saved: " + e.message); }
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
    for (const b of document.querySelectorAll("#steps [data-step]")) b.setAttribute("aria-current", b.dataset.step === S.step ? "step" : "false");
    const notes = S.saved.latest_recording_notes || {}, tag = (k, t) => { document.querySelector('[data-state="' + k + '"]').textContent = t; };
    const seen = (notes.visibility_by_observer || []).length, all = subs().length, counted = subs().filter((s) => primaryOf(s.subsample_id)).length;
    const qcItems = qcSample().items, qcDone = qcItems.filter((s) => secondOf(s.subsample_id)).length;
    tag("visibility", seen ? seen + " of 2 to 3" : "");
    tag("watch", (notes.species_observed || []).length ? notes.species_observed.length + " species" : "");
    tag("count", counted + " of " + all);
    tag("qc", qcDone + " of " + qcItems.length);
    paintReportBtn();
  }
  function setStep(step) {
    if (step === "report") { openReport(); return; }
    const was = S.qc;
    S.step = step; S.qc = step === "qc";
    const counting = step === "count" || step === "qc";
    $("workspace").hidden = !counting; $("step-visibility").hidden = step !== "visibility"; $("step-watch").hidden = step !== "watch";
    setMotion(false);
    if (!counting) $("loop").pause();
    const wv = $("watch-video");
    if (step === "watch") {
      const url = Data.windowUrl(S.runId);
      $("watch-missing").hidden = !!url; wv.hidden = !url;
      wv.onerror = () => { wv.hidden = true; $("watch-missing").hidden = false; };
      if (url && !wv.src.endsWith(url)) { wv.src = url; wv.load(); }
    } else wv.pause();
    if (step === "visibility") {
      const first = subs().slice().sort((a, b) => (a.t_s ?? 0) - (b.t_s ?? 0))[0];
      if (first) $("vis-still").src = Data.mediaUrl(S.runId, "subsamples", first.subsample_id, "still");
    }
    if (counting && (was !== S.qc || !S.selId)) { S.selId = null; renderChrome(); const q = queue(); if (q.length) select(q[0]); else showNoSelection(); }
    else renderChrome();
  }
  function nameHint() { $("name-hint").hidden = !!reviewer() || !S.results; }

  // ---------- new video: choose, process in the background, open ----------
  const NV = { videos: [], jobs: [], timer: null, seen: {}, uploading: false, previewAsk: 0 };
  const JOB_TEXT = { queued: "Waiting", running: "Processing", done: "Ready", failed: "Failed", cancelled: "Cancelled" };
  const fmtSize = (b) => (b >= 1e9 ? (b / 1e9).toFixed(1) + " GB" : Math.max(1, Math.round(b / 1e6)) + " MB");
  const fmtSpan = (s) => (s >= 3600 ? Math.floor(s / 3600) + " h " : "") + Math.floor((s % 3600) / 60) + " min " + (s % 60) + " s";
  function nvStatus(text, kind) { const p = $("nv-status"); p.textContent = text || ""; p.className = "fb-status " + (kind || ""); }
  async function loadVideos(pick) {
    const d = await api("/api/videos");
    NV.videos = d.videos;
    $("nv-folder").textContent = d.folder;
    const box = $("nv-model"); box.disabled = !d.detector_ready; if (!d.detector_ready) box.checked = false;
    $("nv-model-off").hidden = d.detector_ready;
    const sel = $("nv-video"), keep = pick || sel.value; clear(sel);
    sel.append(el("option", { value: "", text: d.videos.length ? "Choose a video..." : "No videos here yet" }));
    for (const v of d.videos) sel.append(el("option", { value: v.id, text: v.id + (v.files.length > 1 ? " (" + v.files.length + " parts)" : "") + ", " + fmtSize(v.size) }));
    sel.value = keep; suggestName();
  }
  function suggestName() {
    const v = NV.videos.find((x) => x.id === $("nv-video").value);
    if (v) $("nv-name").value = v.suggested_name;
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
      for (const f of d.frames) box.append(el("button", { type: "button", "aria-pressed": "false", title: "Start the window at " + fmtTime(f.t_s), on: { click: (e) => {
        $("nv-start").value = f.t_s;
        for (const b of box.children) b.setAttribute("aria-pressed", b === e.currentTarget ? "true" : "false");
      } } }, el("img", { src: f.url, alt: "Frame at " + fmtTime(f.t_s) }), el("span", { text: fmtTime(f.t_s) })));
    } catch (e) { if (ask === NV.previewAsk) nvStatus(e.message, "error"); }
  }
  function uploadVideo(file) {
    if (!file || NV.uploading) return;
    NV.uploading = true; $("nv-file").disabled = true; const bar = $("nv-upload"); bar.hidden = false; bar.value = 0;
    nvStatus("Copying " + file.name + " into the videos folder...");
    const x = new XMLHttpRequest(), done = () => { NV.uploading = false; $("nv-file").disabled = false; $("nv-file").value = ""; bar.hidden = true; };
    x.open("PUT", "/api/videos/upload?name=" + enc(file.name));
    x.setRequestHeader("X-ClipSift-Upload", "1");
    x.upload.onprogress = (e) => { if (e.lengthComputable) { bar.max = e.total; bar.value = e.loaded; } };
    x.onerror = () => { done(); nvStatus("The copy stopped. Is ClipSift still running?", "error"); };
    x.onload = async () => {
      done();
      let b = null; try { b = JSON.parse(x.responseText); } catch (e) { /* not JSON */ }
      if (x.status >= 300) { nvStatus((b && b.error) || "The copy failed.", "error"); return; }
      await loadVideos(b.id); nvStatus("Added. Check the name, then press Start.", "ok");
    };
    x.send(file);
  }
  async function startJob() {
    const num = (id) => { const v = $(id).value.trim(); return v === "" ? null : Number(v); };
    const body = { video: $("nv-video").value || null, path: $("nv-path").value, name: $("nv-name").value.trim(), layer: $("nv-model").checked ? 1 : 0, window_start: num("nv-start"), window_end: num("nv-end"), video_id: $("nv-id").value.trim(), interval: num("nv-points") };
    try {
      await post("/api/jobs", body);
      nvStatus("Added to the list. You can close this and keep working.", "ok");
      for (const id of ["nv-video", "nv-path", "nv-name", "nv-id", "nv-start", "nv-end"]) $(id).value = "";
      $("nv-preview-wrap").hidden = true;
      await pollJobs();
    } catch (e) { nvStatus(e.message, "error"); }
  }
  function paintJobs() {
    const ul = $("nv-jobs"); clear(ul);
    $("nv-jobs-h").hidden = !NV.jobs.length;
    for (const j of NV.jobs.slice().reverse()) {
      const live = j.status === "queued" || j.status === "running";
      const line = el("li", {}, el("span", { class: "nv-name", text: j.name }), badge(JOB_TEXT[j.status] || j.status, j.status === "failed" ? "flag" : j.status === "done" ? "info" : ""));
      if (j.status === "running") line.append(el("span", { class: "hint", text: j.progress + ", " + fmtSpan(j.elapsed_s) }), el("progress", { max: "100", value: String(j.percent) }));
      if (j.status === "done") line.append(el("span", { class: "hint", text: "Took " + fmtSpan(j.elapsed_s) }), el("button", { type: "button", class: "primary", text: "Open", on: { click: async () => { $("new-dlg").close(); await fillRuns(); $("run-select").value = j.name; loadRun(j.name); } } }));
      if (live) line.append(el("button", { type: "button", class: "quiet", text: "Cancel", on: { click: async () => { if (!confirm("Stop processing " + j.name + "?")) return; try { await post("/api/jobs/" + enc(j.id) + "/cancel", {}); await pollJobs(); } catch (e) { nvStatus(e.message, "error"); } } } }));
      if (j.error) line.append(el("p", { class: "warn-text", text: j.error }));
      ul.append(line);
    }
    const run = NV.jobs.find((j) => j.status === "running"), waiting = NV.jobs.filter((j) => j.status === "queued").length, b = $("job-badge");
    b.hidden = !run && !waiting;
    b.textContent = run ? "Processing " + run.name + ": " + run.progress + (waiting ? ", " + waiting + " waiting" : "") : waiting + " waiting";
  }
  async function pollJobs() {
    clearTimeout(NV.timer);
    try { NV.jobs = (await api("/api/jobs")).jobs; } catch (e) { return; }
    let finished = null;
    for (const j of NV.jobs) { if (NV.seen[j.id] && NV.seen[j.id] !== "done" && j.status === "done") finished = j; NV.seen[j.id] = j.status; }
    paintJobs();
    if (finished) { await fillRuns(); message(finished.name + " is ready. Pick it from the Run menu.", "ok"); }
    if (NV.jobs.some((j) => j.status === "queued" || j.status === "running")) NV.timer = setTimeout(pollJobs, 2000);
  }
  async function openNewVideo() {
    closeDialogs(); nvStatus("");
    $("new-dlg").showModal();
    try { await loadVideos(); await pollJobs(); } catch (e) { nvStatus(e.message, "error"); }
  }

  // ---------- summary report: print it, or save it as a PDF from the print window ----------
  function paintReportBtn() {
    const b = $("report-btn"); b.disabled = S.qc;
    b.title = S.qc ? "The report shows first counts, so it stays closed in QC mode" : "Counts, times and species for this video, to print or save as a PDF";
  }
  function reportName(n) { const r = resolve(n); return r ? D.speciesLabel(r, S.names) : n; }
  function openReport() {
    if (S.qc || !S.results) return;
    closeDialogs();
    const rep = D.buildReport(S.results, S.saved), box = $("report-body"); clear(box);
    const dec = (v, d) => (v == null ? null : v.toFixed(d));
    const table = (cols, rows) => el("table", { class: "rp-table" }, el("thead", {}, el("tr", {}, cols.map((c) => el("th", { text: c })))), el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) => el("td", { text: c == null ? "" : String(c) }))))));
    const stat = (l, v) => el("div", { class: "rp-stat" }, el("b", { text: v == null ? "n/a" : String(v) }), el("span", { text: l }));
    const meta = [rep.transect && "Transect " + rep.transect, rep.stat && statText(rep.stat), rep.year, rep.season].filter(Boolean).join(", ");
    box.append(el("h1", { text: "ClipSift count report" }), el("p", { class: "rp-meta", text: "Video " + rep.video + (meta ? ". " + meta : "") + "." + (rep.windowStart != null ? " Analysis window " + fmtTime(rep.windowStart) + " to " + fmtTime(rep.windowEnd) + "." : "") }),
      el("div", { class: "rp-stats" }, stat("Points counted", rep.counted + " of " + rep.planned), stat("MeanCount (fish per point)", dec(rep.meanCount, 2)), stat("Standard deviation", dec(rep.sd, 2)), stat("Standard error", dec(rep.se, 2)), stat("Points with no fish", rep.zeroPoints), stat("Fish", rep.totalFish), stat("Invertebrates", rep.totalInv), stat("Unknown", rep.totalUnknown), stat("Species observed in the window", rep.speciesObserved.length), stat("Species in counted points", rep.species.length)));
    const vis = rep.visibility.map((v) => v.observer + ": " + v.category).join("; ");
    box.append(el("p", { class: "rp-meta", text: "One point every " + (rep.interval ?? "?") + " s. Visibility: " + (vis || "not recorded") + ". Juveniles: " + (rep.juveniles == null ? "not recorded" : rep.juveniles ? "present" : "absent") + "." }));
    if (rep.counted < rep.planned) box.append(el("p", { class: "warn-text", text: "Not finished: " + (rep.planned - rep.counted) + " of " + rep.planned + " points have no count yet." }));
    box.append(el("h2", { text: "Species observed in the window" }), el("p", { text: rep.speciesObserved.length ? rep.speciesObserved.map(reportName).join("; ") : "Not recorded yet." }));
    box.append(el("h2", { text: "Species in counted points" }));
    box.append(rep.species.length ? table(["Species", "Count", "Points seen at", "MeanCount"], rep.species.map((s) => [reportName(s.name), s.total, s.points, s.meanCount.toFixed(2)])) : el("p", { text: "No species recorded yet." }));
    box.append(el("h2", { text: "Points" }), table(["Point", "Time", "Fish", "Invertebrates", "Unknown", "Species", "Visibility", "Counter", "Notes"],
      rep.points.map((p) => [p.id, fmtTime(p.t), p.counted ? p.fish : "not counted", p.inv, p.unknown, Object.entries(p.species).map(([n, c]) => reportName(n) + ": " + c).join("; "), p.visibility, p.counter, p.notes])));
    if (rep.qcPairs) box.append(el("h2", { text: "Quality check" }), el("p", { text: rep.qcPairs + " points counted twice, " + rep.qcRecounts + " need a recount." + (rep.qcAgreement != null ? " Agreement " + rep.qcAgreement + "% (provisional formula)." : "") }));
    box.append(el("p", { class: "rp-note", text: "Counts are a relative index, not abundance. Every count here was made by a person. Created " + new Date().toLocaleString() + (rep.modelVersion ? ". Model used for suggestions: " + rep.modelVersion : "") + "." }));
    S.report = rep;
    const shots = el("div", { class: "rp-shots" });
    if (rep.counted) box.insertBefore(el("h2", { text: "Screenshots" }), box.lastChild), box.insertBefore(shots, box.lastChild);
    $("report-dlg").showModal();
    for (const p of rep.points.filter((x) => x.counted)) addShot(shots, p);
  }
  // A counted frame with its counter's marks drawn on, like Coastal Action's marked screenshots.
  function addShot(box, p) {
    const img = new Image(), fig = el("figure", {}, el("figcaption", { text: p.id + " at " + fmtTime(p.t) + ": " + p.fish + " fish, " + (p.inv || 0) + " invertebrates" }));
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
    const ctx = { run: S.runId || null, view: (isSimple() ? "simple" : "more tools") + ", " + (S.mode === "sub" ? "subsample points" : "motion segments") + (S.qc ? ", QC mode" : ""), demo: !!DEMO };
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
    { target: "steps", title: "Follow the steps", body: "These five steps follow Coastal Action's protocol, in order. Each one shows its progress. The ? button at the top has more help." },
    { target: "timeline-wrap", title: "The whole recording", body: "Each tick is a point to count. Grey means not counted yet, green means done. Click a tick to jump to it." },
    { target: "clip-wrap", title: "1. Watch the clip", body: "The clip plays around the point. Count only in the green COUNT NOW second. Use 0.25x to slow it down." },
    { target: "stage-wrap", title: "2. Mark what you see", body: "Click each animal on the picture to place a dot. Not sure about one? Leave it out. Undo removes your last dot." },
    { target: "side-sub", title: "3. Check your count", body: "The totals fill in from your dots. The suggested counts are only a hint to compare with. Tick which features you can see." },
    { target: "save-sub", title: "4. Save and go to the next", body: "Press Save to keep your count and open the next point. The ? button at the top has help and can replay this tour." },
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
    $("new-video").addEventListener("click", openNewVideo);
    $("nv-close").addEventListener("click", () => $("new-dlg").close());
    $("nv-start-btn").addEventListener("click", startJob);
    $("nv-video").addEventListener("change", suggestName);
    $("nv-path").addEventListener("change", loadPreview);
    for (const b of document.querySelectorAll("#steps [data-step]")) b.addEventListener("click", () => setStep(b.dataset.step));
    $("rn-save-vis").addEventListener("click", saveNotes);
    for (const b of document.querySelectorAll("[data-note]")) b.addEventListener("click", () => {
      const box = $("c-notes"), text = b.dataset.note;
      if (!box.value.includes(text)) box.value = (box.value.trim() + " " + text).trim();
    });
    makeCombo($("rn-sp-input"), $("rn-sp-list"), (sel) => {
      const box = $("rn-species"), have = box.value.split("\n").map((x) => x.trim()).filter(Boolean);
      if (sel.value && !have.includes(sel.value)) box.value = have.concat([sel.value]).join("\n");
      $("rn-sp-input").value = "";
    });
    $("nv-file").addEventListener("change", (e) => uploadVideo(e.target.files[0]));
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
    $("reviewer").addEventListener("input", nameHint);
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
    $("show-suggest").addEventListener("change", (e) => {
      S.boxes = e.target.checked; paintSuggestToggle(); drawBoxes();
      if (S.mode === "sub" && S.selId) { const u = unit(S.selId); if (u) paintSuggest(u); }
    });
    for (const k of ["brightness", "contrast", "saturation"]) $("f-" + k).addEventListener("input", (e) => { S.filters[k] = parseInt(e.target.value, 10); applyFilters(); });
    $("filter-reset").addEventListener("click", resetFilters);
    for (const k of ["brightness", "contrast", "saturation"]) {
      $("f-" + k).addEventListener("change", (e) => { S.filters[k] = parseInt(e.target.value, 10); applyFilters(); });  // some browsers only fire change
      $("f-" + k).addEventListener("dblclick", () => { S.filters[k] = 100; applyFilters(); });
    }
    for (const b of document.querySelectorAll("[data-speed]")) b.addEventListener("click", () => {
      document.querySelectorAll("[data-speed]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
      $("loop").playbackRate = parseFloat(b.dataset.speed); $("stage-clip").playbackRate = parseFloat(b.dataset.speed);
    });
    $("step-back").addEventListener("click", () => frameStep(-1)); $("step-fwd").addEventListener("click", () => frameStep(1));
    $("play-pause").addEventListener("click", () => { const v = $("loop"); v.paused ? v.play() : v.pause(); });
    $("to-count").addEventListener("click", () => { const o = countOffset(); if (o != null) { $("loop").currentTime = o; $("loop").play().catch(() => {}); } });
    $("loop").addEventListener("timeupdate", onTime); $("loop").addEventListener("loadedmetadata", () => { $("loop").playbackRate = currentSpeed(); onTime(); });
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
      release: () => { if (S.stopAfterDrag) { S.stopAfterDrag = false; setMotion(false); } else $("stage-clip").play().catch(() => {}); } });
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
    $("rn-save").addEventListener("click", saveNotes);
    wireTools();
    document.addEventListener("keydown", onKey);
  }
  init().then(() => { if (!DEMO) pollJobs(); });
})();
