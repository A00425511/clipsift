# ClipSift backlog

Logged 5 Nov 2026 from the team check-in and app feedback. Ticked items are done.

## Small fixes
- [x] Contrast Reset doesn't work for Ali or Gina. Reproduce first. Could not reproduce in Chromium (scripted and real clicks: Reset set contrast back to 100% every time), so the cause is unconfirmed. Hardened: one `resetFilters()` that writes the same object the sliders use and clears the saved setting, storage errors no longer interrupt it, the button now says "Reset sliders" (the other one is "Reset zoom", which may have been mistaken for it), and double-clicking a slider resets just that slider. If it still fails, ask which browser and whether they pressed Reset sliders or Reset zoom.
- [x] Clear all marks button, with a confirmation (Gina, in feedback and meeting).
- [x] Edit or remove a single dot, e.g. right-click. Click a dot in Dot mode to remove it (the label page does the same). Editing a dot is remove and place again.
- [x] Plainer label and explanation for the black and white difference image. Now "Movement view", with a line saying bright areas changed between frames.
- [x] Say clearly that the still is the count and the clip is context.
- [ ] Add a sharpen control.
- [x] `tools/pull_feedback.py` failed on 5 Nov while the same query worked directly through wrangler. Find out why. It works now from the same machine, so the exact cause is not proven. The script hid the real error (it showed stderr only, and `wrangler --json` prints errors on stdout), could wait on an npx prompt with no one to answer, and had a fragile Windows path. All three are fixed in `run_wrangler()`, which `tools/pull_labels.py` also uses. If it fails again the message now shows wrangler's own output.
- [ ] Run names in the menu should read as plain labels.

## Bigger features
- [x] Simple label-only mode: image, mark, next, with blind double counting for agreement. `/label.html`, see README, Labelling.
- [ ] Summary report of counts, seconds and species, as CSV and PDF.
- [ ] Save and reopen a full analysis (Ali).
- [ ] Windows package that needs no setup, for handoff (Ali).

## Model work
- [x] Reject static boxes (pole, seabed). Done 6 Nov: `clipsift/static_filter.py`, persistence plus movement check, rejected boxes kept with `static: true`. On 100 frames of T1-STAT2 411, boxes at threshold 0.1 went from 28.8 to 14.2 per frame; empty-frame checks 169 to 79 boxes; labelled-frame hits unchanged (24 of 103). One recording, tuned on the same frames. See `2026 Problem Prep/detector-test/STATIC-FILTER.md`.
- [x] Mask the measuring pole. Config `static_filter.masks` (polygons or a JSON file) and `tools/make_static_mask.py` to suggest one from persistent boxes. A person must check the mask.
- [ ] Review app: hide `static` detections by default with a "show static" toggle (field is in results.json; app not changed yet).
- [ ] Static filter on frames where the whole scene moves (camera sway or surge, e.g. 1220 s and 1240 s): align frames or subtract a global movement baseline before the movement check. Persistence also misses boxes that shift a few pixels.
- [ ] Check the static filter on a second recording or site, and on a crab or still-fish case, before trusting it.
- [x] Add a Community Fish Detector backend with tiling. See `2026 Problem Prep/detector-test/RESULTS.md`. Done 5 Nov: `clipsift/stages/cfd.py`, fish only, untrained on Nova Scotia footage, scored on one frame. Next: more labelled frames and a held-out test.
- [ ] Turn dots into boxes for fine-tuning.
- [ ] Separate approach for crabs and other invertebrates.
