"""Suggest a hand mask for the pipe and pole from boxes that recur in the same place.

It only SUGGESTS. A person must open the PNG over a frame, check it covers the pipe and pole and
not the water where fish swim, edit the polygons if needed, and then point config static_filter.masks at the JSON.

Sources of boxes (give one):
  --run runs/<id>/results.json   uses boxes the pipeline already marked static with reason "persistent"
                                 (or --all-static for any static reason except mask)
  --boxes frames.json            recomputes persistence from {"width","height","frames":[{"t","boxes":[[x,y,w,h,score],..]}]}
                                 (frames with no boxes still count). Uses the static_filter.persistence settings.
Outputs (original pixels):
  --json mask.json   {"width","height","polygons":[[[x,y],..],..],"note"}   use in config: masks: [{match: ..., file: mask.json}]
  --png mask.png     white = excluded, black = analysed (view it beside a frame, or use --overlay frame.jpg)
  --overlay FRAME    also writes <png stem>_overlay.jpg: the frame with the polygons drawn on it

Example:
  python tools/make_static_mask.py --run runs/411/results.json --json config/masks/t1s2.json --png config/masks/t1s2.png --overlay frame.jpg
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clipsift import static_filter as sfm  # noqa: E402
from clipsift.config import load_config  # noqa: E402
from clipsift.schema import Detection  # noqa: E402


def boxes_from_run(path, all_static=False):
    res = json.loads(Path(path).read_text(encoding="utf-8"))
    rec = res["recording"]
    dets = [d for s in res["subsamples"] for d in s["auto"]["detections"]]
    dets += [d for g in res["segments"] for d in g["detections"]]
    keep = []
    for d in dets:
        if not d.get("static"):
            continue
        why = (d.get("static_reason") or "").split("+")
        if "persistent" in why or (all_static and any(w != "mask" for w in why)):
            keep.append(d["box"])
    return keep, rec["width"], rec["height"]


def boxes_from_frames(path, cfg):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    frames = [(f["t"], [Detection(t=f["t"], box=b[:4], score=b[4] if len(b) > 4 else 1.0) for b in f["boxes"]])
              for f in d["frames"]]
    over = {"static_filter": {"enabled": True, "movement": {"enabled": False}, "masks": []}}
    c = sfm.settings({"static_filter": {**cfg.get("static_filter", {}), **over["static_filter"]}})
    sfm.apply(frames, {"static_filter": c}, d["width"], d["height"])
    return [x.box for _, ds in frames for x in ds if x.static], d["width"], d["height"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run"); ap.add_argument("--boxes"); ap.add_argument("--all-static", action="store_true")
    ap.add_argument("--json"); ap.add_argument("--png"); ap.add_argument("--overlay")
    ap.add_argument("--pad", type=float, default=0.25, help="grow each box by this share of its size (default 0.25)")
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    if bool(a.run) == bool(a.boxes):
        ap.error("give exactly one of --run or --boxes")
    if not (a.json or a.png):
        ap.error("give --json and/or --png")
    try:
        if a.run:
            boxes, w, h = boxes_from_run(a.run, a.all_static)
        else:
            boxes, w, h = boxes_from_frames(a.boxes, load_config(a.config))
    except (OSError, KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    polys = sfm.suggest_polygons(boxes, w, h, pad=a.pad)
    print(f"{len(boxes)} persistent boxes -> {len(polys)} polygons ({w}x{h}). CHECK IT BY EYE before using it.")
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps({
            "width": w, "height": h, "polygons": polys,
            "note": "Suggested from boxes that recurred in the same place. Not checked by a person yet."},
            indent=1), encoding="utf-8")
        print("wrote", a.json)
    m = np.zeros((h, w), np.uint8)
    for p in polys:
        cv2.fillPoly(m, [np.round(np.array(p)).astype(np.int32)], 255)
    if a.png:
        Path(a.png).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(a.png, m)
        print("wrote", a.png)
        if a.overlay:
            fr = cv2.imread(a.overlay)
            if fr is None:
                print(f"Error: cannot read {a.overlay}", file=sys.stderr)
                return 1
            fr = cv2.resize(fr, (w, h))
            tint = fr.copy()
            tint[m > 0] = (0, 0, 255)
            fr = cv2.addWeighted(fr, 0.6, tint, 0.4, 0)
            for p in polys:
                cv2.polylines(fr, [np.round(np.array(p)).astype(np.int32)], True, (0, 255, 255), 3)
            out = Path(a.png).with_name(Path(a.png).stem + "_overlay.jpg")
            cv2.imwrite(str(out), fr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
