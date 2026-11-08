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

### 1.4.1 (2026-11-08)
Brings in the team's work from main. No app behaviour changes.
- Adrien: a ByteTrack tracker option (not used: his own test found it worse than the default), `config/yolo.yaml` for his YOLOv8n ONNX model, `combine_yolo_track.py`, and a Windows Coastal kit (`1-setup.bat`, `2-Process-Video.bat`, `3-Open-Clipsift.bat`, `README-COASTAL.txt`). `a1.pdf` is removed from the branch (it is still in history, so the repo stays private).
- Ali: the experimental DIGI4ECO fine-tuned RF-DETR Small detector in `experiments/digi4eco-finetuned/`, kept separate from the app.
- To check before the Coastal handoff:
  - The Coastal kit and README describe the older process-then-review flow with suggested counts. 1.4.x counts first and shows the model's guess only after a count is saved.
  - `config/yolo.yaml` keeps class ids 1 and 4, which are small fish and jellyfish in the Brackish class list, not fish (0).
  - Neither new model's weights are in git. Neither has been benchmarked on the frozen Coastal frames.

### 1.4.0 (2026-11-08)
Ready to package for Coastal. See docs/SHIP_TRIM.md.
- Mac package: `tools/package_mac.py` builds a portable zip with its own Python and ffmpeg, and `--with-model` adds the fish detector (CFD nano). Work is saved in Documents/ClipSift. The CFD weights' licence must be settled before the detector zip leaves the team.
- The app finds a bundled ffmpeg when the computer has none. The packaged app serves quietly through waitress.
- Removed: More tools (the picture sliders are now under "Adjust picture", and the grid's Rows and Columns show while the grid is on), the Classic layout, the "Every 15 s" spacing, the duplicate home button, and the retired motion-segment review screen.
- Feedback and Label fish now show on the team site only.
- "Bigger picture" is now "Largest picture", matching the Layout menu. On a Mac, the example path on the home screen is a Mac path.
- Docs: backup demo recordings in docs/demo (demo-backup.mp4, setup-fast.mp4) with a README.

### 1.3.0 (2026-11-08)
Screen layouts for different monitors, and the whole-window video on the team site.
- New **Layout** choice in the top bar, remembered on each computer, so a laptop and a big monitor can each keep their own:
  - **Fit to screen** (default): the picture is sized so it, its play controls and Save all fit in the window. On screens under 1300 px wide the point list becomes a strip above the picture.
  - **Largest picture**: hides the summary and timeline for the biggest picture. The V key and Bigger picture switch to it and back.
  - **Picture above panels**: the picture uses the full width, the panels sit underneath and Save floats at the bottom right.
  - **Classic**: the earlier layout.
- Choosing a point brings the picture to the top of the window in the fitted layouts.
- Step 1 Visibility and Step 2 Watch window now show the video at the same large size, instead of a small picture with black space.
- Checked at 1920x1080, 1366x768 and 1024x768: the picture, play row and Save stay on screen in every layout.
- Team site: the demo videos now include the whole analysis window, so Whole-window scrub works there.

### 1.2.0 (2026-11-07)
Fixes from three more simulated trials, the model comparison handoff and quality-of-life requests. See the ClipSift Usability Trial 2, 3 and 4 docs.
- Visibility: choosing better or worse needs the new category. Each point's value is worked out from the video's rating and the changes before it, so a correction carries on to later points.
- Step 3: a read-only panel shows other people's counts on the point, with their marks dashed if wanted. Hidden from anyone counting blind or about to recount.
- Names: choosing a name that already has counts asks first. Step 2 says who recorded it and asks before replacing their entries.
- Unknown is the total minus the animals with a species, and updates as species change. A typed number is kept.
- The Possible animals tick is its own field and CSV column, so notes only hold what was typed. Older notes are read the same way.
- Opening a video goes to Step 1 for anyone who hasn't rated visibility. Messages float instead of pushing the page down.
- Step 3: scrolls back to the picture on each point, pins Save and No animals, allows marking on a paused clip frame, and keeps the Play button and Space in step. Display settings reset for a new person, and the species box clears each point.
- Step 2: Enter picks the top match, and saving needs a species or the none seen tick.
- Report: DRAFT until the quality check is done. Adds invertebrate MeanCount, Step 2 notes, a Features column and an invertebrate average in the quality check.
- Compare scrolls to the picture and can hide marks. Step 6 shows keys 1 to 6, Enter saves, and flags on Unsure marks say so.
- Home shows Ready to sign off or In progress, with progress per step. Short clips get start frames inside the clip.
- Model guess after counting: an optional toggle on the count tool, off for every video. Once a count is saved, it shows the model's guess as pink boxes beside the person's number. Never in a blind count or recount. Each count records whether the guess was shown, and the report says on how many points.
- Model check: Step 6 and the guess use whole-frame Nano at 640 with a 0.23 threshold (`model_check` in the config), about 1 false box per empty frame on our test frames. Tiled stays available as a setting. Step 6 says when it finds fewer items than asked.
- No model by default: `layer: 0` in the config and README.
- Check model flags: the divider no longer keeps following the mouse after a release it missed.
- From Trials 3 and 4: totals stay in step with the marks, down to 0 when the last mark is removed. A click on the picture only adds a mark. Remove with right-click or Undo.
- Step 3: drag the picture to move around it in any tool. Wheel zoom is stronger and zooms at the pointer, + and - zoom 2x where the mouse last was, and the zoom level shows. Each point opens at the whole picture.
- Step 3: the first frame step goes to the count second. After the last point, any uncounted point opens. The point name shows beside Save.
- Step 2: typed notes save when you leave the step, and the tab says "notes only" until species are recorded.
- No counts sit in the page behind the name box. "See the summary in Step 6" keeps Step 6 through the name prompt.
- Report: "None seen in the watch window" notes animals counted at points, visibility shows the most common rating, and 0 against 0 reads "both 0".
- Setup: custom spacing between count points, by seconds or by the number of points wanted, with the resulting count shown. The report flags spacing that isn't the protocol's 60 s.
- Step 1: rate visibility at the first count point, or scrub the whole window to the clearest view. The time it was judged is saved and shown in the report.
- Change window or spacing: cut new count points from the same video after setup. Before counting they replace the old points. Once counting has started they make a new version beside the original. Visibility ratings and watch notes carry over, and a replaced folder is kept in runs/.replaced.
- Server: refuses blind counts on frames that aren't held for the check, and asks for `replace` before one person's first count replaces another's.
- One summary for the app, its CSVs and the command line export, so they agree. The summary CSV adds points with no fish, MeanCount per species, visibility changes and model guess use. A test checks the exports agree.

### 1.1.0 (2026-11-07)
Fixes from a simulated trial with three staff. See the ClipSift Usability Trial doc.
- Blind counts: MeanCount, Step 2 notes and the comparison stay hidden from anyone yet to count. The name box has a solid background and can't be skipped when a video opens.
- Quality check: every count shows with its name, and the rule for the value used is stated. Agreement also shows on frames with animals. Recount species and notes reload and reach the report.
- Step 3: saving over someone else's first count asks first.
- Step 3: larger picture and a Bigger picture button (`V`), a No animals button (`N`), the cursor leaves the box on each new point, and the mark type resets after Unsure. Unknown fills in from marks.
- Report: Used in MeanCount column, file name, survey date, who counted, a Reviewed by line, and species split from unidentified groups. Setup has a Survey date box.
- Step 6: the box is drawn on the crop, with a Play button, keys, a finished message and links to frames with missed animals. Save stays on screen.
- Step 6 fix: a set could pick the same item twice. Saving twice quickly could record a decision against the wrong item.
- Polish: point count shown in setup, video time on the Step 2 player, tick boxes no longer jump, counts in the point list, and smaller wording fixes.

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
