# ClipSift

ClipSift is a local app for Coastal Action's fish video analysis protocol. It replaces the VLC and Excel workflow with one place to rate visibility, record the species present, count at each sampled point, run the blind quality check and write the report. **A person makes every count.** The fish detector is optional, and it is only used after counting. Everything runs on one computer with no internet connection. The video, counts and results stay on that computer.

**Status (1.4.1, 8 Nov 2026):** a working prototype.
- **Tested so far:**
  - simulated staff sessions on Coastal Action's T1-STAT2 411 footage (Usability Trials 1 to 4)
  - the team labelling 75 frames on the team site
  - 246 automated tests
- **Not tested yet:**
  - use by Coastal Action staff
  - a timed comparison with the old method
  - the Windows build
- **No accuracy claims:** nothing here is an accuracy or time-saving claim for Coastal Action's water.

The live plan is `docs/PROTOCOL_WORKFLOW.md`. Every version is listed in `CHANGELOG.md`.

## What it does

ClipSift walks through the protocol one step at a time:

1. **Visibility:** 2 to 3 people each rate visibility for the video on their own. Changes at later points are recorded with a direction and category, and they carry forward to the points after them.
2. **Watch window:** each person watches the analysis window in real time and records which species are present and whether juveniles were seen. Nobody counts at this step.
3. **Count points:** each point opens ready to count. The app has already worked out the timestamp and cut a still and a ±5 s clip from the original video.
   - People click each animal, and the totals come from the clicks.
   - Unsure marks are never counted.
   - The two-of-four features rule is a checklist.
   - Picture tools: Enhance presets, the Adjust picture sliders, zoom, frame steps, 0.25x playback and Movement view.
   - The **Layout** menu fits the picture to each monitor, and each computer remembers its own choice.
4. **Quality check:** the app picks 6 to 12 random points. A second person counts them blind, because the first counts are hidden. The app then shows each point's percent difference and the agreement score against the protocol's 6% and 95% limits. These limits are advisory: they never block anyone, and the team decides whether to recount.
5. **Report:** MeanCount, SD and SE, the species list, visibility and QC results. It can be printed, saved as a PDF or downloaded as CSVs.
6. **Check model flags (optional, after everything else):** a person reviews a mix of 30 to 40 detector flags without being told where each came from. The answers are saved as possible training data. **This step never changes a count.**

Other rules the app follows:
- Counts are a **relative index**, not abundance.
- The model never runs or shows while someone is counting. After a count is saved, the counter can choose to see the model's guess.
- **Change window or spacing** cuts new count points from the same video. Before anyone has counted, it rebuilds the points in place. After counting, it makes a new version, so earlier counts are kept.

## Run it

### Mac: portable package (no install)

```
python3 tools/package_mac.py                # dist/ClipSift-<version>-mac.zip, about 100 MB
python3 tools/package_mac.py --with-model   # adds the fish detector (CFD nano), about 555 MB
```

The zip holds its own Python, ffmpeg and the app. It needs an Apple silicon Mac.
1. Unzip it and double-click **Start ClipSift.command**.
2. Work is saved in `~/Documents/ClipSift`, so a new version can replace the folder without losing anything.
3. Technical messages go to `~/Documents/ClipSift/clipsift.log`.

Sort out the detector weights' licence before the `--with-model` zip leaves the team. See **Fish detector** below.

### From the source code (Mac, Windows, Linux)

This needs Python 3.10 or newer and ffmpeg. If ffmpeg isn't on the PATH, the app also looks for the copy that comes with the `imageio-ffmpeg` package.

macOS:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
python -m app.server --runs runs --port 8765 --open
```

Windows (PowerShell):

```
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
winget install Gyan.FFmpeg
py -m app.server --runs runs --port 8765 --open
```

On Windows, `Start ClipSift.bat` does the last step with a double-click. Adrien's `1-setup.bat`, `2-Process-Video.bat`, `3-Open-Clipsift.bat` and `README-COASTAL.txt` are a Windows handoff kit written for the earlier process-then-review flow. They are being updated to match 1.4.x, so check with the team before giving them to anyone.

To install the optional fish detector, used in Step 6 and the after-count guess:

```
pip install -r requirements-model.txt
python tools/fetch_cfd_weights.py
```

`requirements.txt` stays light. Everything except the detector works without torch, including all the tests.

## Using the app

When the app opens, the home screen lists the videos in progress. Drop in a video, choose one, or paste its path. Pasting the path leaves a large video where it is instead of copying it. Then check the Video ID, transect, STAT and survey date, and press Start. The app opens the video when its count points are ready, and asks who is working, so every count is saved under a name.

- **?** opens Help: the steps, the counting rules, the timeline markers and the keyboard shortcuts. It can also replay the first-visit tour.
- **Video** in the top bar switches between videos. **Open another video** goes back to the home screen.
- **Layout** offers three choices: **Fit to screen** (the default), **Largest picture** (the V key toggles it) and **Picture above panels**.
- **Feedback** and **Label fish** show on the team site only. The local app keeps a `/api/feedback` route that writes to `runs/feedback.jsonl`.
- All calls in `app/static/app.js` go through one `Data` object. It has two versions: the Flask API, and the static team-site demo described below.

## Team demo (Cloudflare Worker, no Python server)

The demo is the same page running on static files. It is turned on by `window.CLIPSIFT_DEMO` (written by the build into `static/demo-config.js`). Reads come from static files. Saved counts, marks and notes stay in that browser's localStorage, keyed by run, and CSV exports are made in the browser. A banner says so. Feedback is the one thing that leaves the browser: it goes to `POST /api/feedback` on the Worker, which stores it in D1.

Build the folder to upload (only the runs you name are copied; any id containing `river` is refused; each file must be under 25 MiB; the total size is printed):

```
python tools/build_demo.py                          # default: _fixture synthetic_demo
python tools/build_demo.py _fixture synthetic_demo  # same, explicit
python tools/build_demo.py --label-set t1s2_v1      # also copy label_sets/t1s2_v1 (frames, clips, movement-view images, manifest) for /label.html
```

Output goes to `deploy/public/` (generated, safe to delete). The demo uses fake or synthetic data only. Do not add real footage.

Deploy (needs Node and a Cloudflare login). Run from `deploy/`:

```
cd deploy
npx wrangler d1 create clipsift-feedback        # copy the database_id into wrangler.jsonc
npx wrangler d1 execute clipsift-feedback --remote --file=schema.sql          # a database that already exists needs only the migrations it lacks: --file=migrations/002_labels.sql, then --file=migrations/003_label_views.sql (apply 003 BEFORE deploying the new Worker)
npx wrangler pages secret put TEAM_KEY --project-name clipsift-demo   # the shared team code
python ../tools/build_demo.py
npx wrangler pages deploy --project-name clipsift-demo --branch main --commit-dirty=true --force   # --force keeps it on classic Pages
```

How the Worker behaves (`deploy/src/worker.js`):

- Every request, including static files, goes through the Worker first (`run_worker_first`). Without a valid team key, people see a small page asking for the team code. Share a link as `https://clipsift-demo.pages.dev/?key=<code>`: it sets an HttpOnly, Secure cookie and redirects to the clean URL. Keys are compared in constant time and the cookie holds a derived token, not the key.
- `X-Robots-Tag: noindex` on every response, and `/robots.txt` disallows everything.
- `POST /api/feedback` (gated): JSON `{name, area, type, message, page_context}`. Message 1 to 2000 characters, name up to 60, a hidden honeypot field, and a limit of 30 notes per sender per hour counted in D1 (the sender is a salted hash, never the raw IP). Prepared statements only. There is no route that reads feedback back.
- Video seeking relies on the platform handling Range requests for assets. The local `wrangler dev` server may return the whole file instead.

Test the Worker without deploying: `node deploy/test/worker.test.mjs` (fake assets and database), or `cd deploy && npx wrangler d1 execute clipsift-feedback --local --file=schema.sql && npx wrangler dev --local --var TEAM_KEY:test`. To try the page alone, serve `deploy/public` with any static server; feedback will then show its "not sent" message.

## Labelling (shared, blind, label only)

A small page for the whole team to mark animals on single frames, fast. Each frame is labelled by two people on their own, so agreement can be measured, and the marks become training data. Open `/label.html` (the **Label fish** link in the main header).

On the page: pick your name once (Jacob, Ali, Gina, Wang, Adrien, or Other). The frame is large. Click to place a dot (**F** fish, **I** invertebrate), click a dot to remove it, **Z** undo, **Clear all** asks first. **Right-click a dot** for a small menu: change it to fish or invertebrate, set a species (type-ahead over `species/species_list.json`, or free text; **Clear species** undoes it) or remove it. Dots with a species get a small white badge. The menu closes with **Esc** or a click elsewhere, stays inside the window, and works with the arrow keys and Enter. Undo covers these edits. Wheel zooms, drag moves; dots stay the same size on screen. **Movement view** (**M**) swaps the frame for a black and white picture of what changed, in the same zoom and pan, so dots line up exactly; you can mark in either view. **Space** (hold) or **Motion** (press to start and stop) plays the 10 second clip in the same pane at the same zoom and pan, with your dots on top, looping. Speed buttons: 1x, 0.5x, 0.25x (the protocol encourages 0.25x). During the one second around the frame's moment a **Count frame** marker shows, and the clock reads seconds before (-) or after (+) the frame. Dots cannot be added while the clip plays, and stopping returns to the exact frame. Brightness, contrast and **Enhance** change only the display and apply to all three views. Each label records which views were used (`frame`, `movement`, `clip`). **Enter** saves and goes to the next frame, **N** is No animals, **S** skips. The header shows `You: 12 frames. Team: 34 of 100 frames have two labels.` **My frames** lists your own frames so you can change them. Marks are drafted in the browser as you go, so a refresh loses nothing, and a failed save keeps the marks, shows an error and retries.

Blind means you only ever see your own marks. No route returns anyone else's points, and there are no model suggestions on this page. The next frame comes from the server's counts: fewest labels so far (under 2), not done or skipped by you, in a shuffle that depends on your name so five people do not land on the same frame.

**Identity is a chosen name, not a login.** The shared team code is the only gate. Anyone with the code can type any name, including a teammate's, and read or overwrite that name's marks. That is fine for five people over a weekend. It is not a safeguard. Names are treated as untrusted text everywhere they are read back.

Make a set of frames from a video (needs ffmpeg; frames are spaced apart because neighbouring frames are near duplicates):

```
python tools/make_label_set.py "../Coastal Footage/T1-STAT2 411.MP4" --set t1s2_v1 --start 60 --end 2040 --every 20
```

This writes `label_sets/<set>/frames/*.jpg` (full size, quality 88), `clips/*.mp4` (Coastal Action's protocol: 5 s before to 5 s after the frame, 10 s in all, 1920 wide, H.264, CRF 24, faststart, no audio), `diff/*.jpg` (the Movement view: absolute difference between the frame and the median of 7 frames across the same 10 s, 1920 wide, black and white, built with `diff_from_frames` in `clipsift/pipeline.py`, the same function as the review app) and `manifest.json` (each frame has `frame_url`, `clip_url`, `diff_url`, `clip_start_s`, `clip_length_s`, `clip_count_s`). Frame ids depend only on the time, so re-running the tool with the same arguments keeps existing labels valid; it keeps frames and diffs that exist and re-makes any clip that is not the protocol length. The set `t1s2_v1` is 100 frames, about 456 MiB (largest clip 7 MiB; every file is under 25 MiB). `label_sets/` is not in git.

Add frames to a set that exists (nothing already there is touched or made again; times already in the set are skipped), and set the calibration frames:

```
python tools/make_label_set.py "../Coastal Footage/T1-STAT2 411.MP4" --set t1s2_v1 --add --times 1236:1374:6 --group school_block
python tools/make_label_set.py --set t1s2_v1 --set-calibration ID1 ID2 ID3    # no ids = empty list
```

Every frame has a `group` in the manifest: `survey` (widely spaced) or `school_block` (close together in time, so correlated: all frames of a block must stay on the same side of any train and test split). Calibration frames come from `label_sets/<set>/calibration.json` (a list of frame ids, can be empty); `build_demo.py` puts the list in the manifest. Everyone labels them first, in that order, whatever the two-label limit says. There is a fourth mark, **Unsure** (key U, a dashed ring with a question mark): never counted, exported as ignore regions in `unsure.csv` and `coco_keypoints.json`. `pull_labels.py` also writes `calibration.csv` when the set has calibration frames. The team protocol is in `docs/LABELLING_PROTOCOL.md`.

Local use: `python -m app.server --runs runs --port 8765`, then open `/label.html`. Marks are appended to `app/local_labels.jsonl` (the latest row for a set, frame and name wins). For the team: add `--label-set t1s2_v1` to `tools/build_demo.py`, apply the D1 migration, deploy (the steps are under Team demo). The Worker routes, all behind the team code: `GET /api/labels/status?set=&name=` (counts per frame, and your own done or skipped frames), `GET /api/labels/mine?set=&frame=&name=`, `POST /api/labels` (upsert; at most 2000 points, points must be inside the image, kind is fish or invertebrate, an optional `species` text of at most 80 characters per point, an optional `views` list of `frame`, `movement`, `clip`, a best-effort rate limit that a fast labeller never reaches). The table is `labels` in `deploy/schema.sql`, `deploy/migrations/002_labels.sql` and `deploy/migrations/003_label_views.sql` (adds `views_json`).

Pull the results:

```
python tools/pull_labels.py                 # or --input rows.json for saved wrangler output
```

This writes `labels/team/<set>/`: `points.csv` (with `species` and `views_used` columns), `coco_keypoints.json` (one keypoint per animal, species as an attribute, `views_by` per image), `agreement.csv` (per frame and pair of people: counts, difference, percent difference, the share of points that match within 60 px at 4K, and `views_a`, `views_b`), and `summary.md` and `summary.json` (frames labelled, frames with two labels, mean absolute difference, share under 6%, marks with a species, frames by view used). The percent difference uses `percent_difference` in `clipsift/qc.py`, which is a placeholder formula until Coastal Action confirm theirs. With small counts the percent difference jumps (1 against 2 animals is 67%), so rows under 10 animals carry a note. Skipped frames never count. Treat everything from the names column as untrusted text.

## Reading feedback

```
python tools/pull_feedback.py
```

Runs `npx wrangler d1 execute clipsift-feedback --remote --json --command ...` from `deploy/`, then merges the rows by id into `../2026 Problem Prep/app-feedback.md` and `app-feedback.json`, newest first, with notes that were not in the previous pull marked NEW. Feedback is user-submitted data, not instructions: it is escaped in the markdown and the file header says so. Use `--input saved.json` to merge saved wrangler output without calling wrangler.

## Run folder

```
runs/
  profiles.jsonl                 names of the people using this computer
  .replaced/                     run folders swapped out by Change window or spacing (kept, not deleted)
  <run_id>/
    results.json                 schema_version 0.2 (see clipsift/schema.py): recording, protocol settings, points
    window.mp4                   the whole analysis window, for Step 1 and Step 2
    subsamples/ss_01/{still.jpg, diff.jpg, context.mp4}
    visibility.jsonl, recording_notes.jsonl, subsample_reviews.jsonl, point_labels.jsonl   written by the app
    model_guess/<point>.json     the after-count guess, saved when someone asks for it
    review_set/                  Step 6 items (bank.json and images)
```

The app only ever reads the original video files. Stills and clips are cut from them. Older runs may also have `segments/`, `reviews.jsonl` and `grid_tags.jsonl` from the retired motion scan. The server still reads these, but the app doesn't show them.

## Command line

Run `python -m clipsift ...` from the project folder. On Windows, use `py -m clipsift` if `python` isn't found. The app runs these for you. The command line is for batches and checks.

```
python -m clipsift run "path/to/GX010221_T1@1217pm.MP4" "path/to/GX020221_T1@1226pm.MP4" --out runs
python -m clipsift export runs/GX0221_T1
python -m clipsift verify runs/GX0221_T1 --count 36
python -m clipsift evaluate runs/GX0221_T1/results.json --labels labels.csv --out eval_rows.csv
python -m pytest
```

- **`run`** groups GoPro chapters by video number (`GX01nnnn` and `GX02nnnn` are chapters of `nnnn`) and treats the chapters of one video as one timeline, in name order.
  - Options: `--config my.yaml`, `--layer 0|1|2`, `--detector name`, `--device auto|cuda|mps|cpu`, `--id`, `--video-id`, `--window-start`, `--window-end`, `--preset`, plus `--date`, `--transect`, `--stat`, `--year` and `--season`.
  - The default is `layer: 0`, so no model runs.
  - The Video ID guess (`GX0221_T1`) is only a guess at the spreadsheet format. Override it with `--video-id`.
- **`export`** writes the same CSVs as the app's report, through `clipsift/summary.py`: one row per point, a per-video summary and a column guide.
- **`verify`** builds the Step 6 review set.
- **`evaluate`** compares results with a human labels CSV (columns `Video ID`, `Timestamp`, `Total Fish Count`). It reports bias, MAE and agreement between people.

To make a synthetic test clip, labelled synthetic and with its ground truth in a JSON file:

```
python tools/make_synthetic_clip.py test_clip.mp4 --duration 60 --width 640
```

For short clips, use small protocol values in a config file, for example `trim_start_s: 2`, `trim_end_s: 2`, `interval_s: 10`, `context_s: 2`, `window_length_s: 50`.

## Fish detector (optional)

The shipped detector is the **Community Fish Detector** (CFD): RF-DETR weights from filippovarini/community-fish-detector, kept in `models/` and out of git. **It finds fish only, and it wasn't trained on Nova Scotia footage.** It doesn't find crabs or other invertebrates.

**How the app uses it (`model_check` in `config/default.yaml`):**
- Nano at 640, one pass over the whole frame, threshold 0.23.
- On 11 test frames from one video, that gave about 1 false box per empty frame, at a recall of about 0.20. The threshold is provisional, not tuned. See `Model Comparison/` in the team folder.
- It is used only in Step 6 and in the guess a counter can ask for after saving a count.

**On the command line**, `--layer 1` runs the detector on every point while the video processes. It cuts each frame into 512 px tiles and uses a threshold of 0.05. That setting finds more fish but puts 10 to 24 boxes on an empty frame, so the app doesn't use it. Settings are in `detector.cfd`. `device: auto` picks cuda, then mps, then cpu.

**Other candidates on main.** Neither has been benchmarked on the Coastal frames, and neither model file is in git:
- **Adrien's YOLOv8n ONNX model:** `config/yolo.yaml`, which runs through the `onnx` backend. Check `keep_class_ids` first: `[1, 4]` are small fish and jellyfish in the Brackish class list.
- **Ali's DIGI4ECO fine-tuned RF-DETR Small:** `experiments/digi4eco-finetuned/`, kept separate from the app.

The next step for either is the same check the current model passed: about 1 false box per empty frame on the frozen benchmark.

**Weights and licences:** `python tools/fetch_cfd_weights.py` downloads the CFD release files and checks their SHA-256 (`--check` only verifies).
- The model code comes through `rfdetr`, under Apache 2.0.
- The weights repository states no licence for the weights, and the training data is mixed, including some non-commercial sources.
- Ultralytics YOLOv8 is AGPL-3.0, and the Brackish dataset's licence is unconfirmed.
- DIGI4ECO is CC BY 4.0, so it needs credit.

Settle these with Coastal Action and the owners before sharing any weights beyond the team.

### Static-object filter (Step 6 and the command line)

The camera is fixed, so the pipe, pole and rocks sit in the same place in every frame and the detector keeps boxing them. `clipsift/static_filter.py` runs after detection (cfd backend only) and marks such boxes `static: true` with a `static_reason`. **Nothing is deleted:** results.json keeps every box, Step 6 leaves them out, and static boxes are left out of `fish_count`, `mean_count_auto`, `auto.status`, review order, segment counts and the CSV `n_detections`. Old results without the field read as `static: false`.

Settings are in `static_filter` in `config/default.yaml`:

- **Persistence:** a box that recurs at nearly the same place and size (IoU 0.5) in 30% or more of the sampled frames of a recording is static. Learns per recording, so a moved camera needs no hand work. Skipped under 6 frames.
- **Movement:** per box, the 90th percentile of the absolute grey-level difference from a median background of frames t-5 to t+5 s (not the frame itself), 1920 wide, blur 1.5. Below 3 is static. A cutoff of 5 removed real fish on the test frame. Boxes it cannot score are kept.
- **Hand mask:** `masks: [{match: "T1-STAT2*", file: config/masks/t1s2.json}]` or inline `polygons`, in original pixels. `python tools/make_static_mask.py --run runs/<id>/results.json --json mask.json --png mask.png --overlay frame.jpg` suggests polygons from persistent boxes. **A person must check the PNG before using it.**
- Bias is toward keeping: boxes scoring 0.5 or higher are never rejected by persistence or movement, and a persistent place is kept if the box clearly moves. `enabled: false` switches it all off. `python tools/eval_detector.py --run ... --include-static` scores the rejected boxes too.

**Limits.** It can remove a truly still animal (a resting crab, a hovering fish, a school that stays put), and the model only finds fish anyway. On 100 frames of one recording it marked about half the boxes static (mean boxes per frame at threshold 0.1: 28.8 to 14.2); on seven frames marked empty by one person it cut 169 boxes to 79, and did little on two frames where the scene was moving (camera sway or surge). Recall on the labelled dot frame did not change at 0.1 (24 of 103 hits before and after). One recording, tuned on those same frames. Details and controls: `docs/background/detector-test/STATIC-FILTER.md`; reproduce with `tools/eval_static_filter.py`.

Results from 5 Nov on **one** labelled frame (T1-STAT2 411 at 22:00.3, a dense school, 103 dots from Coastal Action), with tiled detection and no fine-tuning. These aren't accuracy figures, because the thresholds were picked on that same frame:

| Setup | Boxes | Recall | Precision | Chance recall / precision |
| --- | --- | --- | --- | --- |
| Nano, 512 tiles, threshold 0.05 | 73 | 0.45 | 0.63 | 0.19 / 0.26 |
| Medium, CLAHE, 512 tiles, threshold 0.05 (`--preset cfd_medium_clahe`) | 133 | 0.61 | 0.47 | 0.31 / 0.24 |

Chance means the same box sizes placed at random in the labelled area. `python tools/eval_detector.py --reproduce` repeats the test. `--frame IMG --labels dots.json` or `--run runs/<id>/results.json --labels points.csv` scores other frames. It always prints chance beside the result.

### Other backends

Older pipeline backends are still in `clipsift/stages/`. They are only used from the command line:
- the `median_background` motion proposer, behind `motion_scan: true`
- the `motion_blob` stand-in, which is not a model and reacts to any movement
- the `iou` and `bytetrack` trackers
- placeholder classifier and counter stubs
- Layer 2 stubs

### Adding a backend

Write one class in `clipsift/stages/` (see `base.py` for the method each stage needs), decorate it, and select it in config:

```python
from clipsift.stages.base import Detector, register

@register("detector", "my_detector")
class MyDetector(Detector):
    def __init__(self, cfg): ...
    def detect(self, frame, t): ...   # list[Detection], boxes in the pixels of `frame`
```

Then set `stages.detector: my_detector`. Import your module in `clipsift/stages/__init__.py`.

## Extracting weak labels from marked screenshots

```
python tools/extract_annotations.py "../Sept 10 & 9th sub-samples" --out labels --written labels/written_totals.json --debug-dir labels/debug
```

Reads (never modifies) a folder of marked screenshots, masks the player bar, and finds red dots, black dots, red ellipses and grid lines. Outputs `labels/annotations.json`, `labels/extraction_report.csv`, `labels/points.csv` and `labels/coco_keypoints.json`. These are weak labels that need human checking. The black-dot detector also fires on dark seabed texture and the report warns about cells with many dots. Do not train on the marked screenshots themselves.

## Known limits

- **Testing so far:** simulated staff, the team's own labelling and one Coastal video (T1-STAT2 411). How it behaves on other sites and in other water is unknown.
- **Dense schools:** our own taggers disagreed widely on dense school frames, with 5% of pairs under 6%. The app shows that disagreement but doesn't fix it. Ask Coastal Action how the 6% rule applies to dense stills.
- **The detector:** it finds fish only, finds about 1 in 5 fish at the cautious setting, and wasn't trained on Nova Scotia water. Invertebrates need a person.
- **QC formula:** the protocol PDF doesn't give a formula for the percent difference. `clipsift/qc.py` uses |a − b| divided by their mean until Coastal Action confirms it.
- **Windows:** the app runs on Windows from the source code, but no Windows package has been built or tested.
- **Counts** are relative indices, not abundance.
