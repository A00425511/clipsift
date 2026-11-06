# Training data for ClipSift: start here

This page is the one thing you need to read before you touch the data. It covers what we have, how to get it onto your computer, how the train/val/test files work, and a few rules that stop us fooling ourselves about how good the detector is.

The images themselves are **not** in this repo. They are about 5.5 GB, far too big for GitHub. The repo holds the small files that describe them (the split files, the fetch script and our notes), and the script downloads the pictures from the original sources.

## What we have

| Source | Licence | Images we use | Boxes | Classes | How well it matches Coastal Action's water |
|---|---|---|---|---|---|
| Puget Sound nearshore fish (NOAA, hosted by LILA BC) | CDLA-Permissive-1.0 | 21,623 (the low and medium visibility part of the 77,739 in the full download) | 49,270, plus 2,232 empty frames with no boxes | fish, crab, fish_or_crab, unknown | High: murky water, fixed camera, has crabs |
| Tweed / Tallebudgera luderick (PANGAEA) | CC-BY-4.0 | 4,280 | 9,429 | luderick (9,304), bream (125) | Medium: clearer, warmer seagrass water, no crabs |

In total that is 25,903 images. A "box" is a rectangle drawn round one animal, stored as `[x, y, width, height]` in pixels. "Visibility" is the dataset authors' own rating of how clear the water was in each video.

## Why Puget Sound is the main set and Tweed is secondary

Coastal Action's footage comes from a fixed camera in murky, cold water, and the animals we care about include crabs. Puget Sound is the closest public match: murky water, a camera that stays put, and a real crab class. Tweed is a useful extra source of fish pictures, but its water is much clearer and warmer, it has no crabs, and many of its fish are not boxed (see "Known limits"). So train mainly on Puget, and treat Tweed as something to try: add it, then check that your scores on the Puget validation set actually improved before you keep it.

## How to get the data

You need Python 3.9 or newer. Nothing needs installing: the script uses only what comes with Python.

- **Disk space:** about 5.5 GB for the finished images, and about 10 GB free while it runs (the downloaded zips are deleted after unpacking). If you add `--keep-zips` you need about 17 GB.
- **Time:** the download is about 11.4 GB in total. Expect roughly 15 to 45 minutes on a normal home or campus connection, plus a few minutes to check and unpack. If it stops, run the same command again and it carries on where it left off.

Open a terminal in the folder where you cloned the repo, then run one of these. By default the data goes into a folder called `Footage Sources` sitting **next to** the repo folder, so git never sees the images.

macOS or Linux:

```bash
# everything (Puget Sound and Tweed)
python3 data/tools/fetch_datasets.py

# just Puget Sound, or just Tweed
python3 data/tools/fetch_datasets.py --only puget
python3 data/tools/fetch_datasets.py --only tweed

# choose your own folder, e.g. a bigger drive
python3 data/tools/fetch_datasets.py --dest ~/clipsift-data

# check afterwards that every image is there (changes nothing)
python3 data/tools/fetch_datasets.py --check
```

Windows (PowerShell or Command Prompt; use `py` if `python` is not found):

```
python data\tools\fetch_datasets.py
python data\tools\fetch_datasets.py --only tweed
python data\tools\fetch_datasets.py --dest D:\clipsift-data
python data\tools\fetch_datasets.py --check
```

If you pass `--dest` to fetch, pass the same `--dest` to `--check`. If someone has already shared the two zip files with you, skip the download with `--zip-dir <folder holding the zips>`; the script checks the files are intact (size and fingerprint) before using them. `--keep-zips` keeps the zips after unpacking.

The script downloads only the exact files named in the split files, checks them against known sizes and sha256 fingerprints, unpacks only the images we use, and ends by counting every image. When it works you will see "All images named in the splits are present" and a total of 25,903. If it fails it prints a plain message and stops with an error. Do not edit the files it creates.

Afterwards your `Footage Sources` folder looks like this, and the paths match the `image_root` written inside each split file:

```
Footage Sources/
  Puget Sound LILA/images/   (21,623 .jpg)
  Tweed Estuary/images/      (4,280 .jpg)
  splits/                    (six .json files)
```

## How the train/val/test splits work

Training teaches the model, validation (val) is what you check while you tune, and test is held back to see how well it copes with new places. The six files are in `data/splits/` (gzipped; the fetch script unpacks them into `Footage Sources/splits/`), in COCO JSON format. Full details, with every number, are in `data/splits/SPLITS.md`.

Frames from one video look almost identical, so if neighbouring frames land in different splits the model just memorises them and the scores look better than they are. The splits therefore keep whole groups together:

- **Puget Sound** is split by whole site (10 camera sites). Train has 7 sites (17,260 images), val has 1 (1,737) and test has 2 (2,626). No site appears in two splits.
- **Tweed** is split by deployment and date (18 groups, 138 video clips). Train has 2,994 images, val 643 and test 643, and no clip is in more than one split.

Two things to know. The Puget val set is almost all low-visibility, magenta-tinted frames (94%), so it is a hard, narrow check. And the Puget test set has far fewer fish per image than train because it is crab-heavy.

`data/tools/make_splits.py` is the record of how the splits were made (fixed random seed, 20261106). You do not need to run it; the committed split files are the ones everyone uses.

## The rules that protect our results

1. **Treat `fish_or_crab` and `unknown` boxes as ignore regions, not background.** These boxes mark a real animal the original labellers could not name. If you train on them as "nothing here", you teach the model that real animals are empty. Mask them out of the loss, or skip any prediction that overlaps one when you score. Do not delete the boxes either.
2. **Never train on Coastal Action's own held-out labelled frames.** Those frames are the real final test of whether the detector works on their footage. They must not go into training, and we should not tune settings against them either. Scores on our Puget and Tweed splits only tell us the pipeline works.
3. **Use our Tweed split, not the published one.** The published Tweed split puts one clip (`2205_Luderick_25.mov`) in both train and test, which leaks answers into the test.

## Known limits

- **Puget labels are noisy on faint animals.** In a spot check of 6 boxes, about half could not be confirmed from a single still image, even at full size. Crabs are the worst for this. Expect some wrong or missing boxes.
- **Crabs are scarce in training.** There are only 1,712 crab boxes in the Puget train split (428 in val, 687 in test).
- **Many Puget frames have a magenta cast.** About 58% of the full Puget set was filmed through a magenta-tinted filter. Coastal Action's water looks grey-green, so use colour augmentation. In our splits the share is 34.8% of train, 94.2% of val and 57.8% of test.
- **Tweed fish are often not boxed.** Visible background fish frequently have no box, and the model will learn to treat them as background. Tweed water is also clearer than our target.
- **Tweed has almost no bream.** Only 125 boxes in total, so do not read much into bream scores. Some Tweed boxes overhang the image edge by up to 2 pixels; clip them when training.
- The sets are from the Pacific Northwest and Queensland, not Nova Scotia, and they are still frames cut from video, not the video itself.

## What is blocked, and who is doing what

| Source | Status |
|---|---|
| **Coastal Action's own other clips and count sheets** | **The top ask.** Public data is only a stand-in. More footage from their fixed camera, plus any counts they made by hand, would help far more than any extra public set. |
| **USGS Great Herring Pond** (juvenile river herring, Massachusetts) | The public release is tables only: counts, no video or frames, so it cannot train a detector. Jacob emailed Dr. Roy about the underlying files. Dr. Roy has replied and copied a PhD student on the project who may be able to help. Follow-up is in progress and nothing has been received yet. |
| **Moreton Bay (Queensland) low-visibility dataset** | The best remaining lead on paper (murky water, fixed camera, a crab class, 8,696 annotated images). But it states no data licence and is behind a password, so we have not downloaded it. We need the author's permission first. |
| **EyeSea (PNNL, US)** | Needs a registered PNNL account plus a Globus sign-in. Not downloaded. Optional. |
| Ocean Networks Canada, DFO Bay of Fundy and Quoddy, FORCE / CIOOS Atlantic | Weak matches or nothing downloadable today. See `data/sources/atlantic-check.md`. |

Please do not look for passwords or try to get into the Moreton Bay files yourself.

## Attribution we must keep

If any of this data, or a model trained on it, is shared outside the team, keep the licence text and credit the sources:

- **Puget Sound:** released under CDLA-Permissive-1.0 (https://cdla.io/permissive-1-0/). Cite Farrell et al. 2023, Scientific Data 10:799, https://doi.org/10.1038/s41597-023-02557-6 (data collection: Ferriss et al. 2021, Aquaculture Environment Interactions 13:439-54).
- **Tweed:** licensed CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/). Cite Ditria, Connolly, Jinks and Lopez-Marcano (2021), Frontiers in Marine Science 8, https://doi.org/10.3389/fmars.2021.629485 (data: https://doi.pangaea.de/10.1594/PANGAEA.926930).

## What else is in `data/`

- `data/splits/`: the six split files (`*.json.gz`) and `SPLITS.md`.
- `data/tools/`: `fetch_datasets.py` (what you run) and `make_splits.py` (a record only).
- `data/sources/`: our notes on every dataset we looked at (`puget-sound.md`, `tweed.md`, `eyesea.md`, `moreton-bay.md`, `atlantic-check.md`), the catalogue spreadsheet and `p2-footage-sources.md`.
