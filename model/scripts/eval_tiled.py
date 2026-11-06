"""Score any RF-DETR checkpoint on the tiled Puget set, identically every time.

  .venv/bin/python eval_tiled.py --ckpt X.pth --name cfd_nano_baseline            # val: also CHOOSES and saves the threshold
  .venv/bin/python eval_tiled.py --ckpt X.pth --name run2 --split valid           # same
  .venv/bin/python eval_tiled.py --ckpt X.pth --name run2 --threshold-file eval_out/run2/threshold.json --split valid

Matching: per tile and class, detections sorted by score, greedy one-to-one match to GT at IoU >= t (t = 0.3 and 0.5).
AP = area under the all-point interpolated PR curve over pooled tiles (VOC/COCO-style monotone envelope), per class.
Threshold = score maximising F1 at IoU 0.5, per class, chosen on --split valid and saved to eval_out/<name>/threshold.json.
Tiles overlap by 25%, so a fish near a tile border is counted once per tile it falls in (tile-level scoring, not frame-level).
A one-class checkpoint (CFD) is scored as fish; crab is reported as n/a. For 2-class checkpoints class_id order = class_names order
(fish, crab). If a checkpoint's class_names are missing, assume class 0 = fish, 1 = crab.
"""
import argparse, json, time
from pathlib import Path
import numpy as np, cv2
from common import *

TILES = HERE / "tiles" / "puget_v1"
CLASSES = ["fish", "crab"]

def run_detections(model, split, batch, limit=None, cache=None):
    if cache and cache.exists():
        z = np.load(cache, allow_pickle=True); return list(z["dets"]), list(z["gts"]), float(z["secs"])
    d = json.load(open(TILES / split / "_annotations.coco.json"))
    gts = {}
    for a in d["annotations"]:
        x, y, w, h = a["bbox"]; gts.setdefault(a["image_id"], []).append((a["category_id"], [x, y, x+w, y+h]))
    ims = d["images"][:limit] if limit else d["images"]
    dets, G = [], []; t0 = time.perf_counter()
    for i in range(0, len(ims), batch):
        chunk = ims[i:i+batch]
        rgbs = [cv2.imread(str(TILES / split / im["file_name"]))[:, :, ::-1] for im in chunk]
        out = predict_batch(model, rgbs, 0.01)
        for im, o in zip(chunk, out):
            dets.append(o); G.append(gts.get(im["id"], []))
    secs = time.perf_counter() - t0
    if cache: np.savez(cache, dets=np.array(dets, dtype=object), gts=np.array(G, dtype=object), secs=secs)
    return dets, G, secs

def per_class_match(dets, gts, cls, iou_t, map_cls):
    """Returns (scores, tp flags, n_gt) pooled over tiles for one class."""
    S, TP, ngt = [], [], 0
    for (xy, cf, ci), g in zip(dets, gts):
        gb = np.array([b for c, b in g if c == cls], float).reshape(-1, 4); ngt += len(gb)
        m = np.array([map_cls(c) == cls for c in ci], bool) if len(ci) else np.zeros(0, bool)
        xy, cf = xy[m], cf[m]
        order = cf.argsort()[::-1]; xy, cf = xy[order], cf[order]
        M = iou_matrix(xy, gb); used = np.zeros(len(gb), bool)
        for k in range(len(xy)):
            ok = False
            if len(gb):
                r = np.where(used, -1, M[k]); j = int(r.argmax())
                if r[j] >= iou_t: used[j] = True; ok = True
            S.append(cf[k]); TP.append(ok)
    return np.array(S), np.array(TP, bool), ngt

def ap_and_pr(S, TP, ngt):
    if ngt == 0: return None
    o = S.argsort()[::-1]; tp = TP[o]; ctp = np.cumsum(tp); cfp = np.cumsum(~tp)
    rec = ctp/ngt; prec = ctp/np.maximum(ctp+cfp, 1)
    mrec = np.r_[0, rec, 1]; mpre = np.r_[0, prec, 0]
    mpre = np.maximum.accumulate(mpre[::-1])[::-1]
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(((mrec[idx+1]-mrec[idx])*mpre[idx+1]).sum())

def at_threshold(S, TP, ngt, thr):
    k = S >= thr; tp = int(TP[k].sum()); n = int(k.sum())
    p = tp/n if n else float("nan"); r = tp/ngt if ngt else float("nan")
    return dict(thr=float(thr), dets=n, tp=tp, precision=p, recall=r)

def best_f1_thr(S, TP, ngt):
    if ngt == 0 or not len(S): return None
    best = (-1, 0.5)
    for t in np.unique(np.r_[np.round(np.linspace(0.02, 0.95, 94), 3)]):
        k = S >= t; tp = TP[k].sum(); n = k.sum()
        if n == 0: continue
        p = tp/n; r = tp/ngt; f = 2*p*r/(p+r) if p+r else 0
        if f > best[0]: best = (f, float(t))
    return best[1], best[0]

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--split", default="valid"); ap.add_argument("--device", default="auto"); ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--agnostic", action="store_true", help="count every class as fish (untrained COCO stock model)"); ap.add_argument("--limit", type=int); ap.add_argument("--threshold-file"); ap.add_argument("--reuse-cache", action="store_true")
    a = ap.parse_args(argv)
    out = HERE / "eval_out" / a.name; out.mkdir(parents=True, exist_ok=True)
    model = load_model(a.ckpt, a.device); names = class_map(model)
    nc = len(names) if names else 1
    single = (nc == 1) or a.agnostic
    map_cls = (lambda c: 0) if single else (lambda c: int(c))   # id->our class index (fish=0, crab=1)
    print("checkpoint", a.ckpt, "| class_names", names, "| device", pick_device(a.device), flush=True)
    cache = (out / f"dets_{a.split}.npz") if a.reuse_cache else None
    dets, gts, secs = run_detections(model, a.split, a.batch, a.limit, cache)
    print(f"{len(dets)} tiles inferred in {secs:.0f}s ({len(dets)/max(secs,1e-9):.1f} tiles/s)", flush=True)
    thr_file = Path(a.threshold_file) if a.threshold_file else None
    saved = json.load(open(thr_file)) if thr_file else {}
    res = {"ckpt": str(a.ckpt), "split": a.split, "tiles": len(dets), "class_names": names, "tile_level": True, "classes": {}}
    new_thr = {}
    for ci, cn in enumerate(CLASSES):
        if single and ci == 1:
            res["classes"][cn] = "n/a (one-class model)"; continue
        r = {}
        S5, TP5, n5 = per_class_match(dets, gts, ci, 0.5, map_cls)
        if thr_file is None:
            bt = best_f1_thr(S5, TP5, n5) if n5 else None
            new_thr[cn] = {"threshold": bt[0], "f1_at_iou0.5": bt[1]} if bt else None
            t = bt[0] if bt else None
        else:
            t = (saved.get(cn) or {}).get("threshold")
        r["n_gt"] = n5
        for it in (0.3, 0.5):
            S, TP, ngt = (S5, TP5, n5) if it == 0.5 else per_class_match(dets, gts, ci, it, map_cls)
            r[f"AP@{it}"] = ap_and_pr(S, TP, ngt)
            if t is not None: r[f"IoU{it}"] = at_threshold(S, TP, ngt, t)
        res["classes"][cn] = r
    if thr_file is None:
        (out / "threshold.json").write_text(json.dumps(new_thr, indent=1)); res["threshold_chosen_on"] = a.split
    else: res["threshold_from"] = str(thr_file)
    (out / f"metrics_{a.split}.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))

if __name__ == "__main__":
    main()
