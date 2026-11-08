# combine_yolo_track.py -- YOLO (Adrien's ONNX, tiled) -> ByteTrack (V6's tracker idea)
# Run from C:\Users\Dunks\Desktop\clipsift2 with the clipsift2 venv active.
#   .venv\Scripts\Activate.ps1
#   py combine_yolo_track.py "C:\Users\Dunks\Desktop\clipsift\T1-STAT2 411.MP4" --start 60 --seconds 10
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import supervision as sv
from trackers import ByteTrackTracker



# Your YOLO inference code (tiled) lives in the clipsift repo -- reuse it.
sys.path.insert(0, r"C:\Users\Dunks\Desktop\clipsift\inference")
import run as yolo_run

MODEL = r"C:\Users\Dunks\Desktop\clipsift\weights\clipsift-yolov8n.onnx"
CONF = 0.25
TRACK_FPS = 5  # V6's tracker runs at 5 fps


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--start", type=float, default=60.0, help="clip start, seconds")
    p.add_argument("--seconds", type=float, default=10.0, help="clip length, seconds")
    p.add_argument("--conf", type=float, default=CONF)
    args = p.parse_args()

    session = ort.InferenceSession(args.model, providers=["CPUExecutionProvider"])
    inp = session.get_inputs()[0]
    input_name, input_shape = inp.name, list(inp.shape)

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / TRACK_FPS)))  # every 6th frame at 30 fps
    start_frame = int(args.start * fps)
    n_frames = int(args.seconds * TRACK_FPS)

    tracker = tracker = ByteTrackTracker(
        frame_rate=TRACK_FPS,
        track_activation_threshold=0.15,
        high_conf_det_threshold=0.10,
        minimum_consecutive_frames=2,
        minimum_iou_threshold=0.10,
        lost_track_buffer=10,
    )

    all_tracks, total_dets = set(), 0

    for i in range(n_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame + i * step)
        ok, frame = cap.read()
        if not ok or frame is None:
            print(f"frame {i}: could not read -- skipping")
            continue
        dets = yolo_run.run_onnx_on_frame(session, input_name, input_shape,
                                          frame, args.conf, 640, 0.2)
        fish = [d for d in dets if d["class"] == "fish"]
        total_dets += len(fish)
        if fish:
            xyxy = np.array([[d["x_min"], d["y_min"], d["x_max"], d["y_max"]]
                             for d in fish], dtype=np.float32)
            conf = np.array([d["confidence"] for d in fish], dtype=np.float32)
            sv_dets = sv.Detections(xyxy=xyxy, confidence=conf,
                                    class_id=np.zeros(len(fish), dtype=int))
        else:
            sv_dets = sv.Detections.empty()
        tracked = tracker.update(sv_dets)
        ids = [int(t) for t in tracked.tracker_id if t is not None and int(t) >= 0]
        all_tracks.update(ids)
        print(f"frame {i} (t={args.start + i / TRACK_FPS:.1f}s): "
              f"{len(fish)} detections, tracks present: {sorted(set(ids))}")
    cap.release()

    print(f"\nDone: {total_dets} raw detections across {n_frames} frames, "
          f"{len(all_tracks)} unique tracks: {sorted(all_tracks)}")
    print("Unique tracks = the tracked-fish count for this clip. "
          "Compare it with the raw detection total -- the gap is the duplicates tracking removes.")


if __name__ == "__main__":
    main()
