"""Balanced train subset from tiles/puget_v1/train (symlinks, no copies). Seed 20261106, ceiling 16,000 tiles.
Keep every crab tile; cap fish-only positive tiles per site (cap lowered from 3000 only if needed for the ceiling);
empties ~20% of total, equal quota per site with spill."""
import json, random, collections, os
from pathlib import Path
H = Path(__file__).resolve().parent; T = H/"tiles"/"puget_v1"
CEIL, CAP0, EMPTY = 16000, 3000, 0.20
d = json.load(open(T/"train"/"_annotations.coco.json"))
cls = collections.defaultdict(set)
for a in d["annotations"]: cls[a["image_id"]].add(a["category_id"])
crab, fish, emp = [], collections.defaultdict(list), collections.defaultdict(list)
for im in d["images"]:
    c = cls.get(im["id"], set())
    if 1 in c: crab.append(im)
    elif 0 in c: fish[im["location"]].append(im)
    else: emp[im["location"]].append(im)
rng = random.Random(20261106)
for v in list(fish.values())+list(emp.values()): rng.shuffle(v)
def build(cap):
    pos = list(crab) + [i for s in fish for i in fish[s][:cap]]
    n_emp = int(round(len(pos)*EMPTY/(1-EMPTY)))
    return pos, n_emp
cap = CAP0
while True:
    pos, n_emp = build(cap)
    if len(pos)+n_emp <= CEIL: break
    cap -= 50
pos, n_emp = build(cap)
chosen, left = [], {s: list(v) for s, v in emp.items()}; active = sorted(left)
while len(chosen) < n_emp and active:
    q = max(1, (n_emp-len(chosen))//len(active)); nxt = []
    for s in active:
        chosen += left[s][:q]; left[s] = left[s][q:]
        if left[s]: nxt.append(s)
        if len(chosen) >= n_emp: break
    active = nxt
chosen = chosen[:n_emp]
sel = {i["id"] for i in pos+chosen}
out = T/"train_balanced"; out.mkdir(exist_ok=True)
for f in out.glob("*.jpg"): f.unlink()
nd = {"info": {"description": f"balanced subset of puget_v1/train, fish-only cap/site {cap}, seed 20261106"}, "categories": d["categories"], "images": [], "annotations": []}
remap = {}
for im in d["images"]:
    if im["id"] in sel:
        remap[im["id"]] = len(nd["images"]); nd["images"].append({**im, "id": remap[im["id"]]})
        os.symlink(os.path.relpath(T/"train"/im["file_name"], out), out/im["file_name"])
aid = 0
for a in d["annotations"]:
    if a["image_id"] in remap:
        aid += 1; nd["annotations"].append({**a, "id": aid, "image_id": remap[a["image_id"]]})
json.dump(nd, open(out/"_annotations.coco.json", "w"))
root = T.parent/"puget_bal_root"; root.mkdir(exist_ok=True)
for n, tgt in (("train", out), ("valid", T/"valid")):
    l = root/n
    if l.is_symlink(): l.unlink()
    os.symlink(os.path.relpath(tgt, root), l)
site = collections.Counter(i["location"][:12] for i in nd["images"])
cat = collections.defaultdict(collections.Counter)
im_loc = {i["id"]: i["location"][:12] for i in nd["images"]}
for a in nd["annotations"]: cat[im_loc[a["image_id"]]][a["category_id"]] += 1
st = {"cap_used": cap, "tiles": len(nd["images"]), "crab_tiles": len(crab), "fish_only_tiles": len(pos)-len(crab), "empty_tiles": len(chosen),
      "per_site_tiles": dict(site), "per_site_boxes_fish": {s: cat[s][0] for s in site}, "per_site_boxes_crab": {s: cat[s][1] for s in site},
      "boxes_fish": sum(c[0] for c in cat.values()), "boxes_crab": sum(c[1] for c in cat.values()),
      "crab_tiles_by_site": dict(collections.Counter(i["location"][:12] for i in crab))}
json.dump(st, open(T/"train_balanced_stats.json", "w"), indent=1); print(json.dumps(st, indent=1))
