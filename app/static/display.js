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
  // Blind counts, the same rules as clipsift/qc.py (the static demo has no server to ask). See that file for the assumptions.
  function percentDiff(a, b) {
    if (a == null || b == null) return null;
    return a === 0 && b === 0 ? 0 : Math.abs(a - b) / ((a + b) / 2) * 100;
  }
  function assessPoint(rows, limit, smallGap) {
    smallGap = smallGap == null ? 1 : smallGap;
    let best = null;
    const fish = (r) => r.total_fish_count || 0, inv = (r) => r.invertebrate_count || 0;
    for (let i = 0; i < rows.length; i++) for (let j = i + 1; j < rows.length; j++) {
      const fd = percentDiff(fish(rows[i]), fish(rows[j])), id = percentDiff(inv(rows[i]), inv(rows[j])), worst = Math.max(fd, id);
      if (!best || worst <= best.worst) best = { worst, fd, id, a: rows[i], b: rows[j] };
    }
    const { a, b } = best, gap = Math.max(Math.abs(fish(a) - fish(b)), Math.abs(inv(a) - inv(b))), over = best.worst > limit;
    const counts = rows.map((r) => ({ counter: r.counter, fish: fish(r), inv: inv(r) }));
    return { gap, small_gap: over && gap <= smallGap, counts, has_animals: counts.some((c) => c.fish || c.inv), all_average_fish: counts.reduce((x, c) => x + c.fish, 0) / counts.length, fish_diff: best.fd, inv_diff: best.id, percent_diff: best.worst, first_counter: a.counter, second_counter: b.counter,
      first_fish: fish(a), second_fish: fish(b), first_inv: inv(a), second_inv: inv(b), first_total: fish(a) + inv(a), second_total: fish(b) + inv(b),
      average_fish: (fish(a) + fish(b)) / 2, average_inv: (inv(a) + inv(b)) / 2, n_counts: rows.length, counters: rows.map((r) => r.counter), recount_needed: over && gap > smallGap };
  }
  function qcVerdict(sample, primaryIds, points, limit, target) {
    const done = sample.filter((s) => points[s]), diffs = done.map((s) => points[s].percent_diff);
    const agreement = diffs.length ? Math.round(Math.max(0, 100 - diffs.reduce((x, y) => x + y, 0) / diffs.length) * 10) / 10 : null;
    const recount = done.filter((s) => points[s].recount_needed);
    const animal = done.filter((s) => points[s].has_animals).map((s) => points[s].percent_diff);
    const animalAgreement = animal.length ? Math.round(Math.max(0, 100 - animal.reduce((x, y) => x + y, 0) / animal.length) * 10) / 10 : null;
    let status = "pass";
    if (!sample.length) status = "no_sample";
    else if (sample.some((s) => !primaryIds.has(s))) status = "counting";
    else if (done.length < sample.length) status = "waiting_second";
    else if (recount.length) status = "review";
    return { sample: sample.slice(), n_sample: sample.length, n_done: done.length, recount, n_within: done.length - recount.length, agreement, limit, target, n_animal_frames: animal.length, animal_agreement: animalAgreement, status };
  }
  // The wording for a recommendation. One place, so the step and the report say the same thing.
  function qcMessage(c) {
    const left = c.n_sample - c.n_done;
    const animals = c.n_animal_frames == null ? "" : c.n_animal_frames ? " " + c.n_animal_frames + " of " + c.n_done + " frames had animals, and agreement on those is " + c.animal_agreement + "%." : " No checked frame had animals, so this only shows that both people saw nothing.";
    return {
      no_sample: ["No frames to check", "This video has no count points yet."],
      counting: ["Waiting for the first count", c.n_sample + " frames have been picked at random. They stay hidden until the first count is finished."],
      waiting_second: ["Waiting for a second person", left + " of " + c.n_sample + " frames still need a blind second count."],
      review: ["Worth a second look", c.recount.length + " of " + c.n_done + " frames differ by more than " + c.limit + "% and by more than one animal. A recount is optional, preferably with a different person. Agreement is " + c.agreement + "%, and the protocol's target is " + c.target + "%." + animals],
      pass: ["Counts are close", c.agreement >= c.target ? ("Agreement is " + c.agreement + "%, and no frame needs another look." + animals) : ("Agreement is " + c.agreement + "%, under the protocol's " + c.target + "% target, but no frame differs by more than a small gap. This is common when frames have few fish." + animals)],
    }[c.status];
  }
  // Every count of a frame, by name, then the rule for the value used. Nothing is dropped from view.
  function qcCounts(q) {
    const rows = q.counts || [{ counter: q.first_counter, fish: q.first_fish, inv: q.first_inv }, { counter: q.second_counter, fish: q.second_fish, inv: q.second_inv }];
    return { people: rows.map((c) => c.counter).join(", "), fish: rows.map((c) => c.fish).join(", "), inv: rows.map((c) => c.inv).join(", "),
      rule: rows.length > 2 ? "Uses the closest two counts, " + q.first_counter + " and " + q.second_counter + ". Averaging all " + rows.length + " gives " + (Math.round(q.all_average_fish * 100) / 100) + "." : "" };
  }
  // Marks two people placed on one frame, paired by distance. Shows why two counts differ, and never changes them.
  function matchMarks(a, b, radius) {
    const at = (m) => (m.w != null ? [m.x + m.w / 2, m.y + m.h / 2] : [m.x, m.y]), left = b.slice(), both = [], onlyA = [];
    for (const m of a) {
      const [x, y] = at(m);
      let hit = -1, best = radius;
      left.forEach((o, i) => { const [ox, oy] = at(o), d = Math.hypot(ox - x, oy - y); if (d <= best) { best = d; hit = i; } });
      if (hit < 0) onlyA.push(m); else both.push([m, left.splice(hit, 1)[0]]);
    }
    return { both, onlyA, onlyB: left };
  }
  const VIS_ORDER = ["<0.5 m", "0.5-1.0 m", "1.0-1.5 m", ">1.5 m"];
  // Whether the people who rated visibility agree. Categories apart counts the steps between lowest and highest.
  function visibilitySummary(rows) {
    const ranks = rows.map((r) => VIS_ORDER.indexOf(r.category)).filter((i) => i >= 0);
    if (!ranks.length) return { n: 0, spread: 0, low: null, usual: null };
    const tally = {}; for (const i of ranks) tally[i] = (tally[i] || 0) + 1;
    const usual = Number(Object.keys(tally).sort((x, y) => tally[y] - tally[x] || x - y)[0]);
    return { n: ranks.length, spread: Math.max(...ranks) - Math.min(...ranks), low: Math.min(...ranks) === 0, usual: VIS_ORDER[usual] };
  }
  // Everything the summary report shows, from the run and the saved primary counts. Model numbers are left out on purpose.
  function buildReport(results, saved) {
    const rec = results.recording || {}, run = results.run || {}, proto = results.protocol || {};
    const latest = saved.latest_primary || {}, qc = Object.values(saved.qc || {});
    const points = (results.subsamples || []).filter((s) => s && s.subsample_id).slice().sort((a, b) => (a.t_s || 0) - (b.t_s || 0)).map((s) => {
      const r = latest[s.subsample_id];
      const finalFish = (saved.final_fish || {})[s.subsample_id];
      return { id: s.subsample_id, t: s.t_s, counted: !!r, fish: r ? r.total_fish_count : null, finalFish: finalFish == null ? (r ? r.total_fish_count : null) : finalFish, inv: r ? r.invertebrate_count : null, unknown: r ? r.unknown_count || 0 : null,
        species: r ? r.species_counts || {} : {}, visibility: r ? r.visibility_category : null, visibilityDirection: r ? r.visibility_direction || null : null, counter: r ? r.counter : null, notes: r ? r.notes || "" : "" };
    });
    const counted = points.filter((p) => p.counted), sum = (k) => counted.reduce((a, p) => a + (p[k] || 0), 0), bySpecies = {};
    const n = counted.length, mean = n ? sum("finalFish") / n : null;
    const sd = n > 1 ? Math.sqrt(counted.reduce((a, p) => a + ((p.finalFish || 0) - mean) ** 2, 0) / (n - 1)) : null;
    const notes = saved.latest_recording_notes || {};
    const qcRows = (saved.subsample_reviews || []).filter((r) => r.pass !== "primary");
    for (const p of counted) for (const [name, n] of Object.entries(p.species)) {
      const row = bySpecies[name] || (bySpecies[name] = { name, total: 0, points: 0 });
      row.total += n; row.points += 1;
    }
    return { video: rec.video_id || rec.recording_id || "", transect: rec.transect, stat: rec.stat, year: rec.year, season: rec.season,
      windowStart: proto.window_start_s, windowEnd: proto.window_end_s, modelVersion: run.model_version || null, layer: run.layer,
      planned: points.length, counted: counted.length, meanCount: saved.mean_count_final != null ? saved.mean_count_final : (saved.mean_count_reviewed == null ? null : saved.mean_count_reviewed),
      meanFirst: saved.mean_count_reviewed == null ? null : saved.mean_count_reviewed, qcCheck: saved.qc_check || null, qcPoints: saved.qc || {}, noneSeen: !!notes.none_seen,
      visibilityChanges: points.filter((p) => p.visibilityDirection).map((p) => ({ id: p.id, t: p.t, direction: p.visibilityDirection, category: p.visibility })), reviewSet: saved.review_set || null,
      totalFish: sum("fish"), totalInv: sum("inv"), totalUnknown: sum("unknown"), points,
      sd, se: sd == null ? null : sd / Math.sqrt(n), zeroPoints: counted.filter((p) => !p.fish).length,
      interval: proto.interval_s, speciesObserved: [...new Set([...(notes.species_observed || []), ...Object.keys(bySpecies), ...qcRows.flatMap((r) => Object.keys(r.species_counts || {}))])],
      qcNotes: qcRows.filter((r) => r.notes || Object.keys(r.species_counts || {}).length).map((r) => ({ id: r.subsample_id, counter: r.counter, fish: r.total_fish_count, species: r.species_counts || {}, notes: r.notes || "" })), juveniles: notes.juveniles == null ? null : notes.juveniles,
      visibility: saved.visibility || notes.visibility_by_observer || [],
      fileName: ((rec.source_files || [])[0] || "").split(/[\\/]/).pop() + ((rec.source_files || []).length > 1 ? " and " + (rec.source_files.length - 1) + " more" : ""), surveyDate: rec.date || null,
      counters: [...new Set(counted.map((p) => p.counter).filter(Boolean))], secondCounters: [...new Set(qcRows.map((r) => r.counter).filter(Boolean))],
      species: Object.values(bySpecies).map((s) => ({ ...s, meanCount: s.total / n })).sort((a, b) => b.total - a.total || (a.name < b.name ? -1 : 1)),
      qcPairs: qc.length, qcRecounts: qc.filter((q) => q.recount_needed).length, qcAgreement: saved.qc_agreement == null ? null : saved.qc_agreement };
  }
  function reportCsv(rep, fmtTime) {
    const names = rep.species.map((s) => s.name);
    const header = ["Video", "Point", "Time", "Time (s)", "Counted", "Fish", "Fish used in MeanCount", "Invertebrates", "Unknown", "Visibility", "Counter", "Notes"].concat(names.map((n) => "Count: " + n));
    const rows = rep.points.map((p) => [rep.video, p.id, fmtTime(p.t), p.t, p.counted ? "yes" : "no", p.fish, p.finalFish, p.inv, p.unknown, p.visibility, p.counter, p.notes].concat(names.map((n) => (n in p.species ? p.species[n] : ""))));
    return csvText(header, rows);
  }
  // A named species has a two-word name. Anything else ("Unknown fish", Actinopterygii) is a broader group.
  const isSpeciesName = (n) => /^(?!Unknown|Unidentified)[A-Z][a-z]+ [a-z]+$/.test(n);
  const api = { isSpeciesName, percentDiff, assessPoint, qcVerdict, qcMessage, qcCounts, matchMarks, visibilitySummary, VIS_ORDER, inCount, countBands, csvText, buildReport, reportCsv, clipRange, scrubTime, clipControl, ENHANCE_PRESETS, enhanceFilter, cleanEnhance, nextEnhance, forKind, speciesName, speciesLabel, cleanNameMode, relTime };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ClipSiftDisplay = api;
})(typeof window !== "undefined" ? window : globalThis);
