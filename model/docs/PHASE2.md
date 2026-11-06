# ClipSift Phase 2: balanced fine-tuning runs (finished 6 Nov 18:17)

Nothing here used Coastal frames, team labels or puget_test for training or tuning. No thresholds were chosen on Coastal data. Commands to regenerate the tables: `.venv/bin/python make_table.py` (reads eval_out/*/metrics_valid.json, threshold.json and coastal_snapshot.json).

## Contamination warning
CFD weights were trained on the Community Fish Detection Dataset, which includes Puget Sound Nearshore Fish. Every Puget-val number for untrained CFD AND for the CFD-start fine-tunes is CONTAMINATED (marked below). Only stock-start Puget-val scores are clean. CFD vs stock can only be compared on Coastal frames, and the Coastal verified frame is ONE dense school: a dev check, not accuracy.

## Setup
- Balanced train set `tiles/puget_v1/train_balanced/` (symlinks; trainer root `tiles/puget_bal_root/`; valid unchanged = 6,243 tiles). `make_balanced.py`, seed 20261106. 15,936 tiles: 3,904 crab-containing (all kept), 8,845 fish-only, 3,187 empty (20%). Fish-only cap per site 2,250 (lowered from 3,000 to respect the 16,000 ceiling). Boxes: fish 11,818, crab 3,919.
- Tiles per site: bca6b86b 4,551; bc90692b 3,445; bc8df6bd 3,188; bcbc68ad 3,104; bc9ddc8c 636; bcb89731 557; bcade628 455. Crab boxes per site: bca6b86b 1,859; bc8df6bd 889; bc90692b 739; bcbc68ad 399; bc9ddc8c 33; others 0. Fish boxes: bc90692b 3,651; bca6b86b 3,010; bcbc68ad 2,874; bc8df6bd 2,033; bc9ddc8c 148; bcb89731 102; bcade628 0. (tiles/puget_v1/train_balanced_stats.json)
- Training (`train_run.py`, launched by `nohup caffeinate -i ./run_phase2.sh`): Nano, res 640, batch 2, grad accum 4 (effective 8), 3 epochs (1,992 optimiser steps each), rfdetr default LRs (1e-4, encoder 1.5e-4, `step` scheduler with no drop inside 3 epochs, so effectively constant; no reason found to change), EMA on, num_classes=2, device mps. Per-epoch EMA weights: `runs/p2_{stock,cfd}/ema_epoch{1,2,3}.pth`; full `checkpoint_<n>.ckpt` for resume (resume tested in a dry run).
- Wall time: stock-start 11,487 s (3.19 h); CFD-start 14,660 s (4.07 h, includes 3 val passes; swap 7-9 GB with other apps open, which I was told not to stop). The CFD run went slightly over the 4 h per run line I had projected (3.6 h); I did not stop it.
- Eval: `eval_tiled.py` for Puget val (fish/crab AP at IoU 0.3 and 0.5, threshold chosen on val per checkpoint), `eval_coastal.py` for Coastal (one method for all models).

## Puget val (tile level, 6,243 tiles, one site). AP, rfdetr-trained checkpoints and untrained baselines
| model | fish AP.3 | fish AP.5 | crab AP.3 | crab AP.5 | val thr (fish) |
|---|---|---|---|---|---|
| untrained CFD Nano (CONTAMINATED) | 0.458 | 0.422 | n/a (1-class) | n/a | 0.29 |
| untrained stock Nano, COCO classes, any class = fish | 0.068 | 0.061 | n/a | n/a | 0.16 |
| stock-start epoch 1 (clean) | 0.642 | 0.603 | 0.650 | 0.612 | 0.28 |
| stock-start epoch 2 (clean) | 0.659 | 0.614 | 0.645 | 0.592 | 0.30 |
| stock-start epoch 3 (clean) | 0.669 | 0.628 | 0.646 | 0.592 | 0.35 |
| cfd-start epoch 1 (CONTAMINATED) | 0.685 | 0.640 | 0.638 | 0.583 | 0.27 |
| cfd-start epoch 2 (CONTAMINATED) | 0.698 | 0.652 | 0.644 | 0.600 | 0.28 |
| cfd-start epoch 3 (CONTAMINATED) | 0.655 | 0.619 | 0.564 | 0.525 | 0.28 |

## Coastal checks, frozen label snapshot
Verified frame: 103 dots. "Puget-val thr" row = the threshold from the table above, no retuning. top-K = top K boxes by score (after merge, fish class only for 2-class models; the K budget is applied before the labelled-area filter, so slightly fewer may be scored). Cells are recall / precision (chance recall / precision from tools/eval_detector.py).
Team frames: label snapshot `label_snapshot_20261106/points.csv`, sha256 `d632b561415eb0211d89a1a78694c62110e99e8e62e645a8531e727a2fd3c989` (17 frames; 201 not_fish, 9 invertebrate, 457 fish, 139 unsure marks; fish and unsure marks are not used by this check). The share is not_fish marks that fall inside one of the top 50 boxes of that frame (lower is better). Invertebrate hit = mark inside a top-50 box; for 2-class models only fish-class boxes are counted, so crab-like invertebrates are not expected to be hit.
| model | @Puget-val thr: boxes, R / P | top25 | top50 | top100 | top200 | not_fish in box | invert. hit |
|---|---|---|---|---|---|---|---|
| untrained CFD Nano | 7: 0.04/0.57 (0.02/0.33) | 0.15/0.79 (0.06/0.30) | 0.24/0.74 (0.09/0.29) | 0.37/0.66 (0.15/0.26) | 0.59/0.54 (0.27/0.25) | 85/201 = 0.42 | 7/9 |
| untrained stock Nano (any class) | 6: 0.01/0.17 (0.02/0.27) | 0.05/0.26 (0.04/0.24) | 0.12/0.29 (0.09/0.23) | 0.19/0.23 (0.18/0.22) | 0.30/0.20 (0.32/0.21) | 102/201 = 0.51 | 6/9 |
| stock-start ep 1 | 27: 0.18/0.70 (0.07/0.27) | 0.12/0.71 (0.05/0.29) | 0.24/0.69 (0.09/0.27) | 0.42/0.61 (0.18/0.26) | 0.57/0.50 (0.27/0.24) | 85/201 = 0.42 | 1/9 |
| stock-start ep 2 | 16: 0.09/0.56 (0.05/0.30) | 0.10/0.59 (0.04/0.25) | 0.17/0.50 (0.09/0.26) | 0.36/0.52 (0.16/0.24) | 0.58/0.46 (0.27/0.21) | 81/201 = 0.40 | 3/9 |
| stock-start ep 3 | 12: 0.07/0.58 (0.03/0.27) | 0.12/0.57 (0.05/0.26) | 0.20/0.55 (0.10/0.26) | 0.37/0.51 (0.18/0.25) | 0.57/0.42 (0.31/0.23) | 73/201 = 0.36 | 1/9 |
| cfd-start ep 1 | 13: 0.11/0.85 (0.04/0.33) | 0.18/0.90 (0.07/0.34) | 0.31/0.76 (0.13/0.32) | 0.42/0.58 (0.21/0.29) | 0.60/0.49 (0.32/0.26) | 79/201 = 0.39 | 4/9 |
| cfd-start ep 2 | 14: 0.13/0.93 (0.05/0.34) | 0.15/0.79 (0.06/0.30) | 0.25/0.68 (0.11/0.30) | 0.41/0.62 (0.18/0.28) | 0.56/0.45 (0.29/0.23) | 71/201 = 0.35 | 2/9 |
| cfd-start ep 3 | 13: 0.11/0.85 (0.05/0.37) | 0.15/0.79 (0.06/0.32) | 0.23/0.71 (0.10/0.32) | 0.39/0.62 (0.18/0.28) | 0.54/0.47 (0.30/0.26) | 74/201 = 0.37 | 2/9 |
Per-category not_fish in box (snapshot): untrained CFD algae 6/24, bubbles 11/19, equipment 12/70, other 14/19, seabed 42/69; stock-start ep3 11/24, 8/19, 10/70, 9/19, 35/69; cfd-start ep3 9/24, 11/19, 6/70, 17/19, 31/69. Full per-model JSON: `eval_out/<name>/coastal_snapshot.json`.

## Why the denominators differed (item 1)
The team label set was still being labelled and the export was re-pulled during the day; not by me after my first pull (I ran `pull_labels.py` once, about 09:55). `clipsift/labels/team/t1s2_v1/` was last rewritten at 17:18:42 (all eight files share that mtime; `points.csv` updated_at stamps run 12:12Z-19:56Z). My first pull had 9 frames, 245 not_fish, 3 invertebrate, 0 fish. The stock-start evals (about 14:00) read 251 / 5, the cfd-start and re-run evals (after 17:18) read 201 / 9. The current file has 17 frames: new frames were labelled (including fish marks on frames at t=1300-1344 s, near the verified frame at 1320 s), and some existing frames were relabelled (e.g. frame t01220 went from 27 marks to 2 and t01460 from 29 to 5, with not_fish marks removed or turned into unsure/invertebrate). I only know the file contents at three points in time; I cannot say who re-pulled it or exactly when before 17:18. No labeller names were read into any output; the labeller column is never loaded by eval_coastal.py.
The old per-model team results for the untrained and stock-start rows (245/3 and 251/5) are superseded by the snapshot table above and should not be compared with it.

## What I changed, and one mistake (items 2 and 3)
- Added `--team-csv` and `--out-name` to eval_coastal.py (default behaviour unchanged). Snapshot results go to `eval_out/<name>/coastal_snapshot.json`; `rerun_snapshot.sh` re-ran all 8 models on the snapshot (inference only, same Puget-val thresholds).
- Mistake: before I received the freeze instruction I had started a re-run on the live labels file and it overwrote `eval_out/{cfd_nano_baseline,stock_untrained,p2_stock_ep1,p2_stock_ep2,p2_stock_ep3}/coastal.json` (five files, not six) with results on the 17-frame live file. The cfd-start `coastal.json` files were not touched. I stopped that run and copied all eight files as found to `old_results/` before re-running, but the original 245/3 and 251/5 outputs for those five are lost as files; their numbers survive only in my earlier report text. Note the 8 snapshot files and the 5 overwritten `coastal.json` agree exactly because the live file did not change after 17:18.
- Verified-frame check (item 3): for all 8 models, the verified-frame rows (Puget-val threshold row and top 25/50/100/200, recall, precision, strict, chance) are identical before and after the re-run. For the 3 cfd-start models this is a file-level comparison against the untouched original outputs; for the other 5 it compares against the numbers I printed in the first table at two-decimal precision plus the overwritten file (same code, same frame). No difference found. Inference is deterministic here, as expected.

## cfd-start epoch 3 drop on Puget val (item 4)
Fact: rfdetr's own val (EMA) goes mAP50 0.607, 0.622, 0.573 over epochs 1-3 and recall 0.533, 0.582, 0.507 with precision flat (0.737, 0.720, 0.735); my eval_tiled fish AP.5 0.640, 0.652, 0.619 and crab AP.5 0.583, 0.600, 0.525. The stock-start run moves only +-0.015 between epochs (mAP50 0.602, 0.599, 0.611).
Logs: no NaN or non-finite loss in either run. Mean per-micro-batch train loss by epoch (logged every 20 batches, /accum scaling, noisy): cfd-start 1.156, 1.064, 0.954 (falling; last quarter of epoch 3 1.008 vs 0.924 in the third quarter; last quarter of epoch 2 1.178 vs 1.056); stock-start 1.206, 1.063, 1.025. Single-batch spikes: cfd-start up to 8.46 (epoch 2) and 8.71 (epoch 3); stock-start max 5.44. LR was constant.
Reading: not a crash or divergence, and training loss kept falling, so there is no sign of a broken run. But the drop is a recall loss about 3-5x larger than the stock run's epoch-to-epoch wobble, the CFD run had large loss spikes in both late epochs, and crab AP is measured on only 1,065 val boxes from one site. I cannot tell real instability (constant LR, lr 1e-4 on a model that already starts close to a solution, EMA) from noise on one val site, with one seed. Treat epoch 3 of the CFD run as unreliable; do not use it. Not retrained.

## Recommendation (item 5)
Evidence rules: Puget val is only a fair guide for the stock-start run (clean). Coastal is one frame of one dense school (plus a not_fish false-alarm check on 17 frames), so it is dev evidence only.
1. Checkpoint to use next as the base: `runs/p2_stock/ema_epoch3.pth` (stock-start epoch 3). It is the only candidate with clean validation support: fish AP.5 rose each epoch (0.603, 0.614, 0.628), crab AP.5 stayed 0.59-0.61, and its not_fish false-alarm share was the lowest of the stock epochs (0.36 vs 0.42 and 0.40). CFD-start Puget scores cannot select anything because of contamination.
2. Plainly: neither start has been shown to beat the untrained CFD Nano on Coastal. At top 100 boxes untrained CFD is 0.37/0.66, the best trained rows are 0.42/0.61 (stock ep1) and 0.42/0.58 (cfd ep1), with 0.37/0.51 for stock ep3 and 0.39/0.62 for cfd ep3. That difference is inside what I would expect from one frame and a few percent. At top 25 the CFD-start and untrained CFD have higher precision (0.79-0.90) than stock-start (0.57-0.71). False-alarm share barely moves (0.35-0.42 for CFD models, 0.51 untrained stock). Keep untrained CFD (with a top-K budget, not the Puget-val threshold) as the fallback detector. The trained models do add a crab class and are much better than untrained stock, but that is the Puget task, not Coastal.
3. The Puget-val thresholds (0.27-0.35) are far too high for Coastal: only 6-27 boxes against 103 dots. Use a fixed box budget or a Coastal-style score calibration rather than a Puget threshold when running on Coastal.

## What the next run should change
- Evaluation: use the frozen snapshot, and treat the dense-school team frames (fish marks on t01300, t01332, t01340, t01344) as an eval-only set so Coastal evidence is more than one frame. Do not train on them.
- Fix noise: run at least 2 seeds or evaluate every half epoch; the CFD epoch-3 drop cannot be explained from one run.
- LR: add decay for the last epoch or lower the encoder LR (CFD start especially), and train longer (stock fish AP was still rising at epoch 3) with val tracked per epoch.
- Domain gap: Coastal fish are far fainter than most Puget fish. Add haze/contrast/low-light augmentation, or weight the low-visibility Puget sites more, since the Puget-val threshold gives almost no boxes on Coastal.
- Data: only 3 sites carry crabs in any number, and the unlabelled crabs in Puget are under-labelled; do not read the crab AP as reliable. Keep per-site balance but consider fewer fish-only tiles from the two sites that dominate.

## What I could not confirm
- Who rewrote the team labels file and when before 17:18, and how the 245/3 and 251/5 files differed in detail (I only have counts).
- Whether the cfd-start epoch 3 drop is real or noise.
- Whether the Apache-2.0 licence applies to the stock weights themselves (carried over from phase 1).
- The original 245/3 and 251/5 team-frame outputs as files for five models (overwritten by my mistake; see above).
