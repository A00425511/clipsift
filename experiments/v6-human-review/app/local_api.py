"""Local-only ClipSift V6 demo API.

Run from repository root: python -m uvicorn app.local_api:app --host 127.0.0.1 --port 8765
The server reads existing V6 evidence and can launch the existing CLI for a new subsample.
No model weights or videos are uploaded to an external service.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from urllib.parse import quote
import io

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (ROOT / "outputs").resolve()
DEMO_HTML = Path(__file__).with_name("demo.html")

app = FastAPI(title="ClipSift Local API", version="0.1.0")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _safe_run(name: str) -> Path:
    if not name or not all(c.isalnum() or c in "_-" for c in name):
        raise HTTPException(400, "Run name must contain only letters, numbers, - or _")
    directory = (OUTPUTS / name).resolve()
    if not directory.is_relative_to(OUTPUTS):
        raise HTTPException(400, "Invalid output directory")
    return directory


def _review_csv(run: str) -> Path:
    return _safe_run(run) / "review_v2" / "candidate_review_queue.csv"


def _decision_file(run: str) -> Path:
    return _safe_run(run) / "review_v2" / "review_decisions.json"


def _load_decisions(run: str) -> dict:
    path = _decision_file(run)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_rows(run: str) -> list[dict]:
    path = _review_csv(run)
    if not path.is_file():
        raise HTTPException(404, f"Review CSV not found for {run}; run build_review_queue_v2.py first")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    decisions = _load_decisions(run)
    for row in rows:
        key = f"{row['subsample_index']}:{row['track_id']}"
        update = decisions.get(key, {})
        row["reviewer_decision"] = update.get("decision", "")
        row["reviewer_notes"] = update.get("notes", "")
        # Do not expose an arbitrary filesystem path as a public URL.
        row["evidence_url"] = (
            f"/api/runs/{run}/evidence/{row['subsample_index']}/{row['track_id']}"
            if row.get("evidence_image") else None
        )
        row["full_frame_url"] = (
            f"/api/runs/{run}/evidence-full/{row['subsample_index']}/{row['track_id']}"
            if row.get("full_frame_image") else None
        )
    return rows


@app.get("/")
def homepage():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/videos", status_code=307)


@app.get("/api/health")
def health():
    return {"status": "ok", "local_only": True, "model_loaded": False}


@app.get("/api/runs")
def runs():
    if not OUTPUTS.is_dir():
        return {"runs": []}
    result = []
    for p in sorted(OUTPUTS.iterdir()):
        if p.is_dir() and (p / "subsamples_v6.json").is_file():
            result.append({"name": p.name, "has_review_queue": (p / "review_v2" / "candidate_review_queue.csv").exists()})
    return {"runs": result}


@app.get("/api/runs/{run}/summary")
def summary(run: str):
    p = _safe_run(run) / "subsamples_v6.json"
    if not p.is_file():
        raise HTTPException(404, "V6 results not found")
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"version": data.get("version"), "protocol_note": data.get("protocol_note"),
            "subsamples": [{k: s.get(k) for k in (
                "subsample_timestamp_seconds", "sampled_count_frames",
                "max_high_candidates_in_count_window", "max_reviewable_candidates_in_count_window",
                "status", "confirmed_fish_count")}
                for s in data.get("subsamples", [])]}


@app.get("/api/runs/{run}/candidates")
def candidates(run: str):
    rows = _load_rows(run)
    return {"run": run, "candidates": rows, "total": len(rows),
            "reviewed": sum(bool(r["reviewer_decision"]) for r in rows),
            "note": "Track IDs and HIGH status are not validated fish counts"}


@app.get("/api/runs/{run}/evidence/{subsample}/{track}")
def evidence(run: str, subsample: int, track: int):
    # Resolve evidence only through a matching CSV entry, inside the run output.
    rows = _load_rows(run)
    match = next((r for r in rows if int(r["subsample_index"]) == subsample and int(r["track_id"]) == track), None)
    if not match or not match.get("evidence_image"):
        raise HTTPException(404, "Evidence unavailable")
    path = Path(match["evidence_image"])
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.is_relative_to(_safe_run(run)) or not path.is_file():
        raise HTTPException(404, "Evidence unavailable")
    return FileResponse(path, media_type="image/jpeg")


@app.get('/api/runs/{run}/evidence-full/{subsample}/{track}')
def evidence_full(run: str, subsample: int, track: int):
    rows = _load_rows(run)
    row = next((r for r in rows if int(r['subsample_index']) == subsample
                and int(r['track_id']) == track), None)
    if not row or not row.get('full_frame_image'):
        raise HTTPException(404, 'Full-frame evidence unavailable')
    path = Path(row['full_frame_image'])
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.is_relative_to(_safe_run(run)) or not path.is_file():
        raise HTTPException(404, 'Full-frame evidence unavailable')
    return FileResponse(path, media_type='image/jpeg')


class Review(BaseModel):
    decision: Literal["FISH", "INVERTEBRATE", "EQUIPMENT", "BACKGROUND", "UNCERTAIN", ""]
    notes: str = Field(default="", max_length=1500)


@app.put("/api/runs/{run}/review/{subsample}/{track}")
def save_review(run: str, subsample: int, track: int, review: Review):
    rows = _load_rows(run)
    valid = any(int(r["subsample_index"]) == subsample and int(r["track_id"]) == track for r in rows)
    if not valid:
        raise HTTPException(404, "Candidate not found")
    with _lock:
        data = _load_decisions(run)
        data[f"{subsample}:{track}"] = {"decision": review.decision, "notes": review.notes}
        dest = _decision_file(run)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(dest)
    return {"saved": True, "candidate": f"{subsample}:{track}",
            "notice": "No confirmed abundance calculated from track IDs"}


@app.get("/api/runs/{run}/export.csv")
def export(run: str):
    rows = _load_rows(run)
    if not rows:
        raise HTTPException(404, "No candidates")
    out = io.StringIO()
    fields = [k for k in rows[0].keys() if k not in ("evidence_url", "full_frame_url")]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows({k: v for k, v in row.items() if k in fields} for row in rows)
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="clipsift_{run}_review.csv"'})


class AnalysisRequest(BaseModel):
    video_path: str = Field(min_length=1)
    timestamp: str = Field(min_length=1, max_length=20)
    run_name: str = Field(default="v6_web", pattern=r"^[A-Za-z0-9_-]+$")


def _process_job(job_id: str, args: list[str], result_dir: Path):
    try:
        proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
        with _lock:
            job = _jobs[job_id]
            job["log"] = (proc.stdout + "\n" + proc.stderr)[-12000:]
            job["status"] = "error" if proc.returncode else "completed"
        if proc.returncode == 0:
            build = ROOT / "scripts" / "build_review_queue_v2.py"
            if build.is_file():
                cmd = [sys.executable, str(build), str(result_dir / "subsamples_v6.json")]
                proc2 = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
                with _lock:
                    _jobs[job_id]["log"] += "\n" + proc2.stdout + proc2.stderr
                    if proc2.returncode:
                        _jobs[job_id]["status"] = "error"
    except Exception as exc:
        with _lock:
            _jobs[job_id].update(status="error", log=str(exc))


@app.post("/api/analyze", status_code=202)
def analyze(payload: AnalysisRequest):
    # The API listens on localhost only. Input is a local path, never an upload.
    # Do not expose this endpoint on a public network without authentication and sandboxing.
    video = Path(payload.video_path)
    if not video.is_file() or video.suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(400, "Video must be an existing local supported file")
    run_dir = _safe_run(payload.run_name)
    if (run_dir / "subsamples_v6.json").exists():
        raise HTTPException(409, "Run name already exists; choose another to preserve previous outputs")
    with _lock:
        if any(j["status"] == "running" for j in _jobs.values()):
            raise HTTPException(409, "An analysis is already running")
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"status": "running", "run_name": payload.run_name, "log": ""}
    args = [sys.executable, str(ROOT / "scripts" / "analyze_full_video.py"), str(video),
            "--timestamps", payload.timestamp, "--save-clips", "--output-dir", str(run_dir)]
    thread = threading.Thread(target=_process_job, args=(job_id, args, run_dir), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "running", "run_name": payload.run_name}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(404, "Unknown job")
        return dict(_jobs[job_id])


# ClipSift subsample overview extension
from app.subsample_routes import router as subsample_router
app.include_router(subsample_router)

# ClipSift evidence gallery extension
from app.gallery_routes import router as gallery_router
app.include_router(gallery_router)


# ClipSift three-page navigation routes v1
@app.get('/videos', include_in_schema=False)
def videos_page():
    return FileResponse(Path(__file__).with_name('videos.html'), media_type='text/html')

@app.get('/review', include_in_schema=False)
def review_page():
    return FileResponse(DEMO_HTML, media_type='text/html')

# ClipSift Results Dashboard v1
from app.results_routes import router as results_router
app.include_router(results_router)
