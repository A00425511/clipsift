# Static-object filter test, 6 Nov 2026

Filter: `clipsift/static_filter.py`, run after detection. Scored with `clipsift/tools/eval_static_filter.py` (reproducible: `detect` once, then `report`). Detector: Nano, 512 tiles, threshold 0.05 for detection, 0.05 and 0.1 reported. Run on Jacob's M4 Pro, about 5 s per frame for detection and 3 s for movement scoring.

**Read this as a small, tuned-on-itself sample.** One recording (T1-STAT2 411), one site, one camera position, one labelled dense-school frame, and seven empty-frame labels from one person (faint fish could be missed). Defaults were set from two frames before this test, and the numbers below are on frames that were already looked at. Nothing here is accuracy.

## What it does
1. **Persistence.** A box that recurs at nearly the same place and size (IoU 0.5) in at least 30% of the sampled frames of a recording is static. Frames with no boxes count in the denominator. Needs 6 or more frames, otherwise skipped with a log note. No hand work, and a moved camera adapts.
2. **Movement.** Score = 90th percentile of absolute grey-level difference inside the box, at 1920 wide, blur sigma 1.5, against the median of frames from t-5 s to t+5 s (one per second, never the frame itself). Below 3 = static. Not scored (box kept) when fewer than 3 background frames exist.
3. **Hand mask.** `static_filter.masks`: polygons in original pixels, per camera or recording (`match` is fnmatch on the recording id or file name), or a JSON file from `tools/make_static_mask.py`. A box is masked if its centre, or half its area, is inside.
Bias to keeping: boxes scoring 0.5 or higher are never rejected by checks 1 and 2; a persistent place is kept if the box itself clearly moves (movement 8 or more). Rejected boxes stay in results.json with `static: true`, `static_reason` (`persistent`, `no_movement`, `mask`, joined with +) and `movement`, are not counted in `fish_count`, status, review order or the CSV `n_detections`, and `eval_detector.py --run` leaves them out unless `--include-static`.

**It can remove truly still animals** (a resting crab, a hovering fish, a school sitting in one place for a third of the recording), and the model only finds fish anyway, so crabs are not seen either way. A unit test documents the crab case.

## Settings tried
Defaults (share 0.30, IoU 0.5, movement 3, protect 0.5) were chosen before the full run; share 0.30 and movement 3 came from the earlier two-frame test. The sweep below is sensitivity, not a search. I did not change the defaults after seeing it.

| Persistence share | Persistence | Movement cutoff | Labelled frame, thr 0.1: strict R / P | Boxes left on the 7 empty frames, thr 0.1 | Boxes left on all 100 frames, thr 0.1 |
|---|---|---|---|---|---|
| 0.30 (default) | on | 3 | 0.23 / 0.73 (24 hits, 33 boxes) | 79 | 1424 |
| 0.20 | on | 3 | 0.23 / 0.73 | 74 | 1328 |
| 0.50 | on | 3 | 0.23 / 0.73 | 84 | 1553 |
| 0.30 | on | off | 0.23 / 0.73 | 119 | 2137 |
| off | off | 3 | 0.23 / 0.69 (24 hits, 35 boxes) | 98 | 1755 |
| off | off | 2 | 0.23 / 0.69 | 139 | 2293 |
| off | off | 4 | 0.20 / 0.68 (21 hits) | 76 | 1284 |
| off | off | 5 | 0.14 / 0.74 (14 hits) | 62 | 990 |
| 0.30 | on | 5 | 0.14 / 0.74 (14 hits) | 53 | 892 |

Movement 5 cut empty-frame boxes further but lost 10 of the 24 dot hits, so real fish are faint, as the earlier test found. 3 stays.

## Labelled frame, 22:00.3 (103 dots), strict matching, "chance" = same boxes placed at random, "shifted" = real boxes moved 150 to 400 px (40 tries, mean and range of hits)
Persistence learned from the 100 grid frames plus this one. Only boxes above the lowest dot plus 80 px are scored, as in `controls.py`.

| Threshold | | Boxes | Hits | Recall | Precision | Chance hits | Shifted hits |
|---|---|---|---|---|---|---|---|
| 0.05 | before | 73 | 42 | 0.41 | 0.58 | 9.6 | 8.9 (1 to 15) |
| 0.05 | after | 68 | 41 | 0.40 | 0.60 | 9.9 | 8.2 (0 to 16) |
| 0.1 | before | 35 | 24 | 0.23 | 0.69 | 4.5 | 5.2 (0 to 10) |
| 0.1 | after | 33 | 24 | 0.23 | 0.73 | 5.0 | 4.9 (0 to 10) |

Both stay far above chance and above the shifted control, so the matches survive the filter. It lost one hit at 0.05 (a box that moved little). Over the whole frame it removed 14 boxes at 0.05 and 7 at 0.1, mostly seabed and pipe. With persistence learned from only 15 frames spaced 60 s apart (a pipeline-sized pool): 0.05 gives 41 hits, 67 boxes; 0.1 gives 24 hits, 32 boxes.

Why recall barely moves: this frame's boxes are mostly in the school, and the filter targets the seabed, so it mainly improves the boxes-per-frame picture below, not this frame's score.

## 100 frames (every 20 s, 60 to 2040 s), whole frame, defaults
| Threshold | Mean boxes per frame | Median | Total |
|---|---|---|---|
| 0.05, before | 92.7 | 96 | 9265 |
| 0.05, after | 42.6 | 38 | 4260 (54% marked static) |
| 0.1, before | 28.8 | 28 | 2880 |
| 0.1, after | 14.2 | 12 | 1424 (51% marked static) |

Fewest remaining at 0.1 (time, before to after): 540 s (15 to 0), 600 s (10 to 0), 620 s (15 to 0), 580 s (15 to 1), 900 s (20 to 1), 220 s (11 to 2), 360 s (13 to 2), 500 s (21 to 2), 560 s (17 to 2), 320 s (10 to 3).
Most remaining at 0.1: 720 s (55 to 51), 1320 s (60 to 48), 1100 s (50 to 38), 700 s (45 to 38), 1160 s (52 to 37), 1340 s (52 to 35), 1480 s (44 to 34), 1080 s (45 to 33), 1660 s (42 to 32), 1440 s (39 to 32).
Per-frame counts for all frames are in `frame_boxes.json` (same folder, keyed by frame id with `time_s`; `raw_005`, `after_005`, `raw_01`, `after_01`). I did not check which of the "most remaining" frames hold real fish; some are probably the school and some may be leftover seabed.

## Empty-frame checks (Jacob: no fish at these times)
| Time | Thr 0.05, before to after | Thr 0.1, before to after |
|---|---|---|
| 140 s | 78 to 14 | 21 to 4 |
| 160 s | 73 to 20 | 23 to 10 |
| 900 s | 97 to 8 | 20 to 1 |
| 1220 s | 102 to 76 | 31 to 21 |
| 1240 s | 112 to 86 | 28 to 23 |
| 1500 s | 102 to 24 | 26 to 6 |
| 1560 s | 69 to 32 | 20 to 14 |
| Total | 633 to 260 | 169 to 79 |

The filter helps a lot on five frames and little on 1220 s and 1240 s. On those two, boxes sit on the same pipe, pole tip and rocks as before, but movement scores are high (median 5.5 and 7.0 grey levels, against about 2.3 on the clean frames), which looks like camera sway or water surge or changing light moving the whole scene. Boxes then shift a few pixels between frames, so persistence misses them too. I looked at 1220 s by eye: the remaining boxes are mostly on the pipe, seabed and a few possible small objects. Not fixed. A fix to try next (not done, to avoid tuning on these frames): align each frame to its background before differencing, or subtract a per-frame global movement baseline. A hand mask over the pole and pipe would also catch these, which is what the mask is for. Remaining boxes on "empty" frames could also be fish Jacob missed.

## Not validated
- One recording, one camera position, one dense-school frame. Other sites, crabs, low visibility: untested.
- The pool here is 100 frames, more than a pipeline run (about 15 subsample stills at 60 s plus a few segment frames). The 15-frame check above is the closer match and gave the same labelled-frame result.
- The full pipeline path (`pipeline.run` with a real model) was tested only with fake detections and a synthetic clip. The evaluation script calls the same functions on real frames.
- Persistence assumes the camera is fixed within a recording. A school that stays put for a third of the sampled frames would be flagged.
- Frames at 20 s spacing for the pool; the label set manifest also held extra frames added later, which were left out of the pool.
