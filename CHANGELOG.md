# ClipSift change log

Every change pushed to GitHub gets a line here. The app version lives in `clipsift/__init__.py`.

- **App versions:** add a new entry at the top of "App versions", update `__version__`, and tag the commit (for example `v0.5.0`). Use a new middle number for a new feature and a new last number for a fix.
- **Model versions:** add a row to the table whenever a different model or different detector settings are used. Record what it was trained on and how it was tested. Model files stay out of git, so the file name and test result here are the record of which model is which.

## Model versions

| Version | Date | Model file | Settings | Training | Test result | Status |
|---|---|---|---|---|---|---|
| M0 | 2026-11-05 | `cfd-rf-detr-nano-640-2026.02.02.cp-011.20260706-release.pth` | Tiles 512, overlap 0.25, candidates at 0.05, suggested count at 0.1, static filter on | None. Community Fish Detector as released, not trained on Coastal Action footage | One labelled frame: recall 0.45, precision 0.63, against 0.20 and 0.28 by chance. Tested on very little data, so not validated | In use |

No team-trained model has been added to this repository yet.

## App versions

### 0.5.0 (2026-11-06)
- Both pages: drag the playhead to move through the clip.
- Both pages: Count second only toggle (O) loops just the 1 second count window. Off plays the full clip.
- Review app: Motion button, so the clip can stay in the picture without holding Space.

### 0.4.0 (2026-11-06), commit ce5dfec
Deployed to the team website.
- Review app: hold Space to play the clip in the picture, with the count second highlighted.
- Review app: right-click removes a dot, ellipse or box.
- Both pages: Restart each time toggle (R), Enhance presets Off, Light, Strong and Silhouette (C), and a Common/Scientific name toggle.
- Both pages: species lists follow fish or invertebrate. Every species now has a `kind`.
- Fix: the review app's count second is now centred on the count point, as the protocol says.
- Change: Space no longer controls the small clip player. Use its Play/pause button.

### 0.3.0 (2026-11-06), commit b87f1b5
- Labelling protocol, calibration mode, Unsure marks and the static-object filter.

### 0.2.0 (2026-11-06), commit 730f6fe
- Shared blind label page and the fish detector backend.

### 0.1.0 (2026-11-05), commit 10876b8
- First ClipSift prototype and background documents.
