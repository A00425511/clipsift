"""ClipSift V6: protocol timing and video metadata (no AI inference).

The count window is provisional until Coastal Action confirms its sampling convention.
"""
from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2


@dataclass(frozen=True)
class VideoMetadata:
    path: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_seconds: float


@dataclass(frozen=True)
class SubsampleWindow:
    timestamp_seconds: float
    context_start_seconds: float
    context_end_seconds: float
    count_start_seconds: float
    count_end_seconds: float

    def counts_at(self, time_seconds: float) -> bool:
        # Half-open interval avoids double counting at a shared boundary.
        return self.count_start_seconds <= time_seconds < self.count_end_seconds


def parse_timestamp(value: str | int | float) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS (decimals allowed in final part)."""
    if isinstance(value, bool):
        raise ValueError('Timestamp cannot be boolean')
    if isinstance(value, (int, float)):
        seconds = float(value)
    else:
        parts = str(value).strip().split(':')
        if not 1 <= len(parts) <= 3 or not all(p.strip() for p in parts):
            raise ValueError(f'Invalid timestamp: {value!r}')
        try:
            nums = [float(part) for part in parts]
        except ValueError as exc:
            raise ValueError(f'Invalid timestamp: {value!r}') from exc
        if len(nums) > 1 and any(x >= 60 for x in nums[1:]):
            raise ValueError(f'Minutes/seconds must be below 60: {value!r}')
        seconds = sum(num * 60 ** power for power, num in enumerate(reversed(nums)))
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f'Timestamp must be finite and nonnegative: {value!r}')
    return seconds


def read_video_metadata(video_path: str | Path) -> VideoMetadata:
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise RuntimeError(f'Cannot open video: {path}')
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not math.isfinite(fps) or fps <= 0 or frames <= 0 or width <= 0 or height <= 0:
            raise ValueError(f'Invalid video metadata: {path}')
        return VideoMetadata(str(path), fps, frames, width, height, frames / fps)
    finally:
        cap.release()


def build_windows(
    timestamps: Iterable[str | int | float],
    duration_seconds: float,
    context_radius_seconds: float = 5.0,
    count_window_seconds: float = 1.0,
) -> list[SubsampleWindow]:
    """Clip windows at video bounds; keep count window within context window."""
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError('Video duration must be positive and finite')
    if (not math.isfinite(context_radius_seconds) or context_radius_seconds < 0
            or not math.isfinite(count_window_seconds) or count_window_seconds <= 0
            or count_window_seconds > 2 * context_radius_seconds):
        raise ValueError('Invalid context/count window configuration')
    result = []
    for raw in timestamps:
        t = parse_timestamp(raw)
        if t >= duration_seconds:
            raise ValueError(f'Subsample {raw!r} falls outside the video ({duration_seconds:.2f}s)')
        result.append(SubsampleWindow(
            timestamp_seconds=t,
            context_start_seconds=max(0.0, t - context_radius_seconds),
            context_end_seconds=min(duration_seconds, t + context_radius_seconds),
            count_start_seconds=max(0.0, t - count_window_seconds / 2),
            count_end_seconds=min(duration_seconds, t + count_window_seconds / 2),
        ))
    return result


def load_timestamps_csv(csv_path: str | Path) -> list[str]:
    """Read a CSV with column 'timestamp' (e.g. 05:00, 22:00)."""
    with open(csv_path, newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or 'timestamp' not in reader.fieldnames:
            raise ValueError("CSV must include a 'timestamp' header")
        values = [str(row['timestamp']).strip() for row in reader if row.get('timestamp') and str(row['timestamp']).strip()]
    if not values:
        raise ValueError('No timestamps in CSV')
    return values


def windows_as_dicts(windows: Iterable[SubsampleWindow]) -> list[dict]:
    return [asdict(window) for window in windows]
