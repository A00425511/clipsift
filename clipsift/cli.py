"""python -m clipsift run|export|evaluate"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import protocol as proto
from .config import load_config, resolve_path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}


def _expand(inputs) -> list:
    files = []
    for i in inputs:
        p = Path(i)
        if p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.suffix.lower() in VIDEO_EXT and not f.name.startswith(".")]
        else:
            files.append(p)
    return files


def cmd_run(a) -> int:
    from .pipeline import run
    ov = {}
    if a.layer is not None:
        ov["layer"] = a.layer
    if a.detector:
        ov.setdefault("stages", {})["detector"] = a.detector
    if a.sample_fps:
        ov["sample_fps"] = a.sample_fps
    if a.interval:
        ov.setdefault("protocol", {})["interval_s"] = a.interval
    if a.device:
        ov.setdefault("detector", {}).setdefault("cfd", {})["device"] = a.device
    config_path = a.config
    if a.preset:
        config_path = resolve_path(f"config/presets/{a.preset}.yaml")
        if not Path(config_path).is_file():
            print(f"No preset named '{a.preset}' in config/presets.", file=sys.stderr)
            return 2
        if a.config:
            print("Use either --config or --preset, not both.", file=sys.stderr)
            return 2
    cfg = load_config(config_path, ov)
    out = Path(a.out) if a.out else resolve_path(cfg["paths"]["runs_dir"])
    files = _expand(a.videos)
    if not files:
        print("No video files found.", file=sys.stderr)
        return 2
    groups = proto.group_chapters(files)
    if len(groups) > 1 and (a.video_id or a.id):
        print("--id/--video-id can only be used with one video (one GoPro number).", file=sys.stderr)
        return 2
    for key, paths in groups.items():
        print(f"== video {key}: {[p.name for p in paths]}")
        d = run(paths, cfg, out, recording_id=a.id, video_id=a.video_id,
                window_start_s=a.window_start, window_end_s=a.window_end,
                meta={"transect": a.transect, "stat": a.stat, "year": a.year, "season": a.season, "date": a.date})
        print(f"run folder: {d}")
    return 0


def cmd_verify(a) -> int:
    from .verify import build_review_set
    cfg = load_config(a.config, {})
    if a.device:
        cfg.setdefault("detector", {}).setdefault("cfd", {})["device"] = a.device
    built = build_review_set(a.run_dir, cfg, total=a.count)
    print(f"review set: {built['counts']}")
    return 0


def cmd_export(a) -> int:
    from .export import export_run
    for p in export_run(a.run_dir, a.out):
        print(p)
    return 0


def cmd_evaluate(a) -> int:
    from .evaluate import evaluate, format_report
    rep = evaluate(a.results, a.labels)
    print(format_report(rep))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        rows = rep["rows"]
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
                w.writeheader()
                w.writerows(rows)
        print(f"per-row table: {a.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clipsift")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run", help="process video files (or folders) into run folders")
    r.add_argument("videos", nargs="+")
    r.add_argument("--config"); r.add_argument("--out"); r.add_argument("--layer", type=int, choices=[0, 1, 2])
    r.add_argument("--detector"); r.add_argument("--sample-fps", type=float)
    r.add_argument("--preset", help="name of a file in config/presets, e.g. cfd_medium_clahe")
    r.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], help="device for the cfd detector")
    r.add_argument("--id", help="recording id (folder name)"); r.add_argument("--video-id")
    r.add_argument("--interval", type=float, help="seconds between count points")
    r.add_argument("--window-start", type=float); r.add_argument("--window-end", type=float)
    r.add_argument("--transect"); r.add_argument("--stat"); r.add_argument("--year", type=int); r.add_argument("--season"); r.add_argument("--date")
    r.set_defaults(fn=cmd_run)
    f = sp.add_parser("verify", help="after counting: build the set of model flags for a person to check")
    f.add_argument("run_dir"); f.add_argument("--count", type=int, default=36); f.add_argument("--config")
    f.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"])
    f.set_defaults(fn=cmd_verify)
    e = sp.add_parser("export", help="write CSVs for a run folder")
    e.add_argument("run_dir"); e.add_argument("--out")
    e.set_defaults(fn=cmd_export)
    v = sp.add_parser("evaluate", help="compare results.json with human labels CSV")
    v.add_argument("results", nargs="+"); v.add_argument("--labels", required=True); v.add_argument("--out")
    v.set_defaults(fn=cmd_evaluate)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (FileNotFoundError, ValueError, PermissionError, NotImplementedError, ImportError) as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
