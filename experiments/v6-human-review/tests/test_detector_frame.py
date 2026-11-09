
import os
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clipsift.detector import FishDetector


VIDEO_PATH = Path(os.environ.get("CLIPSIFT_TEST_VIDEO", str(ROOT / "data" / "sample.avi"))).expanduser()
OUTPUT_PATH = ROOT / "outputs" / "detector_frame_test.jpg"

# Select a frame near the fish school.
FRAME_TIME_SECONDS = 17.0


def main():
    if not VIDEO_PATH.is_file():
        raise FileNotFoundError(VIDEO_PATH)

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError("Could not open video.")

    try:
        cap.set(
            cv2.CAP_PROP_POS_MSEC,
            FRAME_TIME_SECONDS * 1000,
        )
        success, frame = cap.read()
    finally:
        cap.release()

    if not success:
        raise RuntimeError("Could not read selected frame.")

    print("Frame dimensions:", frame.shape)

    detector = FishDetector()
    detections = detector.detect(frame)

    print("Detections after NMS:", len(detections))

    for i, box in enumerate(detections.xyxy):
        confidence = float(detections.confidence[i])
        print(
            f"Candidate {i + 1}: "
            f"confidence={confidence:.3f}, "
            f"box={box.round(1).tolist()}"
        )

        x1, y1, x2, y2 = map(int, box)

        cv2.rectangle(
            frame, (x1, y1), (x2, y2),
            (0, 255, 0), 2
        )
        cv2.putText(
            frame,
            f"{confidence:.2f}",
            (x1, max(y1 - 8, 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )

    if not cv2.imwrite(str(OUTPUT_PATH), frame):
        raise RuntimeError("Could not save annotated frame.")

    print("Saved annotated frame:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
