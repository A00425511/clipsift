
import supervision as sv
from trackers import ByteTrackTracker


class FishTracker:
    """ByteTrack wrapper for ClipSift."""

    def __init__(self, fps=5.0):
        self.fps = fps
        self._create_tracker()

    def _create_tracker(self):
        self.tracker = ByteTrackTracker(
            frame_rate=self.fps,
            track_activation_threshold=0.15,
            high_conf_det_threshold=0.10,
            minimum_consecutive_frames=2,
            minimum_iou_threshold=0.10,
            lost_track_buffer=10,
        )

    def update(self, detections: sv.Detections) -> sv.Detections:
        """Associate detections across sequential video frames."""
        return self.tracker.update(detections)

    def reset(self):
        """Start a new, independent video sequence."""
        self._create_tracker()
