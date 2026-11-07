
import os
from pathlib import Path

import cv2
import numpy as np
import supervision as sv
from rfdetr import RFDETRSmall


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = Path(os.environ.get(
    "CLIPSIFT_MODEL_PATH", str(PROJECT_ROOT / "models" / "cfd-small.pth")
)).expanduser()

DETECTION_THRESHOLD = 0.03
NMS_THRESHOLD = 0.50


class FishDetector:
    """Community Fish Detector using RF-DETR Small."""

    def __init__(
        self,
        model_path=DEFAULT_MODEL_PATH,
        confidence=DETECTION_THRESHOLD,
        nms_threshold=NMS_THRESHOLD,
    ):
        self.model_path = Path(model_path)
        self.confidence = confidence
        self.nms_threshold = nms_threshold

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Model not found: {self.model_path}"
            )

        print(f"Loading CFD model: {self.model_path}")

        self.model = RFDETRSmall(
            pretrain_weights=str(self.model_path),
            num_classes=1,
            device="cpu",
        )
        

        print("CFD model loaded successfully.")

    def detect(self, frame_bgr: np.ndarray) -> sv.Detections:
        """Detect fish candidates in an OpenCV BGR frame."""

        if frame_bgr is None or frame_bgr.size == 0:
            raise ValueError("Input frame is empty.")

        frame_rgb = cv2.cvtColor(
            frame_bgr, cv2.COLOR_BGR2RGB
        )

        detections = self.model.predict(
            frame_rgb,
            threshold=self.confidence,
        )

        detections = detections.with_nms(
            threshold=self.nms_threshold,
            class_agnostic=True,
        )

        return detections
