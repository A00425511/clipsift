"""Re-runnable leak-free split maker.  Run:  python3 -I make_splits.py ["path/to/Footage Sources"]
Record of how the committed splits were made; teammates do not need to run it.
Reads only JSON/CSV metadata (no images are copied or opened) from the Footage Sources
folder (default: a "Footage Sources" folder beside the repo) and writes the six JSONs
to <Footage Sources>/splits/.
Seed is fixed (SEED) and recorded in every output file."""
import csv, json, os, re, random, sys, collections as C

SEED = 20261106
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(_REPO), "Footage Sources")
HERE = os.path.join(ROOT, "splits")               # output folder
os.makedirs(HERE, exist_ok=True)
PUGET = os.path.join(ROOT, "Puget Sound LILA")
TWEED = os.path.join(ROOT, "Tweed Estuary")
TMETA = os.path.join(TWEED, "extracted", "Fish_automated_identification_and_counting")

# Puget: whole-site hold-out, chosen by inspection of per-site crab / low-visibility / filter counts
# (see SPLITS.md). Site ids are the `location` field.
PUGET_TEST = ["loc_bccc994d", "loc_bcc8a0b0"]   # prefixes of the full location ids
PUGET_VAL = ["loc_bcbd2c38"]


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def puget():
    d = json.load(open(os.path.join(PUGET, "subset_low_medium_vis.json")))
    locs = sorted({i["location"] for i in d["images"]})
    assert len(locs) == 10, locs
    # resolve ids by prefix so a typo cannot silently pass
    test = [l for l in locs if l[:12] in PUGET_TEST]; val = [l for l in locs if l[:12] in PUGET_VAL]
    assert len(test) == 2 and len(val) == 1, (test, val)
    which = {l: "train" for l in locs}
    for l in test: which[l] = "test"
    for l in val: which[l] = "val"
    boxes = C.defaultdict(list)
    for a in d["annotations"]:
        if "bbox" in a and a["category_id"] != 0:   # empty rows carry no box
            boxes[a["image_id"]].append(a)
    out = {s: {"images": [], "annotations": []} for s in ("train", "val", "test")}
    for im in sorted(d["images"], key=lambda x: x["file_name"]):
        s = which[im["location"]]; o = out[s]
        nid = len(o["images"]) + 1
        o["images"].append({"id": nid, "file_name": im["file_name"], "width": im["width"], "height": im["height"],
                            "orig_id": im["id"], "location": im["location"], "visibility": im["visibility"],
                            "filter": im["filter"], "habitat_type": im["habitat_type"],
                            "deployment": "_".join(im["file_name"][:-4].split("_")[:-2])})
        for a in boxes.get(im["id"], []):
            x, y, w, h = a["bbox"]
            o["annotations"].append({"id": len(o["annotations"]) + 1, "image_id": nid, "category_id": a["category_id"],
                                     "bbox": a["bbox"], "area": w * h, "iscrowd": 0, "orig_id": a["id"],
                                     "sequence_level_annotation": a.get("sequence_level_annotation")})
    for s, o in out.items():
        o["info"] = {"description": "NOAA Puget Sound nearshore fish, low/medium-visibility subset, site-level split: " + s,
                     "seed": SEED, "split": s, "split_key": "location (whole site held out)",
                     "image_root": "Puget Sound LILA/images (relative to Footage Sources/)",
                     "sites_in_this_split": sorted(l for l in locs if which[l] == s),
                     "licence": "CDLA-Permissive-1.0; cite Farrell et al. 2023, Sci Data 10:799",
                     "note": "Training/dev only. fish_or_crab (3) and unknown (4) should be treated as ignore regions, not background. Category 0 'empty' has no boxes; empty frames are images with no annotations."}
        o["image_root"] = "Puget Sound LILA/images"
        o["categories"] = d["categories"]
        o["licenses"] = [{"id": 1, "name": "CDLA-Permissive-1.0"}]
        dump(os.path.join(HERE, "puget_%s.json" % s), o)
    return which


def clip_of(fn):
    return re.sub(r"(_5fps)?_\d+\.jpg$", "", fn)


def tweed():
    t = json.load(open(os.path.join(TMETA, "luderick_seagrass_all.json")))
    rows = list(csv.DictReader(open(os.path.join(TMETA, "dataset_images.csv"))))
    meta = {r["file_name"]: r for r in rows}
    gkey = lambda r: r["deployment"] + "|" + r["date_day/month/year"]
    groups = C.defaultdict(list)
    for r in rows: groups[gkey(r)].append(r["file_name"])
    # every clip must live in one group (checked), so grouping by deployment+date keeps clips whole
    clipgroups = C.defaultdict(set)
    for r in rows: clipgroups[clip_of(r["file_name"])].add(gkey(r))
    assert all(len(v) == 1 for v in clipgroups.values())
    idname = {i["id"]: i["file_name"] for i in t["images"]}
    nbox = C.Counter(); nbream = C.Counter()
    for a in t["annotations"]:
        g = gkey(meta[idname[a["image_id"]]]); nbox[g] += 1; nbream[g] += a["category_id"] == 0
    keys = sorted(groups); N = len(rows)
    target = {"train": .70 * N, "val": .15 * N, "test": .15 * N}
    rng = random.Random(SEED); best = None
    for _ in range(200000):
        asg = {k: rng.choice(("train", "val", "test")) for k in keys}
        n = C.Counter(); b = C.Counter()
        for k in keys: n[asg[k]] += len(groups[k]); b[asg[k]] += nbream[k]
        cost = sum(abs(n[s] - target[s]) for s in target)
        cost += sum(200 for s in ("val", "test") if b[s] < 15)   # keep some bream in val and test
        if best is None or cost < best[0]: best = (cost, asg)
    asg = best[1]
    out = {s: {"images": [], "annotations": []} for s in ("train", "val", "test")}
    byimg = C.defaultdict(list)
    for a in t["annotations"]: byimg[a["image_id"]].append(a)
    for im in sorted(t["images"], key=lambda x: x["file_name"]):
        r = meta[im["file_name"]]; s = asg[gkey(r)]; o = out[s]; nid = len(o["images"]) + 1
        o["images"].append({"id": nid, "file_name": im["file_name"], "width": im["width"], "height": im["height"],
                            "orig_id": im["id"], "clip": clip_of(im["file_name"]), "deployment": r["deployment"],
                            "date": r["date_day/month/year"], "dataset": r["dataset"], "published_split": r["suggested_use"]})
        for a in byimg[im["id"]]:
            o["annotations"].append({"id": len(o["annotations"]) + 1, "image_id": nid, "category_id": a["category_id"],
                                     "bbox": a["bbox"], "area": a["area"], "iscrowd": 0, "orig_id": a["id"]})
    for s, o in out.items():
        o["info"] = {"description": "Tweed/Tallebudgera luderick-seagrass, deployment+date split: " + s, "seed": SEED, "split": s,
                     "split_key": "deployment + date (published train/test split ignored; it leaks clip 2205_Luderick_25.mov)",
                     "groups_in_this_split": sorted(k for k in keys if asg[k] == s),
                     "image_root": "Tweed Estuary/images (relative to Footage Sources/)",
                     "licence": "CC-BY-4.0; cite Ditria et al. 2021, Front. Mar. Sci. 8:629485",
                     "note": "Training/dev only. Boxes can overhang the image edge by up to 2 px; clip when training."}
        o["image_root"] = "Tweed Estuary/images"
        o["categories"] = t["categories"]
        o["licenses"] = [{"id": 1, "name": "CC-BY-4.0"}]
        dump(os.path.join(HERE, "tweed_%s.json" % s), o)
    return asg


if __name__ == "__main__":
    print("seed", SEED)
    print("puget sites:", puget())
    print("tweed groups:", tweed())
