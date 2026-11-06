"""Tile the Puget Sound train/val splits into COCO tiles for RF-DETR (fish=0, crab=1 after rfdetr remap).
Usage: .venv/bin/python prep_tiles.py [--tile 512] [--overlap 0.25]
Reads Footage Sources/splits/puget_{train,val}.json (never modified). puget_test is NOT touched."""
import argparse, json, sys, random, collections, csv
from pathlib import Path
import numpy as np, cv2
from multiprocessing import Pool

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "Footage Sources"
sys.path.insert(0, str(ROOT / "clipsift"))
from clipsift.stages.cfd import tile_boxes   # read-only import

SEED = 20261106
MIN_FRAC = 0.30          # drop boxes with < 30% of their area inside the tile
IGN_MIN_PX2 = 16         # a tile overlapping an ignore box by >= 16 px^2 is dropped
EMPTY_FRAC = 0.25        # empties <= 25% of the final set
KEEP = {1: 0, 2: 1}      # source cat id -> our class index (fish, crab)
IGN = {3, 4}             # fish_or_crab, unknown

def gray_world(img):
    """Per-frame gray-world white balance: scale B,G,R so channel means equal the mean of the means."""
    f = img.astype(np.float32)
    m = f.reshape(-1, 3).mean(0)
    gain = np.clip(m.mean() / np.maximum(m, 1e-6), 0.4, 4.0)
    return np.clip(f * gain, 0, 255).astype(np.uint8), gain

def inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0) * max(h, 0)

def plan_split(split, tile, overlap, empty_frac):
    d = json.load(open(SRC / "splits" / f"puget_{split}.json"))
    by = collections.defaultdict(list)
    for a in d["annotations"]:
        by[a["image_id"]].append(a)
    stats = collections.Counter(); pos = []; emp = []
    for im in d["images"]:
        W, H = im["width"], im["height"]
        anns = by[im["id"]]
        ign = [(a["bbox"][0], a["bbox"][1], a["bbox"][0]+a["bbox"][2], a["bbox"][1]+a["bbox"][3]) for a in anns if a["category_id"] in IGN]
        for (x0, y0, x1, y1) in tile_boxes(W, H, tile, overlap):
            stats["tiles_total"] += 1
            t = (x0, y0, x1, y1)
            if any(inter(t, g) >= IGN_MIN_PX2 for g in ign):
                stats["tiles_dropped_ignore_overlap"] += 1; continue
            boxes = []
            for a in anns:
                if a["category_id"] not in KEEP: continue
                bx, by_, bw, bh = a["bbox"]
                b = (bx, by_, bx+bw, by_+bh)
                area = bw*bh
                if area <= 0: continue
                ia = inter(t, b)
                if ia <= 0: continue
                if ia < MIN_FRAC*area:
                    stats["slivers_dropped"] += 1; continue
                cb = [max(b[0], x0)-x0, max(b[1], y0)-y0, min(b[2], x1)-x0, min(b[3], y1)-y0]
                if cb[2]-cb[0] < 2 or cb[3]-cb[1] < 2: stats["slivers_dropped"] += 1; continue
                if ia < area-1e-6: stats["boxes_clipped"] += 1
                boxes.append((KEEP[a["category_id"]], cb))
            rec = dict(image=im["file_name"], loc=im["location"], filt=bool(im["filter"]), vis=im["visibility"],
                       tile=t, boxes=boxes, img_empty=len(anns) == 0)
            (pos if boxes else emp).append(rec)
    rng = random.Random(SEED)
    n_emp = int(round(len(pos) * empty_frac / (1 - empty_frac)))
    # stratified by site: equal quota per site, spill to sites with spare tiles
    sites = collections.defaultdict(list)
    for r in emp: sites[r["loc"]].append(r)
    for s in sites.values(): rng.shuffle(s)
    chosen = []; active = sorted(sites)
    while len(chosen) < n_emp and active:
        quota = max(1, (n_emp - len(chosen)) // len(active)); nxt = []
        for s in active:
            take = sites[s][:quota]; sites[s] = sites[s][quota:]; chosen += take
            if sites[s]: nxt.append(s)
            if len(chosen) >= n_emp: break
        active = nxt
    chosen = chosen[:n_emp]
    stats.update(tiles_positive=len(pos), tiles_empty_available=len(emp), tiles_empty_kept=len(chosen),
                 boxes_fish=sum(1 for r in pos for c, _ in r["boxes"] if c == 0),
                 boxes_crab=sum(1 for r in pos for c, _ in r["boxes"] if c == 1),
                 images=len(d["images"]), tiles_kept=len(pos)+len(chosen))
    stats["empty_kept_by_site"] = dict(collections.Counter(r["loc"][:12] for r in chosen))
    stats["pos_by_site"] = dict(collections.Counter(r["loc"][:12] for r in pos))
    return d["image_root"], pos + chosen, stats

def render(args):
    root, outdir, image, recs = args
    img = cv2.imread(str(SRC / root / image))
    out = []
    wb = None
    if recs[0][0]["filt"]:
        img, wb = gray_world(img)
    for r, name in recs:
        x0, y0, x1, y1 = r["tile"]
        cv2.imwrite(str(outdir / name), img[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 92])
    return None if wb is None else [float(g) for g in wb]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tile", type=int, default=512); ap.add_argument("--overlap", type=float, default=0.25)
    ap.add_argument("--out", default=str(HERE / "tiles" / "puget_v1")); a = ap.parse_args()
    out = Path(a.out); allstats = {}
    cats = [{"id": 0, "name": "fish", "supercategory": "none"}, {"id": 1, "name": "crab", "supercategory": "none"}]
    for split, folder in (("train", "train"), ("val", "valid")):
        root, recs, stats = plan_split(split, a.tile, a.overlap, EMPTY_FRAC)
        od = out / folder; od.mkdir(parents=True, exist_ok=True)
        coco = {"info": {"description": f"Puget {split} tiles {a.tile}px overlap {a.overlap}, gray-world WB on filter=True frames"},
                "categories": cats, "images": [], "annotations": []}
        groups = collections.defaultdict(list); aid = 0
        for i, r in enumerate(recs):
            name = f"{Path(r['image']).stem}__{r['tile'][0]}_{r['tile'][1]}.jpg"
            r["name"] = name
            coco["images"].append({"id": i, "file_name": name, "width": r["tile"][2]-r["tile"][0], "height": r["tile"][3]-r["tile"][1],
                                   "source": r["image"], "tile_xy": [r["tile"][0], r["tile"][1]], "location": r["loc"], "wb_gray_world": r["filt"], "visibility": r["vis"]})
            for c, b in r["boxes"]:
                aid += 1
                coco["annotations"].append({"id": aid, "image_id": i, "category_id": c, "bbox": [round(b[0], 2), round(b[1], 2), round(b[2]-b[0], 2), round(b[3]-b[1], 2)],
                                            "area": round((b[2]-b[0])*(b[3]-b[1]), 2), "iscrowd": 0})
            groups[r["image"]].append((r, name))
        jobs = [(root, od, im, rr) for im, rr in groups.items()]
        with Pool(8) as p: gains = p.map(render, jobs, chunksize=32)
        g = np.array([x for x in gains if x is not None])
        stats["wb_images"] = int(len(g)); stats["wb_gain_bgr_mean"] = g.mean(0).round(3).tolist() if len(g) else None
        stats["wb_tiles"] = sum(1 for r in recs if r["filt"])
        json.dump(coco, open(od / "_annotations.coco.json", "w"))
        allstats[split] = stats
        print(split, json.dumps(stats, indent=1), flush=True)
    json.dump(allstats, open(out / "prep_stats.json", "w"), indent=1)

if __name__ == "__main__":
    main()
