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
  const api = { ENHANCE_PRESETS, enhanceFilter, cleanEnhance, nextEnhance, forKind, speciesName, speciesLabel, cleanNameMode, relTime };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ClipSiftDisplay = api;
})(typeof window !== "undefined" ? window : globalThis);
