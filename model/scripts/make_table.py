import json
from pathlib import Path
H = Path(__file__).resolve().parent / "eval_out"
rows = [("untrained CFD Nano", "cfd_nano_baseline", True), ("untrained stock Nano (COCO, any class = fish)", "stock_untrained", False)]
for s, c in (("stock", False), ("cfd", True)):
    for e in (1, 2, 3): rows.append((f"{s}-start epoch {e}", f"p2_{s}_ep{e}", c))
f = lambda x: "n/a" if x is None or isinstance(x, str) else f"{x:.3f}"
v = ["| model | fish AP.3 | fish AP.5 | crab AP.3 | crab AP.5 | val thr (fish) |", "|---|---|---|---|---|---|"]
c1 = ["| model | @Puget-val thr: boxes, R / P (chance R / P) | top25 R/P (chance) | top50 | top100 | top200 | not_fish in box (top50/frame) | invert. hit |", "|---|---|---|---|---|---|---|---|"]
for lab, n, cont in rows:
    try:
        m = json.load(open(H/n/"metrics_valid.json")); fi, cr = m["classes"]["fish"], m["classes"]["crab"]
        thr = json.load(open(H/n/"threshold.json"))["fish"]["threshold"]
        star = " (CONTAMINATED)" if cont else ""
        v.append(f"| {lab}{star} | {f(fi['AP@0.3'])} | {f(fi['AP@0.5'])} | {f(cr.get('AP@0.3') if isinstance(cr, dict) else None)} | {f(cr.get('AP@0.5') if isinstance(cr, dict) else None)} | {thr:.2f} |")
    except Exception as e: v.append(f"| {lab} | missing ({e}) | | | | |")
    try:
        c = json.load(open(H/n/"coastal_snapshot.json")); vf = c["verified_frame"]; fa = c["false_alarm_team_frames"]
        cell = lambda r: f"{r['recall']:.2f}/{r['precision']:.2f} ({r['chance_recall']:.2f}/{r['chance_precision']:.2f})"
        p = vf["puget_val_threshold"]
        c1.append(f"| {lab} | {p['boxes']}: " + cell(p) + " | " + " | ".join(cell(vf[f"top{k}"]) for k in (25, 50, 100, 200)) +
                  f" | {fa['not_fish_in_box']}/{fa['not_fish_marks']} = {fa['not_fish_share_in_box']:.2f} | {fa['invertebrate_in_box']}/{fa['invertebrate_marks']} |")
    except Exception as e: c1.append(f"| {lab} | missing ({e}) |")
print("\n".join(v)); print(); print("\n".join(c1))
