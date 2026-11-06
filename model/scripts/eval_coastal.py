"""Dev checks on Coastal frames. NOT a test set, NEVER train on them, never choose a threshold on them.

  .venv/bin/python eval_coastal.py --ckpt X.pth --name run2 --threshold-file eval_out/run2/threshold.json

Same method for every checkpoint. Tiles each 4K frame with clipsift.stages.cfd.tile_boxes (512, overlap 0.25), runs the
checkpoint at score >= 0.01, merges with merge_boxes (0.5). 2-class checkpoints: fish class only.
(a) Verified frame T1-STAT2_411_t1320.303 (103 fish dots): scored with tools/eval_detector.py score_frames (imported read-only,
    same matching + chance baseline) (i) at the Puget-val threshold, (ii) at fixed budgets = top 25/50/100/200 boxes by score.
(b) False-alarm check on the team-labelled frames (labels/team/t1s2_v1/points.csv): for the top 50 boxes per frame, the share of
    not_fish marks inside a box (lower is better), by category, and whether the invertebrate marks are inside a box.
    Labeller names are never read into the output.
This is a dev check on one dense school, not accuracy."""
import sys
sys.dont_write_bytecode = True
import argparse, json, time, csv, collections
import numpy as np, cv2
from common import *
from clipsift.stages.cfd import tile_boxes, merge_boxes
sys.path.insert(0, str(CLIPSIFT / "tools"))
import eval_detector as ED          # read-only import

FRAME = CLIPSIFT / "labels/verified/T1-STAT2_411_t1320.303.png"
LABELS = FRAME.with_suffix(".json")
TEAM_CSV = CLIPSIFT / "labels/team/t1s2_v1/points.csv"
TEAM_FRAMES = CLIPSIFT / "label_sets/t1s2_v1/frames"
BUDGETS = (25, 50, 100, 200)
TOPK_TEAM = 50

AGNOSTIC = False
def detect(model, names, img_rgb, tile, overlap, batch, thr=0.01):
    H, W = img_rgb.shape[:2]; crops = tile_boxes(W, H, tile, overlap); B, S = [], []
    for i in range(0, len(crops), batch):
        grp = crops[i:i+batch]
        out = predict_batch(model, [img_rgb[y0:y1, x0:x1] for x0, y0, x1, y1 in grp], thr)
        for (x0, y0, _, _), (xy, cf, ci) in zip(grp, out):
            keep = (ci == 0) if (len(names) > 1 and not AGNOSTIC) else np.ones(len(ci), bool)
            b = xy[keep].copy(); b[:, [0, 2]] += x0; b[:, [1, 3]] += y0; B.append(b); S.append(cf[keep])
    B = np.vstack(B) if B else np.zeros((0, 4)); S = np.hstack(S) if S else np.zeros(0)
    if len(B):
        k = merge_boxes(B, S, 0.5); B, S = B[k], S[k]       # best score first
    return B, S

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--threshold", type=float); ap.add_argument("--threshold-file")
    ap.add_argument("--device", default="auto"); ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--tile", type=int, default=512); ap.add_argument("--overlap", type=float, default=0.25)
    ap.add_argument("--team-csv", default=str(TEAM_CSV)); ap.add_argument("--out-name", default="coastal.json")
    ap.add_argument("--agnostic", action="store_true", help="count every class as fish (for the untrained COCO stock model)")
    a = ap.parse_args(argv)
    global AGNOSTIC; AGNOSTIC = a.agnostic
    if (a.threshold is None) == (a.threshold_file is None):
        ap.error("give exactly one of --threshold or --threshold-file (chosen on Puget val, not here)")
    thr = a.threshold if a.threshold is not None else json.load(open(a.threshold_file))["fish"]["threshold"]
    model = load_model(a.ckpt, a.device); names = class_map(model)
    t0 = time.perf_counter()
    img = cv2.imread(str(FRAME))[:, :, ::-1]; W = img.shape[1]
    B, S = detect(model, names, img, a.tile, a.overlap, a.batch)
    dots = ED.load_dots_json(LABELS)["dots"]
    fr = lambda b, s: [{"boxes": b, "scores": s, "dots": dots, "width": W}]
    rows = {"puget_val_threshold": ED.score_frames(fr(B[S >= thr], S[S >= thr]), thr)}
    for k in BUDGETS:
        r = ED.score_frames(fr(B[:k], S[:k]), 0.0); r["budget"] = k; r["boxes_available"] = int(min(k, len(B))); rows[f"top{k}"] = r
    # (b) team frames, labeller column deliberately not read
    marks = collections.defaultdict(list)
    for r in csv.DictReader(open(a.team_csv, newline="", encoding="utf-8")):
        marks[r["frame_id"]].append((float(r["x"]), float(r["y"]), r["kind"], r["category"] or "none"))
    tot = collections.Counter(); hit = collections.Counter(); inv_hit = inv_tot = 0; per_frame = {}
    for fid, ms in sorted(marks.items()):
        im = cv2.imread(str(TEAM_FRAMES / f"{fid}.jpg"))[:, :, ::-1]
        if im.shape[1] != W: s = W/im.shape[1]
        else: s = 1.0
        b, sc = detect(model, names, im, a.tile, a.overlap, a.batch)
        b = b[:TOPK_TEAM]; nh = 0; nn = 0
        for x, y, kind, cat in ms:
            x, y = x*s, y*s
            inside = bool(len(b) and ((b[:, 0] <= x) & (x <= b[:, 2]) & (b[:, 1] <= y) & (y <= b[:, 3])).any())
            if kind == "not_fish": tot[cat] += 1; hit[cat] += inside; nn += 1; nh += inside
            elif kind == "invertebrate": inv_tot += 1; inv_hit += inside
        per_frame[fid] = {"boxes": int(len(b)), "not_fish_marks": nn, "not_fish_in_box": nh}
    nf_tot = sum(tot.values()); nf_hit = sum(hit.values())
    fa = {"top_k_per_frame": TOPK_TEAM, "frames": len(marks), "not_fish_marks": nf_tot, "not_fish_in_box": nf_hit,
          "not_fish_share_in_box": nf_hit/max(nf_tot, 1),
          "by_category": {c: {"marks": tot[c], "in_box": hit[c], "share": hit[c]/tot[c]} for c in sorted(tot)},
          "invertebrate_marks": inv_tot, "invertebrate_in_box": int(inv_hit), "per_frame": per_frame}
    res = {"ckpt": str(a.ckpt), "threshold_from_puget_val": thr, "tile": a.tile, "overlap": a.overlap, "seconds": time.perf_counter()-t0, "team_csv": str(a.team_csv),
           "verified_frame": rows, "false_alarm_team_frames": fa,
           "note": "Dev check on one dense school (verified frame) plus 9 team frames, not accuracy."}
    out = HERE / "eval_out" / a.name; out.mkdir(parents=True, exist_ok=True)
    (out / a.out_name).write_text(json.dumps(res, indent=1, default=float))
    print(f"{a.name}: verified frame, Puget-val thr {thr:.3f} and fixed budgets")
    print(ED.format_table(list(rows.values())))
    print(f"false alarms (top {TOPK_TEAM}/frame): not_fish in a box {nf_hit}/{nf_tot} = {fa['not_fish_share_in_box']:.2f}; "
          + ", ".join(f"{c} {v['in_box']}/{v['marks']}" for c, v in fa["by_category"].items()) + f"; invertebrates hit {inv_hit}/{inv_tot}")
    print("Dev check on one dense school, not accuracy. Never tune on it.")

if __name__ == "__main__":
    main()
