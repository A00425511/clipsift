"""Make a SYNTHETIC murky-water test clip with known ground truth. Not real footage.

Drifting particles, swaying 'kelp', gentle camera shake, quiet stretches, a few faint moving
blobs (two 'fish' passes, a pair of fish together) and one slow low-contrast blob imitating a
cryptic crab. Ground truth goes to <out>.json. Event times are fractions of the duration,
so short clips work too (for tests).

    python tools/make_synthetic_clip.py out.mp4 --duration 60 --width 640 --fps 12
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def make(out, duration=60.0, width=640, fps=12.0, seed=7):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    W, H = int(width), int(width * 9 / 16) // 2 * 2
    W -= W % 2
    n = int(duration * fps)
    # murky green-brown background with low-frequency texture
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    base = 70 + 30 * (1 - yy) + cv2.resize(rng.normal(0, 6, (6, 8)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    base = np.stack([base * 0.85, base * 1.0, base * 0.8], axis=2)
    # events as fractions of the duration: (name, kind, f_start, f_end, contrast, size(w,h), y_frac, dir)
    events = [
        dict(id="fish_1", kind="fish", f0=0.17, f1=0.28, contrast=45, size=[46, 18], y=0.40, dir=1),
        dict(id="fish_2", kind="fish", f0=0.50, f1=0.63, contrast=40, size=[44, 18], y=0.30, dir=-1),
        dict(id="fish_3", kind="fish", f0=0.52, f1=0.65, contrast=40, size=[40, 16], y=0.55, dir=1),
        dict(id="crab_slow", kind="cryptic_crab_like", f0=0.76, f1=0.97, contrast=-22, size=[34, 22], y=0.78, dir=1, slow=True),
    ]
    px = rng.uniform(0, W, 120); py = rng.uniform(0, H, 120)
    pv = rng.uniform(-6, 6, (2, 120)) / fps * 2
    kelp_x = [int(W * f) for f in (0.08, 0.15, 0.9)]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp = out.with_suffix(".tmp.mp4")
    vw = cv2.VideoWriter(str(tmp), fourcc, fps, (W, H))
    shake = np.zeros(2)
    gt_frames = []
    for i in range(n):
        t = i / fps
        f = base.copy()
        f += 3 * np.sin(2 * np.pi * t / 25)  # slow haze brightness drift
        for kx in kelp_x:  # swaying kelp: thin dark strands
            pts = [(int(kx + 2.5 * np.sin(2 * np.pi * (t / 3.0) + k * 0.4) * k / 8), H - k * 6) for k in range(0, 14)]
            cv2.polylines(f, [np.array(pts, np.int32)], False, (58, 72, 52), 3)
        px = (px + pv[0]) % W; py = (py + pv[1]) % H
        for x, y in zip(px, py):
            cv2.circle(f, (int(x), int(y)), 1, (120, 130, 115), -1)
        present = []
        for ev in events:
            a, b = ev["f0"] * duration, ev["f1"] * duration
            if a <= t <= b:
                u = (t - a) / (b - a)
                span = 0.25 if ev.get("slow") else 0.8
                x = W * (0.1 + span * u) if ev["dir"] > 0 else W * (0.9 - span * u)
                y = H * ev["y"] + 4 * np.sin(2 * np.pi * t / 2.0)
                m = np.zeros((H, W), np.float32)
                cv2.ellipse(m, (int(x), int(y)), (ev["size"][0] // 2, ev["size"][1] // 2), 0, 0, 360, 1.0, -1)
                m = cv2.GaussianBlur(m, (7, 7), 0)
                f += ev["contrast"] * m[:, :, None]
                present.append(ev["id"])
        shake += rng.normal(0, 0.35, 2)
        shake *= 0.9
        M = np.float32([[1, 0, shake[0]], [0, 1, shake[1]]])
        f = cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        f += rng.normal(0, 2.5, f.shape).astype(np.float32)
        vw.write(np.clip(f, 0, 255).astype(np.uint8))
        gt_frames.append(len(present))
    vw.release()
    # re-encode to H.264 if ffmpeg exists, otherwise keep mp4v
    import shutil, subprocess
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-c:v", "libx264", "-crf", "20",
                        "-pix_fmt", "yuv420p", str(out)], check=True)
        tmp.unlink()
    else:
        tmp.replace(out)
    gt = {"synthetic": True, "note": "SYNTHETIC test clip, not real footage. Known ground truth.",
          "duration_s": duration, "fps": fps, "width": W, "height": H, "seed": seed,
          "events": [{"id": e["id"], "kind": e["kind"], "start_s": e["f0"] * duration, "end_s": e["f1"] * duration,
                      "contrast": e["contrast"], "size_px": e["size"], "slow": bool(e.get("slow"))} for e in events],
          "max_simultaneous": int(max(gt_frames)),
          "quiet_periods_s": [[0, events[0]["f0"] * duration], [events[0]["f1"] * duration, events[1]["f0"] * duration],
                              [events[2]["f1"] * duration, events[3]["f0"] * duration]]}
    out.with_suffix(".json").write_text(json.dumps(gt, indent=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    print(make(a.out, a.duration, a.width, a.fps, a.seed))
