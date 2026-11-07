# ClipSift V6 — Independent Human-Review Prototype

This folder is an **independent local Python/FastAPI prototype**, developed in parallel with the team's Flask application. Do not assume it is the backend for the Cloudflare Pages demo. It is included to make the V6 work inspectable and reproducible without changing the team's pipeline.

## Start in Windows PowerShell

From the repository root:

```powershell
cd experiments\v6-human-review
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:CLIPSIFT_MODEL_PATH = 'C:\path\to\authorized\cfd-small.pth'
.\.venv\Scripts\python.exe -m uvicorn app.local_api:app --host 127.0.0.1 --port 8766
```

Open http://127.0.0.1:8766/videos . The model file is **not** supplied. The dependency snapshot was collected in one developer environment; a clean installation is not yet certified. Depending on your environment, you may have to install a platform-compatible version of PyTorch separately.

The input video must already exist **on the server's filesystem**, and its location is entered as a path on the Videos page; this is not a remote upload form. Keep the original video available because evidence crops are regenerated from original frames.

## Analyze one protocol point

In a *second* PowerShell window, from this V6 folder:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_full_video.py 'C:\path\to\authorized\video.mp4' --timestamps '14:04' --save-clips --output-dir outputs\demo_1404
.\.venv\Scripts\python.exe scripts\build_review_queue_v2.py outputs\demo_1404\subsamples_v6.json
```

`14:04` means 14 minutes, 4 seconds. The input video must be long enough.

Then visit:

- http://127.0.0.1:8766/videos
- http://127.0.0.1:8766/subsamples?run=demo_1404
- http://127.0.0.1:8766/review?run=demo_1404
- http://127.0.0.1:8766/results?run=demo_1404

Decisions are saved in `outputs/<run>/review_v2/review_decisions.json`. Do not share this file or original footage publicly without permission. Track candidates and HIGH peaks do **not** equal confirmed individual fish.

## Isolation and development notes

- Start the team Flask application separately from the **team repository root** according to the team's own README; choose a different port.
- Start the V6 application from **this folder**, not from the team repository root. It uses local-relative imports and outputs.
- Use a **separate virtual environment**: team's `requirements.txt` and V6's pinned `requirements.txt` are different.
- The root team `app/`, `clipsift/`, `deploy/`, `tools/`, README and requirements must remain unchanged.
- Do not publicly expose the V6 FastAPI service. It allows local video paths and has no production-grade authentication, sandboxing, or rate limits.
- The Cloudflare demonstration currently uses the team's separate Flask/static pipeline, not this V6 FastAPI project. Integrating them would require a deliberate API/data contract and security review.
- Model weights, video files, outputs, environments, and secrets are excluded from this release. The existing source is provided for research/code review, not as a plug-and-play packaged executable.
