"""Evaluate the static-object filter on the T1-STAT2 label set and the labelled 22:00 frame.

Two steps, so the slow part runs once:
  python tools/eval_static_filter.py detect --video "../Coastal Footage/T1-STAT2 411.MP4" --cache CACHE_DIR
      Runs the Nano detector (threshold 0.05) on label_sets/t1s2_v1 frames (read from the video at the
      listed times) and on labels/verified/*.png, scores a movement value per box, saves one JSON per frame.
      Options: --every N (use every Nth frame), --limit N.
  python tools/eval_static_filter.py report --cache CACHE_DIR [--frame-boxes OUT.json]
      Applies the filter with the default settings, prints recall and precision before and after (strict
      matching, chance and box-shift controls), boxes per frame, the empty-frame checks, and a settings sweep.

Everything is scored on the same few frames the settings were looked at on. Small sample. Not accuracy.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from eval_detector import STRICT, chance_hits, labelled_area, load_dots_json, match_hits  # noqa: E402

LABEL_ID = "T1-STAT2_411_t1320.303"
EMPTY_TIMES = [140, 160, 900, 1220, 1240, 1500, 1560]  # Jacob marked these as no fish (one person's labels)
THRS = (0.05, 0.1)


# --------------------------------------------------------------------- detect step
def cmd_detect(a) -> int:
    import cv2
    from clipsift import static_filter as sfm
    from clipsift.config import load_config
    from clipsift.stages import get_backend
    from clipsift.video import Timeline
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    cfg = load_config(None, {"detector": {"cfd": {"variant": "nano", "threshold": 0.05, "tile_size": 512,
                                                   "overlap": 0.25, "device": a.device}}})
    det = get_backend("detector", "cfd", cfg)
    tl = Timeline([Path(a.video)])
    man = json.loads((ROOT / "label_sets/t1s2_v1/manifest.json").read_text(encoding="utf-8"))
    items = [(f["frame_id"], float(f["time_s"]), None) for f in man["frames"]][::a.every]
    if a.limit:
        items = items[:a.limit]
    lab = ROOT / f"labels/verified/{LABEL_ID}.png"
    items.append((LABEL_ID, 1320.303, lab))
    for fid, t, png in items:
        out = cache / f"{fid}.json"
        if out.exists():
            continue
        t0 = time.perf_counter()
        still = cv2.imread(str(png)) if png else tl.get_frame(t)
        if still is None:
            print("no frame", fid, t)
            continue
        dets = det.detect(still, t)
        t1 = time.perf_counter()
        sfm.score_movement(tl, t, still, dets, cfg)
        t2 = time.perf_counter()
        out.write_text(json.dumps({"frame_id": fid, "time_s": t, "width": still.shape[1], "height": still.shape[0],
                                   "detect_s": t1 - t0, "movement_s": t2 - t1,
                                   "boxes": [[*d.box, d.score, d.movement] for d in dets]}), encoding="utf-8")
        print(f"{fid} t={t:.1f}: {len(dets)} boxes, detect {t1 - t0:.1f}s, movement {t2 - t1:.1f}s", flush=True)
    return 0


# --------------------------------------------------------------------- report helpers
def load_cache(cache):
    fr = []
    for p in sorted(Path(cache).glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        fr.append(d)
    # The 20 s grid only (60 to 2040 s) plus the labelled frame. The label set manifest can also carry extra
    # frames added later; they would crowd the pool around the school, so they are left out of the pool.
    fr = [d for d in fr if d["frame_id"] == LABEL_ID or abs(d["time_s"] / 20 - round(d["time_s"] / 20)) < 1e-6]
    fr.sort(key=lambda d: d["time_s"])
    return fr


def run_filter(frames, cfg_over, pool_ids=None):
    """Apply the filter over the pool of frames (default all). Returns {frame_id: [Detection]}."""
    from clipsift import static_filter as sfm
    from clipsift.schema import Detection
    dets = {}
    for f in frames:
        dets[f["frame_id"]] = [Detection(t=f["time_s"], box=b[:4], score=b[4], movement=b[5]) for b in f["boxes"]]
    pool = [f for f in frames if pool_ids is None or f["frame_id"] in pool_ids]
    sfm.apply([(f["time_s"], dets[f["frame_id"]]) for f in pool], cfg_over, pool[0]["width"], pool[0]["height"])
    # frames outside the pool: judged against the pool's persistent places (add them in, then read back)
    return dets, pool


def xyxy(dets):
    return np.array([[d.box[0], d.box[1], d.box[0] + d.box[2], d.box[1] + d.box[3]] for d in dets],
                    float).reshape(-1, 4)


def strict_row(dets, dots, width, thr, static_out, rng):
    """Strict recall and precision of boxes >= thr (static ones excluded when static_out)."""
    ds = [d for d in dets if d.score >= thr and not (static_out and d.static)]
    B = xyxy(ds)
    _, ymax = labelled_area(dots, width)
    if len(B):
        B = B[(B[:, 1] + B[:, 3]) / 2 < ymax]
    hit = match_hits(B, dots, **STRICT)
    ch = chance_hits(B, dots, width, rng, **STRICT)
    # box-shift control: the same boxes moved 150 to 400 px in a random direction
    sh = []
    for _ in range(40):
        ang, r = rng.uniform(0, 6.283), rng.uniform(150, 400)
        dx, dy = r * np.cos(ang), r * np.sin(ang)
        sh.append(match_hits(B + [dx, dy, dx, dy], dots, **STRICT) if len(B) else 0)
    n, nd = len(B), len(dots)
    return {"boxes": n, "hits": hit, "recall": hit / nd, "precision": hit / n if n else float("nan"),
            "chance_hits": ch, "shift_mean": float(np.mean(sh)), "shift_min": int(min(sh)),
            "shift_max": int(max(sh))}


def fmt_row(label, r, nd):
    return (f"{label:<34} boxes {r['boxes']:>3} hits {r['hits']:>3}/{nd} R {r['recall']:.2f} P {r['precision']:.2f} | "
            f"chance hits {r['chance_hits']:.1f} | shifted hits {r['shift_mean']:.1f} ({r['shift_min']}-{r['shift_max']})")


def cmd_report(a) -> int:
    frames = load_cache(a.cache)
    ids = [f["frame_id"] for f in frames]
    grid = [f for f in frames if f["frame_id"] != LABEL_ID]
    lab = load_dots_json(ROOT / f"labels/verified/{LABEL_ID}.json")
    dots = lab["dots"]
    print(f"{len(grid)} grid frames, labelled frame {'present' if LABEL_ID in ids else 'MISSING'}, "
          f"{len(dots)} dots\n")
    base = {"static_filter": {}}
    rng = np.random.default_rng(7)

    def labelled(cfg_over, pool_ids=None):
        d, _ = run_filter(frames, cfg_over, pool_ids)
        return d

    out_text = []

    def P(s=""):
        print(s)
        out_text.append(s)

    # ---- 1. labelled frame
    P("== Labelled frame 22:00.3 (103 dots), Nano, strict matching ==")
    P("Persistence pool: all grid frames plus this frame. Defaults: persistence share 0.30, IoU 0.5, movement cutoff 3.")
    d = labelled(base)
    W = next(f for f in frames if f["frame_id"] == LABEL_ID)["width"]
    for thr in THRS:
        P(f"threshold {thr}")
        P(fmt_row("  before (no filter)", strict_row(d[LABEL_ID], dots, W, thr, False, rng), len(dots)))
        P(fmt_row("  after (static removed)", strict_row(d[LABEL_ID], dots, W, thr, True, rng), len(dots)))
        rem = [x for x in d[LABEL_ID] if x.static and x.score >= thr]
        P(f"  removed {len(rem)} boxes: reasons {sorted({x.static_reason for x in rem})}")
    # which removed boxes were hits
    # ---- 2. per-frame counts
    P("\n== Boxes per grid frame, before and after (defaults) ==")
    rows = {}
    for f in grid:
        ds = d[f["frame_id"]]
        rows[f["frame_id"]] = {"time_s": f["time_s"]}
        for thr in THRS:
            key = f"{thr:g}".replace(".", "")
            rows[f["frame_id"]][f"raw_{key}"] = sum(1 for x in ds if x.score >= thr)
            rows[f["frame_id"]][f"after_{key}"] = sum(1 for x in ds if x.score >= thr and not x.static)
    for thr in THRS:
        key = f"{thr:g}".replace(".", "")
        raw = np.array([r[f"raw_{key}"] for r in rows.values()])
        aft = np.array([r[f"after_{key}"] for r in rows.values()])
        P(f"threshold {thr}: mean {raw.mean():.1f} -> {aft.mean():.1f}, median {np.median(raw):.0f} -> "
          f"{np.median(aft):.0f}, total {raw.sum()} -> {aft.sum()} ({100 * (1 - aft.sum() / max(1, raw.sum())):.0f}% removed)")
    k = "01"
    srt = sorted(rows.items(), key=lambda kv: (kv[1][f"after_{k}"], kv[1]["time_s"]))
    fmt = lambda it: ", ".join(f"{int(v['time_s'])}s ({v['raw_' + k]}->{v['after_' + k]})" for _, v in it)  # noqa: E731
    P("fewest remaining at 0.1 (time, before->after): " + fmt(srt[:10]))
    P("most remaining at 0.1: " + fmt(srt[::-1][:10]))
    # ---- 3. empty frames
    P("\n== Frames Jacob marked as no fish (one person's labels; faint fish could be missed) ==")
    P("time   | 0.05 before->after | 0.1 before->after")
    tot = {t: [0, 0] for t in THRS}
    for tt in EMPTY_TIMES:
        fid = next((k_ for k_, v in rows.items() if abs(v["time_s"] - tt) < 0.5), None)
        if fid is None:
            P(f"{tt}s: not in cache")
            continue
        v = rows[fid]
        P(f"{tt:>5}s | {v['raw_005']:>3} -> {v['after_005']:<3}        | {v['raw_01']:>3} -> {v['after_01']}")
        for thr in THRS:
            key = f"{thr:g}".replace(".", "")
            tot[thr][0] += v[f"raw_{key}"]
            tot[thr][1] += v[f"after_{key}"]
    P("total over those frames: " + "; ".join(f"{thr}: {a_} -> {b_}" for thr, (a_, b_) in tot.items()))
    # ---- 4. pipeline-sized pool
    P("\n== Same, but persistence learned from only 15 frames (like one 15-minute window at 60 s spacing) ==")
    sub = [f["frame_id"] for f in grid][::len(grid) // 15 or 1][:15] + [LABEL_ID]
    d15 = labelled(base, set(sub))
    for thr in THRS:
        P(fmt_row(f"  thr {thr} labelled frame after", strict_row(d15[LABEL_ID], dots, W, thr, True, rng), len(dots)))
    # ---- 5. sweep
    P("\n== Settings sweep (sensitivity, NOT a search for the best: the defaults above were fixed before looking) ==")
    P("persist share | persist | movement cutoff | 0.1 labelled R / P (strict) | 0.1 empty-frame boxes | 0.1 all-frame boxes")
    for share, pers, cut, mov in [(0.3, True, 3, True), (0.2, True, 3, True), (0.5, True, 3, True), (0.3, True, 0, False),
                                  (0.3, False, 3, True), (0.3, False, 2, True), (0.3, False, 4, True), (0.3, False, 5, True),
                                  (0.3, True, 5, True)]:
        over = {"static_filter": {"persistence": {"enabled": pers, "share": share},
                                  "movement": {"enabled": mov, "cutoff": cut}}}
        dd = labelled(over)
        r = strict_row(dd[LABEL_ID], dots, W, 0.1, True, np.random.default_rng(1))
        em = sum(1 for tt in EMPTY_TIMES for k_, v in rows.items() if abs(v["time_s"] - tt) < 0.5
                 for x in dd[k_] if x.score >= 0.1 and not x.static)
        allb = sum(1 for f in grid for x in dd[f["frame_id"]] if x.score >= 0.1 and not x.static)
        P(f"{share:<13} | {str(pers):<7} | {cut if mov else 'off':<15} | {r['recall']:.2f} / {r['precision']:.2f} ({r['hits']} hits, "
          f"{r['boxes']} boxes) | {em} | {allb}")
    if a.frame_boxes:
        Path(a.frame_boxes).write_text(json.dumps({
            "note": "Boxes per frame after the static filter (defaults: persistence share 0.30, IoU 0.5, movement "
                    "cutoff 3). raw_* = before. 005 = threshold 0.05, 01 = threshold 0.1. T1-STAT2 411, Nano, "
                    "label set t1s2_v1. Small sample; Nano finds fish only.",
            "frames": rows}, indent=1), encoding="utf-8")
        print("wrote", a.frame_boxes)
    if a.text_out:
        Path(a.text_out).write_text("\n".join(out_text), encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--video", required=True); d.add_argument("--cache", required=True)
    d.add_argument("--every", type=int, default=1); d.add_argument("--limit", type=int, default=0)
    d.add_argument("--device", default="auto")
    r = sub.add_parser("report")
    r.add_argument("--cache", required=True); r.add_argument("--frame-boxes"); r.add_argument("--text-out")
    a = ap.parse_args(argv)
    return cmd_detect(a) if a.cmd == "detect" else cmd_report(a)


if __name__ == "__main__":
    raise SystemExit(main())
