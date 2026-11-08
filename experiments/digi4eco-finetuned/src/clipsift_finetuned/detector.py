"""Single-class RF-DETR fish detector, compatible with V6 detector.detect(frame_bgr).

The returned supervision.Detections are *candidates*, not verified fish.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def tile_starts(image_length: int, tile_size: int, overlap: int) -> list[int]:
    """Cover an image axis fully, including the last uneven edge."""
    if image_length <= 0 or tile_size <= 0 or not 0 <= overlap < tile_size:
        raise ValueError("Invalid image length, tile size, or overlap")
    if image_length <= tile_size:
        return [0]
    stride = tile_size - overlap
    last = image_length - tile_size
    starts = list(range(0, last + 1, stride))
    if starts[-1] != last:
        starts.append(last)
    return starts


def tile_origins(width: int, height: int, tile_size: int, overlap: int) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in tile_starts(height, tile_size, overlap)
        for x in tile_starts(width, tile_size, overlap)
    ]


class FishDetector:
    """V6-compatible fish detector with optional full-frame tiling."""

    def __init__(
        self,
        model_path: str | Path,
        confidence: float = 0.03,
        nms_threshold: float = 0.50,
        resolution: int = 512,
        device: str = "cpu",
        tiled: bool = False,
        tile_size: int = 1024,
        overlap: int = 256,
    ) -> None:
        path = Path(model_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {path}")
        if not 0 <= confidence <= 1 or not 0 <= nms_threshold <= 1:
            raise ValueError("Confidence and NMS thresholds must lie in [0,1]")
        if resolution <= 0:
            raise ValueError("Resolution must be positive")
        if tile_size <= 0 or not 0 <= overlap < tile_size:
            raise ValueError("Invalid tile settings")
        from rfdetr import RFDETRSmall

        self.model_path = path
        self.confidence = confidence
        self.nms_threshold = nms_threshold
        self.resolution = resolution
        self.device = device
        self.tiled = tiled
        self.tile_size = tile_size
        self.overlap = overlap
        self.model = RFDETRSmall(
            pretrain_weights=str(path),
            num_classes=1,
            resolution=resolution,
            device=device,
        )

    def detect(self, frame_bgr: np.ndarray) -> sv.Detections:
        import supervision as sv

        if frame_bgr is None or frame_bgr.size == 0 or frame_bgr.ndim != 3:
            raise ValueError("Expected nonempty BGR image")
        if not self.tiled:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            predictions = self.model.predict(rgb, threshold=self.confidence)
            return predictions.with_nms(threshold=self.nms_threshold, class_agnostic=True)

        height, width = frame_bgr.shape[:2]
        candidate_boxes: list[np.ndarray] = []
        confidences: list[float] = []
        for x, y in tile_origins(width, height, self.tile_size, self.overlap):
            crop = frame_bgr[y:y+self.tile_size, x:x+self.tile_size]
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            predictions = self.model.predict(rgb, threshold=self.confidence)
            ch, cw = crop.shape[:2]
            for box, confidence in zip(predictions.xyxy, predictions.confidence):
                global_box = np.asarray(box, dtype=np.float32).copy()
                global_box[0::2] = np.clip(global_box[0::2], 0, cw) + x
                global_box[1::2] = np.clip(global_box[1::2], 0, ch) + y
                if global_box[2] <= global_box[0] or global_box[3] <= global_box[1]:
                    continue
                candidate_boxes.append(global_box)
                confidences.append(float(confidence))

        if not candidate_boxes:
            return sv.Detections.empty()
        combined = sv.Detections(
            xyxy=np.asarray(candidate_boxes, dtype=np.float32),
            confidence=np.asarray(confidences, dtype=np.float32),
            class_id=np.zeros(len(candidate_boxes), dtype=int),
        )
        return combined.with_nms(threshold=self.nms_threshold, class_agnostic=True)
