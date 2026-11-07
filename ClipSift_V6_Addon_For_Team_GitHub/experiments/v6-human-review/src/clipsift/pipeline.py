"""ClipSift V6: seek only to protocol windows and run V5 per window.

HIGH/REVIEW are candidate priorities, never confirmed fish. Count-window
numbers are unvalidated simultaneous candidate estimates for human review.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2

from .counting import CandidateCollector
from .protocol import SubsampleWindow, VideoMetadata


TARGET_FPS = 5.0


def analyze_window(
    metadata: VideoMetadata,
    window: SubsampleWindow,
    detector,
    tracker_factory,
    target_fps: float = TARGET_FPS,
    output_video: str | Path | None = None,
) -> dict:
    """Read just the window's frames, track them and count only in count interval.

    A fresh tracker and collector are used for every independent subsample.
    Sample indices are based on source FPS, not CPU processing time.
    """
    if not math.isfinite(target_fps) or target_fps <= 0:
        raise ValueError("target_fps must be positive")

    source_fps = metadata.fps
    stride = max(1, round(source_fps / target_fps))
    actual_fps = source_fps / stride
    start_frame = max(0, int(math.ceil(window.context_start_seconds * source_fps - 1e-7)))
    end_frame = min(metadata.frame_count, int(math.ceil(window.context_end_seconds * source_fps - 1e-7)))
    if start_frame >= end_frame:
        raise ValueError("No source frames in context window")

    cap = cv2.VideoCapture(metadata.path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {metadata.path}")
    tracker = tracker_factory(fps=actual_fps)
    collector = CandidateCollector()
    writer = None
    output_path = str(output_video) if output_video is not None else None
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            output_path, cv2.VideoWriter_fourcc(*"mp4v"), actual_fps,
            (metadata.width, metadata.height),
        )
        if not writer.isOpened():
            cap.release()
            raise RuntimeError(f"Could not create annotated video: {output_path}")

    sampled_frame_indices = []
    sampled_frames = 0
    detection_events = 0
    unassigned_events = 0
    try:
        if not cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame):
            raise RuntimeError("Video seek failed")
        # Some codecs seek to a nearby keyframe. Use the actual decoded index.
        next_frame = start_frame
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_idx = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
            if frame_idx < start_frame:
                continue
            if frame_idx >= end_frame:
                break
            if frame_idx < next_frame:
                continue
            next_frame = frame_idx + stride
            timestamp = frame_idx / source_fps
            detections = detector.detect(frame)
            tracked = tracker.update(detections)
            collector.update(tracked, timestamp=timestamp, frame_index=frame_idx)
            sampled_frames += 1
            sampled_frame_indices.append(frame_idx)
            detection_events += len(detections)
            ids = getattr(tracked, "tracker_id", None)
            if ids is not None:
                unassigned_events += sum(int(track_id) < 0 for track_id in ids)
            if writer is not None:
                # Draw candidate ID boxes only; these are NOT confirmed fish.
                for i, box in enumerate(tracked.xyxy):
                    track_id = int(ids[i]) if ids is not None else -1
                    if track_id < 0:
                        continue
                    x1, y1, x2, y2 = (int(v) for v in box)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.putText(frame, f"Candidate #{track_id}",
                                (x1, max(15, y1-8)), cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 255, 255), 1)
                writer.write(frame)
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    full_context = collector.finalize(metadata.width, metadata.height)
    count_frames = {
        frame_idx: info for frame_idx, info in full_context["frame_count_results"].items()
        if window.counts_at(info["timestamp"])
    }
    if not count_frames:
        raise RuntimeError("No frames were sampled inside count window")

    def peak(key: str) -> tuple[int, float | None]:
        best = max(count_frames.values(), key=lambda r: r[key])
        return int(best[key]), float(best["timestamp"])

    # Retain observations and mark exact count-window presence per track.
    # Track-span overlap alone is not evidence of presence in the window.
    frame_to_clip_index = {source_idx: i for i, source_idx in enumerate(sampled_frame_indices)}
    candidate_tracks = []
    for track in full_context["tracks"]:
        observations = []
        for obs in track["observations"]:
            observations.append({
                "frame_index": int(obs["frame_index"]),
                "context_frame_index": frame_to_clip_index.get(int(obs["frame_index"])),
                "timestamp": float(obs["timestamp"]),
                "confidence": float(obs["confidence"]),
                "bbox": [int(v) for v in obs["bbox"]],
                "in_count_window": bool(window.counts_at(float(obs["timestamp"]))),
            })
        candidate_tracks.append({
            **{k: v for k, v in track.items() if k != "observations"},
            "observed_in_count_window": any(o["in_count_window"] for o in observations),
            "observations": observations,
        })

    high, high_time = peak("high_after_dedup")
    reviewable, review_time = peak("reviewable_after_dedup")
    return {
        "subsample_timestamp_seconds": window.timestamp_seconds,
        "context_start_seconds": window.context_start_seconds,
        "context_end_seconds": window.context_end_seconds,
        "count_start_seconds": window.count_start_seconds,
        "count_end_seconds": window.count_end_seconds,
        "actual_analysis_fps": round(actual_fps, 4),
        "sampled_context_frames": sampled_frames,
        "sampled_count_frames": len(count_frames),
        "detection_events": detection_events,
        "unassigned_detection_events": unassigned_events,
        "raw_tracks_in_context": full_context["raw_track_count"],
        "reviewable_tracks_in_context": full_context["reviewable_track_count"],
        "merged_trajectories_in_context": full_context["merged_trajectory_count"],
        "max_high_candidates_in_count_window": high,
        "max_high_time_seconds": high_time,
        "max_reviewable_candidates_in_count_window": reviewable,
        "max_reviewable_time_seconds": review_time,
        "duplicate_events_removed_in_context": full_context["same_frame_duplicate_events_removed"],
        "status": "PENDING_HUMAN_REVIEW",
        "confirmed_fish_count": None,
        "count_window_frames": [
            {"frame_index": int(idx), **record}
            for idx, record in sorted(count_frames.items())
        ],
        "candidate_tracks": candidate_tracks,
        "context_video": output_path,
    }
