# ClipSift (working title)

A local tool that helps Coastal Action staff review long underwater video from turbid Nova Scotia water. It finds the moments worth a look, cuts stills and short loops from the original files, and lets a person confirm and count. It runs offline on a desktop with no GPU. This is a prototype skeleton for a student team to extend.

Status: built and tested on a synthetic clip only. It has not been run on real footage, and nothing here is an accuracy or speed claim.

## What it does

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

Windows (PowerShell):

```
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
winget install Gyan.FFmpeg
```

## Commands

Run `python -m clipsift ...` from the project folder (use `py -m clipsift` on Windows if `python` is not found).

```
python -m clipsift run "path/to/GX010221_T1@1217pm.MP4" "path/to/GX020221_T1@1226pm.MP4" --out runs
python -m clipsift run path/to/folder_of_videos --layer 0
python -m clipsift export runs/GX0221_T1
python -m clipsift evaluate runs/GX0221_T1/results.json --labels labels.csv --out eval_rows.csv
python -m pytest
```

- `run` groups GoPro chapters by video number (`GX01nnnn` and `GX02nnnn` are chapters of `nnnn`) and treats chapters of one video as one timeline in name order. Options: `--config my.yaml`, `--layer 0|1|2`, `--detector name`, `--id`, `--video-id`, `--window-start`, `--window-end`.
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
python -m app.server --runs runs --port 8765
```

Then open the address it prints. The app opens in a **Simple view**: one path for each point (1 Watch the clip, 2 Mark what you see, 3 Check your count, 4 Save and go to the next). The **More tools** button in the header shows everything else (motion segments tab, recording notes, QC mode, exports, grid settings, contrast sliders, detection boxes, ellipse and box tools). The choice is remembered in the browser.

- **?** in the header opens Help: what the tool does, a first count in 5 steps, what the timeline markers mean, keyboard shortcuts, the counting rules in brief, and what suggested counts are. It can also replay the short first-visit tour, which is shown once per browser.
- **Feedback** in the header opens a small form (name, area, type, message). The current run, point and view are attached. In the local app, notes are appended to `runs/feedback.jsonl`. Treat the text as untrusted.
- All calls in `app/static/app.js` go through one `Data` object with two implementations: the Flask API, and a static demo (below).

## Team demo (Cloudflare Worker, no Python server)

The demo is the same page running on static files. It is turned on by `window.CLIPSIFT_DEMO` (written by the build into `static/demo-config.js`). Reads come from static files. Saved counts, marks and notes stay in that browser's localStorage, keyed by run, and CSV exports are made in the browser. A banner says so. Feedback is the one thing that leaves the browser: it goes to `POST /api/feedback` on the Worker, which stores it in D1.

Build the folder to upload (only the runs you name are copied; any id containing `river` is refused; each file must be under 25 MiB; the total size is printed):

```
python tools/build_demo.py                          # default: _fixture synthetic_demo
python tools/build_demo.py _fixture synthetic_demo  # same, explicit
```

Output goes to `deploy/public/` (generated, safe to delete). The demo uses fake or synthetic data only. Do not add real footage.

Deploy (needs Node and a Cloudflare login). Run from `deploy/`:

```
cd deploy
npx wrangler d1 create clipsift-feedback        # copy the database_id into wrangler.jsonc
npx wrangler d1 execute clipsift-feedback --remote --file=schema.sql
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
| 1, local model | layer 0 plus detector, tracker, classifier, counter | pipeline works; no model weights included |
| 2a, bigger local models | stubs | `NotImplementedError` with instructions |
| 2b, cloud comparison | stub, off unless `cloud.enable_2b: true` | `NotImplementedError`; any network use belongs only here |

Backends that exist:

- Proposer: `median_background`.
- Detector: `onnx` (YOLO-style, CPU, needs `detector.onnx.model_path`, nothing is downloaded), `motion_blob`.
- Tracker: `iou` (greedy IoU; ByteTrack or similar can replace it).
- Classifier: `placeholder` (always `fish_unknown`).
- Counter: `basic` (MaxN and its time, MeanCount over fixed intervals, unique tracks).
- Counting model (optional, for schools): only a stub, `point_density_stub`.

**`motion_blob` is a development stand-in, not a model.** It exists so the pipeline runs with no weights. It reacts to any movement (shake, kelp, bubbles), and every detection it makes has `source: motion_blob`. Never report its counts as model accuracy. Subsample suggestions from it are moving-blob counts.

Tiled inference (`tiling.enabled`) splits frames into overlapping tiles for small midwater fish, then merges with NMS. It is off by default and untested on real footage.

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
- No species classifier. Invertebrate counts are always null from software.
- Quick pass and full scan both use the same simple motion method; crash-resume per chunk is a TODO in `pipeline.py`.
- QC: the protocol PDF does not contain its percent-difference formula. `clipsift/qc.py` uses a placeholder (`percent_difference`) that must be replaced once confirmed. This tool does not claim to meet the protocol's QC thresholds.
- The shake flag and low-visibility flag use simple, uncalibrated measures.

## Extracting weak labels from marked screenshots

```
python tools/extract_annotations.py "../Sept 10 & 9th sub-samples" --out labels --written labels/written_totals.json --debug-dir labels/debug
```

Reads (never modifies) a folder of marked screenshots, masks the player bar, and finds red dots, black dots, red ellipses and grid lines. Outputs `labels/annotations.json`, `labels/extraction_report.csv`, `labels/points.csv` and `labels/coco_keypoints.json`. These are weak labels that need human checking. The black-dot detector also fires on dark seabed texture and the report warns about cells with many dots. Do not train on the marked screenshots themselves.

## Known limits

- Only tested on one synthetic clip. Behaviour on real footage is unknown.
- A fish that stays still for a whole background window is absorbed into the background of the motion scan.
- Background windows are not aligned across window boundaries.
- Counts are relative indices, not abundance.
