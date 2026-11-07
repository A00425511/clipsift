"""Read-only subsample dashboard endpoints. Existing V6 detector and review API are unchanged."""
from __future__ import annotations

import json
import math
import threading
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (ROOT / 'outputs').resolve()
PAGE = Path(__file__).with_name('subsamples.html')
_LOCK = threading.Lock()


def _run(name: str) -> Path:
    if not name or not all(ch.isalnum() or ch in '_-' for ch in name):
        raise HTTPException(400, 'Invalid run name')
    path = (OUTPUTS / name).resolve()
    if not path.is_relative_to(OUTPUTS):
        raise HTTPException(400, 'Invalid run directory')
    return path


def _data(name: str) -> dict:
    path = _run(name) / 'subsamples_v6.json'
    if not path.is_file():
        raise HTTPException(404, 'Analysis JSON is missing')
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise HTTPException(422, f'Invalid analysis JSON: {exc}') from exc
    return obj


def _time(seconds: float) -> str:
    millis = round(float(seconds) * 1000)
    h, remain = divmod(millis, 3_600_000)
    m, remain = divmod(remain, 60_000)
    s, ms = divmod(remain, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def _metadata(video: Path) -> tuple[float, int]:
    if not video.is_file():
        return 0.0, 0
    cap = cv2.VideoCapture(str(video))
    try:
        if not cap.isOpened():
            return 0.0, 0
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0:
            return 0.0, 0
        return fps, frames
    finally:
        cap.release()


@router.get('/subsamples')
def subsample_home():
    return FileResponse(PAGE, media_type='text/html')


@router.get('/api/runs/{run}/subsamples')
def subsamples(run: str):
    data = _data(run)
    video = Path(data.get('video') or '')
    fps, frame_count = _metadata(video)
    filename = video.name
    results = []
    for index, sample in enumerate(data.get('subsamples', []), start=1):
        center = float(sample['subsample_timestamp_seconds'])
        frame_index = min(max(0, round(center * fps)), frame_count - 1) if fps > 0 and frame_count > 0 else None
        tracks = sample.get('candidate_tracks', [])
        reviewable = [t for t in tracks if t.get('status') in ('high_priority_candidate', 'review_candidate')]
        inside = [t for t in reviewable if t.get('observed_in_count_window') is True]
        results.append({
            'index': index,
            'id': f'{video.stem}_S{index:03d}',
            'source_filename': filename,
            'center_seconds': center,
            'center_time': _time(center),
            'source_frame_index_zero_based': frame_index,
            'source_frame_number_one_based': frame_index + 1 if frame_index is not None else None,
            'source_fps': round(fps, 5) if fps else None,
            'center_image_url': f'/api/runs/{run}/subsamples/{index}/center' if fps else None,
            'context_start': _time(sample['context_start_seconds']),
            'context_end': _time(sample['context_end_seconds']),
            'count_start': _time(sample['count_start_seconds']),
            'count_end': _time(sample['count_end_seconds']),
            'sampled_context_frames': sample.get('sampled_context_frames'),
            'sampled_count_frames': sample.get('sampled_count_frames'),
            'peak_high': sample.get('max_high_candidates_in_count_window'),
            'peak_reviewable': sample.get('max_reviewable_candidates_in_count_window'),
            'reviewable_track_count': len(reviewable),
            'reviewable_in_count_window': len(inside),
            'strong_evidence': sum(float(t.get('max_confidence', 0)) >= 0.30 for t in reviewable),
            'additional_evidence': sum(float(t.get('max_confidence', 0)) < 0.30 for t in reviewable),
            'raw_tracks': sample.get('raw_tracks_in_context'),
            'detection_events': sample.get('detection_events'),
            'duplicate_events_removed': sample.get('duplicate_events_removed_in_context'),
            'unassigned_detection_events': sample.get('unassigned_detection_events'),
            'confirmed_fish_count': sample.get('confirmed_fish_count'),
            'status': sample.get('status'),
            'tracks': [{
                'track_id': t.get('track_id'), 'priority': t.get('status'),
                'max_confidence': t.get('max_confidence'),
                'frames_seen': t.get('frames_seen'),
                'observed_in_count_window': t.get('observed_in_count_window'),
            } for t in reviewable],
        })
    return {
        'run': run, 'source_filename': filename, 'video_path': str(video),
        'video_available': bool(fps), 'video_fps': fps or None,
        'protocol_note': data.get('protocol_note'), 'subsamples': results,
        'caveat': 'Peak candidates, detection events and track IDs are not confirmed fish abundance.'
    }


@router.get('/api/runs/{run}/subsamples/{index}/center')
def central_image(run: str, index: int):
    obj = _data(run)
    samples = obj.get('subsamples', [])
    if index < 1 or index > len(samples):
        raise HTTPException(404, 'Subsample not found')
    video = Path(obj.get('video') or '')
    if not video.is_file():
        raise HTTPException(404, 'Original video missing on this computer')
    output = _run(run) / 'center_frames' / f'subsample_{index:03d}.jpg'
    if output.is_file():
        return FileResponse(output, media_type='image/jpeg')
    with _LOCK:
        if not output.exists():
            cap = cv2.VideoCapture(str(video))
            try:
                if not cap.isOpened():
                    raise HTTPException(422, 'Cannot read original video')
                fps = float(cap.get(cv2.CAP_PROP_FPS))
                n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if not math.isfinite(fps) or fps <= 0 or n <= 0:
                    raise HTTPException(422, 'Invalid original video timing')
                target = min(n - 1, max(0, round(float(samples[index - 1]['subsample_timestamp_seconds']) * fps)))
                cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                success, frame = cap.read()
                if not success:
                    raise HTTPException(422, f'Could not decode frame {target}')
                # Keep source frame identity but resize for web delivery.
                h, w = frame.shape[:2]
                if w > 1280:
                    frame = cv2.resize(frame, (1280, round(h * 1280 / w)), interpolation=cv2.INTER_AREA)
                output.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(output), frame, [cv2.IMWRITE_JPEG_QUALITY, 85]):
                    raise HTTPException(500, 'Could not write center image')
            finally:
                cap.release()
    return FileResponse(output, media_type='image/jpeg')
