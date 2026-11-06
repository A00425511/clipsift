"""Static-object filter: marks detections on fixed things (pipe, pole, rocks) as static.

Runs AFTER detection and never deletes anything. A rejected box stays in results with
`static: true` and a `static_reason`; it is hidden by default and left out of suggested counts.

Three independent checks, each switched on or off in config (`static_filter`):
  1. persistence: a box that recurs at nearly the same place and size (IoU) in a high share of the
     sampled frames of one recording is treated as a fixed object. Adapts to a moved camera.
  2. movement: per-box score = 90th percentile of the absolute grey-level difference between the
     frame and a temporal median background built from frames either side of it (not the frame
     itself). Low score = nothing in the box changed.
  3. hand mask: polygons in original pixels, per camera or recording, for the pipe and pole.

Bias is toward keeping. High-confidence boxes are protected from checks 1 and 2, a persistent
place is kept if clearly moving, and movement is skipped (box kept) when it cannot be measured.

LIMITS. A truly still animal (a resting crab, a fish hovering in the current) can be removed by
checks 1 and 2, and a school that sits in one spot for a third of the recording could be flagged as
persistent. The detector only finds fish in the first place. Defaults were set on two frames and then
checked on one recording; see 2026 Problem Prep/detector-test/STATIC-FILTER.md. No torch needed here.
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

import cv2
import numpy as np

DEFAULTS = {
    "enabled": True,
    "persistence": {"enabled": True, "share": 0.30, "iou": 0.5, "min_frames": 6, "min_score": 0.05},
    "movement": {"enabled": True, "cutoff": 3.0, "percentile": 90.0, "width": 1920, "blur_sigma": 1.5,
                 "span_s": 5.0, "step_s": 1.0, "exclude_s": 0.75, "min_background_frames": 3,
                 "persistent_keep_above": 8.0},
    "protect_score": 0.5,
    "mask_overlap": 0.5,
    "masks": [],
}


def settings(cfg: dict | None) -> dict:
    """Defaults merged with config['static_filter'] (two levels deep)."""
    out = json.loads(json.dumps(DEFAULTS))
    for k, v in ((cfg or {}).get("static_filter") or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------- movement
def background_offsets(span_s: float, step_s: float, exclude_s: float) -> list:
    """Time offsets around the target for the background frames, never the target itself."""
    n = int(round(span_s / step_s))
    offs = [i * step_s for i in range(-n, n + 1)]
    return [o for o in offs if abs(o) >= exclude_s]


def _gray_small(frame, width: int, sigma: float):
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    if width and g.shape[1] > width:
        h = int(round(g.shape[0] * width / g.shape[1]))
        g = cv2.resize(g, (width, h), interpolation=cv2.INTER_AREA)
    g = g.astype(np.float32)
    return cv2.GaussianBlur(g, (0, 0), sigma) if sigma > 0 else g


def movement_map(still, others, width: int = 1920, sigma: float = 1.5, min_frames: int = 3):
    """Absolute grey-level difference between `still` and the temporal median of `others`, at `width`.
    Returns (map float32, scale = map width / still width), or (None, 1.0) when there are too few
    background frames of the same shape."""
    others = [f for f in others if f is not None and f.shape == still.shape]
    if len(others) < min_frames:
        return None, 1.0
    s = _gray_small(still, width, sigma)
    bg = np.median(np.stack([_gray_small(f, width, sigma) for f in others]), axis=0)
    return np.abs(s - bg), s.shape[1] / still.shape[1]


def box_movement(diff, box_xywh, scale: float, percentile: float = 90.0):
    """Percentile of the difference map inside a box given in original pixels. None if unmeasurable."""
    if diff is None:
        return None
    x, y, w, h = (float(v) * scale for v in box_xywh)
    x0, y0 = max(0, int(np.floor(x))), max(0, int(np.floor(y)))
    x1, y1 = min(diff.shape[1], int(np.ceil(x + w))), min(diff.shape[0], int(np.ceil(y + h)))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return float(np.percentile(diff[y0:y1, x0:x1], percentile))


def score_movement(timeline, t: float, still, dets: list, cfg: dict) -> None:
    """Set `movement` on each detection from frames around t read from the video. Only boxes are
    measured; nothing is changed or dropped. `still` is the original-resolution frame at t."""
    mc = settings(cfg)["movement"]
    if not mc["enabled"] or not dets:
        return
    lo, hi = 0.0, timeline.duration_s
    others = []
    for o in background_offsets(mc["span_s"], mc["step_s"], mc["exclude_s"]):
        if lo <= t + o <= hi:
            others.append(timeline.get_frame(t + o))
    diff, scale = movement_map(still, others, int(mc["width"]), float(mc["blur_sigma"]),
                               int(mc["min_background_frames"]))
    for d in dets:
        d.movement = box_movement(diff, d.box, scale, float(mc["percentile"]))


# --------------------------------------------------------------------- persistence
def persistence_shares(frames_xywh: list, iou: float = 0.5, chunk: int = 512) -> list:
    """For every box, the share of frames that hold a box with IoU >= `iou` with it (its own frame
    counts). frames_xywh: one (N, 4) array of [x, y, w, h] per sampled frame; empty frames count
    in the denominator. Returns one float array per frame."""
    n_frames = len(frames_xywh)
    arrs = [np.asarray(f, dtype=float).reshape(-1, 4) for f in frames_xywh]
    sizes = [len(a) for a in arrs]
    if not sum(sizes) or not n_frames:
        return [np.zeros(n) for n in sizes]
    B = np.vstack([a for a in arrs if len(a)])
    X0, Y0, X1, Y1 = B[:, 0], B[:, 1], B[:, 0] + B[:, 2], B[:, 1] + B[:, 3]
    area = np.maximum(B[:, 2], 0) * np.maximum(B[:, 3], 0)
    nonempty = [n for n in sizes if n]
    starts = np.concatenate([[0], np.cumsum(nonempty)[:-1]])
    shares = np.zeros(len(B))
    for c0 in range(0, len(B), chunk):
        sl = slice(c0, min(len(B), c0 + chunk))
        iw = np.clip(np.minimum(X1[sl, None], X1[None]) - np.maximum(X0[sl, None], X0[None]), 0, None)
        ih = np.clip(np.minimum(Y1[sl, None], Y1[None]) - np.maximum(Y0[sl, None], Y0[None]), 0, None)
        inter = iw * ih
        u = area[sl, None] + area[None] - inter
        io = inter / np.maximum(u, 1e-9)
        best = np.maximum.reduceat(io, starts, axis=1)  # best IoU with any box of each frame
        shares[sl] = (best >= iou).sum(axis=1) / n_frames
    out, k = [], 0
    for n in sizes:
        out.append(shares[k:k + n])
        k += n
    return out


# --------------------------------------------------------------------- hand mask
def polygons_for(masks: list, names: list, base_dir=None) -> tuple:
    """Pick polygons from config `masks` entries whose `match` (fnmatch, any of `names`) fits.
    An entry is {match: "T1-STAT2*", polygons: [[[x,y],...]]} or {match, file: mask.json}. Returns
    (polygons, reference size or None). Entries without `match` apply to every recording."""
    polys, ref = [], None
    for m in masks or []:
        pat = m.get("match")
        if pat and not any(fnmatch.fnmatch(n, pat) for n in names if n):
            continue
        ps = list(m.get("polygons") or [])
        if m.get("file"):
            p = Path(m["file"])
            if not p.is_absolute() and base_dir:
                p = Path(base_dir) / p
            data = json.loads(p.read_text(encoding="utf-8"))
            ps += data.get("polygons", [])
            if data.get("width") and data.get("height"):
                ref = (int(data["width"]), int(data["height"]))
        polys += ps
    return polys, ref


def raster_mask(polygons: list, width: int, height: int, ref=None, work_width: int = 960):
    """Polygons (original pixels) -> boolean mask at work_width. Returns (mask, scale)."""
    scale = min(1.0, work_width / float(width))
    mw, mh = max(1, int(round(width * scale))), max(1, int(round(height * scale)))
    m = np.zeros((mh, mw), np.uint8)
    if ref and ref != (width, height):  # polygons were drawn on a different frame size
        sx, sy = width / ref[0], height / ref[1]
        polygons = [[[p[0] * sx, p[1] * sy] for p in poly] for poly in polygons]
    for poly in polygons:
        pts = np.round(np.asarray(poly, dtype=float).reshape(-1, 2) * scale).astype(np.int32)
        if len(pts) >= 3:
            cv2.fillPoly(m, [pts], 1)
    return m > 0, scale


def in_mask(box_xywh, mask, scale: float, min_overlap: float = 0.5) -> bool:
    """True when at least `min_overlap` of the box area lies in the mask, or its centre does."""
    x, y, w, h = (float(v) * scale for v in box_xywh)
    x0, y0 = max(0, int(np.floor(x))), max(0, int(np.floor(y)))
    x1, y1 = min(mask.shape[1], int(np.ceil(x + w))), min(mask.shape[0], int(np.ceil(y + h)))
    if x1 <= x0 or y1 <= y0:
        return False
    cx, cy = int(min(mask.shape[1] - 1, max(0, x + w / 2))), int(min(mask.shape[0] - 1, max(0, y + h / 2)))
    return bool(mask[cy, cx]) or float(mask[y0:y1, x0:x1].mean()) >= min_overlap


# --------------------------------------------------------------------- the filter
def apply(frames: list, cfg: dict | None, width: int, height: int, names=(), base_dir=None) -> dict:
    """Mark detections in place. frames: list of (t, [Detection]) for every sampled frame of ONE
    recording (frames with no boxes included, they count towards the persistence share).
    Detections may carry `movement` already (score_movement). Returns a small summary dict.

    Reasons joined with "+": persistent, no_movement, mask. Any earlier static mark is reset first,
    so running twice gives the same answer."""
    sf = settings(cfg)
    summ = {"enabled": bool(sf["enabled"]), "frames": len(frames), "boxes": 0, "static": 0,
            "reasons": {}, "persistence_ran": False, "notes": []}
    all_d = [d for _, ds in frames for d in ds]
    summ["boxes"] = len(all_d)
    for d in all_d:
        d.static, d.static_reason = False, None
    if not sf["enabled"]:
        return summ
    pc, mc = sf["persistence"], sf["movement"]
    protect = sf.get("protect_score")

    shares = None
    if pc["enabled"]:
        if len(frames) >= int(pc["min_frames"]):
            arrs = [np.array([d.box for d in ds if d.score >= pc["min_score"]], float).reshape(-1, 4)
                    for _, ds in frames]
            sh = persistence_shares(arrs, float(pc["iou"]))
            shares = []
            for (_, ds), s in zip(frames, sh):
                it = iter(s)
                shares.append([next(it) if d.score >= pc["min_score"] else 0.0 for d in ds])
            summ["persistence_ran"] = True
        else:
            summ["notes"].append(f"Persistence skipped: {len(frames)} frames, needs {pc['min_frames']}.")

    polys, ref = polygons_for(sf["masks"], list(names), base_dir)
    mask = mscale = None
    if polys:
        mask, mscale = raster_mask(polys, width, height, ref)

    for fi, (_, ds) in enumerate(frames):
        for di, d in enumerate(ds):
            why = []
            if mask is not None and in_mask(d.box, mask, mscale, float(sf["mask_overlap"])):
                why.append("mask")
            protected = protect is not None and d.score >= protect
            if not protected:
                moving = d.movement is not None and d.movement >= float(mc["persistent_keep_above"])
                if shares is not None and shares[fi][di] >= float(pc["share"]) and not moving:
                    why.append("persistent")
                if mc["enabled"] and d.movement is not None and d.movement < float(mc["cutoff"]):
                    why.append("no_movement")
            if why:
                d.static, d.static_reason = True, "+".join(why)
                summ["static"] += 1
                for r in why:
                    summ["reasons"][r] = summ["reasons"].get(r, 0) + 1
    return summ


def live(dets) -> list:
    """Detections that are not static. Accepts Detection objects or dicts (older results have no flag)."""
    return [d for d in dets if not (d.get("static") if isinstance(d, dict) else getattr(d, "static", False))]


# --------------------------------------------------------------------- mask suggestion
def suggest_polygons(boxes_xywh, width: int, height: int, pad: float = 0.25, work_width: int = 960,
                     min_area_frac: float = 0.0) -> list:
    """Polygons covering the given boxes (padded by `pad` of their size, merged where they touch), in
    original pixels. For a person to check and edit, not to trust."""
    scale = min(1.0, work_width / float(width))
    mw, mh = max(1, int(round(width * scale))), max(1, int(round(height * scale)))
    m = np.zeros((mh, mw), np.uint8)
    for x, y, w, h in boxes_xywh:
        x0, y0 = int(round((x - pad * w) * scale)), int(round((y - pad * h) * scale))
        x1, y1 = int(round((x + w + pad * w) * scale)), int(round((y + h + pad * h) * scale))
        m[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        if cv2.contourArea(c) < min_area_frac * mw * mh:
            continue
        ap = cv2.approxPolyDP(c, 2.0, True).reshape(-1, 2) / scale
        if len(ap) >= 3:
            out.append([[round(float(px), 1), round(float(py), 1)] for px, py in ap])
    return out
