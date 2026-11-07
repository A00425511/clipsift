# ClipSift change log

Every change pushed to GitHub gets a line here. The app version lives in `clipsift/__init__.py`.

- **App versions:** add a new entry at the top of "App versions", update `__version__`, and tag the commit (for example `v0.5.0`). Use a new middle number for a new feature and a new last number for a fix.
- **Model versions:** add a row to the table whenever a different model or different detector settings are used. Record what it was trained on and how it was tested. Model files stay out of git, so the file name and test result here are the record of which model is which.

## Model versions

| Version | Date | Model file | Settings | Training | Test result | Status |
|---|---|---|---|---|---|---|
| M0 | 2026-11-05 | `cfd-rf-detr-nano-640-2026.02.02.cp-011.20260706-release.pth` | Tiles 512, overlap 0.25, candidates at 0.05, suggested count at 0.1, static filter on | None. Community Fish Detector as released, not trained on Coastal Action footage | One labelled frame: recall 0.45, precision 0.63, against 0.20 and 0.28 by chance. Tested on very little data, so not validated | In use |

No team-trained model has been added to this repository yet.

## App versions

### 1.0.2 (2026-11-07)
- Count points: after scrubbing or stepping with `,` and `.`, the frame stays paused. Space goes back to the count frame, and the next press plays.

### 1.0.1 (2026-11-07)
- Team site: the Label fish link stays visible. In the local app it sits behind More tools.
- Team site: step 6 no longer calls a server route the site doesn't have.

### 1.0.0 (2026-11-07)
Rebuilt the review app as a local workflow app. The automated counter is off, and is now a prototype for later. See `docs/PROTOCOL_WORKFLOW.md`.
- Home screen: drop a video, choose one from this computer without copying it, or type a path. The parts of a split GoPro video are joined. Lists videos in progress.
- Setup: Video ID, transect, STAT, year and season can be edited. New videos process with no model.
- Profiles: everyone picks their name when a video opens, and counts, ratings and marks are saved under it.
- Step 1: one visibility rating per person for the whole video, hidden from others until they've rated. Notes from the protocol's comments and Baker 2022.
- Step 2: watch the whole window, or the 10 seconds at each point. Records species present, juveniles and notes only.
- Step 3: the clip plays in the picture, so the separate video is gone. Suggested counts and model boxes are gone. Each point records whether visibility got better or worse.
- Step 4: the app holds the random frames, locks first counts away from the second person, compares the counts and shows how close they are. Compare view shows both people's marks on a frame.
- Quality check: the 6% and 95% figures are shown but advisory, so nothing blocks a video. A frame is only flagged if it's over 6% and more than one animal apart, because one fish is over 6% on any frame under 17 fish (`qc_small_gap`). A recount is optional.
- Quality check: fish and invertebrates are checked separately, a recount that agrees with either count settles a frame, and MeanCount uses the average of checked frames, as the protocol says. Formulas are still provisional.
- Quality check: the API refuses a blind count from the first counter. Each video now gets its own random frames.
- Home screen: agreement between each pair of people across all videos.
- Step 6: optional check of model flags after everything else. 30 to 40 items mix agreements with the counter, flags the counter didn't mark, and flags between count points. The source stays hidden until a person decides. Results export as CSV for training later and never change a count.
- Report: visibility changes, quality check table and summary, and the MeanCount from first counts.
- `Start ClipSift.bat` starts the app and opens the browser on Windows. Not yet tried on a Windows computer.
- Fixes: empty CSV cells no longer export as an apostrophe. The command line export reads juveniles and uses the same quality check rule as the app.

### 0.10.0 (2026-11-07)
- Species bank: new `/species_bank.html` page for a second species check after counting. It shows the clearest view of each candidate, with a close crop and the full frame. Hold the frame to play 2.5 seconds either side, and drag the pane edge to enlarge the images.
- Species bank: `tools/build_species_bank.py` builds a bank from V6 output. It merges overlapping tracks of one animal, sets aside likely fixed objects and flags candidates that look unusual, sit near the seabed or are small in the frame.
- Species bank: reviewers record a species, life stage, Not an animal, Can't tell or Needs an expert. Listed invasive, at-risk and range-expanding species show a warning. Decisions export as CSV and never change counts.

### 0.9.0 (2026-11-06)
- Label page: a label set can give one named person extra frames, through `personal` in `calibration.json`. Nobody else is offered those frames, even after the set reopens, so a recorded demo cannot unblind a label.
- Label page and label results: frames listed under `archived` in `calibration.json` are held back from everyone, leave My frames, and are left out of everything `tools/pull_labels.py` writes. Saved labels stay in the database.
- Label page: help text matches the team tagging rules (movement alone is not enough, Unsure means exactly one characteristic, click the middle of the body, do not mark what never moves).
- Label results: `tools/pull_labels.py` takes the calibration list from `calibration.json` when there is one, so added practice frames are included.

### 0.8.0 (2026-11-06)
- Review app: Unsure marks (never counted), and `F`, `I` and `U` keys.
- Review app: Undo also brings back a removed mark.
- Review app: quick note buttons, and visibility carries over from the last counted point (not in blind counts).
- Review app: the QC badge is hidden while counting, so first counters can't tell which points will be checked.
- Report: species counted at points join the species observed list.
- Label page: No animals asks for the clip and Movement view first.

### 0.7.1 (2026-11-06)
- Label page: hold every frame back except the five calibration frames, until the team debrief. Saved labels are kept. To reopen, set `calibration_only` to false in `label_sets/<set>/calibration.json` and rebuild the site.

### 0.7.0 (2026-11-06)
Rebuilt around Coastal Action's protocol. See `docs/PROTOCOL_WORKFLOW.md`.
- Review app: five steps in protocol order: Visibility, Watch window, Count points, Quality check, Report.
- New Watch window step: the analysis window as one video, beside the species observed list and juveniles.
- New video: frames at each minute to choose when the sediment has settled, Video ID, and 15 or 60 count points.
- Points run in time order. Motion badges, the motion segment screens and the motion scan are gone from the workflow (`motion_scan: true` turns the scan back on).
- Count second now starts at the point, with tolerance shown either side, following the protocol's walk-through. This replaces the centred window from 0.4.0 and is a question for Coastal Action.
- Report adds standard deviation, standard error, points with no fish, MeanCount per species, species observed, visibility, juveniles and marked screenshots.
- New `docs/PROTOCOL_WORKFLOW.md` with the step-by-step plan, literature review and questions for Coastal Action.

### 0.6.0 (2026-11-06)
- Review app (on this computer): New video button. Choose or copy in a video, process it in the background, then open it. Videos wait in a list and run one at a time.
- Review app: Report button, with counts, times and species so far. Print it, save it as a PDF or download a CSV. It stays closed in QC mode, so first counts remain hidden.

### 0.5.0 (2026-11-06)
- Both pages: drag the playhead to move through the clip.
- Both pages: Count second only toggle (O) loops just the 1 second count window. Off plays the full clip.
- Review app: Motion button, so the clip can stay in the picture without holding Space.

### 0.4.0 (2026-11-06), commit ce5dfec
Deployed to the team website.
- Review app: hold Space to play the clip in the picture, with the count second highlighted.
- Review app: right-click removes a dot, ellipse or box.
- Both pages: Restart each time toggle (R), Enhance presets Off, Light, Strong and Silhouette (C), and a Common/Scientific name toggle.
- Both pages: species lists follow fish or invertebrate. Every species now has a `kind`.
- Fix: the review app's count second is now centred on the count point, as the protocol says.
- Change: Space no longer controls the small clip player. Use its Play/pause button.

### 0.3.0 (2026-11-06), commit b87f1b5
- Labelling protocol, calibration mode, Unsure marks and the static-object filter.

### 0.2.0 (2026-11-06), commit 730f6fe
- Shared blind label page and the fish detector backend.

### 0.1.0 (2026-11-05), commit 10876b8
- First ClipSift prototype and background documents.
