"""ClipSift V5 candidate ranking, temporal merging, and duplicate suppression.

Extracted from analyze_video_v5_general.py (uploaded Nov 6, 2026).
All frozen V5 numeric thresholds and the original spatial algorithms are retained.
No video I/O, model weights, or runtime side effects.
Track IDs and HIGH candidate labels are NOT confirmed fish counts.
"""

from collections import defaultdict
from dataclasses import dataclass
import math

HIGH_PRIORITY_MIN_FRAMES = 3
HIGH_PRIORITY_MAX_CONF = 0.30
REVIEW_MIN_CONF = 0.10
MERGE_MAX_GAP_SEC = 1.0
MERGE_MAX_DISTANCE_RATIO = 0.05
MERGE_MIN_AREA_RATIO = 0.45
MERGE_MAX_AREA_RATIO = 2.20
DUPLICATE_IOU_THRESHOLD = 0.35
DUPLICATE_CENTER_RATIO = 0.35
DUPLICATE_MIN_AREA_RATIO = 0.50
DUPLICATE_MAX_AREA_RATIO = 2.00


@dataclass
class TrackSummary:
    track_id: int
    frames_seen: int
    max_confidence: float
    mean_confidence: float


def rank_candidate(track: TrackSummary) -> str:
    if (track.frames_seen >= HIGH_PRIORITY_MIN_FRAMES
            and track.max_confidence >= HIGH_PRIORITY_MAX_CONF):
        return "HIGH"
    if track.max_confidence >= REVIEW_MIN_CONF:
        return "REVIEW"
    return "LOW"


def status_name(priority):
    return {"HIGH": "high_priority_candidate",
            "REVIEW": "review_candidate",
            "LOW": "low_priority_candidate"}[priority]


def bbox_center(box):

    x1, y1, x2, y2 = box

    return (
        (x1 + x2) / 2,
        (y1 + y2) / 2
    )

def bbox_area(box):

    x1, y1, x2, y2 = box

    return max(
        1.0,
        (x2 - x1) * (y2 - y1)
    )

def bbox_diagonal(box):

    x1, y1, x2, y2 = box

    width = max(
        1.0,
        x2 - x1
    )

    height = max(
        1.0,
        y2 - y1
    )

    return math.sqrt(
        width ** 2
        +
        height ** 2
    )

def bbox_iou(box_a, box_b):

    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(
        ax1,
        bx1
    )

    inter_y1 = max(
        ay1,
        by1
    )

    inter_x2 = min(
        ax2,
        bx2
    )

    inter_y2 = min(
        ay2,
        by2
    )

    inter_w = max(
        0,
        inter_x2 - inter_x1
    )

    inter_h = max(
        0,
        inter_y2 - inter_y1
    )

    intersection = (
        inter_w
        *
        inter_h
    )

    area_a = bbox_area(
        box_a
    )

    area_b = bbox_area(
        box_b
    )

    union = (
        area_a
        +
        area_b
        -
        intersection
    )

    if union <= 0:
        return 0.0

    return (
        intersection
        /
        union
    )

def center_distance(
    center_a,
    center_b
):

    dx = (
        center_a[0]
        -
        center_b[0]
    )

    dy = (
        center_a[1]
        -
        center_b[1]
    )

    return math.sqrt(
        dx ** 2
        +
        dy ** 2
    )

def predict_next_center(
    observations,
    target_time
):

    if len(observations) < 2:

        return observations[
            -1
        ][
            "center"
        ]


    a = observations[-2]
    b = observations[-1]


    dt = (
        b["timestamp"]
        -
        a["timestamp"]
    )


    if dt <= 0:

        return b[
            "center"
        ]


    vx = (
        b["center"][0]
        -
        a["center"][0]
    ) / dt


    vy = (
        b["center"][1]
        -
        a["center"][1]
    ) / dt


    future_dt = (
        target_time
        -
        b["timestamp"]
    )


    return (

        b["center"][0]
        +
        vx * future_dt,

        b["center"][1]
        +
        vy * future_dt
    )

def are_same_frame_duplicates(
    det_a,
    det_b
):

    box_a = det_a[
        "bbox"
    ]

    box_b = det_b[
        "bbox"
    ]


    # --------------------------------------------------------
    # 1. OVERLAP
    # --------------------------------------------------------

    iou = bbox_iou(
        box_a,
        box_b
    )


    if iou < DUPLICATE_IOU_THRESHOLD:

        return False


    # --------------------------------------------------------
    # 2. CENTER DISTANCE
    # --------------------------------------------------------

    center_a = bbox_center(
        box_a
    )

    center_b = bbox_center(
        box_b
    )


    distance = center_distance(
        center_a,
        center_b
    )


    diag_a = bbox_diagonal(
        box_a
    )

    diag_b = bbox_diagonal(
        box_b
    )


    average_diag = (
        diag_a
        +
        diag_b
    ) / 2


    center_ratio = (
        distance
        /
        max(
            average_diag,
            1.0
        )
    )


    if (
        center_ratio
        >
        DUPLICATE_CENTER_RATIO
    ):

        return False


    # --------------------------------------------------------
    # 3. SIZE SIMILARITY
    # --------------------------------------------------------

    area_a = bbox_area(
        box_a
    )

    area_b = bbox_area(
        box_b
    )


    area_ratio = (
        area_b
        /
        area_a
    )


    if not (

        DUPLICATE_MIN_AREA_RATIO
        <= area_ratio
        <= DUPLICATE_MAX_AREA_RATIO

    ):

        return False


    return True

def remove_same_frame_duplicates(
    candidates
):

    # Strongest detection first

    sorted_candidates = sorted(

        candidates,

        key=lambda x:
            x["confidence"],

        reverse=True
    )


    kept = []

    removed = []


    for candidate in sorted_candidates:

        duplicate_of = None


        for existing in kept:

            if are_same_frame_duplicates(
                candidate,
                existing
            ):

                duplicate_of = existing
                break


        if duplicate_of is None:

            kept.append(
                candidate
            )

        else:

            removed.append({

                "track_id":
                    candidate[
                        "track_id"
                    ],

                "duplicate_of":
                    duplicate_of[
                        "track_id"
                    ],

                "confidence":
                    candidate[
                        "confidence"
                    ]
            })


    return (
        kept,
        removed
    )

class CandidateCollector:
    """Collect observations; then run V5 post-processing after all frames.

    Existing `update(detections)` calls remain compatible. For full V5
    post-processing pass timestamp, frame_index, and frame_shape as well.
    """

    def __init__(self):
        self.observations = defaultdict(list)
        self.track_history = defaultdict(list)
        self.frame_records = {}
        self._next_frame_index = 0

    def update(self, detections, timestamp=None, frame_index=None, frame_shape=None):
        if frame_index is None:
            frame_index = self._next_frame_index
        self._next_frame_index = max(self._next_frame_index, frame_index + 1)
        if timestamp is None:
            timestamp = float(frame_index) / 5.0
        frame_items = []
        ids = getattr(detections, "tracker_id", None)
        confidences = getattr(detections, "confidence", None)
        if ids is not None:
            for i, value in enumerate(ids):
                track_id = int(value)
                if track_id < 0:
                    continue
                confidence = float(confidences[i])
                bbox = [int(v) for v in detections.xyxy[i]]
                observation = {
                    "frame_index": frame_index,
                    "timestamp": float(timestamp),
                    "confidence": confidence,
                    "bbox": bbox,
                    "center": bbox_center(bbox),
                    "area": bbox_area(bbox),
                }
                self.observations[track_id].append(confidence)
                self.track_history[track_id].append(observation)
                frame_items.append({"track_id": track_id,
                                    "confidence": confidence, "bbox": bbox})
        self.frame_records[frame_index] = {"timestamp": float(timestamp),
                                           "detections": frame_items}

    def get_summary(self):
        results = []
        for track_id, confidences in self.observations.items():
            summary = TrackSummary(track_id, len(confidences),
                                   max(confidences),
                                   sum(confidences) / len(confidences))
            results.append({
                "track_id": track_id,
                "frames_seen": summary.frames_seen,
                "max_confidence": round(summary.max_confidence, 3),
                "mean_confidence": round(summary.mean_confidence, 3),
                "priority": rank_candidate(summary),
            })
        return sorted(results, key=lambda x: (
            {"HIGH": 0, "REVIEW": 1, "LOW": 2}[x["priority"]],
            -x["max_confidence"],
        ))

    def finalize(self, width, height):
        """Produce original V5-style track/merge/dedup summaries.

        `width` and `height` are source frame dimensions; merging uses the
        image diagonal, not hard-coded pixel coordinates.
        """
        if width <= 0 or height <= 0:
            raise ValueError("Frame width and height must be positive")
        image_diagonal = math.hypot(width, height)
        tracks = []
        for track_id, observations in sorted(self.track_history.items()):
            confidences = [o["confidence"] for o in observations]
            summary = TrackSummary(track_id, len(observations),
                                   max(confidences),
                                   sum(confidences) / len(confidences))
            tracks.append({
                "track_id": track_id,
                "first_seen_sec": round(observations[0]["timestamp"], 2),
                "last_seen_sec": round(observations[-1]["timestamp"], 2),
                "duration_sec": round(observations[-1]["timestamp"] - observations[0]["timestamp"], 2),
                "frames_seen": len(observations),
                "max_confidence": round(summary.max_confidence, 3),
                "mean_confidence": round(summary.mean_confidence, 3),
                "status": status_name(rank_candidate(summary)),
                "observations": observations,
            })
        status_by_id = {t["track_id"]: t["status"] for t in tracks}
        eligible_tracks = [t for t in tracks if t["status"] != "low_priority_candidate"]
        eligible_tracks.sort(key=lambda t: t["first_seen_sec"])

        # Original V5 single-best-successor greedy track merging.
        merge_parent = {}
        used_as_child = set()
        for track_a in eligible_tracks:
            if track_a["track_id"] in used_as_child:
                continue
            obs_a = track_a["observations"]
            best_candidate = None
            best_distance_ratio = None
            for track_b in eligible_tracks:
                if track_a["track_id"] == track_b["track_id"]:
                    continue
                if track_b["track_id"] in used_as_child:
                    continue
                gap = track_b["first_seen_sec"] - track_a["last_seen_sec"]
                if gap <= 0 or gap > MERGE_MAX_GAP_SEC:
                    continue
                obs_b = track_b["observations"]
                predicted_center = predict_next_center(obs_a, obs_b[0]["timestamp"])
                new_center = obs_b[0]["center"]
                distance_ratio = center_distance(predicted_center, new_center) / image_diagonal
                if distance_ratio > MERGE_MAX_DISTANCE_RATIO:
                    continue
                area_ratio = obs_b[0]["area"] / obs_a[-1]["area"]
                if not (MERGE_MIN_AREA_RATIO <= area_ratio <= MERGE_MAX_AREA_RATIO):
                    continue
                if best_distance_ratio is None or distance_ratio < best_distance_ratio:
                    best_candidate = track_b
                    best_distance_ratio = distance_ratio
            if best_candidate is not None:
                merge_parent[best_candidate["track_id"]] = track_a["track_id"]
                used_as_child.add(best_candidate["track_id"])

        def root_track(track_id):
            seen = set()
            current = track_id
            while current in merge_parent:
                if current in seen:
                    break
                seen.add(current)
                current = merge_parent[current]
            return current

        trajectory_groups = {}
        for track in eligible_tracks:
            root = root_track(track["track_id"])
            trajectory_groups.setdefault(root, []).append(track["track_id"])

        frame_count_results = {}
        max_high_before_dedup = 0
        max_high_after_dedup = 0
        max_reviewable_after_dedup = 0
        max_high_before_time = 0.0
        max_high_after_time = 0.0
        max_reviewable_time = 0.0
        total_same_frame_duplicates_removed = 0
        for frame_idx, info in self.frame_records.items():
            detections_here = info["detections"]
            high_candidates = [d for d in detections_here if status_by_id.get(d["track_id"]) == "high_priority_candidate"]
            high_before = len(high_candidates)
            high_after_candidates, high_removed = remove_same_frame_duplicates(high_candidates)
            high_after = len(high_after_candidates)
            reviewable_candidates = [d for d in detections_here if status_by_id.get(d["track_id"]) in ("high_priority_candidate", "review_candidate")]
            reviewable_after_candidates, reviewable_removed = remove_same_frame_duplicates(reviewable_candidates)
            reviewable_after = len(reviewable_after_candidates)
            total_same_frame_duplicates_removed += len(reviewable_removed)
            frame_count_results[frame_idx] = {
                "timestamp": info["timestamp"],
                "high_before_dedup": high_before,
                "high_after_dedup": high_after,
                "reviewable_after_dedup": reviewable_after,
                "high_duplicates_removed": high_removed,
                "reviewable_duplicates_removed": reviewable_removed,
            }
            if high_before > max_high_before_dedup:
                max_high_before_dedup = high_before
                max_high_before_time = info["timestamp"]
            if high_after > max_high_after_dedup:
                max_high_after_dedup = high_after
                max_high_after_time = info["timestamp"]
            if reviewable_after > max_reviewable_after_dedup:
                max_reviewable_after_dedup = reviewable_after
                max_reviewable_time = info["timestamp"]

        return {
            "raw_track_count": len(tracks),
            "reviewable_track_count": len(eligible_tracks),
            "merged_trajectory_count": len(trajectory_groups),
            "max_high_before_dedup": max_high_before_dedup,
            "max_high_before_dedup_time": round(max_high_before_time, 2),
            "max_high_after_dedup": max_high_after_dedup,
            "max_high_after_dedup_time": round(max_high_after_time, 2),
            "max_reviewable_after_dedup": max_reviewable_after_dedup,
            "max_reviewable_after_dedup_time": round(max_reviewable_time, 2),
            "same_frame_duplicate_events_removed": total_same_frame_duplicates_removed,
            "trajectory_groups": trajectory_groups,
            "tracks": tracks,
            "frame_count_results": frame_count_results,
        }
