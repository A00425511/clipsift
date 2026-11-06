"""Pipeline: video files -> run folder (results.json, subsample and segment media).

Order of work:
  1. subsample points (main review unit): stills, diffs, context clips from the ORIGINALS,
     then a quick pass over only the context windows
  2. full-window motion scan (supporting pass): segments, set-aside, audit samples
  3. Layer 1 only: detector, tracker, classifier, counter on active segments
Per-stage runtimes are recorded. Counts are relative indices, not abundance.

TODO (crash safety): save per-chunk progress so a crash does not restart a recording.
"""
from __future__ import annotations

import copy
import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from . import protocol as proto
from . import static_filter as sfm
from .config import ROOT as ROOT_DIR, config_hash
from .schema import (Counts, Detection, Recording, Results, Run, Subsample, Track, validate)
from .stages import get_backend
from .stages.layer1 import tiled_detect
from .stages.base import list_backends  # noqa: F401
from .video import Timeline, resize_to_width


class _Timer:
    def __init__(self):
        self.t = {}

    def stage(self, name):
        timer = self

        class _C:
            def __enter__(s):
                s.t0 = time.perf_counter()

            def __exit__(s, *a):
                timer.t[name] = timer.t.get(name, 0.0) + time.perf_counter() - s.t0
        return _C()


def _mid_share(dets, rc) -> float:
    """Share of detections whose score sits in the mid-confidence band (review.mid_conf_*)."""
    dets = sfm.live(dets)  # rejected static boxes do not drive review order
    if not dets or not rc:
        return 0.0
    lo, hi = rc["mid_conf_low"], rc["mid_conf_high"]
    sc = [(d.score if isinstance(d, Detection) else d["score"]) for d in dets]
    return sum(1 for v in sc if lo <= v <= hi) / len(sc)


def review_priority_segment(seg, rc=None) -> float:
    """Higher comes first. Audit samples and uncertain segments rank high."""
    if seg.kind == "set_aside":
        return 0.85 if seg.audit_sample else 0.0
    base = {"movement_unidentified": 0.7, "unclear": 0.7, "fish_unknown": 0.6, "known": 0.3}.get(seg.status, 0.5)
    if seg.flags.low_visibility or seg.flags.shake:
        base += 0.1
    base += 0.15 * _mid_share(seg.detections, rc)  # mid-confidence boxes are what a person should check first
    return min(1.0, base)


def review_priority_subsample(ss, rc=None, detector_ran=False) -> float:
    """Higher comes first. With a model detector: mid-confidence detections and disagreement between
    motion and detections (motion but no boxes, or boxes but no motion) rank first. QC samples stay top."""
    a = ss.auto
    p = 0.5 + (0.2 if a["motion_near_point"] else 0.0) + (0.1 if a["movement_unidentified"] else 0.0)
    p += 0.1 if a["visibility_score"] < 0.25 else 0.0
    if detector_ran:
        has = bool(sfm.live(a["detections"]))
        if has != bool(a["motion_near_point"]):
            p += 0.2
        p += 0.25 * _mid_share(a["detections"], rc)  # scaled by share, so points stay distinguishable
        p = min(p, 0.94)
    if ss.qc_sample:
        p = max(p, 0.95)
    return min(1.0, p)


def subsample_status(auto: dict) -> str:
    """Suggested status for a point: boxes present is fish_unknown; motion without boxes stays
    movement_unidentified (never dropped); neither is none."""
    if sfm.live(auto["detections"]):
        return "fish_unknown"
    if auto["motion_near_point"] or auto["movement_unidentified"]:
        return "movement_unidentified"
    return "none"


# ---------------------------------------------------------------- media helpers
def diff_from_frames(still, frames):
    """Black and white difference image: absolute difference between `still` and the median of `frames`
    (all the same shape as `still`). Bright means it changed. Contrast is stretched for viewing only.
    tools/make_label_set.py uses this too, so the label page's Movement view matches the review app."""
    if len(frames) < 3:
        return np.zeros(still.shape[:2], np.uint8)
    bg = np.median(np.stack(frames), axis=0)
    d = np.abs(still.astype(np.float32) - bg).max(axis=2)
    d = cv2.GaussianBlur(d, (3, 3), 0)
    hi = max(float(np.percentile(d, 99.5)), 8.0)
    return np.clip(d * 255.0 / hi, 0, 255).astype(np.uint8)


def make_diff_image(timeline: Timeline, t: float, a: float, b: float, n: int = 7):
    """Difference between the still and the median of frames across [a, b], from originals.
    Contrast is stretched for viewing. The original files are never changed."""
    still = timeline.get_frame(t)
    if still is None:
        return None
    ts = np.linspace(a, max(a, b - 0.05), n)
    frames = [f for f in (timeline.get_frame(x) for x in ts) if f is not None and f.shape == still.shape]
    return diff_from_frames(still, frames)


def write_still_and_diff(timeline, out_dir: Path, t, a, b, fr=None):
    """Write still.jpg and diff.jpg. Pass `fr` (the original frame at t) to avoid decoding it twice."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if fr is None:
        fr = timeline.get_frame(t)
    if fr is not None:
        cv2.imwrite(str(out_dir / "still.jpg"), fr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    d = make_diff_image(timeline, t, a, b)
    if d is not None:
        cv2.imwrite(str(out_dir / "diff.jpg"), d, [cv2.IMWRITE_JPEG_QUALITY, 90])


# ---------------------------------------------------------------- detection helper
def detect_track_classify(frames, scale, detector, tracker, classifier, tiling=None):
    """frames: list of (t, bgr). Boxes are scaled by `scale` to original pixels.
    Returns (detections, tracks, sample_times)."""
    detector.prepare([f for _, f in frames])
    per_frame = []
    for t, f in frames:
        if tiling and tiling.get("enabled"):
            ds = tiled_detect(detector, f, t, tiling["tile_size"], tiling["overlap"], tiling["nms_iou"])
        else:
            ds = detector.detect(f, t)
        for d in ds:
            d.box = [v * scale for v in d.box]
        per_frame.append(ds)
    tracks = tracker.track(per_frame)
    by_t = {t: f for t, f in frames}
    all_dets = [d for ds in per_frame for d in ds]
    for tr in tracks:
        pts = [d for d in all_dets if d.track_id == tr.track_id]
        best = max(pts, key=lambda d: d.score)
        f = by_t[best.t]
        x, y, w, h = (int(v / scale) for v in best.box)
        crop = f[max(0, y):max(0, y) + max(1, h), max(0, x):max(0, x) + max(1, w)]
        tr.species_topk = classifier.classify(crop)[:3]
        tr.status = "fish_unknown" if tr.species_topk[0].name == "fish_unknown" else "known"
    return all_dets, tracks, [t for t, _ in frames]


def sparse_detect(frames, detector, log=None):
    """Single-frame detection for model backends (cfd). `frames` yields (t, original-resolution BGR).
    Frames are far apart in time, so there is no tracking: each frame stands alone and
    unique_tracks stays null. Returns (detections, per-frame counts {t: n}, Counts)."""
    dets, per_t = [], {}
    for t, f in frames:
        ds = detector.detect(f, t)
        per_t[t] = len(ds)
        dets += ds
        if log:
            log(f"  detect t={t:.1f}s: {len(ds)} boxes")
    if not per_t:
        return dets, per_t, Counts(maxn=0, maxn_time_s=None, mean_count=0.0, unique_tracks=None)
    tmax = max(per_t, key=lambda k: per_t[k])
    return dets, per_t, Counts(maxn=per_t[tmax], maxn_time_s=tmax if per_t[tmax] else None,
                               mean_count=sum(per_t.values()) / len(per_t), unique_tracks=None)


def recount_frames(per_t_dets: dict) -> Counts:
    """Counts from {t: [Detection]} ignoring static boxes. Same fields as sparse_detect's Counts."""
    per_t = {t: len(sfm.live(ds)) for t, ds in per_t_dets.items()}
    if not per_t:
        return Counts(maxn=0, maxn_time_s=None, mean_count=0.0, unique_tracks=None)
    tmax = max(per_t, key=lambda k: per_t[k])
    return Counts(maxn=per_t[tmax], maxn_time_s=tmax if per_t[tmax] else None,
                  mean_count=sum(per_t.values()) / len(per_t), unique_tracks=None)


def _score(d) -> float:
    return d["score"] if isinstance(d, dict) else getattr(d, "score", 0.0)


def segment_status(tracks, cc) -> str:
    if not tracks:
        return "movement_unidentified"
    if any(t.status == "known" and t.species_topk[0].score >= cc["known_threshold"] for t in tracks):
        return "known"
    if any(t.status == "known" and t.species_topk[0].score >= cc["unclear_threshold"] for t in tracks):
        return "unclear"
    return "fish_unknown"


# ---------------------------------------------------------------- main
def run(video_paths, config: dict, out_dir, recording_id=None, video_id=None,
        window_start_s=None, window_end_s=None, log=print) -> Path:
    """Run the pipeline on one recording (one or more chapter files, used in name order).
    Writes <out_dir>/<recording_id>/ and returns that folder."""
    cfg = copy.deepcopy(config)
    layer = int(cfg["layer"])
    pc = cfg["protocol"]
    paths = sorted((Path(p) for p in video_paths), key=lambda p: p.name)
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(f"Video file not found: {p}")
    tm = _Timer()
    t_run = time.perf_counter()
    timeline = Timeline(paths)
    info = proto.parse_names([str(p) for p in paths])
    vid = video_id or cfg["recording"].get("video_id") or info["video_id"]
    rec_id = recording_id or vid or paths[0].stem
    run_dir = Path(out_dir) / rec_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ws, we = proto.analysis_window(timeline.duration_s, pc,
                                   window_start_s if window_start_s is not None else pc.get("window_start_s"),
                                   window_end_s if window_end_s is not None else pc.get("window_end_s"))
    for w in proto.window_warnings(timeline.duration_s, ws, we, pc):
        warnings.warn(w)

    # Backends. Layer 0 never loads detector/tracker/classifier/counter.
    proposer = get_backend("proposer", cfg["stages"]["proposer"], cfg)
    det = trk = cls = cnt = None
    if layer >= 1:
        det = get_backend("detector", cfg["stages"]["detector"], cfg)
        trk = get_backend("tracker", cfg["stages"]["tracker"], cfg)
        cls = get_backend("classifier", cfg["stages"]["classifier"], cfg)
        cnt = get_backend("counter", cfg["stages"]["counter"], cfg)
        if getattr(det, "load_s", None):
            tm.t["detector_load"] = det.load_s
    full_res = layer >= 1 and bool(getattr(det, "needs_full_res", False))
    rc = cfg.get("review")
    cm = None
    if layer >= 1 and cfg["stages"].get("counting_model"):
        cm = get_backend("counting_model", cfg["stages"]["counting_model"], cfg)
    scale_det = lambda fr: timeline.width / fr.shape[1]  # noqa: E731
    dw = cfg["detect_width"]

    # ---- 1. subsample points: media from originals, then quick pass over context windows
    sfm_base = ROOT_DIR
    sf_on = full_res and bool(sfm.settings(cfg)["enabled"])
    sf_frames: list = []   # (t, [Detection]) for every full-resolution frame the detector saw
    sf_segs: dict = {}     # segment_id -> {t: [Detection]}
    times = proto.subsample_times(ws, we, pc)
    qc = proto.pick_qc(len(times), pc)
    subsamples = []
    log(f"plan: {len(times)} points")
    qcfg = copy.deepcopy(cfg)
    qcfg["sample_fps"] = pc["context_sample_fps"]
    quick = get_backend("proposer", cfg["stages"]["proposer"], qcfg)
    for i, t in enumerate(times):
        sid = f"ss_{i + 1:02d}"
        c0, c1 = max(0.0, t - pc["context_s"]), min(timeline.duration_s, t + pc["context_s"])
        ss = Subsample(subsample_id=sid, t_s=t, context_start_s=c0, context_end_s=c1, qc_sample=i in qc)
        d = run_dir / "subsamples" / sid
        with tm.stage("subsample_media"):
            still = timeline.get_frame(t)  # original resolution, also what a full-res detector sees
            write_still_and_diff(timeline, d, t, c0, c1, fr=still)
            timeline.cut_loop(c0, c1, d / "context.mp4", cfg["loop"]["max_width"], cfg["loop"]["crf"])
        with tm.stage("subsample_pass"):
            frames = list(timeline.iter_samples(pc["context_sample_fps"], width=dw, start_s=c0, end_s=c1))
            if frames:
                ss.auto.update(_quick_pass(quick, frames, t, pc, cfg["proxy_width"]))
        if full_res and still is not None:
            # Model detector: run on the exact-time still at full resolution (tiled inside the backend).
            # Suggestions only. invertebrate_count stays null: the model finds fish only.
            with tm.stage("subsample_detect"):
                dets = det.detect(still, t)
            if sf_on:
                with tm.stage("static_movement"):
                    sfm.score_movement(timeline, t, still, dets, cfg)
                sf_frames.append((t, dets))
            ss.auto["detections"] = dets
            # Boxes at the sensitive threshold are review candidates. The suggested count uses a stricter
            # one, because at 0.05 an empty frame still gets about 50 boxes (pole, seabed, noise).
            count_thr = cfg["detector"].get("cfd", {}).get("count_threshold", 0.0)
            ss.auto["fish_count"] = sum(1 for d in dets if _score(d) >= count_thr)
        elif layer >= 1 and frames and not full_res:
            with tm.stage("subsample_detect"):
                dets, tracks, _ = detect_track_classify(frames, scale_det(frames[0][1]), det, trk, cls, cfg["tiling"])
                lo, hi = t - pc["count_tolerance_s"], t + pc["count_window_s"] + pc["count_tolerance_s"]
                inwin = [x for x in dets if x.track_id is not None and lo <= x.t <= hi]
                exact = [x for x in inwin if t <= x.t <= t + pc["count_window_s"]]
                per_t: dict = {}
                for x in exact:
                    per_t[x.t] = per_t.get(x.t, 0) + 1
                # Counts here are suggestions. invertebrate_count stays null: no backend can tell yet.
                ss.auto["fish_count"] = max(per_t.values()) if per_t else 0
                ss.auto["detections"] = inwin
                if cm is not None:
                    # point-based counts are suggestions; the point nearest the exact time is used
                    tf = min(frames, key=lambda x: abs(x[0] - t))
                    sc = scale_det(tf[1])
                    ss.auto["points"] = [[p[0] * sc, p[1] * sc, p[2]] for p in cm.count_points(tf[1], tf[0])]
                    ss.auto["fish_count"] = len(ss.auto["points"])
        if layer >= 1:
            ss.auto["status"] = subsample_status(ss.auto)
        ss.review_priority = review_priority_subsample(ss, rc, detector_ran=full_res)
        subsamples.append(ss)
        log(f"subsample {sid} at {t:.1f}s" + (f": {ss.auto['fish_count']} suggested" if full_res else ""))

    # ---- 2. one playable video of the window: the protocol asks for it to be watched in real time
    wv = cfg.get("window_video") or {}
    if wv.get("enabled"):
        log("window video")
        with tm.stage("window_video"):
            timeline.cut_window(ws, we, run_dir / "window.mp4", wv.get("max_width", 0), wv.get("crf", 28))

    # ---- optional whole-window motion scan. Off by default: the protocol does not use it
    segments = []
    if cfg.get("motion_scan"):
        with tm.stage("motion_scan"):
            frames_g = timeline.iter_samples(cfg["sample_fps"], width=cfg["proxy_width"], gray=True,
                                             start_s=ws, end_s=we)
            segments = proposer.propose(frames_g, start_s=ws, end_s=we)
        log(f"motion scan: {len(segments)} segments")

    # ---- 3. Layer 1 on active segments
    if layer >= 1:
        for seg in segments:
            if seg.kind != "active":
                continue
            if full_res:
                if not cfg["detect_fps_segments"]:  # 0 means skip the sparse pass; subsample points still run
                    continue
                # Sparse pass: a few original-resolution frames per active segment, never every sample.
                with tm.stage("segment_detect"):
                    frs = timeline.iter_samples(cfg["detect_fps_segments"], width=0,
                                                start_s=seg.start_s, end_s=seg.end_s)
                    dets, per_t, seg.counts = sparse_detect(frs, det)
                if sf_on:
                    by_t = {t_: [] for t_ in per_t}
                    for x in dets:
                        by_t[x.t].append(x)
                    with tm.stage("static_movement"):
                        for t_, ds_ in by_t.items():
                            if ds_:
                                sfm.score_movement(timeline, t_, timeline.get_frame(t_), ds_, cfg)
                    sf_segs[seg.segment_id] = by_t
                    sf_frames += list(by_t.items())
                seg.detections, seg.tracks = dets, []
                seg.status = "fish_unknown" if dets else "movement_unidentified"
                if seg.counts.maxn_time_s is not None:
                    seg.still_time_s = seg.counts.maxn_time_s
                continue
            fr = list(timeline.iter_samples(cfg["sample_fps"], width=dw, start_s=seg.start_s, end_s=seg.end_s))
            if not fr:
                continue
            with tm.stage("detect_track_classify"):
                dets, tracks, st = detect_track_classify(fr, scale_det(fr[0][1]), det, trk, cls, cfg["tiling"])
            with tm.stage("count"):
                seg.counts = cnt.count(tracks, dets, st)
            seg.detections, seg.tracks = dets, tracks
            seg.status = segment_status(tracks, cfg["classifier"])
            if seg.counts.maxn_time_s is not None:
                seg.still_time_s = seg.counts.maxn_time_s

    # ---- static-object filter: persistence needs every sampled frame, so it runs once at the end
    if sf_on:
        with tm.stage("static_filter"):
            summ = sfm.apply(sf_frames, cfg, timeline.width, timeline.height,
                             names=[rec_id, vid, paths[0].stem], base_dir=sfm_base)
        for n in summ["notes"]:
            log(n)
        log(f"static filter: {summ['static']} of {summ['boxes']} boxes marked static "
            f"{summ['reasons']} over {summ['frames']} frames")
        count_thr = cfg["detector"].get("cfd", {}).get("count_threshold", 0.0)
        for ss in subsamples:
            dets = ss.auto["detections"]
            ss.auto["fish_count"] = sum(1 for d in sfm.live(dets) if _score(d) >= count_thr)
            ss.auto["status"] = subsample_status(ss.auto)
            ss.review_priority = review_priority_subsample(ss, rc, detector_ran=True)
        for seg in segments:
            if seg.segment_id in sf_segs:
                seg.counts = recount_frames(sf_segs[seg.segment_id])
                seg.status = "fish_unknown" if sfm.live(seg.detections) else "movement_unidentified"
                seg.still_time_s = seg.counts.maxn_time_s if seg.counts.maxn_time_s is not None else seg.still_time_s

    # ---- media for active and audit segments
    with tm.stage("segment_media"):
        lc = cfg["loop"]
        for i, seg in enumerate(segments):
            seg.review_priority = review_priority_segment(seg, rc if full_res else None)
            if seg.kind == "active" or seg.audit_sample:
                log(f"segment media {i + 1} of {len(segments)}")
                d = run_dir / "segments" / seg.segment_id
                write_still_and_diff(timeline, d, seg.still_time_s, seg.start_s, seg.end_s)
                a = max(seg.start_s, min(seg.still_time_s - lc["max_s"] / 2, seg.end_s - lc["max_s"]))
                timeline.cut_loop(a, min(seg.end_s, a + lc["max_s"]), d / "loop.mp4", lc["max_width"], lc["crf"])

    # ---- results
    sw = model_version = None
    if layer >= 1:
        model_version = det.model_version
    res = Results(
        recording=Recording(recording_id=rec_id, video_id=vid, transect=info["transect"], stat=info["stat"],
                            year=info["year"], season=info["season"], site=cfg["recording"].get("site"),
                            date=cfg["recording"].get("date"), **timeline.meta()),
        run=Run(layer=layer, model_version=model_version, config_hash=config_hash(cfg),
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                sample_fps=cfg["sample_fps"]),
        segments=segments, subsamples=subsamples,
        protocol={**pc, "window_start_s": ws, "window_end_s": we})
    res.compute_summary()
    res.run.stage_runtimes_s = dict(tm.t)
    res.run.runtime_s = time.perf_counter() - t_run
    d = res.to_dict()
    errs = validate(d)
    if errs:
        raise ValueError("results.json would be invalid: " + "; ".join(errs[:5]))
    with open(run_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    log(f"wrote {run_dir / 'results.json'}")
    return run_dir


def _quick_pass(quick, frames, t, pc, proxy_width) -> dict:
    """Cheap motion check over one context window."""
    grays = [(ft, cv2.cvtColor(resize_to_width(f, proxy_width), cv2.COLOR_BGR2GRAY)) for ft, f in frames]
    stats = quick.analyse(grays)
    lo, hi = t - pc["count_tolerance_s"], t + pc["count_window_s"] + pc["count_tolerance_s"]
    near = any(s.confirmed and lo <= s.t <= hi for s in stats)
    runs, prev = 0, False
    for s in stats:
        if s.confirmed and not prev:
            runs += 1
        prev = s.confirmed
    return {"motion_near_point": bool(near), "movement_unidentified": runs,
            "visibility_score": float(np.mean([s.visibility for s in stats])) if stats else 0.0}
