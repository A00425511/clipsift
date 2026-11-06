"""Make a FAKE sample run at runs/_fixture so the review app can be tried without footage.

    python -m app.fixtures.make_fixture [--runs runs]

Everything here is generated (murky noise plus moving blobs). It is not real data.
Existing reviews.jsonl and grid_tags.jsonl are left alone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

W, H, FPS, N_FRAMES = 640, 360, 12, 24
DURATION = 600.0


def murky(rng, shift=0):
    y = np.linspace(40, 85, H, dtype=np.float32)[:, None]
    base = np.repeat(y, W, axis=1)
    noise = cv2.GaussianBlur(rng.normal(0, 9, (H, W)).astype(np.float32), (0, 0), 6)
    g = np.clip(base + noise + shift, 0, 255)
    img = np.dstack([g * 0.7, g * 1.0, g * 0.8]).astype(np.uint8)  # green-brown tint (BGR)
    return img


def draw_fish(img, cx, cy, size, angle=0.0):
    cv2.ellipse(img, (int(cx), int(cy)), (size, size // 3), angle, 0, 360, (150, 175, 160), -1)
    tail = np.array([[cx - size, cy], [cx - size - size // 2, cy - size // 3], [cx - size - size // 2, cy + size // 3]])
    cv2.fillPoly(img, [tail.astype(np.int32)], (140, 165, 150))


def frame_at(rng_seed, t, fish):
    img = murky(np.random.default_rng(rng_seed))
    for i, (x0, y0, size) in enumerate(fish):
        draw_fish(img, x0 + t * 160 * (1 if i % 2 == 0 else -1), y0 + 8 * np.sin(t * 6 + i), size)
    return img


def write_loop(path: Path, seed, fish, n_frames=N_FRAMES):
    """Short H.264 clip. Browsers cannot play mp4v, so warn if only that is available."""
    for code in ("avc1", "H264", "mp4v"):
        vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*code), FPS, (W, H))
        if vw.isOpened():
            break
    else:
        raise RuntimeError("OpenCV could not open any video writer")
    if code == "mp4v":
        print("WARNING: no H.264 encoder here; loops may not play in a browser.")
    for k in range(n_frames):
        vw.write(frame_at(seed, k / FPS, fish))
    vw.release()


CTX_S = 1.5  # fixture-only context (real default is 5 s) to keep the sample small


def school(rng, n, x0=60, x1=560, y0=40, y1=300):
    return [(int(rng.integers(x0, x1)), int(rng.integers(y0, y1)), 7) for _ in range(n)]


def make_subsample(ss_dir: Path, seed, fish, files=("still", "diff", "context")):
    """Still at the exact point time, plus a 3 s clip centred on it (count second starts at CTX_S)."""
    ss_dir.mkdir(parents=True, exist_ok=True)
    a, b = frame_at(seed, 0.0, fish), frame_at(seed, 0.083, fish)
    if "still" in files:
        cv2.imwrite(str(ss_dir / "still.jpg"), a)
    if "diff" in files:
        cv2.imwrite(str(ss_dir / "diff.jpg"), np.clip(cv2.absdiff(a, b).astype(np.int32) * 6, 0, 255).astype(np.uint8))
    if "context" in files:
        write_loop(ss_dir / "context.mp4", seed, fish, n_frames=int(2 * CTX_S * FPS))


def make_segment(seg_dir: Path, seed, fish, files=("still", "diff", "loop")):
    seg_dir.mkdir(parents=True, exist_ok=True)
    a, b = frame_at(seed, 0.0, fish), frame_at(seed, 0.5, fish)
    if "still" in files:
        cv2.imwrite(str(seg_dir / "still.jpg"), b)
    if "diff" in files:
        d = cv2.absdiff(a, b)
        d = np.clip(d.astype(np.int32) * 4, 0, 255).astype(np.uint8)
        cv2.imwrite(str(seg_dir / "diff.jpg"), d)
    if "loop" in files:
        write_loop(seg_dir / "loop.mp4", seed, fish)


def det(t, box, score, track, source="fixture"):
    return {"t": t, "box": box, "score": score, "track_id": track, "source": source}


def track(tid, s, e, n, topk, status):
    return {"track_id": tid, "start_s": s, "end_s": e, "n_points": n, "species_topk": topk, "status": status}


def seg(i, start, end, kind, status, **kw):
    base = {"segment_id": f"seg_{i:04d}", "start_s": start, "end_s": end, "kind": kind,
            "audit_sample": False, "motion_score": 0.5, "flags": {"shake": False, "low_visibility": False},
            "visibility_score": 0.6, "status": status, "still_time_s": round((start + end) / 2, 2),
            "detections": [], "tracks": [],
            "counts": {"maxn": None, "maxn_time_s": None, "mean_count": None, "unique_tracks": None},
            "review_priority": 0.5}
    base.update(kw)
    return base


def build(runs_root: Path):
    run = runs_root / "_fixture"
    (run / "segments").mkdir(parents=True, exist_ok=True)
    fish_sets = {
        1: [(120, 160, 40), (400, 220, 30)], 2: [(200, 180, 28)], 3: [(300, 150, 24)],
        4: [(260, 200, 20)], 5: [], 6: [], 7: [(500, 100, 18)], 8: [(150, 250, 16)],
        9: [(100, 100, 34), (350, 180, 30), (480, 260, 26)], 10: [(220, 140, 30)],
        11: [(300, 220, 32)], 12: [],
    }
    salmon = [{"name": "Salmo salar", "aphia_id": 127186, "score": 0.81},
              {"name": "Salvelinus fontinalis", "aphia_id": 127190, "score": 0.12}]
    pickerel = [{"name": "Esox niger", "aphia_id": 154389, "score": 0.64}]
    segs = [
        seg(1, 30, 42, "active", "known", motion_score=0.82, review_priority=0.35,
            detections=[det(36.0, [110, 150, 90, 40], 0.93, 1), det(36.0, [390, 215, 70, 30], 0.88, 2)],
            tracks=[track(1, 31, 41, 20, salmon, "known"), track(2, 33, 40, 14, pickerel, "known")],
            counts={"maxn": 2, "maxn_time_s": 36.0, "mean_count": 1.4, "unique_tracks": 2}),
        seg(2, 75, 85, "active", "fish_unknown", motion_score=0.6, visibility_score=0.2,
            flags={"shake": False, "low_visibility": True}, review_priority=0.72,
            detections=[det(80.0, [190, 170, 60, 26], 0.55, 3)],
            tracks=[track(3, 77, 84, 9, [], "fish_unknown")],
            counts={"maxn": 1, "maxn_time_s": 80.0, "mean_count": 0.8, "unique_tracks": 1}),
        seg(3, 120, 131, "active", "unclear", motion_score=0.4, flags={"shake": True, "low_visibility": False},
            review_priority=0.8, detections=[det(125.0, [290, 140, 50, 22], 0.31, None)],
            counts={"maxn": 1, "maxn_time_s": 125.0, "mean_count": None, "unique_tracks": None}),
        seg(4, 200, 214, "active", "movement_unidentified", motion_score=0.7, visibility_score=None,
            review_priority=0.9),
        seg(5, 260, 270, "active", "none", motion_score=0.1, review_priority=0.1,
            counts={"maxn": 0, "maxn_time_s": None, "mean_count": 0.0, "unique_tracks": 0}),
        seg(6, 300, 380, "set_aside", "none", motion_score=0.0, still_time_s=340.0, review_priority=0.0),
        seg(7, 390, 450, "set_aside", "none", audit_sample=True, motion_score=0.02, review_priority=0.95),
        seg(8, 460, 500, "set_aside", "movement_unidentified", audit_sample=True, motion_score=0.05,
            flags={"shake": True, "low_visibility": True}, visibility_score=0.1, review_priority=0.97),
        seg(9, 510, 530, "active", "known", motion_score=0.95,
            flags={"shake": True, "low_visibility": True}, review_priority=0.6,
            detections=[det(515.0, [90, 90, 80, 34], 0.9, 4), det(515.0, [340, 170, 70, 30], 0.7, 5),
                        det(515.0, [470, 250, 60, 26], 0.45, None, "motion")],
            tracks=[track(4, 511, 528, 30, salmon, "known"), track(5, 512, 525, 22, [], "unclear")],
            counts={"maxn": 3, "maxn_time_s": 515.0, "mean_count": 2.1, "unique_tracks": 2}),
        seg(10, 540, 552, "active", "fish_unknown", motion_score=None, visibility_score=None,
            still_time_s=None, review_priority=None),
        seg(11, 560, 572, "active", "fish_unknown", motion_score=0.5, review_priority=0.55,
            detections=[det(566.0, [280, 205, 64, 28], 0.6, None)]),
        seg(12, 575, 600, "set_aside", "none", motion_score=None, visibility_score=None, review_priority=0.0),
    ]
    for s in segs:
        n = int(s["segment_id"][-4:])
        files = {11: ("still", "diff"), 12: ()}.get(n, ("still", "diff", "loop"))
        if n == 10:
            files = ("still", "loop")  # no diff image
        if n == 12:
            continue  # no segment folder at all
        make_segment(run / "segments" / s["segment_id"], n, fish_sets[n], files)
    rng = np.random.default_rng(7)
    ss_specs = [  # (t_s, fish positions, auto dict overrides, extras, files)
        (60, school(rng, 3), dict(fish_count=3, invertebrate_count=0, motion_near_point=True), {}, None),
        (120, school(rng, 34), dict(fish_count=22, invertebrate_count=0, motion_near_point=True), {"qc_sample": True}, None),
        (180, [], dict(fish_count=0, invertebrate_count=0), {}, None),
        (240, school(rng, 2), dict(fish_count=None, invertebrate_count=None, visibility_score=None), {}, None),
        (300, school(rng, 5), dict(fish_count=4, invertebrate_count=1, movement_unidentified=2), {"qc_sample": True}, None),
        (360, school(rng, 6), dict(fish_count=6, invertebrate_count=0), {}, ("still", "diff")),  # no context clip
        (420, school(rng, 4), dict(fish_count=2, invertebrate_count=0), {"review_priority": None}, ("still", "context")),  # no diff
        (480, school(rng, 12), dict(fish_count=9, invertebrate_count=2, points=[[100, 100, 0.8], [300, 220, 0.6]]), {}, None),
        (540, school(rng, 1), dict(fish_count=1, invertebrate_count=0, visibility_score=0.15), {}, None),
    ]
    subsamples = []
    for i, (t, fish, over, extra, files) in enumerate(ss_specs, 1):
        ssid = f"ss_{i:02d}"
        auto = {"fish_count": None, "invertebrate_count": None, "detections": [], "motion_near_point": False,
                "movement_unidentified": 0, "visibility_score": 0.5}
        auto.update(over)
        if auto["fish_count"]:
            auto["detections"] = [det(float(t), [int(x) - 14, int(y) - 7, 28, 14], 0.6, None) for x, y, _ in fish[:3]]
        sub = {"subsample_id": ssid, "t_s": float(t), "context_start_s": t - CTX_S, "context_end_s": t + CTX_S,
               "auto": auto, "qc_sample": False, "review_priority": round(0.9 - 0.08 * i, 2)}
        sub.update(extra)
        subsamples.append(sub)
        make_subsample(run / "subsamples" / ssid, 100 + i, fish, files or ("still", "diff", "context"))
    auto_means = [x["auto"]["fish_count"] for x in subsamples if x["auto"]["fish_count"] is not None]
    active = [s for s in segs if s["kind"] == "active"]
    results = {
        "schema_version": "0.2", "fixture": True,
        "recording": {"recording_id": "_fixture", "source_files": ["FAKE_GENERATED"], "duration_s": DURATION,
                      "fps": float(FPS), "width": W, "height": H, "site": None, "date": None,
                      "video_id": "_fixture", "transect": "T1", "stat": "STAT 1", "year": 2026, "season": "fall"},
        "protocol": {"trim_start_s": 60, "trim_end_s": 60, "extra_trim_max_s": 240, "window_length_s": 900,
                     "interval_s": 60, "context_s": CTX_S, "count_window_s": 1, "count_tolerance_s": 0.5,
                     "qc_share": 0.10, "qc_min": 6, "qc_max": 12, "qc_max_percent_diff": 6, "qc_agreement": 95,
                     "window_start_s": 60, "window_end_s": 540},
        "run": {"layer": 1, "model_version": None, "config_hash": "fixture", "created_at": "2026-01-01T00:00:00Z",
                "sample_fps": 2.0, "runtime_s": 0.0, "stage_runtimes_s": {}},
        "subsamples": subsamples,
        "segments": segs,
        "summary": {"n_segments": len(segs), "n_active": len(active), "n_set_aside": len(segs) - len(active),
                    "n_audit": sum(1 for s in segs if s["audit_sample"]), "maxn": 3, "mean_count": None,
                    "unique_tracks": None,
                    "mean_count_auto": round(sum(auto_means) / len(auto_means), 3), "mean_count_reviewed": None,
                    "n_subsamples": len(subsamples)},
    }
    (run / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (run / "FIXTURE.txt").write_text("FAKE sample data made by app/fixtures/make_fixture.py. Not real footage.\n")
    return run


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", default="runs")
    print("Fixture written to", build(Path(p.parse_args().runs)))


if __name__ == "__main__":
    main()
