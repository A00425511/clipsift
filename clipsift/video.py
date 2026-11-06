"""Video access: several chapter files as one timeline, sampling, frames, loops.

Originals are only ever read. Downscaling is for speed in the motion scan and is
configurable; stills, diffs and loops come from the originals.
"""
from __future__ import annotations

import shutil
import subprocess
import warnings
from pathlib import Path

import cv2
import numpy as np


class FFmpegMissing(RuntimeError):
    pass


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def probe(path) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    info = {"path": str(path), "fps": float(fps), "frames": n,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration_s": (n / fps) if fps else 0.0}
    cap.release()
    return info


def resize_to_width(frame, width: int):
    if not width or frame.shape[1] <= width:
        return frame
    h = int(round(frame.shape[0] * width / frame.shape[1]))
    return cv2.resize(frame, (width, h), interpolation=cv2.INTER_AREA)


class Timeline:
    """Chapter files, in the order given, treated as one continuous recording."""

    def __init__(self, paths):
        if not paths:
            raise ValueError("No video files given")
        self.chapters = []
        offset = 0.0
        for p in paths:
            info = probe(p)
            info["offset_s"] = offset
            offset += info["duration_s"]
            self.chapters.append(info)
        self.duration_s = offset
        first = self.chapters[0]
        self.fps, self.width, self.height = first["fps"], first["width"], first["height"]

    def meta(self) -> dict:
        return {"source_files": [c["path"] for c in self.chapters], "duration_s": self.duration_s,
                "fps": self.fps, "width": self.width, "height": self.height}

    def _chapter_at(self, t: float) -> dict:
        for c in reversed(self.chapters):
            if t >= c["offset_s"]:
                return c
        return self.chapters[0]

    def iter_samples(self, sample_fps: float, width: int = 0, gray: bool = False,
                     start_s: float = 0.0, end_s: float | None = None):
        """Yield (t, frame) at about sample_fps. Reads sequentially, no heavy seeking."""
        end_s = self.duration_s if end_s is None else min(end_s, self.duration_s)
        step = 1.0 / sample_fps
        next_t = start_s
        for ch in self.chapters:
            ch_end = ch["offset_s"] + ch["duration_s"]
            if ch_end <= start_s or ch["offset_s"] >= end_s:
                continue
            cap = cv2.VideoCapture(ch["path"])
            fps = ch["fps"] or 30.0
            idx = max(0, int(round((max(next_t, ch["offset_s"]) - ch["offset_s"]) * fps)))
            if idx:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            while True:
                t = ch["offset_s"] + idx / fps
                if t > end_s:
                    break
                if t + 0.5 / fps >= next_t:
                    ok, fr = cap.read()
                    if not ok:
                        break
                    fr = resize_to_width(fr, width)
                    if gray:
                        fr = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
                    yield t, fr
                    while next_t <= t + 0.5 / fps:
                        next_t += step
                else:
                    if not cap.grab():
                        break
                idx += 1
            cap.release()

    def get_frame(self, t: float):
        """Full-resolution frame from the original at time t (BGR), or None."""
        ch = self._chapter_at(t)
        cap = cv2.VideoCapture(ch["path"])
        fps = ch["fps"] or 30.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round((t - ch["offset_s"]) * fps))))
        ok, fr = cap.read()
        cap.release()
        return fr if ok else None

    def cut_loop(self, start_s: float, end_s: float, out_path, max_width: int = 0,
                 crf: int = 23) -> Path:
        """Cut [start_s, end_s] from the original into an H.264 mp4 (browser playable).

        A cut never crosses chapters: it stops at the end of the chapter holding start_s.
        Uses ffmpeg from PATH. If missing, falls back to OpenCV (mp4v, may not play in a browser).
        """
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ch = self._chapter_at(start_s)
        ch_end = ch["offset_s"] + ch["duration_s"]
        end_s = min(end_s, ch_end)
        local_start = max(0.0, start_s - ch["offset_s"])
        dur = max(0.1, end_s - start_s)
        ff = find_ffmpeg()
        if ff:
            vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            if max_width:
                vf = f"scale='min({max_width},iw)':-2"
            cmd = [ff, "-y", "-loglevel", "error", "-ss", f"{local_start:.3f}", "-i", ch["path"],
                   "-t", f"{dur:.3f}", "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {r.stderr.strip()[:400]}")
            return out_path
        warnings.warn("ffmpeg not found on PATH. Install it (see README) for browser-playable H.264 "
                      "loops. Falling back to the OpenCV writer (mp4v), which many browsers cannot play.")
        return self._cut_loop_opencv(ch, local_start, dur, out_path, max_width)

    @staticmethod
    def _cut_loop_opencv(ch, local_start, dur, out_path, max_width):
        cap = cv2.VideoCapture(ch["path"])
        fps = ch["fps"] or 30.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(local_start * fps))
        writer = None
        for _ in range(int(dur * fps)):
            ok, fr = cap.read()
            if not ok:
                break
            fr = resize_to_width(fr, max_width)
            if writer is None:
                writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps,
                                         (fr.shape[1], fr.shape[0]))
            writer.write(fr)
        cap.release()
        if writer:
            writer.release()
        return out_path
