/* Display helpers shared by the review app and the label page. Nothing here changes a file or a saved mark.
 * Loaded as a plain script in the browser, and by Node for tests (deploy/test/label.test.mjs). */
(function (root) {
  "use strict";
  // Applied on top of the brightness and contrast sliders. Display only.
  const ENHANCE_PRESETS = [
    { id: "off", label: "Off", filter: "", title: "No enhancement" },
    { id: "light", label: "Light", filter: "contrast(135%) saturate(125%) brightness(105%)", title: "A gentle lift in contrast and colour" },
    { id: "strong", label: "Strong", filter: "contrast(170%) saturate(140%) brightness(105%)", title: "Much more contrast and colour" },
    { id: "silhouette", label: "Silhouette", filter: "grayscale(100%) contrast(190%) brightness(115%)", title: "Black and white with hard contrast, so shapes stand out from green water" },
  ];
  const enhanceFilter = (id) => (ENHANCE_PRESETS.find((p) => p.id === id) || ENHANCE_PRESETS[0]).filter;
  const cleanEnhance = (id) => (ENHANCE_PRESETS.some((p) => p.id === id) ? id : "off");
  function nextEnhance(id) {
    const i = ENHANCE_PRESETS.findIndex((p) => p.id === id);
    return ENHANCE_PRESETS[(i + 1) % ENHANCE_PRESETS.length].id;
  }
  // Fish or invertebrate list. A species with no kind stays in both.
  const forKind = (items, kind) => items.filter((it) => !it.kind || it.kind === kind);
  // How a species reads on screen. What gets saved is always the scientific name.
  function speciesName(it, mode) { return mode === "scientific" ? it.sci : (it.common || it.sci); }
  function speciesLabel(it, mode) {
    if (!it.common) return it.sci;
    return mode === "scientific" ? it.sci + " (" + it.common + ")" : it.common + " (" + it.sci + ")";
  }
  const cleanNameMode = (v) => (v === "scientific" ? "scientific" : "common");
  // Seconds from the count point (negative = before), as text.
  function relTime(t, countS) {
    const r = Math.round((t - countS) * 10) / 10;
    return (r > 0 ? "+" : "") + r.toFixed(1) + " s";
  }
  // The count second starts at the point: the protocol's walk-through counts from 3:40 to the start of 3:41.
  const inCount = (t, countS, windowS) => t >= countS && t <= countS + windowS;
  // The part of the clip that plays: all of it, or only the count second (clipped to the clip).
  function clipRange(countOnly, countS, windowS, len) {
    if (!countOnly || countS == null) return { start: 0, end: len, only: false };
    return { start: countS, end: Math.min(len, countS + windowS), only: true };
  }
  // Where the count second and its tolerance sit on the bar, as percentages.
  function countBands(countS, windowS, tolS, len) {
    const pct = (a, b) => ({ left: (Math.max(0, a) / len) * 100, width: ((Math.min(len, b) - Math.max(0, a)) / len) * 100 });
    return { count: pct(countS, countS + windowS), tolerance: pct(countS - tolS, countS + windowS + tolS) };
  }
  // Pointer position on the track, as a time inside the range.
  function scrubTime(x, left, width, len, range) {
    const t = Math.max(0, Math.min(1, (x - left) / width)) * len;
    return Math.max(range.start, Math.min(range.end, t));
  }
  // Dragging the playhead and looping the count second. Used by both pages.
  // o: video, track, range() gives the playing range, active() says the clip is showing,
  // paint() redraws the bar, release() runs when the drag ends.
  function clipControl(o) {
    const v = o.video, track = o.track;
    let dragging = false, want = null, looping = false;
    const seek = (t) => { want = t; if (!v.seeking) v.currentTime = t; };
    const at = (e) => { const r = track.getBoundingClientRect(); return scrubTime(e.clientX, r.left, r.width, v.duration, o.range()); };
    v.addEventListener("seeked", () => {
      if (dragging) { if (want != null && Math.abs(v.currentTime - want) > 0.02) v.currentTime = want; return; }
      if (looping) { looping = false; if (o.active()) v.play().catch(() => {}); }
    });
    track.addEventListener("pointerdown", (e) => {
      if (!o.active() || !isFinite(v.duration) || e.button > 0) return;
      e.preventDefault(); e.stopPropagation();   // never a mark on the picture underneath
      track.setPointerCapture(e.pointerId);
      dragging = true; looping = false; v.pause(); seek(at(e)); o.paint();
    });
    track.addEventListener("pointermove", (e) => { if (dragging) { seek(at(e)); o.paint(); } });
    const end = () => {
      if (!dragging) return;
      dragging = false;
      if (want != null && Math.abs(v.currentTime - want) > 0.02) v.currentTime = want;   // a fast drag can end before the last seek was sent
      want = null; o.release();
    };
    track.addEventListener("pointerup", end); track.addEventListener("pointercancel", end);
    return {
      dragging: () => dragging,
      time: () => (dragging && want != null ? want : v.currentTime),
      tick() {   // once per frame while the clip shows. Pausing first makes the jump back quick.
        const r = o.range();
        if (dragging || looping || !r.only || v.paused) return;
        if (v.currentTime >= r.end - 0.02 || v.currentTime < r.start - 0.05) { looping = true; v.pause(); v.currentTime = r.start; }
      },
    };
  }
  // Spreadsheet text. Typed text cannot start a formula.
  function csvText(header, rows) {
    const cell = (c) => {
      if (c == null) return "";
      let t = String(c);
      if (typeof c === "string" && /^[=+\-@\t\r]/.test(t)) t = "'" + t;
      return /[",\r\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
    };
    return [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
  }
  // Everything the summary report shows, from the run and the saved primary counts. Model numbers are left out on purpose.
  function buildReport(results, saved) {
    const rec = results.recording || {}, run = results.run || {}, proto = results.protocol || {};
    const latest = saved.latest_primary || {}, qc = Object.values(saved.qc || {});
    const points = (results.subsamples || []).filter((s) => s && s.subsample_id).slice().sort((a, b) => (a.t_s || 0) - (b.t_s || 0)).map((s) => {
      const r = latest[s.subsample_id];
      return { id: s.subsample_id, t: s.t_s, counted: !!r, fish: r ? r.total_fish_count : null, inv: r ? r.invertebrate_count : null, unknown: r ? r.unknown_count || 0 : null,
        species: r ? r.species_counts || {} : {}, visibility: r ? r.visibility_category : null, counter: r ? r.counter : null, notes: r ? r.notes || "" : "" };
    });
    const counted = points.filter((p) => p.counted), sum = (k) => counted.reduce((a, p) => a + (p[k] || 0), 0), bySpecies = {};
    const n = counted.length, mean = n ? sum("fish") / n : null;
    const sd = n > 1 ? Math.sqrt(counted.reduce((a, p) => a + ((p.fish || 0) - mean) ** 2, 0) / (n - 1)) : null;
    const notes = saved.latest_recording_notes || {};
    for (const p of counted) for (const [name, n] of Object.entries(p.species)) {
      const row = bySpecies[name] || (bySpecies[name] = { name, total: 0, points: 0 });
      row.total += n; row.points += 1;
    }
    return { video: rec.video_id || rec.recording_id || "", transect: rec.transect, stat: rec.stat, year: rec.year, season: rec.season,
      windowStart: proto.window_start_s, windowEnd: proto.window_end_s, modelVersion: run.model_version || null, layer: run.layer,
      planned: points.length, counted: counted.length, meanCount: saved.mean_count_reviewed == null ? null : saved.mean_count_reviewed,
      totalFish: sum("fish"), totalInv: sum("inv"), totalUnknown: sum("unknown"), points,
      sd, se: sd == null ? null : sd / Math.sqrt(n), zeroPoints: counted.filter((p) => !p.fish).length,
      interval: proto.interval_s, speciesObserved: [...new Set([...(notes.species_observed || []), ...Object.keys(bySpecies)])], juveniles: notes.juveniles == null ? null : notes.juveniles,
      visibility: notes.visibility_by_observer || [],
      species: Object.values(bySpecies).map((s) => ({ ...s, meanCount: s.total / n })).sort((a, b) => b.total - a.total || (a.name < b.name ? -1 : 1)),
      qcPairs: qc.length, qcRecounts: qc.filter((q) => q.recount_needed).length, qcAgreement: saved.qc_agreement == null ? null : saved.qc_agreement };
  }
  function reportCsv(rep, fmtTime) {
    const names = rep.species.map((s) => s.name);
    const header = ["Video", "Point", "Time", "Time (s)", "Counted", "Fish", "Invertebrates", "Unknown", "Visibility", "Counter", "Notes"].concat(names.map((n) => "Count: " + n));
    const rows = rep.points.map((p) => [rep.video, p.id, fmtTime(p.t), p.t, p.counted ? "yes" : "no", p.fish, p.inv, p.unknown, p.visibility, p.counter, p.notes].concat(names.map((n) => (n in p.species ? p.species[n] : ""))));
    return csvText(header, rows);
  }
  const api = { inCount, countBands, csvText, buildReport, reportCsv, clipRange, scrubTime, clipControl, ENHANCE_PRESETS, enhanceFilter, cleanEnhance, nextEnhance, forKind, speciesName, speciesLabel, cleanNameMode, relTime };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ClipSiftDisplay = api;
})(typeof window !== "undefined" ? window : globalThis);
