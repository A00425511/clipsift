# ClipSift (working title)

A local tool that helps Coastal Action staff review long underwater video from turbid Nova Scotia water. It finds the moments worth a look, cuts stills and short loops from the original files, and lets a person confirm and count. It runs offline on a desktop with no GPU. This is a prototype skeleton for a student team to extend.

Status: built and tested on a synthetic clip. The Community Fish Detector backend has been tried on one labelled Coastal frame and one real recording window (see Layer 1 below). Nothing here is an accuracy or speed claim for Coastal Action's water.

## What it does

ClipSift follows Coastal Action's video analysis protocol step by step: see `docs/PROTOCOL_WORKFLOW.md`, which replaces anything below about motion segments. The motion scan is off by default.

The main unit of review is the **subsample point**, following Coastal Action's draft video analysis protocol:

- The analysis window is the video minus a trimmed start and end (default 60 s each, up to 900 s long).
- A point is placed every `interval_s` seconds (default 60) from the window start.
- Each point gets an exact-time still, a difference image, and a context clip (default 5 s either side), all cut from the original files.
- Counts are a **relative index**, not abundance. Software counts are suggestions. A person makes the final count.

A second, supporting pass scans the whole window for motion and sorts it into **active** segments and **set-aside** segments. Set-aside time is recorded, never deleted. A seeded random share (default 5 percent of set-aside time) is marked as an **audit sample** and goes into the review queue.

Every number in the protocol block of `config/default.yaml` is a setting, because the protocol is a draft with unresolved comments.

## Setup

Needs Python 3.10 or newer and (for browser-playable loops) ffmpeg on the PATH. If ffmpeg is missing, loops fall back to OpenCV with a warning, and many browsers cannot play them.

macOS:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
```

For the fish model (Layer 1 default), also install the model extras and fetch the weights (see **Layer 1 model** below):

```
pip install -r requirements-model.txt
python tools/fetch_cfd_weights.py
```

Windows (PowerShell):

```
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
winget install Gyan.FFmpeg
pip install -r requirements-model.txt
py tools\fetch_cfd_weights.py
```

`requirements.txt` stays light and everything except the CFD backend works without torch: Layer 0, `motion_blob`, `onnx`, the review app and all tests. `rfdetr` (and torch) are imported only when the `cfd` detector is built, with a clear error if they are missing.

## Commands

Run `python -m clipsift ...` from the project folder (use `py -m clipsift` on Windows if `python` is not found).

```
python -m clipsift run "path/to/GX010221_T1@1217pm.MP4" "path/to/GX020221_T1@1226pm.MP4" --out runs
python -m clipsift run path/to/folder_of_videos --layer 0
python -m clipsift export runs/GX0221_T1
python -m clipsift evaluate runs/GX0221_T1/results.json --labels labels.csv --out eval_rows.csv
python -m pytest
```

- `run` groups GoPro chapters by video number (`GX01nnnn` and `GX02nnnn` are chapters of `nnnn`) and treats chapters of one video as one timeline in name order. Options: `--config my.yaml`, `--preset cfd_medium_clahe`, `--layer 0|1|2`, `--detector name`, `--device auto|cuda|mps|cpu`, `--id`, `--video-id`, `--window-start`, `--window-end`. The default Layer 1 detector is `cfd`; use `--detector motion_blob` for the no-model stand-in.
- `export` writes, into the run's `export` folder: one row per subsample, a per-video summary (MeanCount and species list), a segments table, and a column dictionary that states counts are relative indices.
- `evaluate` compares results with a human labels CSV. Subsample style: columns `Video ID`, `Timestamp` (seconds or mm:ss), `Total Fish Count` (and `Total Fish Count B` for a second counter). Segment style: `recording_id`, `segment_id` or `start_s`/`end_s`, `maxn`, `count`. It reports signed bias (model minus human), MAE, per-row rows, human versus human agreement, and a note when the sample is small.
- The Video ID guess (`GX0221_T1`) is only a guess at the spreadsheet format. Override it with `--video-id` or `recording.video_id` in config.

Make a synthetic test clip (labelled synthetic, with ground truth in a JSON file):

```
python tools/make_synthetic_clip.py test_clip.mp4 --duration 60 --width 640
```

For short clips, use small protocol values in a config file, for example `trim_start_s: 2`, `trim_end_s: 2`, `interval_s: 10`, `context_s: 2`, `window_length_s: 50`.

## Review app

```
python -m app.server --runs runs --port 8765   # then press New video in the app to add and process a video
```

Then open the address it prints. The app opens on a home screen: drop or choose a video, set it up, and it opens when the count points are ready. Everyone picks their name when a video opens. The steps are 1 Visibility, 2 Watch window, 3 Count points, 4 Quality check, 5 Report and 6 Check model flags (optional). No model runs or shows while counting. The **More tools** button shows the grid settings, sliders and the Label fish page. See `docs/PROTOCOL_WORKFLOW.md`.

- **?** in the header opens Help: what the tool does, a first count in 5 steps, what the timeline markers mean, keyboard shortcuts, the counting rules in brief. It can also replay the short first-visit tour, which is shown once per browser.
- **Feedback** in the header opens a small form (name, area, type, message). The current run, point and view are attached. In the local app, notes are appended to `runs/feedback.jsonl`. Treat the text as untrusted.
- All calls in `app/static/app.js` go through one `Data` object with two implementations: the Flask API, and a static demo (below).

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
runs/<recording_id>/
  results.json                 schema_version 0.2 (see clipsift/schema.py)
  subsamples/ss_01/{still.jpg, diff.jpg, context.mp4}
  segments/seg_0001/{still.jpg, diff.jpg, loop.mp4}    active and audit segments only
  reviews.jsonl, grid_tags.jsonl, subsample_reviews.jsonl, recording_notes.jsonl, point_labels.jsonl   written by the app
```

Original files are never modified. Stills, diffs and loops come from the originals. The fast motion scan runs on downscaled frames (`proxy_width`); faint movement can vanish at low resolution, so keep that in mind. A loop never crosses a chapter boundary.

## Layers

| Layer | What runs | State |
| --- | --- | --- |
| 0, manual assist | subsample points, motion segments, stills, loops, diffs, no detections | works on the synthetic clip |
| 1, local model | layer 0 plus the Community Fish Detector (fish only), counter | works; weights are fetched separately, not in the repo |
| 2a, bigger local models | stubs | `NotImplementedError` with instructions |
| 2b, cloud comparison | stub, off unless `cloud.enable_2b: true` | `NotImplementedError`; any network use belongs only here |

Backends that exist:

- Proposer: `median_background`.
- Detector: `cfd` (default; Community Fish Detector, tiled), `onnx` (YOLO-style, CPU, needs `detector.onnx.model_path`, nothing is downloaded), `motion_blob`.
- Tracker: `iou` (greedy IoU; ByteTrack or similar can replace it).
- Classifier: `placeholder` (always `fish_unknown`).
- Counter: `basic` (MaxN and its time, MeanCount over fixed intervals, unique tracks).
- Counting model (optional, for schools): only a stub, `point_density_stub`.

**`motion_blob` is a development stand-in, not a model.** It exists so the pipeline runs with no weights. It reacts to any movement (shake, kelp, bubbles), and every detection it makes has `source: motion_blob`. Never report its counts as model accuracy. Subsample suggestions from it are moving-blob counts.

The generic `tiling` block splits frames for the `onnx` and `motion_blob` backends. It is off by default and untested on real footage. The `cfd` backend does its own tiling.

## Layer 1 model: Community Fish Detector (CFD)

`detector: cfd` runs RF-DETR weights from filippovarini/community-fish-detector (Nano, Small, Medium) in `models/` (gitignored). **It finds fish only. It was not trained on Nova Scotia footage.** It does not find crabs or other invertebrates, so `invertebrate_count` stays null. Boxes are suggestions for a person to check, and counts are relative indices.

How it runs (`clipsift/stages/cfd.py`, settings in `detector.cfd`):

- Frames are decoded at original resolution, cut into overlapping tiles (default 512 px, overlap 0.25), run through the model (default threshold 0.05), mapped back to original pixels and merged across tiles by intersection over the smaller box. Whole-frame use finds almost nothing, so tiling is not optional.
- The model is loaded once per run. `device: auto` picks cuda, then mps, then cpu. `batch` sets tiles per call. `enhancement: clahe` applies CLAHE before tiling. `roi_mask` (a grayscale image, non-zero analysed) restricts the area and is off by default.
- Each detection has `source: cfd:<variant>`, and the run's `model_version` is the weights file name.
- **Subsample points first:** the detector runs on the exact-time still at full resolution. That feeds `auto.fish_count`, `auto.detections` (box and score) and `auto.status` (`fish_unknown` with boxes; `movement_unidentified` for motion without boxes, never dropped). `mean_count_auto` is the mean of those point counts. `mean_count_reviewed` stays null until a person counts.
- **Then a sparse pass over active segments** at `detect_fps_segments` (default 0.2, one frame per 5 s), not on every sampled frame. Frames that far apart are not tracked, so segment `unique_tracks` is null. MeanCount is the metric that matters here, and unique counts are not attempted.
- **Review order:** mid-confidence detections (`review.mid_conf_low` to `mid_conf_high`) and disagreement between motion and detections (motion but no boxes, or boxes but no motion) rank first. QC samples stay on top.
- Per-stage runtimes are in `run.stage_runtimes_s` (`detector_load`, `subsample_detect`, `segment_detect`, ...).

### Static-object filter

The camera is fixed, so the pipe, pole and rocks sit in the same place in every frame and the detector keeps boxing them. `clipsift/static_filter.py` runs after detection (cfd backend only) and marks such boxes `static: true` with a `static_reason`. **Nothing is deleted:** results.json keeps every box, the review app should hide `static` ones by default, and static boxes are left out of `fish_count`, `mean_count_auto`, `auto.status`, review order, segment counts and the CSV `n_detections`. Old results without the field read as `static: false`.

Settings are in `static_filter` in `config/default.yaml`:

- **Persistence:** a box that recurs at nearly the same place and size (IoU 0.5) in 30% or more of the sampled frames of a recording is static. Learns per recording, so a moved camera needs no hand work. Skipped under 6 frames.
- **Movement:** per box, the 90th percentile of the absolute grey-level difference from a median background of frames t-5 to t+5 s (not the frame itself), 1920 wide, blur 1.5. Below 3 is static. A cutoff of 5 removed real fish on the test frame. Boxes it cannot score are kept.
- **Hand mask:** `masks: [{match: "T1-STAT2*", file: config/masks/t1s2.json}]` or inline `polygons`, in original pixels. `python tools/make_static_mask.py --run runs/<id>/results.json --json mask.json --png mask.png --overlay frame.jpg` suggests polygons from persistent boxes. **A person must check the PNG before using it.**
- Bias is toward keeping: boxes scoring 0.5 or higher are never rejected by persistence or movement, and a persistent place is kept if the box clearly moves. `enabled: false` switches it all off. `python tools/eval_detector.py --run ... --include-static` scores the rejected boxes too.

**Limits.** It can remove a truly still animal (a resting crab, a hovering fish, a school that stays put), and the model only finds fish anyway. On 100 frames of one recording it marked about half the boxes static (mean boxes per frame at threshold 0.1: 28.8 to 14.2); on seven frames marked empty by one person it cut 169 boxes to 79, and did little on two frames where the scene was moving (camera sway or surge). Recall on the labelled dot frame did not change at 0.1 (24 of 103 hits before and after). One recording, tuned on those same frames. Details and controls: `2026 Problem Prep/detector-test/STATIC-FILTER.md`; reproduce with `tools/eval_static_filter.py`.

Setups tried on **one** labelled frame (T1-STAT2 411 at 22:00.3, a dense school, 103 dots from Coastal Action), no fine-tuning. Not accuracy figures: thresholds were picked on that same frame.

| Setup | Boxes | Recall | Precision | Chance recall / precision |
| --- | --- | --- | --- | --- |
| Nano, no enhancement, 512 tiles, threshold 0.05 (default) | 73 | 0.45 | 0.63 | 0.19 / 0.26 |
| Medium, CLAHE, 512 tiles, threshold 0.05 (`--preset cfd_medium_clahe`) | 133 | 0.61 | 0.47 | 0.31 / 0.24 |

Chance is the same box sizes placed at random in the labelled area. `python tools/eval_detector.py --reproduce` repeats this through the integrated backend. To score other labelled frames: `python tools/eval_detector.py --frame IMG --labels dots.json` (add `--variant`, `--enhancement`, `--thresholds 0.03,0.05,0.1`), or `--run runs/<id>/results.json --labels points.csv`. It always prints chance beside the real result.

Weights: `python tools/fetch_cfd_weights.py` downloads the three release files and checks their sha256 (`--check` only verifies). **Licence caveats:** the model code comes through `rfdetr` (Apache 2.0). The weights repository states no licence for the weights, and the training data is mixed, including some non-commercial sources. Settle this with Coastal Action and the repository owner before sharing or relying on the weights beyond a student prototype.

## Adding a backend

Write one class in `clipsift/stages/` (see `base.py` for the method each stage needs), decorate it, and select it in config:

```python
from clipsift.stages.base import Detector, register

@register("detector", "my_detector")
class MyDetector(Detector):
    def __init__(self, cfg): ...
    def detect(self, frame, t): ...   # list[Detection], boxes in the pixels of `frame`
```

Then set `stages.detector: my_detector`. Import your module in `clipsift/stages/__init__.py`.

## Stubs and what does not work yet

- Layer 2a and 2b backends, and the point or density counting model, are stubs.
- No species classifier. Invertebrate counts are always null from software, because the model only finds fish. Crabs and other benthic animals need a separate approach.
- The CFD model is untrained on Nova Scotia footage. Confidence is low on turbid water, so the threshold is low (0.05) and a share of boxes will be wrong. Check a handful of points by eye before trusting any suggested count.
- Speed depends on the machine. Timings measured on a Mac (see the run notes) are not Coastal Action's PC. Medium with CLAHE is slower than Nano.
- Quick pass and full scan both use the same simple motion method; crash-resume per chunk is a TODO in `pipeline.py`.
- QC: the protocol PDF does not contain its percent-difference formula. `clipsift/qc.py` uses a placeholder (`percent_difference`) that must be replaced once confirmed. This tool does not claim to meet the protocol's QC thresholds.
- The shake flag and low-visibility flag use simple, uncalibrated measures.

## Extracting weak labels from marked screenshots

```
python tools/extract_annotations.py "../Sept 10 & 9th sub-samples" --out labels --written labels/written_totals.json --debug-dir labels/debug
```

Reads (never modifies) a folder of marked screenshots, masks the player bar, and finds red dots, black dots, red ellipses and grid lines. Outputs `labels/annotations.json`, `labels/extraction_report.csv`, `labels/points.csv` and `labels/coco_keypoints.json`. These are weak labels that need human checking. The black-dot detector also fires on dark seabed texture and the report warns about cells with many dots. Do not train on the marked screenshots themselves.

## Known limits

- Tested on one synthetic clip, one labelled real frame and one real recording window. Behaviour elsewhere is unknown.
- A fish that stays still for a whole background window is absorbed into the background of the motion scan.
- Background windows are not aligned across window boundaries.
- Counts are relative indices, not abundance.
