"""Community Fish Detector (CFD) backend: RF-DETR weights, tiled at full resolution.

Fish only. The weights were not trained on Nova Scotia footage and were tested on one frame, so
treat every box as a suggestion for a person to check. Counts are relative indices.

Why tiling: run on a whole 4K frame, the model finds almost nothing (the frame is shrunk to the
model input and small midwater fish disappear). Cutting the full resolution frame into overlapping
tiles and merging the boxes was the biggest gain in the one-frame test.

rfdetr (and torch) are imported lazily, only when this backend is built with real weights, so the
rest of ClipSift works without them. Install with: pip install -r requirements-model.txt

Weights are never downloaded here. Use tools/fetch_cfd_weights.py.
"""
from __future__ import annotations

import glob
import time
from pathlib import Path

import cv2
import numpy as np

from ..config import resolve_path
from ..schema import Detection
from .base import Detector, register

FETCH_HINT = "Run: python tools/fetch_cfd_weights.py"
INSTALL_HINT = "Install the model extras with: pip install -r requirements-model.txt"


class ModelUnavailable(ImportError):
    """rfdetr (or torch) is not installed, so the CFD backend cannot load a real model."""


# --------------------------------------------------------------------- pure helpers (no torch)
def tile_boxes(width: int, height: int, tile: int, overlap: float) -> list:
    """Overlapping tiles as (x0, y0, x1, y1) in pixels. Last row and column are pushed back
    to the frame edge, so every pixel is covered. Same layout as the one-frame test script."""
    tw, th = min(tile, width), min(tile, height)
    step_x = max(1, int(tw * (1.0 - overlap)))
    step_y = max(1, int(th * (1.0 - overlap)))
    xs = sorted(set(list(range(0, width - tw, step_x)) + [width - tw]))
    ys = sorted(set(list(range(0, height - th, step_y)) + [height - th]))
    return [(x, y, x + tw, y + th) for y in ys for x in xs]


def merge_boxes(xyxy, scores, min_overlap: float = 0.5):
    """Greedy cross-tile NMS using intersection over the SMALLER box.

    A fish cut by a tile edge shows up twice, once whole and once partly. Intersection over union
    keeps both; intersection over the smaller box drops the fragment. Returns kept indices,
    best score first."""
    xyxy = np.asarray(xyxy, dtype=float).reshape(-1, 4)
    scores = np.asarray(scores, dtype=float).reshape(-1)
    order = scores.argsort()[::-1]
    keep = []
    while len(order):
        i = order[0]
        keep.append(int(i))
        r = order[1:]
        if not len(r):
            break
        x1 = np.maximum(xyxy[i, 0], xyxy[r, 0]); y1 = np.maximum(xyxy[i, 1], xyxy[r, 1])
        x2 = np.minimum(xyxy[i, 2], xyxy[r, 2]); y2 = np.minimum(xyxy[i, 3], xyxy[r, 3])
        inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        a_i = (xyxy[i, 2] - xyxy[i, 0]) * (xyxy[i, 3] - xyxy[i, 1])
        a_r = (xyxy[r, 2] - xyxy[r, 0]) * (xyxy[r, 3] - xyxy[r, 1])
        order = r[inter / np.maximum(np.minimum(a_i, a_r), 1e-9) < min_overlap]
    return keep


def enhance(frame_bgr, kind: str | None):
    """Optional contrast enhancement before tiling. 'clahe' = CLAHE on the L channel (LAB)."""
    if not kind or kind == "none":
        return frame_bgr
    if kind == "clahe":
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = cv2.createCLAHE(3.0, (8, 8)).apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    raise ValueError(f"Unknown enhancement '{kind}'. Use 'none' or 'clahe'.")


def resolve_device(requested: str | None) -> str:
    """'auto' picks cuda, then mps, then cpu. Imports torch only when asked for auto."""
    if requested and requested != "auto":
        return requested
    try:
        import torch
    except ImportError as e:
        raise ModelUnavailable(f"torch is not installed. {INSTALL_HINT}") from e
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def find_weights(cc: dict, models_dir) -> Path:
    """Weights path from detector.cfd.weights, or the newest models/cfd-rf-detr-<variant>-*.pth."""
    w = cc.get("weights")
    if w:
        p = resolve_path(w)
        if not Path(p).is_file():
            raise FileNotFoundError(f"CFD weights not found at '{p}'. {FETCH_HINT}")
        return Path(p)
    variant = cc.get("variant", "nano")
    hits = sorted(glob.glob(str(Path(models_dir) / f"cfd-rf-detr-{variant}-*.pth")))
    if not hits:
        raise FileNotFoundError(f"No CFD '{variant}' weights found in '{models_dir}' "
                                f"(looked for cfd-rf-detr-{variant}-*.pth). {FETCH_HINT}")
    return Path(hits[-1])


# --------------------------------------------------------------------- model adapter
class RfdetrModel:
    """Thin wrapper so the detector only needs infer(tiles, threshold). Loads rfdetr lazily."""

    def __init__(self, weights: Path, device: str):
        try:
            from rfdetr import from_checkpoint  # lazy: torch is heavy and optional
        except ImportError as e:
            raise ModelUnavailable(f"The CFD backend needs the 'rfdetr' package (and torch). "
                                   f"{INSTALL_HINT}") from e
        # rfdetr forwards extra keywords to the model config; the weights move to `device` on first use.
        self.model = from_checkpoint(str(weights), device=device)
        self.device = device

    def infer(self, tiles, threshold: float):
        """tiles: list of RGB uint8 arrays. Returns a list of (xyxy Nx4, confidence N) per tile."""
        from PIL import Image
        imgs = [Image.fromarray(t) for t in tiles]
        res = self.model.predict(imgs if len(imgs) > 1 else imgs[0], threshold=threshold)
        res = res if isinstance(res, list) else [res]
        return [(np.asarray(d.xyxy, dtype=float).reshape(-1, 4),
                 np.asarray(d.confidence, dtype=float).reshape(-1)) for d in res]


# --------------------------------------------------------------------- the backend
@register("detector", "cfd")
class CfdDetector(Detector):
    """Tiled Community Fish Detector. Boxes are [x, y, w, h] in the pixels of the frame given,
    so give it the ORIGINAL resolution frame (needs_full_res is True; the pipeline does that).

    cfg["detector"]["cfd"]: weights, variant (nano|small|medium), tile_size, overlap, threshold,
    enhancement (none|clahe), device (auto|cuda|mps|cpu), batch, roi_mask, merge_overlap.
    `model` can be passed in for tests (any object with infer(tiles, threshold))."""

    needs_full_res = True      # pipeline must not shrink frames for this backend
    single_frame = True        # each frame stands alone: no tracking across sparse frames

    def __init__(self, cfg, model=None, weights=None):
        cc = cfg["detector"]["cfd"]
        self.cc = cc
        self.variant = cc.get("variant", "nano")
        self.tile = int(cc.get("tile_size", 512))
        self.overlap = float(cc.get("overlap", 0.25))
        self.threshold = float(cc.get("threshold", 0.05))
        self.enhancement = cc.get("enhancement") or "none"
        enhance(np.zeros((8, 8, 3), np.uint8), self.enhancement)  # fail early on a bad name
        self.batch = max(1, int(cc.get("batch", 1)))
        self.merge_overlap = float(cc.get("merge_overlap", 0.5))
        self.roi = self._load_roi(cc.get("roi_mask"))
        self.source = f"cfd:{self.variant}"
        self.load_s = 0.0
        t0 = time.perf_counter()
        if model is not None:
            self.model = model
            self.weights = Path(weights) if weights else None
            self.device = getattr(model, "device", "fake")
        else:
            models_dir = resolve_path((cfg.get("paths") or {}).get("models_dir", "models"))
            self.weights = find_weights(cc, models_dir)
            self.device = resolve_device(cc.get("device", "auto"))
            self.model = RfdetrModel(self.weights, self.device)
        self.load_s = time.perf_counter() - t0
        self.model_version = self.weights.stem if self.weights else f"cfd-{self.variant}"

    @staticmethod
    def _load_roi(path):
        if not path:
            return None
        p = resolve_path(path)
        m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if m is None:
            raise FileNotFoundError(f"Region of interest mask not found or unreadable: '{p}'. "
                                    "Use a grayscale image: white (non-zero) is analysed, black is ignored.")
        return m > 0

    def _roi_for(self, shape):
        if self.roi is None:
            return None
        h, w = shape[:2]
        if self.roi.shape == (h, w):
            return self.roi
        return cv2.resize(self.roi.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0

    def detect(self, frame, t: float) -> list:
        """frame: BGR uint8 at original resolution. Returns list[Detection] (box = [x, y, w, h])."""
        h, w = frame.shape[:2]
        roi = self._roi_for(frame.shape)
        img = enhance(frame, self.enhancement)
        rgb = np.ascontiguousarray(img[:, :, ::-1])
        crops = tile_boxes(w, h, self.tile, self.overlap)
        if roi is not None:
            crops = [c for c in crops if roi[c[1]:c[3], c[0]:c[2]].any()]
        boxes, scores = [], []
        for i in range(0, len(crops), self.batch):
            group = crops[i:i + self.batch]
            results = self.model.infer([rgb[y0:y1, x0:x1] for x0, y0, x1, y1 in group], self.threshold)
            for (x0, y0, _, _), (xy, cf) in zip(group, results):
                if len(xy):
                    b = np.array(xy, dtype=float)
                    b[:, [0, 2]] += x0
                    b[:, [1, 3]] += y0
                    boxes.append(b)
                    scores.append(np.asarray(cf, dtype=float))
        if not boxes:
            return []
        B, S = np.vstack(boxes), np.hstack(scores)
        m = S >= self.threshold
        B, S = B[m], S[m]
        if roi is not None and len(B):
            cx = np.clip(((B[:, 0] + B[:, 2]) / 2).astype(int), 0, w - 1)
            cy = np.clip(((B[:, 1] + B[:, 3]) / 2).astype(int), 0, h - 1)
            m = roi[cy, cx]
            B, S = B[m], S[m]
        if not len(B):
            return []
        keep = merge_boxes(B, S, self.merge_overlap)
        return [Detection(t=t, box=[float(B[i, 0]), float(B[i, 1]), float(B[i, 2] - B[i, 0]),
                                    float(B[i, 3] - B[i, 1])], score=float(S[i]), source=self.source)
                for i in keep]
