# ClipSift backlog

Updated 8 Nov 2026, for version 1.4.1. The live plan is `PROTOCOL_WORKFLOW.md`, and finished work is listed in `../CHANGELOG.md`.

## Before handing ClipSift to Coastal Action
- [ ] **Windows package.** Build and test a Windows version of the Mac package (`tools/package_mac.py`): its own Python, ffmpeg, a `.bat` launcher, and work saved in Documents. It needs a Windows PC to test (Adrien). It should replace the older 1-2-3 `.bat` kit and bring `README-COASTAL.txt` up to the 1.4.x flow.
- [ ] **Licences.**
  - The CFD weights state no licence.
  - Ultralytics YOLOv8 is AGPL-3.0.
  - The Brackish dataset's licence is unconfirmed.
  - DIGI4ECO is CC BY 4.0, so it needs credit.
  - The WoRMS terms for the species list need confirming.

  Settle these before any model or species list leaves the team.
- [ ] **Species statuses.** Check the at-risk and invasive flags against the official registries. The rows marked `needs_status_check` in `species/seed_species.csv` haven't been verified yet.
- [ ] **Questions for Coastal Action**, parked in `PROTOCOL_WORKFLOW.md`:
  - the percent-difference formula
  - how the 6% rule applies to dense school stills
  - whether to use the two closest counts or the average of all counts
  - who signs off a video

## Model
- [ ] **Benchmark the two new candidates** on the frozen 11-frame Coastal benchmark at about 1 false box per empty frame, against the current CFD Nano 640 setting (recall about 0.20).
  - **Ali's DIGI4ECO fine-tuned RF-DETR Small** (`experiments/digi4eco-finetuned/`) uses the same library as the app, so it should be quick to try once the checkpoint and its SHA-256 are shared.
  - **Adrien's YOLOv8n** (`config/yolo.yaml`) needs its model file. Check its class filter first: `[1, 4]` are small fish and jellyfish. It also needs tiling in the `onnx` backend.
- [ ] Let Step 6 and the after-count guess use a detector other than CFD (`model_check_detector` in `clipsift/verify.py` is wired to CFD).
- [ ] Ask Coastal Action for earlier tagged video for training: round one is 15 to 20 videos from 4 or more sites, with one site held out. See the model comparison report.
- [ ] Train from point labels, because Coastal tags points, not boxes. Options: P2PNet, density maps, or fixed-size pseudo-boxes. None has been tested.
- [ ] Find a separate approach for crabs and other invertebrates. The current detectors find fish only.
- [ ] Static filter on frames where the whole scene moves (camera sway or surge), and a check on a second recording or site.

## App
- [ ] **Timed study:** Coastal Action staff use ClipSift and the old method on the same video, with a stopwatch. Today's time figures are estimates.
- [ ] A sharpen control.
- [ ] A supervisor sign-off for a finished video (open decision).

## Done since the 5 Nov check-in
- Contrast reset, Clear all marks, right-click to remove a mark, plainer Movement view wording, still versus clip wording.
- A label-only page for the team (`/label.html`, team site only since 1.4.0).
- The report as a PDF and CSVs.
- Saving and reopening an analysis: every count, rating and mark is saved in the run folder as it is made, and reopening the video picks up where it was left.
- The static-object filter and pole mask.
- The CFD backend with tiling.
- The Mac package.
- The retired motion-segment review screen (removed in 1.4.0).
