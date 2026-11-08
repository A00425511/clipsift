# ClipSift skeleton: build spec (working title)

**Read `PROTOCOL_WORKFLOW.md` first. It overrides this file wherever they differ.** This file is the older build history. Its motion segment, active and set-aside design is retired from the workflow.

Local tool that helps Coastal Action review about 1 hour GoPro recordings of turbid Nova Scotia water: detect, track, count fish, and let a person confirm. Runs offline on a desktop. Background: ../2026 Problem Prep/p2-concepts.md.

This is a skeleton a five-person student team extends over the weekend, so favour clear, small, readable code over cleverness. Real footage hasn't been integrated yet. It must run on a machine with no GPU.

## Stack
Python 3.10+ (tested here on 3.14), OpenCV, NumPy, PyYAML, Flask, onnxruntime, plain HTML/CSS/JS with no CDN and no build step. No internet at run time. No telemetry. No other dependencies without a strong reason. Windows and macOS must both work: use pathlib, no shell-only tricks.

## Layout and ownership
Agents only touch their own paths.
- Pipeline agent: `clipsift/` package, `config/`, `tools/`, `tests/test_pipeline*.py`, `tests/test_counts.py`, `tests/test_evaluate.py`, `README.md`, `requirements.txt`
- App agent: `app/`, `tests/test_app.py`
- Species agent: `species/`, `tests/test_species.py`

## Layers (config `layer: 0|1|2`)
- Layer 0, manual assist: motion segments, stills, loops, difference images. No detections. People tag.
- Layer 1, local model, the core product: Layer 0 plus Detector, Tracker, Classifier, Counter.
- Layer 2a: bigger local models, stub only. Layer 2b: cloud generative comparison, stub only and never enabled by default. Any network use exists only in 2b.

## Stage interface (`clipsift/stages/base.py`)
SegmentProposer(frames) -> list[Segment]; Detector(frame) -> list[Detection]; Tracker(detections per frame) -> list[Track]; Classifier(crop) -> list[SpeciesGuess]; Counter(tracks, detections) -> Counts. Registered by name; config selects a backend per stage. Adding a backend means adding one class.

## Run folder contract (the joint between pipeline and app)
`runs/<recording_id>/`
- `results.json` (below)
- `segments/<segment_id>/still.jpg`, `diff.jpg`, `loop.mp4` (cut from the ORIGINAL footage, full resolution where practical; loop must play in a browser, so H.264)
- `reviews.jsonl`: append-only, written by the app, one JSON object per decision
- `grid_tags.jsonl`: append-only, written by the app

`results.json`:
```json
{
  "schema_version": "0.1",
  "recording": {"recording_id": "str", "source_files": ["path"], "duration_s": 0.0, "fps": 0.0, "width": 0, "height": 0, "site": null, "date": null},
  "run": {"layer": 1, "model_version": "str|null", "config_hash": "str", "created_at": "ISO8601", "sample_fps": 2.0, "runtime_s": 0.0, "stage_runtimes_s": {}},
  "segments": [{
    "segment_id": "seg_0001", "start_s": 0.0, "end_s": 0.0,
    "kind": "active|set_aside",
    "audit_sample": false,
    "motion_score": 0.0,
    "flags": {"shake": false, "low_visibility": false},
    "visibility_score": 0.0,
    "status": "known|fish_unknown|unclear|movement_unidentified|none",
    "still_time_s": 0.0,
    "detections": [{"t": 0.0, "box": [0,0,0,0], "score": 0.0, "track_id": null, "source": "str"}],
    "tracks": [{"track_id": 1, "start_s": 0.0, "end_s": 0.0, "n_points": 0, "species_topk": [{"name": "str", "aphia_id": null, "score": 0.0}], "status": "fish_unknown"}],
    "counts": {"maxn": null, "maxn_time_s": null, "mean_count": null, "unique_tracks": null},
    "review_priority": 0.0
  }],
  "summary": {"n_segments": 0, "n_active": 0, "n_set_aside": 0, "n_audit": 0, "maxn": null, "mean_count": null, "unique_tracks": null}
}
```
`box` is [x, y, w, h] in original pixels. Null means not computed. Set-aside time is recorded, never deleted. A random share of it (config, default 5%, seeded) is marked `audit_sample` and enters the review queue. Motion with no detection is `movement_unidentified`, never dropped. Higher `review_priority` comes first; uncertain segments and audit samples rank high.

`reviews.jsonl` line: `{"segment_id","decision":"confirm|reject|unknown|needs_second_look","species":null,"count":null,"note":"","reviewer":"","at":"ISO8601","model_version":null,"contrast_settings":{}}`. `grid_tags.jsonl` line: `{"segment_id","time_s","grid":[rows,cols],"cell":[r,c],"species":null,"count":1,"reviewer":"","at":"ISO8601"}`.

## Rules from the plan
- Original files are never modified. Contrast is display-only in the UI.
- Accept several chapter files as one recording, in name order.
- Downscaling is for speed only and configurable; stills and loops come from originals. Flag this in a code comment, since faint movement can vanish at low resolution.
- Save per-chunk progress so a crash doesn't restart a recording, if simple. Otherwise leave a TODO.
- Counts are relative indices, not abundance. Say so in the CSV column dictionary.
- Don't invent accuracy or timing claims in the README. Don't claim it works on real footage until it has been tested on it.

## Species file contract
`species/species_list.json` is a list of records: `{"aphia_id": int|null, "gbif_key": int|null, "scientific_name": str, "common_names": [str], "aliases": [str], "group": str, "flags": {"at_risk": bool, "invasive": bool, "range_expander": bool}, "ns_status_tier": "recorded|nearby|unexpected|unknown", "id_notes": str, "sources": [{"name": str, "retrieved": "YYYY-MM-DD"}]}`. The app reads this file. If it's missing, the app still works with an empty list and free text.

Style: no em dashes in docs or UI text. Plain language in the UI for field staff. No gendered pronouns.

# Addendum 1: Coastal Action's Video Analysis Protocol (read 5 Nov). This overrides anything above where they differ.
Source: ../Coastal Action DRAFT FFH Video Analysis Protocol.pdf. It's a draft with unresolved comments, so every number below is a config value, never hard-coded.

## Their method
Stationary, unbaited remote underwater video. Metric: **MeanCount** from systematic subsampling, plus species richness. Purpose: long-term monitoring, so results must stay comparable across years.
- Analysis window: of each ~20 minute video, 15 minutes. Discard first and last minute; up to 4 more minutes may be removed for sediment or setup. Record start and end times used.
- Subsamples: every 60 s, 15 frames. An older draft says 60 points every 12 s, citing an accuracy inflexion at 60 frames. So interval is config, and the tool should make more points cheap.
- Each point: watch about 5 s before and after for context (a comment suggests 10 s, because flounder are missed unless moving). Count only within the designated one second; a fish appearing within about 0.5 s, no more than 1 s, either side at 0.25x speed may count. Purpose: avoid double counting.
- Count **fish and invertebrates** (crabs, shrimp, worms, snails).
- Include an organism only if distinguished by at least two of: shape; anatomical features; colouration or flashes; swimming behaviour or movement. When unsure, exclude. Undercounting is preferred to overcounting.
- Record per subsample: total fish count, invertebrate count, number of species, individuals per species, count in an "Unknown/Unable to ID due to visibility" column, changes in visibility of 0.5 m or more, notes.
- Per video: species observed across the whole window while watching in real time (lowest practicable taxonomic level); juveniles present 1 or 0 (optional).
- Visibility categories: <0.5 m, 0.5-1.0 m, 1.0-1.5 m, >1.5 m, by 2 to 3 observers. Future videos have a 2 m pole with tape marks every 0.5 m.
- Quality control: random review of at least 10% of annotated frames (6 to 12 per video), blind counted by two people, averaged; difference under 6%, otherwise recount, preferably by a different counter; below 95% agreement means reannotate. Track who counted. Thresholds are config; the protocol's percent-difference formula is missing from the PDF, so make it a named function and note this.
- Files: drive > year > season > date > transect > STAT, for example T1 / STAT 1. GoPro chapters such as GX010221_T1@1217pm, GX020221_T1@1226pm, with .THM sidecars. Video ID must match their spreadsheet.

## Design changes
**The subsample point is the main unit of review.** The queue is the subsample points first. Motion segments become a second, supporting pass, for richness and for catching what happens between points.

New config block `protocol`: `trim_start_s: 60`, `trim_end_s: 60`, `extra_trim_max_s: 240`, `window_length_s: 900`, `interval_s: 60`, `context_s: 5`, `count_window_s: 1`, `count_tolerance_s: 0.5`, `qc_share: 0.10`, `qc_min: 6`, `qc_max: 12`, `qc_max_percent_diff: 6`, `qc_agreement: 95`. The user can override window start and end per recording.

Additions to `results.json` (schema_version 0.2):
- `recording` adds `video_id`, `transect`, `stat`, `year`, `season`, parsed where possible from path or filename, otherwise null and editable; chapter files grouped by GoPro number (`GX01nnnn`, `GX02nnnn` are chapters of nnnn).
- top-level `protocol`: the config used, plus `window_start_s`, `window_end_s`.
- top-level `subsamples`: list of `{"subsample_id":"ss_01","t_s":0.0,"context_start_s":0.0,"context_end_s":0.0,"auto":{"fish_count":null,"invertebrate_count":null,"detections":[],"motion_near_point":false,"movement_unidentified":0,"visibility_score":0.0},"qc_sample":false,"review_priority":0.0}`
- `segments` stay, as a supporting scan of the window.
- `summary` adds `mean_count_auto`, `mean_count_reviewed`, `n_subsamples`.

Run folder adds `subsamples/<subsample_id>/still.jpg`, `diff.jpg`, `context.mp4`, cut from originals. Stills use the exact timestamp. The context clip covers plus or minus `context_s`. MeanCount only needs dense processing in these context windows, so a quick pass over them comes first and the full-window scan after it, as a separate stage.

New append-only `subsample_reviews.jsonl`: `{"subsample_id","counter","pass":"primary|qc_blind|recount","total_fish_count":0,"invertebrate_count":0,"species_counts":{"name":0},"unknown_count":0,"total_species":0,"visibility_category":null,"visibility_change":null,"characteristics":[],"notes":"","at":"ISO8601","model_version":null,"contrast_settings":{}}`. New `recording_notes.jsonl` for species observed in the window, juveniles 1 or 0, window times, and visibility category per observer.

Review screen: still; context loop with 0.25x, 0.5x and 1x speed buttons and frame stepping; difference toggle; contrast sliders; fields for fish, invertebrates, per-species counts, unknown count, visibility and notes; a four-item characteristics checklist with a warning, not a block, when fewer than two are ticked; suggested counts from the model shown as suggestions, never prefilled as final. "Movement, unidentified" is a note and is not counted, matching their rule. The grid overlay stays as an optional tool, since the protocol doesn't mention one.

QC mode: picks the random sample, hides the first count and any model suggestion, records the second counter, computes difference, and flags recounts. Export: one row per subsample matching their column names, plus a per-video summary with MeanCount and species list. `evaluate` also compares model counts to subsample rows from their spreadsheets (video ID, timestamp, total fish count), since hand counts are frame-level labels.

Wording: counts are a relative index. Don't state the tool meets their QC thresholds.

# Addendum 2: what the subsample photos show (read 5 Nov). Overrides earlier text where they differ.
Source: `../Sept 10 & 9th sub-samples/` (28 PNG screenshots, about 1918x1078; don't modify them; `Subsample Photos.zip` is the same set). Filenames hold transect, STAT, date and timestamp, for example `T2_STAT 2_Sept 10_count@ 14min.png`.

Observed by the orchestrator:
- Stationary camera, a measuring pole in frame, seabed with rock or sand. The 2 m pole is already in these videos.
- **Grid is how they count schools.** A grid about 5.4 columns by 3 rows is laid over the frame, with one dot per fish and a total written in each cell. `T1-STAT 2_Sept 10 _count @ 22min_enhanced.png` has black dots with handwritten totals reading about 13, 25, 12, 7, 14, 10, 3, 8, 8, 2 (about 102). `T2_STAT 2_Sept 10_count@ 14min.png` has red dots with typed 30, 9, 7 (46) and red ellipses around crabs. Handwriting readings need checking.
- Other frames have only red ellipses around individual animals, some of them large, camouflaged crabs on the bottom.
- `_marked green crab` and `_no enhancements_marks` are the same moment, marked and unmarked. `_enhanced` versions had strong contrast and colour shifts in an image editor.
- Screenshots contain VLC control bars showing time and total length (for example 14:00/36:40, 22:00/35:47), so these recordings are about 36 minutes.
- Annotations and overlays must never go into training images as is, or a model learns red circles and control bars. When videos arrive, clean frames can be pulled at the same timestamps.

Two separate detection problems: small schooling fish in midwater (around 30 px long, many per frame) and large camouflaged benthic animals. A box detector may struggle with the first. Layer 1 needs room for tiled detection or point-based counting there, and motion plus a detector for the second.

## Changes
**App:** add a point tool on the still: click to place a dot on each animal, choose fish or invertebrate and optional species, undo, zoom and pan, grid totals per cell updating live, and the frame total feeding the count fields. Add an ellipse or box tool for larger animals. Save to append-only `point_labels.jsonl`: `{"subsample_id","time_s","x","y","kind":"fish|invertebrate","species":null,"counter","at"}`, coordinates in original pixels. Grid default 6 columns by 3 rows, configurable. This is the main counting tool for schools and it creates training labels as a by-product. Add a contrast preset that imitates their enhancement, display-only.

**Pipeline:** `auto` may carry `points: [[x,y,score]]` as well as detections, and a count may come from a point or density backend, so add a `CountingModel` stage slot alongside Detector, with a stub. Add a config option for tiled inference. Add `tools/extract_annotations.py`: reads a folder of marked screenshots, parses transect, STAT, date and time from filenames, detects red dots, black dots, red ellipses and grid lines with OpenCV, and writes `labels/annotations.json` with points, ellipses, and which image and detector each came from. Mask the player bar region. Report counts per grid cell so they can be compared to the written totals. Label these as extracted weak labels that need human checking. Export COCO-style keypoints or a simple CSV for training. A summary table per image goes to `labels/extraction_report.csv`.

# Addendum 3: label page and review app changes (6 Nov). Overrides earlier text where they differ.
- **Review app:** model suggestions (boxes and the Suggested counts numbers) are hidden by default. One visible toggle, "Show model suggestions", sits in "Mark what you see" in the simple view and replaces the old Detection boxes control. It resets to off whenever a run loads and is never stored. Off: no boxes, and the Suggested counts panel shows a one-line note. On: boxes and numbers with the caution "Rough suggestions. The model flags seafloor and the pipe, and isn't trained on this water." QC mode keeps suggestions hidden and the toggle disabled.
- **Label points** may carry an optional `species` string (cleaned text, at most 80 characters). Right-click a dot for: change kind, set or clear species (type-ahead over `species_list.json`, free text allowed), remove. Undo covers every edit.
- **Label views.** Each label has `views`: the views used on the frame, a subset of `frame`, `movement`, `clip`, stored in a fixed order (D1 column `views_json`, migration 003). `pull_labels.py` writes it to points.csv (`views_used`), agreement.csv (`views_a`, `views_b`), the COCO file (`views_by`) and the summary. Labels saved before this have no views recorded.
- **Movement view** on the label page: `label_sets/<set>/diff/<frame_id>.jpg`, 1920 wide, the absolute difference between the frame and the median of 7 frames across the 10 s around it (same function as the review app). `diff_url` is in the manifest. It shares the zoom and pan plane with the frame and clip, so coordinates always refer to the original frame.
- **Clips** follow Coastal Action's protocol: 5 s before to 5 s after the frame, 10 s, 1920 wide, H.264, CRF about 24, faststart, no audio, each under 25 MiB. The label page plays the clip in the frame pane (hold Space or toggle Motion), loops it, offers 1x, 0.5x and 0.25x, marks the one second around the frame's moment as "Count frame", shows time relative to it, and does not allow dots while it plays. The review app does the same on its still (hold Space, count second highlighted). On both pages a Restart each time toggle (R) chooses between starting the clip from the top and carrying on from where it stopped, and the count second is centred on the count point.
