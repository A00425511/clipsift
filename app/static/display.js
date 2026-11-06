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
  // The part of the clip that plays: all of it, or only the count second (clipped to the clip).
  function clipRange(countOnly, countS, half, len) {
    if (!countOnly || countS == null) return { start: 0, end: len, only: false };
    return { start: Math.max(0, countS - half), end: Math.min(len, countS + half), only: true };
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
  const api = { clipRange, scrubTime, clipControl, ENHANCE_PRESETS, enhanceFilter, cleanEnhance, nextEnhance, forKind, speciesName, speciesLabel, cleanNameMode, relTime };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ClipSiftDisplay = api;
})(typeof window !== "undefined" ? window : globalThis);
