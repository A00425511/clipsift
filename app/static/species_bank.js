/* Species bank: a person identifies candidates. Decisions are saved per item; the latest one counts. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const FILTERS = [
    ["todo", "To review", (i, d) => !d && !has(i, "fixed_object")],
    ["unusual", "Unusual", (i) => has(i, "unusual")],
    ["near_seabed", "Near seabed", (i) => has(i, "near_seabed")],
    ["small_in_frame", "Small in frame", (i) => has(i, "small_in_frame")],
    ["flagged", "Flagged species", (i, d) => d && (d.species_flags || []).length > 0],
    ["expert", "Needs expert", (i, d) => d && d.outcome === "needs_expert"],
    ["done", "Reviewed", (i, d) => !!d],
    ["fixed_object", "Likely fixed objects", (i) => has(i, "fixed_object")],
  ];
  const TAGS = { unusual: "Unusual", near_seabed: "Near seabed", small_in_frame: "Small", fixed_object: "Fixed?" };
  const FLAG_WORDS = { invasive: "invasive", at_risk: "at risk", range_expander: "a possible range expander" };
  const S = { run: "", bank: null, decisions: {}, filter: "todo", item: null, species: [] };
  const has = (item, flag) => (item.flags || []).includes(flag);
  const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
                  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private window */ } } };
  const fileUrl = (name) => `/api/runs/${encodeURIComponent(S.run)}/species_bank/files/${encodeURIComponent(name)}`;
  const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };

  function speciesRecord(text) {
    const t = text.trim().toLowerCase();
    return S.species.find((s) => s.scientific_name.toLowerCase() === t
      || (s.common_names || []).some((c) => c.toLowerCase() === t));
  }
  const visible = () => {
    const f = FILTERS.find((x) => x[0] === S.filter);
    return S.bank.items.filter((i) => f[2](i, S.decisions[i.id]));
  };

  function drawFilters() {
    const box = $("filters");
    box.replaceChildren();
    for (const [key, label, test] of FILTERS) {
      const n = S.bank.items.filter((i) => test(i, S.decisions[i.id])).length;
      const b = el("button", "", `${label} (${n})`);
      b.type = "button";
      b.setAttribute("aria-pressed", String(S.filter === key));
      b.addEventListener("click", () => { S.filter = key; draw(); });
      box.append(b);
    }
  }

  function card(item) {
    const d = S.decisions[item.id];
    const b = el("button", "bank-card" + (d ? " done" : ""));
    b.type = "button";
    b.setAttribute("aria-pressed", String(S.item === item));
    const img = el("img");
    img.loading = "lazy";
    img.alt = `Candidate at ${clock(item.time_s)}`;
    img.src = fileUrl(item.images.crop);
    const meta = el("span", "meta", clock(item.time_s) + " ");
    for (const f of item.flags) meta.append(el("span", "bank-tag", TAGS[f] || f));
    if (d) meta.append(el("span", "bank-tag" + ((d.species_flags || []).length ? " alert" : ""), d.species || d.outcome.replace("_", " ")));
    b.append(img, meta);
    b.addEventListener("click", () => select(item));
    return b;
  }

  function draw() {
    drawFilters();
    const items = visible();
    const grid = $("grid");
    grid.replaceChildren(...items.map(card));
    if (!items.length) grid.append(el("p", "hint", "Nothing here."));
  }

  function checkAlert() {
    const rec = speciesRecord($("d-species").value);
    const flags = rec ? Object.keys(rec.flags || {}).filter((k) => rec.flags[k]) : [];
    const box = $("d-alert");
    box.hidden = !flags.length;
    if (flags.length) {
      box.textContent = `Listed as ${flags.map((f) => FLAG_WORDS[f] || f).join(", ")}. Confirm with an expert before reporting it. ${rec.id_notes || ""}`;
    }
  }

  function otherView(view) {
    const b = el("button");
    b.type = "button";
    b.title = `View at ${clock(view.time_s)}`;
    const img = el("img");
    img.alt = b.title;
    img.src = fileUrl(view.crop);
    b.append(img);
    b.addEventListener("click", () => { $("d-crop").src = fileUrl(view.crop); });
    return b;
  }

  function setClip(item) {
    stopClip();
    const clip = $("d-clip"), name = item.images.clip;
    clip.removeAttribute("src");
    if (name) { clip.src = fileUrl(name); clip.load(); }
    $("d-player").disabled = !name;
    $("d-hold").textContent = name
      ? "Click and hold, or hold Space, to play from 2.5 seconds before to 2.5 seconds after."
      : "No clip for this candidate.";
    const { width, height } = S.bank.source, [x1, y1, x2, y2] = item.bbox, box = $("d-box");
    box.style.left = (100 * x1 / width) + "%";
    box.style.top = (100 * y1 / height) + "%";
    box.style.width = (100 * (x2 - x1) / width) + "%";
    box.style.height = (100 * (y2 - y1) / height) + "%";
  }

  function playClip() {
    const clip = $("d-clip");
    if (!clip.src) return;
    clip.currentTime = 0;
    clip.hidden = false;
    $("d-box").hidden = false;
    clip.play().catch(() => {});
  }

  function stopClip() {
    const clip = $("d-clip");
    clip.pause();
    clip.hidden = true;
    $("d-box").hidden = true;
  }

  function setupPlayer() {
    const p = $("d-player");
    p.addEventListener("pointerdown", (e) => { p.setPointerCapture(e.pointerId); playClip(); });
    for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) p.addEventListener(name, stopClip);
    p.addEventListener("keydown", (e) => {
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); if (!e.repeat) playClip(); }
    });
    p.addEventListener("keyup", stopClip);
    p.addEventListener("blur", stopClip);
    p.addEventListener("contextmenu", (e) => e.preventDefault());
  }

  function setupSplitter() {
    const bank = $("bank"), bar = $("splitter");
    const limit = (w) => Math.round(Math.min(Math.max(w, 320), bank.clientWidth - 280));
    const apply = (w) => {
      const size = limit(w);
      bank.style.setProperty("--pane", size + "px");
      store.set("bank-pane", String(size));
    };
    const saved = Number(store.get("bank-pane"));
    if (saved) bank.style.setProperty("--pane", saved + "px");
    bar.addEventListener("pointerdown", (e) => {
      bar.setPointerCapture(e.pointerId);
      bar.classList.add("dragging");
      bank.classList.add("dragging");
    });
    bar.addEventListener("pointermove", (e) => {
      if (bar.classList.contains("dragging")) apply(bank.getBoundingClientRect().right - 12 - e.clientX);
    });
    const end = () => { bar.classList.remove("dragging"); bank.classList.remove("dragging"); };
    bar.addEventListener("pointerup", end);
    bar.addEventListener("pointercancel", end);
    bar.addEventListener("dblclick", () => apply(380));
    bar.addEventListener("keydown", (e) => {
      const step = { ArrowLeft: 40, ArrowRight: -40 }[e.key];
      if (step) { e.preventDefault(); apply($("detail").offsetWidth + step); }
    });
  }

  function select(item) {
    S.item = item;
    const d = S.decisions[item.id] || {};
    $("pick-hint").hidden = true;
    $("detail-body").hidden = false;
    $("d-title").textContent = `Candidate at ${clock(item.time_s)}`;
    $("d-reasons").replaceChildren(...(item.reasons || []).map((r) => el("li", "", r)));
    $("d-crop").src = fileUrl(item.images.crop);
    $("d-others").replaceChildren(...(item.other_views || []).map(otherView).concat(
      (item.other_views || []).length ? [otherView({ crop: item.images.crop, time_s: item.time_s })] : []));
    $("d-frame").src = fileUrl(item.images.frame);
    setClip(item);
    for (const r of document.querySelectorAll("input[name=outcome]")) r.checked = r.value === d.outcome;
    $("d-species").value = d.species || "";
    $("d-stage").value = d.life_stage || "unknown";
    $("d-notes").value = d.notes || "";
    $("d-status").textContent = d.at ? `Saved by ${d.reviewer}` : "";
    checkAlert();
    draw();
  }

  async function save(ev) {
    ev.preventDefault();
    const outcome = (document.querySelector("input[name=outcome]:checked") || {}).value;
    const reviewer = $("reviewer").value.trim();
    const status = $("d-status");
    if (!reviewer) { status.textContent = "Add your name at the top first."; $("reviewer").focus(); return; }
    if (!outcome) { status.textContent = "Choose what it is first."; return; }
    const rec = speciesRecord($("d-species").value);
    const body = { item_id: S.item.id, outcome, reviewer, life_stage: $("d-stage").value, notes: $("d-notes").value,
                   species: rec ? rec.scientific_name : $("d-species").value.trim() };
    const res = await fetch(`/api/runs/${encodeURIComponent(S.run)}/species_bank/decisions`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { status.textContent = data.error || "Could not save."; return; }
    S.decisions[S.item.id] = data;
    const list = visible();
    if (list.length) select(list[0]);
    else { S.item = null; $("detail-body").hidden = true; $("pick-hint").hidden = false; draw(); }
  }

  async function loadRun(id) {
    S.run = id;
    S.item = null;
    $("detail-body").hidden = true;
    $("pick-hint").hidden = false;
    const res = await fetch(`/api/runs/${encodeURIComponent(id)}/species_bank`);
    const data = await res.json();
    const ready = !!data.available;
    $("empty").hidden = ready;
    $("empty").textContent = "This run has no species bank yet. Build one with tools/build_species_bank.py.";
    $("csv").hidden = true;
    if (!ready) { $("bank").hidden = true; $("gate").hidden = true; return; }
    S.bank = data.bank;
    S.decisions = data.decisions || {};
    $("csv").href = `/api/runs/${encodeURIComponent(id)}/species_bank.csv`;
    const opened = store.get("bank-open-" + id) === "1";
    $("gate").hidden = opened;
    $("bank").hidden = !opened;
    $("csv").hidden = !opened;
    if (opened) draw();
  }

  async function start() {
    const [{ runs }, { species }] = await Promise.all([
      fetch("/api/runs").then((r) => r.json()), fetch("/api/species").then((r) => r.json())]);
    S.species = species || [];
    $("species-list").replaceChildren(...S.species.map((s) => {
      const o = el("option");
      o.value = (s.common_names && s.common_names[0]) || s.scientific_name;
      o.label = s.scientific_name;
      return o;
    }));
    const sel = $("run");
    sel.replaceChildren(...runs.map((r) => { const o = el("option", "", r.run_id); o.value = r.run_id; return o; }));
    const wanted = new URLSearchParams(location.search).get("run");
    if (wanted && runs.some((r) => r.run_id === wanted)) sel.value = wanted;
    $("reviewer").value = store.get("bank-reviewer") || "";
    $("reviewer").addEventListener("change", (e) => store.set("bank-reviewer", e.target.value.trim()));
    sel.addEventListener("change", (e) => loadRun(e.target.value));
    $("d-species").addEventListener("input", checkAlert);
    $("d-form").addEventListener("submit", save);
    setupPlayer();
    setupSplitter();
    $("gate-ok").addEventListener("click", () => { store.set("bank-open-" + S.run, "1"); loadRun(S.run); });
    if (sel.value) await loadRun(sel.value);
  }
  start();
})();
