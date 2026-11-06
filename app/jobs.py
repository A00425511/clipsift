"""Background processing for the review app: one video at a time, in the order they were added.

Each job runs `python -m clipsift run` in its own process, so a crash cannot take the app down.
Jobs are kept in memory: a restart of the app forgets the list, and the finished run folders stay.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

ACTIVE = ("queued", "running")
PLAN_RE = re.compile(r"^plan: (\d+) points")
POINT_RE = re.compile(r"^subsample ss_(\d+) ")
SEGMENT_RE = re.compile(r"^motion scan: (\d+) segments")
MEDIA_RE = re.compile(r"^segment media (\d+) of (\d+)")


def safe_run_name(text: str) -> str:
    """A folder name the app accepts, made from a video's file name."""
    name = re.sub(r"[^A-Za-z0-9_.\-]+", "_", text).strip("._-")
    return name[:100] or "video"


def build_command(paths, runs_root, run_id, layer=0, window_start=None, window_end=None, python=None,
                  video_id=None, interval=None) -> list:
    cmd = [python or sys.executable, "-u", "-m", "clipsift", "run", *[str(p) for p in paths],
           "--out", str(runs_root), "--id", run_id, "--layer", str(int(layer))]
    if window_start is not None:
        cmd += ["--window-start", str(window_start)]
    if window_end is not None:
        cmd += ["--window-end", str(window_end)]
    if video_id:
        cmd += ["--video-id", video_id]
    if interval:
        cmd += ["--interval", str(interval)]
    return cmd


def read_progress(lines) -> dict:
    """Plain words and a rough percentage from the pipeline's log lines."""
    total = done = 0
    text, pct = "Starting", 2
    for line in lines:
        line = line.strip()
        m = PLAN_RE.match(line)
        if m:
            total = int(m.group(1))
            text, pct = "Cutting points from the video", 5
            continue
        m = POINT_RE.match(line)
        if m:
            done = int(m.group(1))
            text = f"Point {done} of {total}" if total else f"Point {done}"
            pct = 5 + int(65 * done / total) if total else 30
            continue
        m = SEGMENT_RE.match(line)
        if m:
            text, pct = f"Checking {m.group(1)} stretches of movement", 80
            continue
        m = MEDIA_RE.match(line)
        if m:
            i, n = int(m.group(1)), int(m.group(2))
            text, pct = f"Cutting movement clips, {i} of {n}", 80 + int(19 * i / n)
            continue
        if line == "window video":
            text, pct = "Making the window video", 75
            continue
        if line.startswith("wrote "):
            text, pct = "Finishing", 99
    return {"text": text, "percent": pct}


def last_error(lines) -> str:
    """The last few useful lines of a failed run, for the screen."""
    keep = [x.rstrip() for x in lines if x.strip()]
    errors = [x for x in keep if x.startswith("Error:")]
    return errors[-1][:500] if errors else " ".join(keep[-3:])[-500:]


class JobQueue:
    def __init__(self, runs_root, project_root):
        self.runs_root = Path(runs_root)
        self.project_root = Path(project_root)
        self.log_dir = self.runs_root / ".jobs"
        self.jobs: list = []
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.proc = None
        self.thread = None

    def add(self, name, paths, layer=0, window_start=None, window_end=None, video_id=None, interval=None) -> dict:
        job = {"id": uuid.uuid4().hex[:12], "name": name, "videos": [Path(p).name for p in paths], "layer": int(layer),
               "status": "queued", "added_at": time.time(), "started_at": None, "ended_at": None, "error": None,
               "cmd": build_command(paths, self.runs_root, name, layer, window_start, window_end, video_id=video_id, interval=interval)}
        with self.lock:
            self.jobs.append(job)
            if self.thread is None:
                self.thread = threading.Thread(target=self._work, daemon=True)
                self.thread.start()
        self.wake.set()
        return self.view(job)

    def busy_with(self, name) -> bool:
        with self.lock:
            return any(j["name"] == name and j["status"] in ACTIVE for j in self.jobs)

    def _log(self, job) -> Path:
        return self.log_dir / f"{job['id']}.log"

    def _lines(self, job) -> list:
        try:
            return self._log(job).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

    def view(self, job) -> dict:
        out = {k: v for k, v in job.items() if k != "cmd"}
        now = job["ended_at"] or time.time()
        out["elapsed_s"] = round(now - job["started_at"]) if job["started_at"] else 0
        p = read_progress(self._lines(job)) if job["status"] == "running" else {"text": "", "percent": 100 if job["status"] == "done" else 0}
        out["progress"] = p["text"]
        out["percent"] = p["percent"]
        return out

    def list(self) -> list:
        with self.lock:
            jobs = list(self.jobs)
        return [self.view(j) for j in jobs]

    def cancel(self, job_id) -> bool:
        with self.lock:
            job = next((j for j in self.jobs if j["id"] == job_id), None)
            if job is None or job["status"] not in ACTIVE:
                return False
            if job["status"] == "queued":
                job["status"] = "cancelled"
                job["ended_at"] = time.time()
                return True
            job["cancel"] = True
            if self.proc is not None:
                self.proc.terminate()
            return True

    def _next(self):
        with self.lock:
            return next((j for j in self.jobs if j["status"] == "queued"), None)

    def _work(self):
        while True:
            job = self._next()
            if job is None:
                self.wake.wait()
                self.wake.clear()
                continue
            self._run(job)

    def _run(self, job):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with self.lock:
            job["status"] = "running"
            job["started_at"] = time.time()
        try:
            with open(self._log(job), "w", encoding="utf-8") as log:
                proc = subprocess.Popen(job["cmd"], cwd=self.project_root, stdout=log, stderr=subprocess.STDOUT)
                with self.lock:
                    self.proc = proc
                code = proc.wait()
        except OSError as ex:
            code, job["error"] = 1, str(ex)
        with self.lock:
            self.proc = None
            job["ended_at"] = time.time()
            if job.pop("cancel", False):
                job["status"] = "cancelled"
            elif code == 0 and (self.runs_root / job["name"] / "results.json").is_file():
                job["status"] = "done"
            else:
                job["status"] = "failed"
                job["error"] = job["error"] or last_error(self._lines(job)) or f"Stopped with code {code}."
