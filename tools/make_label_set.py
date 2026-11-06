"""Make a label set: widely spaced full-resolution frames plus a short clip around each, for the label page.

    python tools/make_label_set.py "../Coastal Footage/T1-STAT2 411.MP4" --set t1s2_v1 --start 60 --end 2040 --every 20

Writes label_sets/<set>/frames/<frame_id>.jpg (full size, JPEG quality 88),
label_sets/<set>/clips/<frame_id>.mp4 (Coastal Action's protocol: 5 s before to 5 s after the frame, 10 s in all,
1920 wide, H.264, CRF 24, no audio, faststart), label_sets/<set>/diff/<frame_id>.jpg (the black and white Movement
view, 1920 wide: absolute difference between the frame and the median of 7 frames across the same 10 s, built with
the same function as the review app) and label_sets/<set>/manifest.json. Frames are spaced apart on purpose: neighbouring frames are near
duplicates and would give two people the same fish twice. Needs ffmpeg and ffprobe on the PATH.
Existing files are kept, so an interrupted run can be restarted. A clip whose length is not the protocol length
(for example an older 3 s clip) is made again. Frame ids depend only on the time, so labels stay valid.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SET_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]{0,39}$")
JPEG_QUALITY = 88
CLIP_BEFORE_S = 5.0          # protocol: watch about 5 s before and 5 s after the count frame
CLIP_AFTER_S = 5.0
CLIP_WIDTH = 1920
CRF = 24
DIFF_WIDTH = 1920
DIFF_FRAMES = 7              # same as the review app
DIFF_QUALITY = 90
MAX_BYTES = 25 * 1024 * 1024


def frame_id_for(set_id: str, t: float) -> str:
    """Stable id from the time, for example t1s2_v1_t00060 (whole seconds) or _t00060p5 for half seconds."""
    whole = int(t)
    frac = round((t - whole) * 10)
    return f"{set_id}_t{whole:05d}" + (f"p{frac}" if frac else "")


def times(start: float, end: float, every: float) -> list:
    out, t = [], start
    while t <= end + 1e-9:
        out.append(round(t, 1))
        t += every
    return out


def probe(video: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(video)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffprobe failed: " + r.stderr.strip()[-300:])
    d = json.loads(r.stdout)
    s = d["streams"][0]
    return {"width": int(s["width"]), "height": int(s["height"]), "duration": float(d["format"]["duration"])}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + r.stderr.strip()[-400:])


def make_frame(video: Path, t: float, dest: Path):
    if dest.is_file() and dest.stat().st_size > 0:
        return
    import cv2
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "f.png"
        # -ss before -i seeks to the nearest earlier keyframe, then decodes forward to the exact time.
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-map", "0:v:0", "-frames:v", "1",
             "-c:v", "png", "-compression_level", "1", str(png)])
        img = cv2.imread(str(png))
        if img is None:
            raise RuntimeError(f"No frame at {t}s")
        tmp_out = dest.with_suffix(".tmp.jpg")
        cv2.imwrite(str(tmp_out), img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        tmp_out.replace(dest)


def clip_window(t: float, duration: float) -> tuple:
    """(start, length) of the clip for a frame at t. Normally t-5 to t+5; clamped at the ends of the video."""
    start = max(0.0, t - CLIP_BEFORE_S)
    end = min(duration, t + CLIP_AFTER_S)
    return start, max(0.5, end - start)


def clip_ok(dest: Path, length: float) -> bool:
    """True if the clip exists and already has the protocol length (so an old 3 s clip is replaced)."""
    if not (dest.is_file() and dest.stat().st_size > 0):
        return False
    try:
        return abs(probe(dest)["duration"] - length) < 0.5
    except (RuntimeError, OSError, KeyError, ValueError):
        return False


def make_clip(video: Path, t: float, dest: Path, duration: float):
    start, length = clip_window(t, duration)
    if clip_ok(dest, length):
        return
    tmp_out = dest.with_suffix(".tmp.mp4")
    # -g 30: a keyframe about every second, so stepping back and slow motion seek quickly.
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{length:.3f}", "-map", "0:v:0", "-an",
         "-vf", f"scale={CLIP_WIDTH}:-2", "-c:v", "libx264", "-preset", "medium", "-crf", str(CRF), "-g", "30", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-f", "mp4", str(tmp_out)])
    tmp_out.replace(dest)


def grab_small(video: Path, t: float, width: int = DIFF_WIDTH):
    """One frame at time t from the original, scaled to `width` wide, as a BGR array."""
    import cv2
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-map", "0:v:0", "-frames:v", "1",
                        "-vf", f"scale={width}:-2:flags=area", "-f", "image2pipe", "-c:v", "png", "-compression_level", "1", "-"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def make_diff(video: Path, t: float, dest: Path, duration: float):
    """Movement view: |frame - median of 7 frames across the clip window|, black and white, 1920 wide."""
    if dest.is_file() and dest.stat().st_size > 0:
        return
    import cv2
    from clipsift.pipeline import diff_from_frames
    a = max(0.0, t - CLIP_BEFORE_S)
    b = min(duration, t + CLIP_AFTER_S)
    still = grab_small(video, t)
    if still is None:
        raise RuntimeError(f"No frame at {t}s")
    ts = np.linspace(a, max(a, b - 0.05), DIFF_FRAMES)
    frames = [f for f in (grab_small(video, x) for x in ts) if f is not None and f.shape == still.shape]
    d = diff_from_frames(still, frames)
    tmp_out = dest.with_suffix(".tmp.jpg")
    cv2.imwrite(str(tmp_out), d, [cv2.IMWRITE_JPEG_QUALITY, DIFF_QUALITY])
    tmp_out.replace(dest)


def build(video: Path, set_id: str, start: float, end: float, every: float, out_root: Path, workers: int = 3) -> dict:
    if not SET_RE.match(set_id):
        raise ValueError("Set id must be letters, digits, _ or - (max 40).")
    if "river" in set_id.lower() or "river" in video.name.lower():
        raise ValueError("Refusing: names containing 'river' are real footage that must not be published.")
    if every <= 0 or end < start:
        raise ValueError("Need --every > 0 and --end >= --start.")
    info = probe(video)
    out = out_root / set_id
    (out / "frames").mkdir(parents=True, exist_ok=True)
    (out / "clips").mkdir(parents=True, exist_ok=True)
    (out / "diff").mkdir(parents=True, exist_ok=True)
    ts = [t for t in times(start, end, every) if t < info["duration"] - 0.1]
    items = [{"frame_id": frame_id_for(set_id, t), "time_s": t} for t in ts]

    def work(it):
        make_frame(video, it["time_s"], out / "frames" / f"{it['frame_id']}.jpg")
        make_clip(video, it["time_s"], out / "clips" / f"{it['frame_id']}.mp4", info["duration"])
        make_diff(video, it["time_s"], out / "diff" / f"{it['frame_id']}.jpg", info["duration"])
        return it["frame_id"]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, fid in enumerate(ex.map(work, items), 1):
            print(f"[{n}/{len(items)}] {fid}", flush=True)

    frames = []
    for it in items:
        fp = out / "frames" / f"{it['frame_id']}.jpg"
        cp = out / "clips" / f"{it['frame_id']}.mp4"
        dp = out / "diff" / f"{it['frame_id']}.jpg"
        cstart, clen = clip_window(it["time_s"], info["duration"])
        for f in (fp, cp, dp):
            if f.stat().st_size >= MAX_BYTES:
                raise RuntimeError(f"{f} is over 25 MiB")
        frames.append({"frame_id": it["frame_id"], "time_s": it["time_s"], "width": info["width"], "height": info["height"],
                       "frame_url": f"/label_sets/{set_id}/frames/{fp.name}", "clip_url": f"/label_sets/{set_id}/clips/{cp.name}",
                       "diff_url": f"/label_sets/{set_id}/diff/{dp.name}",
                       "clip_start_s": round(cstart, 3), "clip_length_s": round(clen, 3), "clip_count_s": round(it["time_s"] - cstart, 3)})
    manifest = {"set_id": set_id, "video": video.name, "video_width": info["width"], "video_height": info["height"],
                "start_s": start, "end_s": end, "every_s": every,
                "clip": {"before_s": CLIP_BEFORE_S, "after_s": CLIP_AFTER_S, "width": CLIP_WIDTH, "crf": CRF, "count_window_s": 1.0},
                "frames": frames}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description="Make frames, short clips and a manifest for the label page")
    p.add_argument("video")
    p.add_argument("--set", required=True, dest="set_id")
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--every", type=float, default=20.0)
    p.add_argument("--out", default=str(ROOT / "label_sets"))
    p.add_argument("--workers", type=int, default=3)
    a = p.parse_args(argv)
    try:
        m = build(Path(a.video), a.set_id, a.start, a.end, a.every, Path(a.out), a.workers)
    except (ValueError, RuntimeError, OSError) as e:
        print("make_label_set: " + str(e), file=sys.stderr)
        return 1
    total = sum(f.stat().st_size for f in (Path(a.out) / a.set_id).rglob("*") if f.is_file())
    print(f"{len(m['frames'])} frames, {total / 2**20:.0f} MiB in {Path(a.out) / a.set_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
