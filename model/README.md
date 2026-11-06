# Jacob Model 0.1.0 (experimental)

First training experiment for the ClipSift fish and crab detector, run on 6 Nov 2026. **It isn't used by the app.** App version 0.8.0 still uses its existing detector, and nothing outside this `model/` folder has changed. This branch was cut from `main`, so it shows older app code than 0.8.0. Don't merge it to update the app.

No checkpoint from this work has been promoted. On the one verified Coastal frame, neither trained model has been shown to beat the untrained Community Fish Detector (CFD).

## What was trained

RF-DETR Nano, 2 classes (fish, crab), 3 epochs, on 15,936 balanced Puget Sound tiles. Two runs used the same data:

| Run | Starting weights | Overlap with training data |
|---|---|---|
| `p2_stock` | Stock RF-DETR Nano | None found with fish datasets |
| `p2_cfd` | CFD Nano 2026.02.02 | Yes: CFD was trained on a dataset that includes Puget |

## Results

Coastal columns use the top 100 boxes on one verified frame (one dense school, 103 dots). This is a development check, not an accuracy figure. Puget scores for anything started from CFD are contaminated, so they aren't fair evidence.

| Model | Coastal recall | Coastal precision | Puget fish AP at 0.5 | Puget crab AP at 0.5 |
|---|---|---|---|---|
| CFD, untrained | 0.37 | 0.66 | Contaminated | n/a |
| Stock, untrained | 0.19 | 0.23 | 0.061 | n/a |
| Stock-start, epoch 1 | 0.42 | 0.61 | 0.603 | 0.612 |
| Stock-start, epoch 3 | 0.37 | 0.51 | 0.628 | 0.592 |
| CFD-start, epoch 2 | 0.41 | 0.62 | 0.652 (contaminated) | 0.600 (contaminated) |
| CFD-start, epoch 3 | 0.39 | 0.62 | 0.619 (contaminated) | 0.525 (contaminated) |

The full tables, method and limits are in `docs/PHASE2.md`. Scores for each model are in `results/`.

## Known limits

- Coastal evidence is one verified frame. The team's fish marks haven't been used for scoring yet.
- Team labels were still changing, so the false-alarm check used a frozen copy with this SHA-256: `d632b561415eb0211d89a1a78694c62110e99e8e62e645a8531e727a2fd3c989`. That copy isn't in this repo because it holds labeller names.
- Each run used one seed. The CFD-start epoch 3 drop on Puget could be real or noise.
- Thresholds tuned on Puget give too few boxes on Coastal: 6 to 27 boxes against 103 dots.
- Licences aren't cleared for shipping. CFD's weights have no stated licence and mixed training data, and the Apache-2.0 licence for the stock weights is unverified.

## What isn't in this branch

- **Checkpoints:** each is about 122 MB, over GitHub's 100 MB file limit, and `*.pth` is ignored. They're on Jacob's machine, and `checkpoints.sha256` lists their hashes.
- **Images and tiles:** use `data/` on the `jacob/training-data` branch to fetch and split the datasets.
- **Coastal frames and team labels:** these are test data and stay out of training.

## Running the scripts

These are the scripts as they were run, not a packaged tool. They expect this layout, so copy `model/scripts/` into a folder beside the `clipsift` checkout first:

```text
workspace/
  clipsift/           this repo
  Footage Sources/    datasets and splits
  Model Training/     contents of model/scripts/, plus a .venv with rfdetr
```

`run_phase2.sh` runs both training runs and their evaluations. On an Apple M4 Pro, each run took 3 to 4 hours.

## Data credit

Puget Sound data is released under CDLA-Permissive-1.0. Cite Farrell et al. 2023, Scientific Data 10:799, https://doi.org/10.1038/s41597-023-02557-6.
