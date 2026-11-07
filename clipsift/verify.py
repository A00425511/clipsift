"""End-of-run review set: a mix of model flags, for a person to check.

This runs after counting, because model hints can sway a count. It never changes a count, MeanCount or
a species list. What people decide here is saved separately as possible training data for the detector.

The set mixes three sources:
  agree        The model flagged something the counter marked.
  model_only   The model flagged something at a count point that the counter did not mark.
  elsewhere    The model flagged something between the count points, where nobody counted.

The reviewer does not see which source an item came from until they have decided. The numbers below are
starting values, not tested ones. The detector is whatever get_backend gives, so a better model can drop in.
"""
from __future__ import annotations

import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import cv2

from . import static_filter as sfm
from .video import find_ffmpeg, resize_to_width

SET_VERSION = 1
SOURCES = ("agree", "model_only", "elsewhere")
MIX = {"agree": 0.34, "model_only": 0.33, "elsewhere": 0.33}
MIN_SCORE = 0.10          # the same threshold as the old suggested count
MATCH_RADIUS = 60 / 3840  # share of frame width, as in tools/eval_detector.py
MATCH_PAD = 20 / 3840
SETTINGS = {"crop_px": 480, "frame_width": 1280, "clip_width": 960, "clip_half_s": 2.5, "max_elsewhere_frames": 14}


def read_marks(run_dir: Path) -> dict:
    """Live fish and invertebrate marks by the first counter of each point: {subsample_id: [mark]}."""
    def rows(name):
        path = run_dir / name
        if not path.is_file():
            return []
        out = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out
    first = {r.get("subsample_id"): r.get("counter") for r in rows("subsample_reviews.jsonl") if r.get("pass") == "primary"}
    live = {}
    for r in rows("point_labels.jsonl"):
        if r.get("op") == "remove":
            live.pop(r.get("label_id"), None)
        elif r.get("label_id"):
            live[r["label_id"]] = r
    marks: dict = {}
    for r in live.values():
        if r.get("kind") in ("fish", "invertebrate") and r.get("counter") == first.get(r.get("subsample_id")):
            marks.setdefault(r["subsample_id"], []).append(r)
    return marks


def mark_centre(m: dict):
    return (m["x"] + m["w"] / 2, m["y"] + m["h"] / 2) if m.get("w") is not None else (m["x"], m["y"])


def match(boxes: list, marks: list, width: int):
    """One-to-one, best score first. boxes are [x, y, w, h] with a score. Returns (pairs, loose boxes, loose marks)."""
    radius, pad = MATCH_RADIUS * width, MATCH_PAD * width
    left, pairs, loose = list(marks), [], []
    for det in sorted(boxes, key=lambda d: -d.score):
        x, y, w, h = det.box
        cx, cy = x + w / 2, y + h / 2
        hit, best = None, float("inf")
        for m in left:
            mx, my = mark_centre(m)
            gap = ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5
            inside = x - pad <= mx <= x + w + pad and y - pad <= my <= y + h + pad
            if (inside or gap <= radius) and gap < best:
                hit, best = m, gap
        if hit is None:
            loose.append(det)
        else:
            left.remove(hit)
            pairs.append((det, hit))
    return pairs, loose, left


def _xyxy(box) -> list:
    x, y, w, h = box
    return [int(x), int(y), int(x + w), int(y + h)]


def _iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def choose(pools: dict, total: int, seed: str) -> list:
    """Take each source's share. A source that runs short passes its places to the others. Within a source,
    picks spread across the scores, so the set isn't only the model's most confident guesses."""
    rng = random.Random(seed)
    want = {s: round(total * MIX[s]) for s in SOURCES}
    want["elsewhere"] += total - sum(want.values())
    take = {s: min(want[s], len(pools.get(s, []))) for s in SOURCES}
    spare = total - sum(take.values())
    while spare > 0:
        room = [s for s in SOURCES if take[s] < len(pools.get(s, []))]
        if not room:
            break
        for s in room[:spare]:
            take[s] += 1
            spare -= 1
    out = []
    for s in SOURCES:
        pool = sorted(pools.get(s, []), key=lambda i: i["max_confidence"] or 0)
        n = take[s]
        if n:
            cuts = [int(i * len(pool) / n) for i in range(n + 1)]   # n bands that never overlap, so nothing is picked twice
            out += [pool[rng.randrange(a, b)] for a, b in zip(cuts, cuts[1:])]
    rng.shuffle(out)
    return out


def _write_images(item: dict, frame, scale: float, files: Path, cfg: dict) -> None:
    """frame may be smaller than the recording, so bbox (recording pixels) is scaled to fit it."""
    x1, y1, x2, y2 = (int(v * scale) for v in item["bbox"])
    h, w = frame.shape[:2]
    pad = max(40, x2 - x1, y2 - y1)
    cx, cy = max(0, x1 - pad), max(0, y1 - pad)
    crop = frame[cy:min(h, y2 + pad), cx:min(w, x2 + pad)]
    if crop.size:
        k = cfg["crop_px"] / max(crop.shape[:2])
        crop = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
        # a crop can hold several fish, so the box says which one the question is about
        cv2.rectangle(crop, (int((x1 - cx) * k), int((y1 - cy) * k)), (int((x2 - cx) * k), int((y2 - cy) * k)), (77, 233, 255), 2)
    marked = frame.copy()
    cv2.rectangle(marked, (x1, y1), (x2, y2), (77, 233, 255), max(3, w // 400))
    name = item["id"]
    cv2.imwrite(str(files / f"{name}_crop.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(str(files / f"{name}_frame.jpg"), resize_to_width(marked, cfg["frame_width"]), [cv2.IMWRITE_JPEG_QUALITY, 82])
    item["images"] = {"crop": f"{name}_crop.jpg", "frame": f"{name}_frame.jpg"}


def _cut(source: Path, out: Path, start: float, length: float, width: int) -> bool:
    ff = find_ffmpeg()
    if not ff or not source.is_file():
        return False
    cmd = [ff, "-y", "-loglevel", "error", "-ss", f"{max(0.0, start):.2f}", "-i", str(source), "-t", f"{length:.2f}",
           "-an", "-vf", f"scale={width}:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", str(out)]
    return subprocess.run(cmd, capture_output=True).returncode == 0 and out.is_file()


def build_review_set(run_dir, cfg: dict, detector=None, total: int = 36, log=print, settings: dict = SETTINGS) -> dict:
    """Write review_set/bank.json and its images, in the same shape as the species bank, and return it."""
    run_dir = Path(run_dir)
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    rec, pc = results.get("recording") or {}, results.get("protocol") or {}
    subs = sorted([s for s in results.get("subsamples") or [] if isinstance(s, dict)], key=lambda s: s.get("t_s") or 0)
    if detector is None:
        from .stages import get_backend
        detector = get_backend("detector", cfg["stages"]["detector"], cfg)
    marks = read_marks(run_dir)
    window = run_dir / "window.mp4"
    cap = cv2.VideoCapture(str(window)) if window.is_file() else None
    start = pc.get("window_start_s") or 0.0
    gaps = [round((a["t_s"] + b["t_s"]) / 2, 2) for a, b in zip(subs, subs[1:])][:settings["max_elsewhere_frames"]] if cap else []
    n_frames = len(subs) + len(gaps)

    frames, stills = [], {}
    width, height = rec.get("width"), rec.get("height")
    for i, s in enumerate(subs):
        log(f"checking frame {i + 1} of {n_frames}")
        img = cv2.imread(str(run_dir / "subsamples" / s["subsample_id"] / "still.jpg"))
        if img is None:
            continue
        width, height = width or img.shape[1], height or img.shape[0]
        stills[s["subsample_id"]] = img
        frames.append((s["t_s"], detector.detect(img, s["t_s"])))
    summary = sfm.apply(frames, cfg, width, height)
    fixed = [_xyxy(d.box) for _, ds in frames for d in ds if getattr(d, "static", False)]

    pools: dict = {s: [] for s in SOURCES}

    def add(source, sid, t, bbox, score, kept=None):
        n = sum(len(v) for v in pools.values())
        pools[source].append({"id": f"r{n:04d}", "source": source, "subsample_id": sid, "time_s": round(float(t), 2),
                              "point_s": t if sid else None, "bbox": bbox, "max_confidence": None if score is None else round(float(score), 3),
                              "flags": [], "reasons": [], "other_views": [], **(kept or {})})

    ids = [s["subsample_id"] for s in subs if s["subsample_id"] in stills]
    for sid, (t, dets) in zip(ids, frames):
        boxes = [d for d in sfm.live(dets) if d.score >= MIN_SCORE]
        pairs, loose, _ = match(boxes, marks.get(sid, []), width)
        for det, m in pairs:
            add("agree", sid, t, _xyxy(det.box), det.score, {"kind_marked": m.get("kind"), "species_marked": m.get("species")})
        for det in loose:
            add("model_only", sid, t, _xyxy(det.box), det.score)

    between = {}
    for i, t in enumerate(gaps):
        log(f"checking frame {len(subs) + i + 1} of {n_frames}")
        cap.set(cv2.CAP_PROP_POS_MSEC, (t - start) * 1000)
        ok, img = cap.read()
        if not ok:
            continue
        between[t] = img
        k = width / img.shape[1]
        for det in detector.detect(img, t):
            if det.score < MIN_SCORE:
                continue
            bbox = [int(v * k) for v in _xyxy(det.box)]
            if not any(_iou(bbox, f) > 0.3 for f in fixed):
                add("elsewhere", None, t, bbox, det.score)
    if cap:
        cap.release()

    log("saving images")
    out_dir = run_dir / "review_set"
    files = out_dir / "files"
    files.mkdir(parents=True, exist_ok=True)
    items = choose(pools, total, str(rec.get("recording_id") or run_dir.name))
    for item in items:
        sid = item["subsample_id"]
        frame = stills[sid] if sid else between[item["time_s"]]
        _write_images(item, frame, frame.shape[1] / width, files, settings)
        clip = files / (f"clip_{sid}.mp4" if sid else f"clip_{item['id']}.mp4")
        if not clip.is_file():
            half = settings["clip_half_s"]
            if sid:
                s = next(x for x in subs if x["subsample_id"] == sid)
                _cut(run_dir / "subsamples" / sid / "context.mp4", clip, s["t_s"] - s["context_start_s"] - half, 2 * half, settings["clip_width"])
            else:
                _cut(window, clip, item["time_s"] - start - half, 2 * half, settings["clip_width"])
        if clip.is_file():
            item["images"]["clip"] = clip.name
    bank = {
        "version": SET_VERSION, "kind": "review_set",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"type": "review_set", "model": getattr(detector, "model_version", None) or getattr(detector, "source", None),
                   "width": width, "height": height, "points": len(ids), "frames_between": len(between)},
        "note": "Items for a person to check. They never change a count. Decisions may become training data.",
        "pools": {s: len(pools[s]) for s in SOURCES},
        "fixed_objects_left_out": summary.get("static", 0),
        "counts": {s: sum(i["source"] == s for i in items) for s in SOURCES} | {"total": len(items)},
        "items": items,
    }
    tmp = out_dir / "bank.json.tmp"
    tmp.write_text(json.dumps(bank, indent=1), encoding="utf-8")
    tmp.replace(out_dir / "bank.json")
    return bank
