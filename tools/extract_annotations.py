"""Extract WEAK LABELS from Coastal Action's marked subsample screenshots.

Finds red dots, black dots, red ellipses and grid lines with plain OpenCV, masks the VLC player
bar, and counts dots per grid cell so they can be compared with the totals written on the images.

These are extracted weak labels. They need human checking. They are NOT ground truth, and the
marked screenshots must never be used as training images as they are (a model would learn red
circles and control bars). Clean frames should be pulled from the videos at the same timestamps.

The input folder is only read. Nothing in it is modified.

    python tools/extract_annotations.py "../Sept 10 & 9th sub-samples" --out labels \
        --written labels/written_totals.json --debug-dir labels/debug

Outputs in --out: annotations.json, extraction_report.csv, points.csv, coco_keypoints.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np

TOOL_NOTE = ("Extracted weak labels from marked screenshots. They need human checking and are not "
             "ground truth. Do not train on the marked screenshots themselves.")

# Fallback VLC bar box (fractions of the image) used only if the bar cannot be found.
PLAYER_BOX = (0.24, 0.85, 0.70, 0.99)  # x0, y0, x1, y1


def find_player_bar(img):
    """The VLC control bar is a wide, light, low-saturation rectangle, at the bottom or the top.
    Returns (x0, y0, x1, y1) in pixels including the hover tooltip area, or None."""
    H, W = img.shape[:2]
    light = (img.min(axis=2) > 185) & ((img.max(axis=2).astype(int) - img.min(axis=2)) < 40)
    light = cv2.morphologyEx(light.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    best = None
    n, lab, st, _ = cv2.connectedComponentsWithStats(light, 8)
    for j in range(1, n):
        x, y, w, h, a = (int(v) for v in st[j])
        if w >= 0.3 * W and 40 <= h <= 140 and a / (w * h) >= 0.5:
            if best is None or w * h > best[2] * best[3]:
                best = (x, y, w, h)
    if best is None:
        return None
    x, y, w, h = best
    pad = 10
    tip = 70  # hover time tooltip sits just above (bottom bar) or below (top bar) the bar
    y0, y1 = y - pad, y + h + pad
    if y > H / 2:
        y0 -= tip
    else:
        y1 += tip
    return max(0, x - pad), max(0, y0), min(W, x + w + pad), min(H, y1)


# ------------------------------------------------------------------ filename
def parse_filename(name: str) -> dict:
    stem = Path(name).stem
    t = re.search(r"\bT(\d)\b", stem.replace("_", " ").replace("-", " "))
    s = re.search(r"STAT\s*(\d+)", stem, re.I)
    d = re.search(r"(Sept?|Oct|Aug)\w*\s*(\d{1,2})", stem, re.I)
    tm = re.search(r"@\s*(\d+)\s*min(?:\s*(\d+)\s*sec)?", stem, re.I)
    secs = int(tm.group(1)) * 60 + int(tm.group(2) or 0) if tm else None
    tags = [x for x in ("enhanced", "marked green crab", "no enhancements") if x in stem.lower()]
    return {"transect": f"T{t.group(1)}" if t else None, "stat": f"STAT {s.group(1)}" if s else None,
            "date": f"{d.group(1).title()} {d.group(2)}" if d else None, "time_s": secs, "tags": tags}


# ------------------------------------------------------------------ grid
def _cluster(idx, gap=6):
    groups, cur = [], [idx[0]] if len(idx) else []
    for i in idx[1:]:
        if i - cur[-1] <= gap:
            cur.append(i)
        else:
            groups.append(cur)
            cur = [i]
    if cur:
        groups.append(cur)
    return [float(np.mean(g)) for g in groups]


def detect_grid(img, panel_mask):
    """Dark, near-black lines spanning most of the frame. Returns (col_edges, row_edges, warnings)."""
    dark = (img.max(axis=2) < 45) & ~panel_mask
    H, W = dark.shape
    cols = np.where(dark.sum(axis=0) > 0.45 * H)[0]
    rows = np.where(dark.sum(axis=1) > 0.45 * W)[0]
    cx = [x for x in _cluster(cols)] if len(cols) else []
    ry = [y for y in _cluster(rows)] if len(rows) else []
    cx = [x for x in cx if 15 < x < W - 15]
    ry = [y for y in ry if 15 < y < H - 15]
    warn = []
    if len(cx) < 2 or len(ry) < 1:
        warn.append("no grid detected")
        return [], [], warn
    return [0.0] + cx + [float(W)], [0.0] + ry + [float(H)], warn


def cell_of(x, y, col_edges, row_edges):
    if not col_edges:
        return None
    c = int(np.searchsorted(col_edges, x, side="right") - 1)
    r = int(np.searchsorted(row_edges, y, side="right") - 1)
    return [min(max(r, 0), len(row_edges) - 2), min(max(c, 0), len(col_edges) - 2)]


# ------------------------------------------------------------------ marks
def _components(mask):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    for j in range(1, n):
        x, y, w, h, a = (int(v) for v in st[j])
        yield j, lab, x, y, w, h, a, cen[j]


def find_dots(mask, max_side=9, min_area=2, max_area=45):
    """Small compact blobs. Typed or handwritten digits are taller than max_side and are skipped."""
    out = []
    for j, lab, x, y, w, h, a, c in _components(mask):
        if min_area <= a <= max_area and w <= max_side and h <= max_side and a / (w * h) >= 0.45:
            out.append({"x": round(float(c[0]), 1), "y": round(float(c[1]), 1), "area": a})
    return out


def find_ellipses(red_mask, min_side=40):
    out = []
    H, W = red_mask.shape
    for j, lab, x, y, w, h, a, c in _components(red_mask):
        if w < min_side or h < min_side:
            continue
        cnts, _ = cv2.findContours((lab == j).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        pts = max(cnts, key=len)
        if len(pts) < 5:
            continue
        (cx, cy), (ax, ay), ang = cv2.fitEllipse(pts)
        out.append({"cx": round(cx, 1), "cy": round(cy, 1), "axes": [round(ax, 1), round(ay, 1)],
                    "angle": round(ang, 1), "bbox": [x, y, w, h],
                    "touches_border": bool(x <= 1 or y <= 1 or x + w >= W - 1 or y + h >= H - 1)})
    return out


def process_image(path: Path, debug_dir=None) -> dict:
    img = cv2.imread(str(path))
    if img is None:
        raise IOError(f"Cannot read {path}")
    H, W = img.shape[:2]
    panel = np.zeros((H, W), bool)
    warns0 = []
    box = find_player_bar(img)
    if box is None:
        warns0.append("player bar not found; used fixed fallback box")
        fx0, fy0, fx1, fy1 = PLAYER_BOX
        box = (int(fx0 * W), int(fy0 * H), int(fx1 * W), int(fy1 * H))
    x0, y0, x1, y1 = box
    panel[y0:y1, x0:x1] = True

    b, g, r = (img[:, :, k].astype(np.int16) for k in (0, 1, 2))
    red = ((r - np.maximum(g, b)) > 90) & (r > 140) & ~panel
    black = (img.max(axis=2) < 45) & ~panel

    col_edges, row_edges, warns = detect_grid(img, panel)
    warns = warns0 + warns
    # remove grid lines from the black mask (a band around each detected line)
    gridband = np.zeros((H, W), bool)
    for x in col_edges[1:-1]:
        gridband[:, max(0, int(x) - 5):int(x) + 6] = True
    for y in row_edges[1:-1]:
        gridband[max(0, int(y) - 5):int(y) + 6, :] = True
    black &= ~gridband
    # image borders sometimes carry dark edges
    black[:3, :] = black[-3:, :] = False
    black[:, :3] = black[:, -3:] = False

    rdots = find_dots(red)
    bdots = find_dots(black)
    ells = find_ellipses(red)
    # red dots inside an ellipse's bounding box that belong to its ring are not dots (ring pieces are large, so fine)
    for d in rdots:
        d["detector"] = "red_dot_cc"
        d["cell"] = cell_of(d["x"], d["y"], col_edges, row_edges)
    for d in bdots:
        d["detector"] = "black_dot_cc"
        d["cell"] = cell_of(d["x"], d["y"], col_edges, row_edges)
    for e in ells:
        e["detector"] = "red_ellipse_fit"
        e["cell"] = cell_of(e["cx"], e["cy"], col_edges, row_edges)
    cells: dict = {}
    for kind, dots in (("red", rdots), ("black", bdots)):
        for d in dots:
            if d["cell"]:
                k = f"{d['cell'][0]},{d['cell'][1]}"
                cells.setdefault(k, {"red": 0, "black": 0})[kind] += 1
    for k, v in cells.items():
        if v["red"] + v["black"] > 40:
            warns.append(f"cell {k} has {v['red'] + v['black']} dots: likely texture false positives")
    rec = {"file": path.name, **parse_filename(path.name), "image_size": [W, H],
           "grid": {"detector": "grid_lines_projection", "col_edges": [round(x, 1) for x in col_edges],
                    "row_edges": [round(y, 1) for y in row_edges],
                    "n_cols": max(0, len(col_edges) - 1), "n_rows": max(0, len(row_edges) - 1)},
           "masked_regions": [{"name": "player_bar", "box": [int(x0), int(y0), int(x1), int(y1)]}],
           "red_dots": rdots, "black_dots": bdots, "red_ellipses": ells, "cell_counts": cells,
           "warnings": warns}
    if debug_dir:
        dbg = img.copy()
        for d in rdots:
            cv2.circle(dbg, (int(d["x"]), int(d["y"])), 6, (0, 255, 255), 1)
        for d in bdots:
            cv2.circle(dbg, (int(d["x"]), int(d["y"])), 6, (255, 0, 255), 1)
        for e in ells:
            cv2.ellipse(dbg, ((e["cx"], e["cy"]), tuple(e["axes"]), e["angle"]), (0, 255, 0), 2)
        cv2.rectangle(dbg, (int(x0), int(y0)), (int(x1), int(y1)), (255, 255, 0), 2)
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(Path(debug_dir) / (path.stem + "_debug.jpg")), dbg, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return rec


# ------------------------------------------------------------------ outputs
def compare_written(rec, written):
    """written: {"r,c": total}. Returns list of per-cell rows and totals."""
    rows = []
    for k, w in sorted(written.items()):
        c = rec["cell_counts"].get(k, {"red": 0, "black": 0})
        n = c["red"] + c["black"]
        rows.append({"cell": k, "written": w, "extracted": n, "diff": n - w})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extract weak labels from marked screenshots (read only).")
    ap.add_argument("folder")
    ap.add_argument("--out", default="labels")
    ap.add_argument("--written", help="JSON {filename: {'row,col': total}} of hand-read totals to compare with")
    ap.add_argument("--debug-dir")
    a = ap.parse_args(argv)
    folder = Path(a.folder)
    files = sorted(p for p in folder.glob("*.png"))
    if not files:
        print(f"No PNG files in {folder}", file=sys.stderr)
        return 2
    written = json.loads(Path(a.written).read_text()) if a.written else {}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    recs = []
    for p in files:
        rec = process_image(p, a.debug_dir)
        w = written.get(p.name)
        if w:
            rec["written_totals_hand_read"] = w
            rec["comparison_to_written"] = compare_written(rec, w)
        recs.append(rec)
    (out / "annotations.json").write_text(json.dumps({"note": TOOL_NOTE, "source_folder": str(folder),
                                                      "images": recs}, indent=1), encoding="utf-8")
    with open(out / "extraction_report.csv", "w", newline="", encoding="utf-8") as f:
        cols = ["file", "transect", "stat", "date", "time_s", "tags", "grid_cols", "grid_rows", "red_dots",
                "black_dots", "red_ellipses", "per_cell_counts", "written_totals_hand_read", "comparison", "warnings"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            cc = ";".join(f"{k}={v['red'] + v['black']}" for k, v in sorted(r["cell_counts"].items()))
            cmp_ = ";".join(f"{x['cell']}: extracted {x['extracted']} vs written {x['written']}"
                            for x in r.get("comparison_to_written", []))
            w.writerow({"file": r["file"], "transect": r["transect"], "stat": r["stat"], "date": r["date"],
                        "time_s": r["time_s"], "tags": "|".join(r["tags"]), "grid_cols": r["grid"]["n_cols"],
                        "grid_rows": r["grid"]["n_rows"], "red_dots": len(r["red_dots"]),
                        "black_dots": len(r["black_dots"]), "red_ellipses": len(r["red_ellipses"]),
                        "per_cell_counts": cc, "written_totals_hand_read": json.dumps(r.get("written_totals_hand_read", "")),
                        "comparison": cmp_, "warnings": "|".join(r["warnings"])})
    with open(out / "points.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "kind", "x", "y", "colour", "cell_row", "cell_col", "detector", "weak_label"])
        for r in recs:
            for colour, key in (("red", "red_dots"), ("black", "black_dots")):
                for d in r[key]:
                    cr, cc_ = d["cell"] or ["", ""]
                    w.writerow([r["file"], "animal_point", d["x"], d["y"], colour, cr, cc_, d["detector"], 1])
            for e in r["red_ellipses"]:
                cr, cc_ = e["cell"] or ["", ""]
                w.writerow([r["file"], "ellipse_center", e["cx"], e["cy"], "red", cr, cc_, e["detector"], 1])
    coco = {"info": {"description": TOOL_NOTE}, "images": [], "annotations": [],
            "categories": [{"id": 1, "name": "animal_point", "keypoints": ["centre"], "skeleton": []},
                           {"id": 2, "name": "marked_animal_ellipse", "keypoints": [], "skeleton": []}]}
    aid = 1
    for i, r in enumerate(recs, 1):
        coco["images"].append({"id": i, "file_name": r["file"], "width": r["image_size"][0], "height": r["image_size"][1]})
        for d in r["red_dots"] + r["black_dots"]:
            coco["annotations"].append({"id": aid, "image_id": i, "category_id": 1, "keypoints": [d["x"], d["y"], 2],
                                        "num_keypoints": 1, "iscrowd": 0, "bbox": [d["x"] - 4, d["y"] - 4, 8, 8],
                                        "area": 64, "attributes": {"detector": d["detector"], "weak": True}})
            aid += 1
        for e in r["red_ellipses"]:
            coco["annotations"].append({"id": aid, "image_id": i, "category_id": 2, "bbox": e["bbox"],
                                        "area": e["bbox"][2] * e["bbox"][3], "iscrowd": 0,
                                        "attributes": {"detector": e["detector"], "weak": True}})
            aid += 1
    (out / "coco_keypoints.json").write_text(json.dumps(coco), encoding="utf-8")
    print(f"{len(recs)} images -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
