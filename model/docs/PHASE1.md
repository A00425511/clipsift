# ClipSift Phase 1: setup, data prep, baseline, smoke test (6 Nov 2026)

Everything below came from a run or a file in this folder. Smoke-test scores mean nothing.
No Coastal frame, Puget test result, Tweed image or team label was used for training or tuning.

## Environment
- `.venv` here, Python 3.14.6 (base interpreter is /opt/anaconda3's; it is the only Python on the machine, no 3.11-3.13 and no uv). `rfdetr[train]==1.11.2`, torch 2.15.0, pytorch-lightning 2.6.6, all from PyPI. clipsift/.venv untouched.
- rfdetr 1.11.2 trains fine on 3.14 + MPS (smoke test below). rfdetr has no max-steps option; the smoke script caps one epoch with Lightning `limit_train_batches`.
- Run everything as `cd "Model Training"; .venv/bin/python <script>` (use `caffeinate -i` for long runs).

## Tile decision (512 px, native scale, overlap 0.25, no rescale)
Puget frames are 1920x1080 (all of them). Box size = sqrt(w*h) in px, p10 / median / p90, from the split JSONs:
| | fish | crab |
|---|---|---|
| train | 36 / 60 / 128 | 60 / 127 / 205 |
| val | 54 / 101 / 164 | 91 / 116 / 152 |

Coastal fish size is not given directly: the verified file has 103 dots, no boxes, and in the clean frame the fish are barely visible (I looked at the frame and at 8x crops around dots; dots were hand-placed on an enhanced screenshot). Two indirect estimates, both rough:
- CFD Nano boxes on that frame (512 tiles, merged, thr 0.05, 132 boxes): sqrt-area p10/50/90 = 35 / 72 / 133 px. At thr 0.2 (16 boxes) median 88.
- Local contrast blobs at 62 of the 103 dots: max dimension p10/50/90 = 7 / 27 / 48 px (crude; the other 41 dots had no blob).

So Coastal animals are roughly 30-90 px at 4K, the same band as Puget (36-128 px at 1080p). A rescale would make the match worse, not better. Kept the deployed geometry: 512 px tiles from `tile_boxes(w, h, 512, 0.25)` (15 tiles per Puget frame: 5 x 3), fed to the model at 640 (rfdetr resizes, same as the Coastal pipeline). Caveat: Coastal fish are much fainter/softer than most Puget fish; size matches, appearance does not.

## Tiled set: `tiles/puget_v1/` (train/, valid/, each with `_annotations.coco.json`; classes fish=0, crab=1)
Command: `.venv/bin/python prep_tiles.py` (log `logs/prep.log`, stats `tiles/puget_v1/prep_stats.json`). Seed 20261106. 1.6 GB.
| | train | val |
|---|---|---|
| images | 17,260 | 1,737 |
| grid tiles | 258,900 | 26,055 |
| dropped: overlap an ignore box (fish_or_crab / unknown, >= 16 px2) | 6,216 | 1,044 |
| slivers dropped (< 30% of box area in tile) | 15,669 | 1,174 |
| boxes clipped to tile edge | 28,815 | 2,112 |
| positive tiles (>= 1 fish/crab box) | 59,829 | 4,682 |
| empty tiles kept (25% of set, equal quota per site, spill to others) | 19,943 | 1,561 |
| **tiles in set** | **79,772** | **6,243** |
| fish / crab box instances | 86,467 / 3,919 | 4,224 / 1,065 |
| gray-world white-balanced tiles | 25,943 (5,533 frames) | 6,060 (1,526 frames) |

Notes:
- Box instances exceed source boxes because 25% overlap puts a box in up to 4 tiles. Tile-level scoring has the same property.
- Train positives are 76% from one site (loc_bc90692b, 45,396 tiles). Two sites have almost none (loc_bc9ddc8c 181, loc_bcb89731 102). Empties are spread across sites as far as each has them; loc_bcb89731 only had 543 available. Subsample positives per site before a long run if site balance matters.
- Ignore regions are never deleted from the source; tiles touching them are just left out. The `unknown` boxes include some huge ones (median 506 px in train), which is part of why 6.2k tiles went.
- Dropped slivers leave a partly visible animal unlabelled in that tile (up to 30% inside).
- puget_test: not prepped, not looked at. No Tweed.
- White balance: the `filter=True` cast in these frames is mostly red/orange rather than magenta. Per-frame gray-world (scale B,G,R so channel means are equal, gains clipped 0.4-4.0), applied before tiling, to all filter=True frames. Mean gains (B,G,R): train 1.03/1.04/0.96, val 1.14/1.17/0.82. Already-neutral filter frames barely change. Not applied to anything else, and not applied at Coastal inference (no cast there).
- Examples: `examples/wb_before_after_val.jpg`, `examples/wb_before_after_val2.jpg` (left raw, right balanced, boxes drawn; green = fish, magenta = crab). I opened both: boxes sit on the same animals, red tiles become grey-green. `.venv/bin/python make_examples.py` regenerates them.

## Baseline: CFD Nano (unmodified) on tiled Puget val, no training
`.venv/bin/python eval_tiled.py --ckpt ../clipsift/models/cfd-rf-detr-nano-640-2026.02.02.cp-011.20260706-release.pth --name cfd_nano_baseline --batch 16 --reuse-cache`
6,243 tiles, 31 tiles/s on MPS. Fish n_gt = 4,224. Crab: n/a (one-class model). Threshold chosen on val = 0.29 (max F1 at IoU 0.5), saved in `eval_out/cfd_nano_baseline/threshold.json`.
| IoU | AP | precision @0.29 | recall @0.29 |
|---|---|---|---|
| 0.3 | 0.458 | 0.628 | 0.422 |
| 0.5 | 0.422 | 0.599 | 0.402 |

Scoring rules (`eval_tiled.py` docstring): per tile and class greedy one-to-one match by score, AP = all-point interpolated PR area pooled over tiles. Tile-level, not frame-level. Crab GT is not counted for the one-class model, and CFD boxes on crabs count as fish false positives. Any checkpoint: `eval_tiled.py --ckpt X --name N` picks and saves its own val threshold per class; `--threshold-file` reuses a saved one on another split. Val is one site, 94% filtered: a hard, narrow check.

## Coastal check (dev only, one frame, never train on it)
`.venv/bin/python eval_coastal.py --ckpt <ckpt> --name N --threshold-file eval_out/N/threshold.json`
Tiles with `cfd.tile_boxes` (512, 0.25), merges with `merge_boxes` (0.5), scores with `tools/eval_detector.py score_frames` imported read-only (same matching and chance baseline). Takes the Puget-val threshold; scores only that one threshold, no sweep. 2-class checkpoints: fish class only.
Unmodified CFD Nano at 0.29: 7 boxes vs 103 dots, recall 0.04, precision 0.57 (chance 0.02 / 0.33). Strict identical. The Puget-val threshold is far too high for this frame (earlier test used 0.05); I did not retune.

## Team labels
`clipsift/.venv/bin/python tools/pull_labels.py` ran with the existing wrangler session, no login or prompt. Wrote only `labels/team/t1s2_v1/`. Frames labelled: 9. Frames with two labellers: 0. Marks by kind: fish 0, invertebrate 3, not_fish 245, unsure 0. Not used for anything.

## Smoke test (<= 100 optimiser steps; scores are meaningless)
Command: `.venv/bin/python smoke_train.py --start cfd|stock --steps 100 --batch 2 --res 640` (logs `logs/smoke_*.log`, per-step data `runs/<tag>/smoke_metrics.json`). Nano, resolution 640, num_classes=2 (fish, crab), EMA on, rfdetr defaults otherwise, device mps. Checkpoints: `runs/smoke_{cfd,stock}_b2_r640_mps/checkpoint_best_total.pth` (also `last_ema.pth`, `checkpoint_best_ema.pth`, `.ckpt`).

| | (a) CFD Nano + new 2-class head | (b) stock RF-DETR Nano |
|---|---|---|
| runs on MPS | yes | yes |
| batch 2 sec/step (median / mean of last 50) | 0.473 / 0.459 | 0.464 / 0.480 |
| train loss, mean of first 10 -> last 10 steps | 8.51 -> 4.91 | 6.39 -> 4.17 (noisy: peaked 8.8 mid-run) |
| MPS driver memory, max | 10.9 GB | 9.9 GB |
| checkpoint saves and reloads (`from_checkpoint`, weights_only) | yes | yes |
| eval_tiled.py scores it (first 600 val tiles; MEANINGLESS) | fish AP.5 0.39, crab 0.01 | fish AP.5 0.08, crab 0.00 |
| eval_coastal.py runs (MEANINGLESS) | yes | not run |
| projected hours per epoch, 79,772 tiles | 5.1 | 5.3 |

Projection = tiles x (sec/step / 2) for the mean-of-last-50 figure; excludes validation (about 3-4 min per val pass at 31 tiles/s plus EMA) and dataloader stalls. A 20k-tile subset is about 1.3 h per epoch.

Findings:
- Batch size: 2 fits. Batch 4 ran for an 8-step dry run (0.74-1.1 s/step) but the 100-step run stalled in swap (swap 9-10 GB, other apps open: Chrome, Claude) and I stopped it. MPS driver memory is about 10-11 GB at either batch size. For a long run: close other apps, or use batch 2 with `grad_accum_steps` 4-8. Batch 8 not tried. Unrelated to model code: it is memory pressure on a 24 GB machine.
- CFD checkpoint loads into the trainer. Inspected with `weights_only=True`: keys model/args/model_name/model_config/rfdetr_version, class_names ['fish'], 465 tensors, head is 1 output (rfdetr reads that as "0 classes"). Gotcha: without `num_classes=2` rfdetr keeps the checkpoint's class count and warns "Using the model's configured value (0)", i.e. it would NOT train a 2-class head. With `num_classes=2` the 29 head tensors are re-initialised (shape 3x256) and the other 436 are loaded (relative weight change after 8 steps median 0.0009, so they did load).
- Stock Nano is trained at 384 (pos-enc 24); at 640 rfdetr interpolates the position embeddings and trains normally. Head re-initialised from 90 classes.
- First step takes about 9-10 s (MPS warm-up).
- `smoke_train.py` needs its `__main__` guard: rfdetr's dataloader workers re-import the script (spawn).

## Stock weights provenance
- URL (rfdetr's own registry, `rfdetr/assets/model_weights.py`, RF_DETR_NANO): https://storage.googleapis.com/rfdetr/nano_coco/checkpoint_best_regular.pth
- Saved by rfdetr as `~/.roboflow/models/rf-detr-nano.pth`, 366,287,238 bytes.
- sha256 `d8d6b9ee57d4d0ed2b1f305163624712a0532cb7bce0c747317984fc5457440d`; md5 `fb6504cce7fbdc783f7a46991f07639f` matches the registry's expected hash.
- Licence: rfdetr package is Apache-2.0 (PyPI metadata). I did not find a separate licence file for the weights in the package; Roboflow documents the Nano/Small/Medium/Base models as Apache-2.0 but I did not verify that online. Check before shipping. No account or token was needed.
- The CFD weights were loaded from `clipsift/models/` (not downloaded).

## Files
`prep_tiles.py`, `make_examples.py`, `common.py`, `eval_tiled.py`, `eval_coastal.py`, `smoke_train.py`; `tiles/puget_v1/`, `eval_out/`, `runs/`, `logs/`, `examples/`.
