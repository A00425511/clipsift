"""Regenerate clean fish-candidate evidence from the ORIGINAL unannotated video.

Never use the context clip for this: it already contains many yellow boxes.
Existing reviewer decisions stay in the separate review_decisions.json file.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import cv2

FIELDS = [
    'subsample_index', 'track_id', 'priority', 'frames_seen_context',
    'max_confidence', 'mean_confidence', 'observed_in_count_window',
    'evidence_timestamp_seconds', 'evidence_frame_index', 'evidence_bbox_xyxy',
    'evidence_image', 'full_frame_image', 'context_video',
    'reviewer_decision', 'reviewer_notes',
]


def find_evidence(track):
    obs = track.get('observations') or []
    if not obs:
        return None, None
    count_obs = [o for o in obs if o.get('in_count_window')]
    return max(count_obs or obs, key=lambda o: float(o.get('confidence', 0))), bool(count_obs)


def image_for_observation(cap, observation, crop_path, full_path):
    if observation is None or not cap.isOpened():
        return False
    frame_number = observation.get('frame_index')
    bbox = observation.get('bbox')
    if frame_number is None or bbox is None or len(bbox) != 4:
        return False
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
    ok, frame = cap.read()
    if not ok:
        return False
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return False
    pad = max(16, int(0.25 * max(x2 - x1, y2 - y1)))
    left, top = max(0, x1-pad), max(0, y1-pad)
    right, bottom = min(w, x2+pad), min(h, y2+pad)
    clean_crop = frame[top:bottom, left:right]
    marked = frame.copy()
    cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 220, 255), max(2, int(w/800)))
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(crop_path), clean_crop) and cv2.imwrite(str(full_path), marked))


def generate(json_file: Path, output_dir: Path):
    data = json.loads(json_file.read_text(encoding='utf-8'))
    source = Path(data.get('video') or '')
    if not source.is_file():
        raise FileNotFoundError(
            'Original, unannotated source video is required to create clean evidence. '
            f'Cannot find: {source}. Reconnect or restore it before rebuilding.'
        )
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open original source video: {source}')
    rows=[]
    saved=0
    try:
        for sample_index, sample in enumerate(data.get('subsamples', []),1):
            for track in sample.get('candidate_tracks', []):
                if track.get('status') == 'low_priority_candidate':
                    continue
                obs, inside = find_evidence(track)
                tid=int(track['track_id'])
                name=f's{sample_index:03d}_track_{tid:04d}.jpg'
                crop=output_dir/'evidence_crops'/name
                marked=output_dir/'evidence_full_frames'/name
                ok=image_for_observation(cap,obs,crop,marked)
                saved+=int(ok)
                rows.append({
                    'subsample_index': sample_index, 'track_id':tid,
                    'priority': {'high_priority_candidate':'HIGH','review_candidate':'REVIEW'}.get(track.get('status'),'LOW'),
                    'frames_seen_context':track.get('frames_seen',''),
                    'max_confidence':track.get('max_confidence',''),
                    'mean_confidence':track.get('mean_confidence',''),
                    'observed_in_count_window': '' if inside is None else str(inside),
                    'evidence_timestamp_seconds': '' if obs is None else obs.get('timestamp',''),
                    'evidence_frame_index': '' if obs is None else obs.get('frame_index',''),
                    'evidence_bbox_xyxy': '' if obs is None else json.dumps(obs.get('bbox')),
                    'evidence_image': str(crop) if ok else '',
                    'full_frame_image': str(marked) if ok else '',
                    'context_video': sample.get('context_video') or '',
                    'reviewer_decision':'', 'reviewer_notes':'',
                })
    finally:
        cap.release()
    output_dir.mkdir(parents=True,exist_ok=True)
    # Write CSV last, only after source validation and evidence generation.
    target=output_dir/'candidate_review_queue.csv'
    temp=target.with_suffix('.csv.tmp')
    with temp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)
    temp.replace(target)
    return target, len(rows), saved


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('json_file',type=Path)
    p.add_argument('--output-dir',type=Path)
    a=p.parse_args()
    target=a.output_dir or a.json_file.parent/'review_v2'
    csv_path, count, saved=generate(a.json_file,target)
    print(f'Reviewable candidates: {count}')
    print(f'Clean evidence pairs saved: {saved}')
    print(f'Review CSV: {csv_path}')
    print('Existing review_decisions.json was NOT modified.')
    print('Images use ORIGINAL video frames; never an already annotated context clip.')

if __name__=='__main__':main()
