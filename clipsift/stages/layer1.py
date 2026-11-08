"""Layer 1: local detector, tracker, classifier, counter. No GPU needed."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..config import resolve_path
from ..schema import Counts, Detection, SpeciesGuess, Track
from .base import Classifier, Counter, Detector, Tracker, register
from .layer0 import _align


def iou(a, b) -> float:
    """IoU of two [x, y, w, h] boxes."""
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


# --------------------------------------------------------------------- detectors
@register("detector", "onnx")
class OnnxDetector(Detector):
    """YOLO-style ONNX detector (CPU). Needs a model file: nothing is downloaded.

    Set detector.onnx.model_path in the config. Handles output shaped (1, 4+nc, N)
    (YOLOv8-style) or (1, N, 5+nc) with has_objectness: true (YOLOv5-style).
    """

    def __init__(self, cfg):
        self.oc = cfg["detector"]["onnx"]
        mp = self.oc.get("model_path")
        if not mp:
            raise FileNotFoundError("The onnx detector needs a model file. Set detector.onnx.model_path "
                                    "in your config (for example models/fish.onnx), or use "
                                    "stages.detector: motion_blob for the no-model stand-in.")
        path = resolve_path(mp)
        if not Path(path).is_file():
            raise FileNotFoundError(f"ONNX model not found at '{path}'. Put the model file there or set "
                                    "detector.onnx.model_path to its location. ClipSift does not download weights.")
        import onnxruntime as ort
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.model_version = f"{Path(path).name} ({Path(path).stat().st_size} bytes)"
        self.source = f"onnx:{Path(path).name}"

    def preprocess(self, frame):
        size = self.oc["input_size"]
        h, w = frame.shape[:2]
        r = min(size / h, size / w)
        nw, nh = int(round(w * r)), int(round(h * r))
        img = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((size, size, 3), 114, np.uint8)
        px, py = (size - nw) // 2, (size - nh) // 2
        canvas[py:py + nh, px:px + nw] = img
        blob = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        return np.ascontiguousarray(blob), r, px, py

    def postprocess(self, out, r, px, py, shape):
        p = np.squeeze(out)
        if p.ndim != 2:
            return []
        if p.shape[0] < p.shape[1]:
            p = p.T  # (N, C)
        boxes = p[:, :4]
        if self.oc.get("has_objectness"):
            scores_all = p[:, 5:] * p[:, 4:5]
        else:
            scores_all = p[:, 4:]
        cls = scores_all.argmax(1)
        conf = scores_all.max(1)
        keep = conf >= self.oc["conf"]
        keep_ids = self.oc.get("keep_class_ids")
        if keep_ids is not None:
            keep &= np.isin(cls, keep_ids)
        boxes, conf = boxes[keep], conf[keep]
        if not len(boxes):
            return []
        xyxy = np.stack([boxes[:, 0] - boxes[:, 2] / 2, boxes[:, 1] - boxes[:, 3] / 2,
                         boxes[:, 0] + boxes[:, 2] / 2, boxes[:, 1] + boxes[:, 3] / 2], 1)
        xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - px) / r
        xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - py) / r
        xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, shape[1])
        xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, shape[0])
        idx = nms(xyxy, conf, self.oc["nms_iou"])
        return [([float(xyxy[i, 0]), float(xyxy[i, 1]), float(xyxy[i, 2] - xyxy[i, 0]),
                  float(xyxy[i, 3] - xyxy[i, 1])], float(conf[i])) for i in idx]

    def detect(self, frame, t):
        blob, r, px, py = self.preprocess(frame)
        out = self.session.run(None, {self.input_name: blob})[0]
        return [Detection(t=t, box=b, score=s, source=self.source)
                for b, s in self.postprocess(out, r, px, py, frame.shape)]


def nms(xyxy, scores, thr):
    """Plain greedy non-maximum suppression. Returns kept indices."""
    order = scores.argsort()[::-1]
    keep = []
    while len(order):
        i = order[0]
        keep.append(int(i))
        if len(order) == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(xyxy[i, 0], xyxy[rest, 0]); yy1 = np.maximum(xyxy[i, 1], xyxy[rest, 1])
        xx2 = np.minimum(xyxy[i, 2], xyxy[rest, 2]); yy2 = np.minimum(xyxy[i, 3], xyxy[rest, 3])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        a_i = (xyxy[i, 2] - xyxy[i, 0]) * (xyxy[i, 3] - xyxy[i, 1])
        a_r = (xyxy[rest, 2] - xyxy[rest, 0]) * (xyxy[rest, 3] - xyxy[rest, 1])
        order = rest[inter / (a_i + a_r - inter + 1e-9) <= thr]
    return keep


@register("detector", "motion_blob")
class MotionBlobDetector(Detector):
    """DEVELOPMENT STAND-IN, NOT A MODEL. Finds moving blobs against a median background.

    It exists so the whole pipeline runs with no weights. It knows nothing about fish:
    leaves, bubbles and divers' fins look the same to it. Every detection has
    source 'motion_blob'. Never report its output as model accuracy.
    """
    model_version = "motion_blob_standin (no model)"

    def __init__(self, cfg):
        self.mc = cfg["detector"]["motion_blob"]
        self.bg = None

    def prepare(self, frames):
        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        if not grays:
            return
        pick = grays[::max(1, len(grays) // 31)]
        k = self.mc["blur_ksize"] | 1
        self.bg = cv2.GaussianBlur(np.median(np.stack(pick), axis=0).astype(np.float32), (k, k), 0)

    def detect(self, frame, t):
        if self.bg is None or self.bg.shape != frame.shape[:2]:
            return []
        k = self.mc["blur_ksize"] | 1
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        g, _ = _align(g, self.bg)
        g = g.astype(np.float32)
        g += float(np.median(self.bg)) - float(np.median(g))
        diff = np.abs(cv2.GaussianBlur(g, (k, k), 0) - self.bg)
        mask = (diff > self.mc["diff_threshold"]).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
        out = []
        for j in range(1, n):
            x, y, w, h, area = (int(v) for v in st[j])
            if area < self.mc["min_area"] or area > self.mc["max_area_frac"] * mask.size:
                continue
            score = min(1.0, float(diff[lab == j].mean()) / 40.0)
            out.append(Detection(t=t, box=[x, y, w, h], score=score, source="motion_blob"))
        return out


def tiled_detect(detector, frame, t, tile_size=640, overlap=0.2, nms_iou=0.5):
    """Run `detector` on overlapping tiles and merge with NMS. Boxes in frame pixels."""
    h, w = frame.shape[:2]
    step = max(1, int(tile_size * (1 - overlap)))
    xs = list(range(0, max(1, w - tile_size) + 1, step)) or [0]
    ys = list(range(0, max(1, h - tile_size) + 1, step)) or [0]
    if xs[-1] + tile_size < w:
        xs.append(w - tile_size)
    if ys[-1] + tile_size < h:
        ys.append(h - tile_size)
    dets = []
    for y in ys:
        for x in xs:
            x0, y0 = max(0, x), max(0, y)
            for d in detector.detect(frame[y0:y0 + tile_size, x0:x0 + tile_size], t):
                d.box = [d.box[0] + x0, d.box[1] + y0, d.box[2], d.box[3]]
                dets.append(d)
    if len(dets) < 2:
        return dets
    xyxy = np.array([[d.box[0], d.box[1], d.box[0] + d.box[2], d.box[1] + d.box[3]] for d in dets])
    keep = nms(xyxy, np.array([d.score for d in dets]), nms_iou)
    return [dets[i] for i in keep]


# --------------------------------------------------------------------- tracker
@register("tracker", "iou")
class IouTracker(Tracker):
    """Simple greedy IoU tracker. ByteTrack (or similar) can replace it: add a Tracker class
    with the same track() method and select it in config."""

    def __init__(self, cfg):
        self.tc = cfg["tracker"]

    def track(self, detections_per_frame):
        active, done, next_id = [], [], 1
        for i, dets in enumerate(detections_per_frame):
            pairs = []
            for ti, tr in enumerate(active):
                if i - tr["last_i"] > self.tc["max_gap_samples"] + 1:
                    continue
                for di, d in enumerate(dets):
                    v = iou(tr["box"], d.box)
                    if v >= self.tc["iou_threshold"]:
                        pairs.append((v, ti, di))
            pairs.sort(reverse=True)
            used_t, used_d = set(), set()
            for v, ti, di in pairs:
                if ti in used_t or di in used_d:
                    continue
                used_t.add(ti); used_d.add(di)
                active[ti]["dets"].append(dets[di]); active[ti]["box"] = dets[di].box; active[ti]["last_i"] = i
            for di, d in enumerate(dets):
                if di not in used_d:
                    active.append({"id": next_id, "box": d.box, "last_i": i, "dets": [d]})
                    next_id += 1
        tracks = []
        for tr in active:
            if len(tr["dets"]) < self.tc["min_points"]:
                continue
            for d in tr["dets"]:
                d.track_id = tr["id"]
            tracks.append(Track(track_id=tr["id"], start_s=tr["dets"][0].t, end_s=tr["dets"][-1].t,
                                n_points=len(tr["dets"])))
        return tracks

@register("tracker", "bytetrack")
class ByteTrackBackend(Tracker):
    """ByteTrack via the `trackers` package (same tracker Ali's V6 wraps).

    Needs: pip install trackers==2.7.0 (and supervision).
    A fresh tracker is created per window, so tracks never leak
    between subsample points or segments.
    """

    def __init__(self, cfg):
        tc = cfg.get("tracker", {})
        self.params = dict(
            frame_rate=tc.get("frame_rate", 5.0),
            track_activation_threshold=tc.get("track_activation_threshold", 0.15),
            high_conf_det_threshold=tc.get("high_conf_det_threshold", 0.10),
            minimum_consecutive_frames=tc.get("minimum_consecutive_frames", 2),
            minimum_iou_threshold=tc.get("minimum_iou_threshold", 0.10),
            lost_track_buffer=tc.get("lost_track_buffer", 10),
        )

    def track(self, detections_per_frame):
        import numpy as np
        import supervision as sv
        from trackers import ByteTrackTracker

        tracker = ByteTrackTracker(**self.params)
        by_id = {}
        for dets in detections_per_frame:
            if dets:
                xyxy = np.array(
                    [[d.box[0], d.box[1], d.box[0] + d.box[2], d.box[1] + d.box[3]] for d in dets],
                    dtype=np.float32,
                )
                conf = np.array([d.score for d in dets], dtype=np.float32)
                sv_dets = sv.Detections(
                    xyxy=xyxy, confidence=conf, class_id=np.zeros(len(dets), dtype=int)
                )
            else:
                sv_dets = sv.Detections.empty()
            tracked = tracker.update(sv_dets)
            for d, tid in zip(dets, tracked.tracker_id):
                if tid is None or int(tid) < 0:
                    continue
                d.track_id = int(tid)
                by_id.setdefault(int(tid), []).append(d)
        return [
            Track(track_id=tid, start_s=ds[0].t, end_s=ds[-1].t, n_points=len(ds))
            for tid, ds in sorted(by_id.items())
        ]

# --------------------------------------------------------------------- classifier
@register("classifier", "placeholder")
class PlaceholderClassifier(Classifier):
    """No species model yet: every crop is 'fish_unknown'. Replace with a real classifier."""

    def __init__(self, cfg):
        pass

    def classify(self, crop):
        return [SpeciesGuess(name="fish_unknown", score=0.0)]


# --------------------------------------------------------------------- counter
@register("counter", "basic")
class BasicCounter(Counter):
    """MaxN (and its time), MeanCount over fixed-interval samples, unique tracks.

    All three are relative indices, not abundance. Only detections that belong to a
    track are counted, so one-frame flickers are ignored.
    """

    def __init__(self, cfg):
        self.interval = cfg["counter"]["mean_count_interval_s"]

    def count(self, tracks, detections, sample_times=None):
        used = [d for d in detections if d.track_id is not None]
        per_t: dict = {}
        for d in used:
            per_t[d.t] = per_t.get(d.t, 0) + 1
        times = sorted(set(sample_times) if sample_times is not None else per_t)
        if not times:
            return Counts(maxn=0, maxn_time_s=None, mean_count=0.0, unique_tracks=len(tracks))
        maxn, maxn_t = 0, None
        for t in times:
            if per_t.get(t, 0) > maxn:
                maxn, maxn_t = per_t[t], t
        # MeanCount: first sample in each interval bin, then average
        bins: dict = {}
        for t in times:
            bins.setdefault(int((t - times[0]) // self.interval), t)
        vals = [per_t.get(t, 0) for t in bins.values()]
        return Counts(maxn=maxn, maxn_time_s=maxn_t, mean_count=sum(vals) / len(vals),
                      unique_tracks=len(tracks))
