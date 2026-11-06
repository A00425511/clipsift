# Train / val / test splits (6 Nov 2026)

**Read this first.** These splits are for **training and development checks only**. They tell us whether the model is learning and whether it overfits to a site. They are NOT our final test. The real final test must be **Coastal Action's own labelled frames, kept out of training entirely**. Never train on them, never tune on them.

- Random seed: **20261106** (fixed in `data/tools/make_splits.py` and recorded in every JSON's `info`).
- Re-run (not needed by teammates; it is the record of how the splits were made): `python3 -I data/tools/make_splits.py "path/to/Footage Sources"`. It only reads metadata JSON/CSV and rewrites the six JSON files in that folder's `splits/`; it never copies or opens images. In this repo the six files are stored gzipped as `data/splits/*.json.gz` and `data/tools/fetch_datasets.py` unpacks them.
- Format: COCO JSON (`images`, `annotations`, `categories`). `bbox` = [x, y, w, h] in pixels. Integer ids were re-numbered; the original id is kept as `orig_id`.
- No images are copied. Each file has a top-level `image_root` (relative to `Footage Sources/`), and each image's `file_name` is relative to that folder:
  - Puget: `Puget Sound LILA/images`
  - Tweed: `Tweed Estuary/images`
- All numbers below were counted from the output JSON files. Every listed image exists on disk.

## Puget Sound (from `subset_low_medium_vis.json`, 21,623 images)

Split by **whole site** (`location`, 10 sites), so no site appears in two splits. The `location` field is not the same as the SD## prefix in file names (one location spans many SD prefixes), so we split on `location`, the stricter key.

- **Test (2 sites):** `loc_bccc994d` and `loc_bcc8a0b0`
- **Val (1 site):** `loc_bcbd2c38`
- **Train (7 sites):** `loc_bc8df6bd`, `loc_bc90692b`, `loc_bc9ddc8c`, `loc_bca6b86b`, `loc_bcade628`, `loc_bcb89731`, `loc_bcbc68ad`

Why these: I tabulated every site's crab boxes, low-visibility frames and filter share, then picked the sites so val and test both have a real crab and low-visibility share. The biggest site (`loc_bc90692b`, 10,276 images) has to stay in train. Two of the three sites with the most low-vis crab frames went to test (`loc_bcc8a0b0` is 100% low-visibility, 526 crab boxes). The test pair has a mixed filter share (58%), the val site is mostly filter (94%).

| | Train | Val | Test |
|---|---|---|---|
| Sites | 7 | 1 | 2 |
| Images | 17,260 (79.8%) | 1,737 (8.0%) | 2,626 (12.1%) |
| Images with no boxes (empties kept) | 1,536 | 150 | 546 |
| fish boxes | 39,412 | 1,700 | 1,448 |
| crab boxes | 1,712 | 428 | 687 |
| fish_or_crab boxes | 2,922 | 411 | 96 |
| unknown boxes | 387 | 43 | 24 |
| Total boxes | 44,433 | 2,582 | 2,255 |
| Low visibility images | 4,424 (25.6%) | 1,636 (94.2%) | 1,923 (73.2%) |
| Medium visibility images | 12,836 | 101 | 703 |
| `filter` (magenta cast) images | 6,014 (34.8%) | 1,636 (94.2%) | 1,517 (57.8%) |

Caveats: val is almost all low-visibility and magenta-filtered, so it is a hard, narrow check. The train set is only 25.6% low-visibility and 34.8% magenta, so train and val differ in look. Test has far fewer fish boxes per image than train because it is crab-heavy.

Files: `puget_train.json`, `puget_val.json`, `puget_test.json`. Original 5 classes kept (`empty`=0 is in the category list but has no boxes; empty frames are just images with no annotations).

### Recommendation for `fish_or_crab` and `unknown`
Do not drop these boxes, but **treat them as ignore regions** (matching our Unsure rule), not as background. Training on them as background teaches the model that real animals are empty. In practice: mask or skip loss in those boxes, or exclude predictions that overlap them from scoring. Also note the source labelling was image-level, so classes are noisy, and crabs are under-labelled at sediment/eelgrass sites.

## Tweed / Tallebudgera (4,280 images, 138 clips)

The published train/test/novel_test split is **ignored**: clip `2205_Luderick_25.mov` appears in both train and test there. Instead, images are grouped by **deployment + date** (18 groups from `dataset_images.csv`; deployment number alone repeats across datasets). A **clip** is the file name stem before the frame number. Every clip falls in exactly one deployment+date group (checked), so every one of the 138 clips sits in exactly one split (checked: 0 clips in more than one split).

Groups were assigned by a seeded random search (200,000 draws) that picks the assignment closest to 70/15/15 by images, with a rule that val and test each keep at least 15 bream boxes.

| | Train | Val | Test |
|---|---|---|---|
| Images | 2,994 (70.0%) | 643 (15.0%) | 643 (15.0%) |
| Clips | 80 | 37 | 21 |
| luderick boxes | 6,637 | 1,066 | 1,601 |
| bream boxes | 83 | 25 | 17 |
| Total boxes | 6,720 | 1,091 | 1,618 |
| Deployment+date groups | 8 | 6 | 4 |

- Train: 11 (5/04/2019), 14 (21/05/2019), 15 (22/05/2019), 16 (18/06/2019), 18 (10/07/2019), 3 (23/03/2019), 6 (4/04/2019), 7 (4/04/2019)
- Val: 10 (5/04/2019), 12 (5/04/2019), 1 (23/03/2019), 2 (23/03/2019), 4 (23/03/2019), 5 (27/03/2019)
- Test: 13 (10/04/2019), 17 (9/07/2019), 8 (4/04/2019), 9 (4/04/2019)

Caveats: bream is tiny (125 boxes in total), so don't read much into bream scores. Tweed has no crabs and is much clearer than our target water. Boxes can overhang the image edge by up to 2 px; clip them when training.

Files: `tweed_train.json`, `tweed_val.json`, `tweed_test.json`.

## Label-quality cautions
- **Tweed labels are incomplete.** Visible background fish are often unboxed, and unlabelled fish train as background. Treat Tweed as secondary and check that adding it helps rather than assuming so. Its water is also much clearer than our target.
- **Puget:** some boxes, crabs especially, cannot be confirmed from a single still even at full resolution (about half of a 6-box spot check), so expect label noise on faint animals.

## Reminder
Neither split replaces the Coastal Action held-out frames. A good score here means "the training pipeline works", not "it will work on South Shore footage".
