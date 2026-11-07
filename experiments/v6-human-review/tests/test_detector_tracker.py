
import os
import sys
from pathlib import Path

import cv2

# --------------------------------------------------
# Project paths
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clipsift.detector import FishDetector
from src.clipsift.tracker import FishTracker
from src.clipsift.counting import CandidateCollector

VIDEO_PATH = Path(os.environ.get("CLIPSIFT_TEST_VIDEO", str(ROOT / "data" / "sample.avi"))).expanduser()

OUTPUT_PATH = ROOT / "outputs" / "tracker_test.mp4"

# --------------------------------------------------
# Test configuration
# --------------------------------------------------

TARGET_FPS = 5.0
START_TIME_SECONDS = 15.0
END_TIME_SECONDS = 17.8


def main():

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {VIDEO_PATH}")

    source_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if source_fps <= 0:
        cap.release()
        raise RuntimeError("Invalid source FPS")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print("Source FPS:", source_fps)
    print("Total source frames:", frame_count)
    print("Target analysis FPS:", TARGET_FPS)
    print("Test window:", START_TIME_SECONDS, "-", END_TIME_SECONDS)

    # --------------------------------------------------
    # Initialize detector and tracker
    # --------------------------------------------------

    detector = FishDetector()
    tracker = FishTracker(fps=TARGET_FPS)
    collector = CandidateCollector()
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    writer = cv2.VideoWriter(
        str(OUTPUT_PATH),
        cv2.VideoWriter_fourcc(*"mp4v"),
        TARGET_FPS,
        (width, height),
    )

    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Could not initialize video writer")

    # --------------------------------------------------
    # Seek to fish-school segment
    # --------------------------------------------------

    start_frame = int(START_TIME_SECONDS * source_fps)

    cap.set(
        cv2.CAP_PROP_POS_FRAMES,
        start_frame
    )

    next_sample_time = START_TIME_SECONDS

    # --------------------------------------------------
    # Statistics
    # --------------------------------------------------

    unique_ids = set()

    processed_frames = 0
    total_detections = 0
    max_active_tracks = 0
    total_unassigned = 0

    # --------------------------------------------------
    # Process frames
    # --------------------------------------------------

    try:

        while True:

            success, frame = cap.read()

            if not success:
                break

            frame_index = int(
                cap.get(cv2.CAP_PROP_POS_FRAMES)
            ) - 1

            timestamp = frame_index / source_fps

            if timestamp >= END_TIME_SECONDS:
                break

            if timestamp + 1e-9 < next_sample_time:
                continue

            next_sample_time += 1.0 / TARGET_FPS

            # Detection
            detections = detector.detect(frame)

            # Tracking
            tracked = tracker.update(detections)
            collector.update(
                tracked,
                timestamp=timestamp,
                frame_index=frame_index,
            )
            processed_frames += 1
            total_detections += len(detections)

            # ------------------------------------------
            # Valid tracking IDs
            # ------------------------------------------

            all_ids = (
                [int(x) for x in tracked.tracker_id]
                if tracked.tracker_id is not None
                else []
            )

            active_ids = [
                track_id
                for track_id in all_ids
                if track_id >= 0
            ]

            unique_ids.update(active_ids)

            unassigned = len(all_ids) - len(active_ids)
            total_unassigned += unassigned

            active_count = len(set(active_ids))

            max_active_tracks = max(
                max_active_tracks,
                active_count
            )

            # ------------------------------------------
            # Draw only valid tracks
            # ------------------------------------------

            annotated = frame.copy()

            for i, box in enumerate(tracked.xyxy):

                track_id = (
                    all_ids[i]
                    if i < len(all_ids)
                    else -1
                )

                if track_id < 0:
                    continue

                x1, y1, x2, y2 = map(int, box)

                cv2.rectangle(
                    annotated,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    annotated,
                    f"ID {track_id}",
                    (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            writer.write(annotated)

            print(
                f"Time={timestamp:.2f}s | "
                f"Detections={len(detections)} | "
                f"Confirmed tracks={active_count} | "
                f"Unassigned={unassigned}"
            )

    finally:

        cap.release()
        writer.release()

    # --------------------------------------------------
    # Final summary
    # --------------------------------------------------

    print("\n=== INTEGRATION TEST SUMMARY ===")

    print("Test window:", START_TIME_SECONDS, "-", END_TIME_SECONDS)
    print("Processed frames:", processed_frames)
    print("Total detection events:", total_detections)
    print("Unique valid track IDs:", len(unique_ids))
    print("Maximum simultaneous tracked IDs:", max_active_tracks)
    print("Total unassigned detection events:", total_unassigned)
    print("Output:", OUTPUT_PATH)

    print(
        "\nNOTE: Tracking IDs are not confirmed fish counts."
    )


    # V5 Candidate Ranking
    print("\n=== V5 CANDIDATE RANKING ===")

    for candidate in collector.get_summary():
        print(candidate)

    # V5 Counting Summary
    result = collector.finalize(
        width=width,
        height=height,
    )

    print("\n=== V5 COUNTING SUMMARY ===")
    print("Raw tracks:", result["raw_track_count"])
    print("Reviewable tracks:", result["reviewable_track_count"])
    print("Merged trajectories:", result["merged_trajectory_count"])
    print("Max HIGH after dedup:", result["max_high_after_dedup"])
    print(
        "Duplicate events removed:",
        result["same_frame_duplicate_events_removed"],
    )


if __name__ == "__main__":
    main()

