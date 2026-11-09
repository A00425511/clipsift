# ClipSift — Local Underwater Video Review Prototype

ClipSift is a **local, human-in-the-loop** prototype that proposes fish-like detections in underwater survey videos, groups observations into candidate tracks, and supports human review. It does **not** autonomously report validated numbers of individual fish.

## Current workflow

1. **Videos** (`/videos`) — choose a video **already present on the same computer** and a protocol timestamp. This is not a browser file-upload service.
2. **Subsamples** (`/subsamples`) — inspect the exact source-video timestamp/frame, representative center still, ±5-second analysis context, provisional centered 1-second count window, candidate summaries, and evidence gallery.
3. **Human Review** (`/review`) — inspect one candidate at a time with a clean close-up and a source frame highlighting only that candidate; record a decision and notes.
4. **Results** (`/results`) — view analysis totals, review progress, and export available results. Candidate-track totals and HIGH peaks are **not** independently validated fish abundance.

Built-in user help explains confidence, candidate tracks, count windows, and review actions.

## Architecture

- **RF-DETR Small** (`src/clipsift/detector.py`): one-class fish candidate proposals, CPU mode; detection threshold `0.03`, NMS `0.50`.
- **ByteTrack** (`src/clipsift/tracker.py`): association of frame-level observations into tracks.
- **V5/V6 counting** (`src/clipsift/counting.py`, `pipeline.py`): candidate ranking, conservative merging, same-frame duplicate suppression, and provisional count-window peaks; human validation required.
- **Local FastAPI** (`app/local_api.py` and route modules): pages, run management, evidence serving, and review decision persistence.
- **Clean evidence** (`scripts/build_review_queue_v2.py`): reads original source-video frames; creates clean crops and source frames with one box. Original video must remain available to rebuild evidence.

See `docs/architecture.md`, `docs/TEAM_WALKTHROUGH.md`, and `docs/validation.md` for details.

## Requirements

- Python and dependencies compatible with the project (the pinned `requirements.txt` reflects one tested development environment and may require platform-specific PyTorch installation).
- Original RF-DETR checkpoint, obtained separately with appropriate authorization. **Model weights are not distributed in this repository.**
- A local video whose use and distribution is authorized. **Videos are not included.**

Example PowerShell setup in the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:CLIPSIFT_MODEL_PATH = "C:\path\to\cfd-small.pth"
python -m uvicorn app.local_api:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Do not bind this local prototype to a public network: it accepts local video paths and has **no authentication, resource isolation, or hardened multiuser job management**.

### Command-line analysis example

```powershell
python scripts\analyze_full_video.py "C:\path\to\input.mp4" --timestamps "14:04" --save-clips --output-dir outputs\demo_1404
python scripts\build_review_queue_v2.py outputs\demo_1404\subsamples_v6.json
```

The web UI normally attempts to generate the evidence queue after analysis. `14:04` means **14 minutes and 4 seconds**, not 14.04 seconds.

## File organization

- `app/` — UI and FastAPI routes
- `src/clipsift/` — detector, tracker, protocol, analysis, candidate handling
- `scripts/` — analysis, evidence builder, audit, validation tools
- `tests/` — development/unit tests; some need a real model and test video
- `config/` — sample subsample timestamp CSV
- `docs/` — technical, reviewer, and team documentation
- `assets/` — help assets
- `outputs/` — generated locally, ignored by Git

Review decisions are stored per run in `outputs/<run>/review_v2/review_decisions.json`. Back them up separately if needed: output directories are **not** included in release ZIPs.

## Evidence and limitations

Development examples (10 manually annotated frames each) produced previously reported TP/FP/FN of 30/80/6 and 17/50/1 at IoU ≥ 0.50. These are small, selected development samples, **not** independent accuracy estimates. A high-confidence candidate can be equipment or background. Overlapping tracks can also represent real overlapping fish. `FISH` review labels do not by themselves resolve duplicate tracks into an independently confirmed fish count.

## Release / team integration

**This archive is a code review candidate, not a fully verified production release.** On the developer's Windows machine, the separate release-folder web pages, local analysis and review persistence were manually tested. A clean-install reproducibility test, deployment/security review, footage/checkpoint licensing verification, and group-repository comparison are pending.

Use a feature branch and PR only after access to the group repository is granted. Do not publish model weights, raw videos, `.env`, virtual environments, generated outputs, or review decisions without explicit permission. GitHub Pages can host a static UI, but **cannot execute this localhost FastAPI backend**; choose an approved hosting architecture or a clearly labelled precomputed demonstration.
