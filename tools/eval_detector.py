"""Score detector boxes against human dots, always beside a random-placement chance baseline.

Frame mode (runs the detector on a frame):
    python tools/eval_detector.py --frame labels/verified/T1-STAT2_411_t1320.303.png \\
        --labels labels/verified/T1-STAT2_411_t1320.303.json --variant medium --enhancement clahe
Run mode (scores detections already stored in a run):
    python tools/eval_detector.py --run runs/coastal_t1s2_cfd/results.json --labels labels/team/set1/points.csv
Reproduce the earlier one-frame test through the integrated backend:
    python tools/eval_detector.py --reproduce

Labels: dots JSON as in labels/verified/ ({"time_s", "points": [{"x","y","kind"}]}), or a CSV with
columns x, y (original pixels) and optionally kind plus one of subsample_id, image or time_s to say
which frame a dot belongs to (the shape labels/team/<set>/points.csv is expected to take).

Matching, as in the one-frame test (chance.py): a dot is a hit when an unused box contains it with
a 20 px margin, or the box centre is within 60 px; each box is used once. Strict: box centre within
25 px of the dot or the dot inside the box with no margin. Only boxes whose centre is above the
lowest dot plus 80 px are scored, because dots were only placed in the upper part of the frame.
Chance: the same box sizes placed uniformly at random in that labelled area, averaged over 30 tries.

This is one frame of a dense school and thresholds are chosen on the same frame. It says nothing
about other sites, crabs or low-visibility water. Do not quote it as accuracy.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LENIENT = dict(rad=60.0, pad=20.0)
STRICT = dict(rad=25.0, pad=0.0)
Y_MARGIN = 80.0
N_CHANCE = 30

# Earlier one-frame results (RESULTS.md), for the --reproduce check. boxes, recall, precision,
# strict recall, strict precision, chance recall, chance precision.
EARLIER = {
    ("nano", "none", 0.05): (73, .45, .63, .41, .58, .20, .28),
    ("medium", "clahe", 0.05): (133, .61, .47, .51, .40, .31, .24),
}


# --------------------------------------------------------------------- scoring
def match_hits(boxes_xyxy, dots, rad=60.0, pad=20.0) -> int:
    """Greedy: for each dot in order, take the nearest unused box that contains it (with pad) or
    whose centre is within rad. Returns the number of hit dots."""
    B = np.asarray(boxes_xyxy, dtype=float).reshape(-1, 4)
    if not len(B) or not len(dots):
        return 0
    C = np.c_[(B[:, 0] + B[:, 2]) / 2, (B[:, 1] + B[:, 3]) / 2]
    used = np.zeros(len(B), bool)
    hits = 0
    for x, y in dots:
        inside = (B[:, 0] - pad <= x) & (x <= B[:, 2] + pad) & (B[:, 1] - pad <= y) & (y <= B[:, 3] + pad)
        d = np.hypot(C[:, 0] - x, C[:, 1] - y)
        ok = (inside | (d < rad)) & ~used
        if ok.any():
            j = int(np.where(ok, d, np.inf).argmin())
            used[j] = True
            hits += 1
    return hits


def labelled_area(dots, width):
    """x range is the whole width; y range is from the top dot minus a margin to the bottom dot plus a margin."""
    P = np.asarray(dots, dtype=float).reshape(-1, 2)
    return max(0.0, P[:, 1].min() - Y_MARGIN), P[:, 1].max() + Y_MARGIN


def chance_hits(boxes_xyxy, dots, width, rng, n_try=N_CHANCE, **match):
    """Mean hits when the same box sizes are placed at random in the labelled area."""
    B = np.asarray(boxes_xyxy, dtype=float).reshape(-1, 4)
    if not len(B) or not len(dots):
        return 0.0
    y0, y1 = labelled_area(dots, width)
    w, h = B[:, 2] - B[:, 0], B[:, 3] - B[:, 1]
    tot = []
    for _ in range(n_try):
        cx = rng.uniform(0, width, len(B))
        cy = rng.uniform(y0, y1, len(B))
        R = np.c_[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        tot.append(match_hits(R, dots, **match))
    return float(np.mean(tot))


def score_frames(frames, thr, seed=1) -> dict:
    """frames: list of dicts {boxes: Nx4 xyxy, scores: N, dots: Mx2, width: int}. One threshold.
    Counts are pooled over frames. Returns real, strict and chance numbers."""
    rng = np.random.default_rng(seed)
    n_box = n_dot = hit = hit_s = 0
    ch = ch_s = 0.0
    errs = []
    for f in frames:
        B = np.asarray(f["boxes"], dtype=float).reshape(-1, 4)
        S = np.asarray(f["scores"], dtype=float).reshape(-1)
        dots = np.asarray(f["dots"], dtype=float).reshape(-1, 2)
        _, ymax = labelled_area(dots, f["width"]) if len(dots) else (0, 0)
        keep = S >= thr
        B = B[keep]
        if len(B):
            B = B[(B[:, 1] + B[:, 3]) / 2 < ymax]
        n_box += len(B)
        n_dot += len(dots)
        hit += match_hits(B, dots, **LENIENT)
        hit_s += match_hits(B, dots, **STRICT)
        ch += chance_hits(B, dots, f["width"], rng, **LENIENT)
        ch_s += chance_hits(B, dots, f["width"], rng, **STRICT)
        errs.append(len(B) - len(dots))
    div = lambda a, b: a / b if b else float("nan")  # noqa: E731
    return {"threshold": thr, "boxes": n_box, "dots": n_dot, "frames": len(frames),
            "recall": div(hit, n_dot), "precision": div(hit, n_box),
            "strict_recall": div(hit_s, n_dot), "strict_precision": div(hit_s, n_box),
            "chance_recall": div(ch, n_dot), "chance_precision": div(ch, n_box),
            "chance_strict_recall": div(ch_s, n_dot), "chance_strict_precision": div(ch_s, n_box),
            "count_error": n_box - n_dot,  # boxes minus dots, summed over frames (signed)
            "count_error_pct": 100.0 * div(n_box - n_dot, n_dot),
            "mean_abs_count_error": float(np.mean(np.abs(errs))) if errs else float("nan")}


def sweep(frames, thresholds, seed=1) -> list:
    return [score_frames(frames, t, seed) for t in thresholds]


def format_table(rows, title="") -> str:
    out = [title] if title else []
    out.append("thr    boxes dots | real R   P    | strict R   P  | CHANCE R   P  | CHANCE strict R   P | count error")
    for r in rows:
        out.append(f"{r['threshold']:<6.3f} {r['boxes']:>5} {r['dots']:>4} | {r['recall']:.2f} {r['precision']:.2f}"
                   f"     | {r['strict_recall']:.2f} {r['strict_precision']:.2f}    | "
                   f"{r['chance_recall']:.2f} {r['chance_precision']:.2f}      | "
                   f"{r['chance_strict_recall']:.2f} {r['chance_strict_precision']:.2f}             | "
                   f"{r['count_error']:+d} ({r['count_error_pct']:+.0f}%)")
    out.append("R = recall, P = precision. CHANCE = same box sizes placed at random in the labelled area "
               "(mean of 30). A result near chance means no signal. One-frame scores, not accuracy.")
    return "\n".join(out)


# --------------------------------------------------------------------- labels
def load_dots_json(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    pts = [(p["x"], p["y"]) for p in d["points"] if p.get("kind", "fish") in ("fish", "animal_point")]
    return {"time_s": d.get("time_s"), "dots": np.array(pts, dtype=float)}


def load_points_csv(path) -> dict:
    """Returns {group_key: {"time_s":..., "dots": Nx2}}. group_key is subsample_id, image, or time_s."""
    groups: dict = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("kind") or "fish") in ("invertebrate", "crab"):
                continue
            key = r.get("subsample_id") or r.get("image") or r.get("frame") or r.get("time_s") or "all"
            g = groups.setdefault(key, {"time_s": float(r["time_s"]) if r.get("time_s") else None, "dots": []})
            g["dots"].append((float(r["x"]), float(r["y"])))
    for g in groups.values():
        g["dots"] = np.array(g["dots"], dtype=float)
    return groups


# --------------------------------------------------------------------- sources of boxes
def boxes_from_detector(frame_path, cfg, thr_min):
    import cv2
    from clipsift.stages import get_backend
    cfg["detector"]["cfd"]["threshold"] = thr_min
    cfg["stages"]["detector"] = "cfd"
    det = get_backend("detector", "cfd", cfg)
    img = cv2.imread(str(frame_path))
    if img is None:
        raise FileNotFoundError(f"Cannot read frame: {frame_path}")
    import time
    t0 = time.perf_counter()
    dets = det.detect(img, 0.0)
    dt = time.perf_counter() - t0
    B = np.array([[d.box[0], d.box[1], d.box[0] + d.box[2], d.box[1] + d.box[3]] for d in dets], dtype=float)
    S = np.array([d.score for d in dets], dtype=float)
    return B.reshape(-1, 4), S, img.shape[1], {"model_version": det.model_version, "seconds": dt,
                                               "device": getattr(det, "device", None)}


def frames_from_run(results_path, labels, include_static=False):
    res = json.loads(Path(results_path).read_text(encoding="utf-8"))
    width = res["recording"]["width"]
    sss = res["subsamples"]
    frames, used = [], []
    for key, g in labels.items():
        ss = next((s for s in sss if s["subsample_id"] == key), None)
        if ss is None and g.get("time_s") is not None:
            ss = min(sss, key=lambda s: abs(s["t_s"] - g["time_s"]))
            if abs(ss["t_s"] - g["time_s"]) > 1.0:
                ss = None
        if ss is None:
            raise ValueError(f"Labels group '{key}' matches no subsample in the run. Give a subsample_id or "
                             "time_s column that falls within 1 s of a subsample point.")
        dets = [d for d in ss["auto"]["detections"] if include_static or not d.get("static")]
        B = np.array([[d["box"][0], d["box"][1], d["box"][0] + d["box"][2], d["box"][1] + d["box"][3]]
                      for d in dets], dtype=float).reshape(-1, 4)
        frames.append({"boxes": B, "scores": [d["score"] for d in dets], "dots": g["dots"], "width": width})
        used.append(ss["subsample_id"])
    return frames, used, res["run"].get("model_version")


# --------------------------------------------------------------------- cli
def _cfg(args):
    from clipsift.config import load_config
    ov = {"detector": {"cfd": {}}}
    c = ov["detector"]["cfd"]
    for k, v in (("variant", args.variant), ("enhancement", args.enhancement), ("tile_size", args.tile),
                 ("overlap", args.overlap), ("device", args.device), ("weights", args.weights)):
        if v is not None:
            c[k] = v
    cfg = load_config(ROOT / "config" / "presets" / f"{args.preset}.yaml" if args.preset else None, ov)
    return cfg


def _thresholds(s):
    return [float(x) for x in s.split(",")]


def reproduce(args) -> int:
    frame = ROOT / "labels/verified/T1-STAT2_411_t1320.303.png"
    lab = load_dots_json(frame.with_suffix(".json"))
    print(f"Reproducing earlier one-frame results on {frame.name} ({len(lab['dots'])} dots)")
    print("Earlier numbers are from RESULTS.md (scripts evalcfd.py, eval2.py, chance.py). Differences below.\n")
    from clipsift.config import load_config
    for (variant, enh, thr), exp in EARLIER.items():
        cfg = load_config(None, {"detector": {"cfd": {"variant": variant, "enhancement": enh, "tile_size": 512,
                                                      "overlap": 0.25, "device": args.device or "auto"}}})
        B, S, W, info = boxes_from_detector(frame, cfg, min(0.03, thr))
        fr = [{"boxes": B, "scores": S, "dots": lab["dots"], "width": W}]
        rows = sweep(fr, [0.03, thr])
        print(format_table(rows, f"{variant}, {enh}, 512 px tiles, overlap 0.25 ({info['model_version']}, "
                                 f"device {info['device']}, {info['seconds']:.1f} s for the frame)"))
        r = next(x for x in rows if abs(x["threshold"] - thr) < 1e-9)
        got = (r["boxes"], r["recall"], r["precision"], r["strict_recall"], r["strict_precision"],
               r["chance_recall"], r["chance_precision"])
        names = ("boxes", "recall", "precision", "strict recall", "strict precision", "chance recall",
                 "chance precision")
        print(f"  at threshold {thr}: " + "; ".join(
            f"{n} {g:.2f} (earlier {e:.2f})" if n != "boxes" else f"boxes {g} (earlier {e})"
            for n, g, e in zip(names, got, exp)) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score boxes against dots, with a chance baseline.")
    ap.add_argument("--frame"); ap.add_argument("--run"); ap.add_argument("--labels")
    ap.add_argument("--reproduce", action="store_true")
    ap.add_argument("--thresholds", type=_thresholds, default=[0.03, 0.05, 0.1, 0.2, 0.3])
    ap.add_argument("--preset"); ap.add_argument("--variant"); ap.add_argument("--enhancement")
    ap.add_argument("--tile", type=int); ap.add_argument("--overlap", type=float)
    ap.add_argument("--include-static", action="store_true",
                    help="with --run: also score boxes the static filter rejected (default: leave them out)")
    ap.add_argument("--device"); ap.add_argument("--weights"); ap.add_argument("--json", help="write rows here")
    a = ap.parse_args(argv)
    try:
        if a.reproduce:
            return reproduce(a)
        if not a.labels or bool(a.frame) == bool(a.run):
            ap.error("give --labels and exactly one of --frame or --run (or use --reproduce)")
        if a.frame:
            lab = load_dots_json(a.labels) if a.labels.endswith(".json") else next(iter(load_points_csv(a.labels).values()))
            B, S, W, info = boxes_from_detector(a.frame, _cfg(a), min(a.thresholds))
            frames = [{"boxes": B, "scores": S, "dots": lab["dots"], "width": W}]
            head = f"{Path(a.frame).name}: {info['model_version']}, device {info['device']}, {info['seconds']:.1f} s"
        else:
            groups = {"all": load_dots_json(a.labels)} if a.labels.endswith(".json") else load_points_csv(a.labels)
            if a.labels.endswith(".json"):
                groups = {"json": groups["all"]}
            frames, used, mv = frames_from_run(a.run, groups, a.include_static)
            head = f"run {a.run}: {mv}; frames {used}. Thresholds below the run's own are not meaningful."
        rows = sweep(frames, a.thresholds)
        print(format_table(rows, head))
        if a.json:
            Path(a.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return 0
    except (FileNotFoundError, ValueError, ImportError) as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
