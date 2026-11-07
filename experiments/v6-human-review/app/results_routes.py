"""Local-only, read-only Results dashboard for ClipSift V6.

Counts review decisions per candidate key. Never converts track IDs or FISH labels
into independent fish abundance. Do not expose the localhost API publicly.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (ROOT / 'outputs').resolve()
RESULTS_PAGE = Path(__file__).with_name('results.html')
RUN_RE = re.compile(r'^[A-Za-z0-9_-]+$')
DECISIONS = ('FISH', 'INVERTEBRATE', 'EQUIPMENT', 'BACKGROUND', 'UNCERTAIN')


def _run(name: str) -> Path:
    if not RUN_RE.fullmatch(name):
        raise HTTPException(400, 'Invalid run name')
    p = (OUTPUTS / name).resolve()
    if not p.is_relative_to(OUTPUTS):
        raise HTTPException(400, 'Invalid run directory')
    return p


def _report(run: str) -> dict:
    folder = _run(run)
    source = folder / 'subsamples_v6.json'
    if not source.is_file():
        raise HTTPException(404, 'Analysis results missing')
    try:
        data = json.loads(source.read_text(encoding='utf-8'))
        subsamples = data['subsamples']
        if not isinstance(subsamples, list):
            raise ValueError('subsamples must be a list')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, 'Analysis JSON invalid') from exc

    review_csv = folder / 'review_v2' / 'candidate_review_queue.csv'
    decisions_file = folder / 'review_v2' / 'review_decisions.json'
    try:
        if decisions_file.is_file():
            decisions = json.loads(decisions_file.read_text(encoding='utf-8'))
            if not isinstance(decisions, dict):
                raise ValueError('Decisions must be an object')
        else:
            decisions = {}
    except (ValueError, OSError) as exc:
        raise HTTPException(422, 'Review decisions file invalid') from exc

    # The V6 candidate_tracks list is the authoritative set of reviewable tracks.
    candidates = []
    for index, sample in enumerate(subsamples, 1):
        for track in sample.get('candidate_tracks', []):
            if track.get('status') not in ('high_priority_candidate', 'review_candidate'):
                continue
            track_id = track.get('track_id')
            key = f'{index}:{track_id}'
            decision_obj = decisions.get(key, {})
            decision = str(decision_obj.get('decision', '')).upper() if isinstance(decision_obj, dict) else ''
            if decision not in DECISIONS:
                decision = ''
            candidates.append({
                'subsample_index': index,
                'track_id': track_id,
                'max_confidence': track.get('max_confidence'),
                'priority': track.get('status'),
                'in_count_window': bool(track.get('observed_in_count_window')),
                'review_decision': decision,
                'review_notes': str(decision_obj.get('notes', '')) if isinstance(decision_obj, dict) else '',
            })

    # Fallback for historical runs whose track JSON lacks candidate records:
    # use CSV, but never double-count the same key.
    if not candidates and review_csv.is_file():
        with review_csv.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                try:
                    index, track_id = int(row['subsample_index']), int(row['track_id'])
                except (KeyError, TypeError, ValueError):
                    continue
                obj = decisions.get(f'{index}:{track_id}', {})
                decision = str(obj.get('decision', '')).upper() if isinstance(obj, dict) else ''
                candidates.append({
                    'subsample_index': index, 'track_id': track_id,
                    'max_confidence': row.get('max_confidence'), 'priority': row.get('priority'),
                    'in_count_window': str(row.get('observed_in_count_window', '')).lower() == 'true',
                    'review_decision': decision if decision in DECISIONS else '',
                    'review_notes': str(obj.get('notes', '')) if isinstance(obj, dict) else '',
                })

    seen = set()
    unique = []
    for candidate in candidates:
        key = (candidate['subsample_index'], str(candidate['track_id']))
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    candidates = unique

    counts = Counter(item['review_decision'] for item in candidates)
    per_sample = []
    for index, sample in enumerate(subsamples, 1):
        subset = [c for c in candidates if c['subsample_index'] == index]
        reviewed = sum(bool(c['review_decision']) for c in subset)
        per_sample.append({
            'index': index,
            'timestamp_seconds': sample.get('subsample_timestamp_seconds'),
            'reviewable_candidates': len(subset),
            'reviewed': reviewed,
            'pending': len(subset) - reviewed,
            'in_count_window': sum(c['in_count_window'] for c in subset),
            'strong': sum(_float(c['max_confidence']) >= .30 for c in subset),
            'peak_high': sample.get('max_high_candidates_in_count_window'),
            'peak_reviewable': sample.get('max_reviewable_candidates_in_count_window'),
            'status': sample.get('status', 'PENDING_HUMAN_REVIEW'),
        })

    total = len(candidates)
    reviewed = sum(counts.get(k, 0) for k in DECISIONS)
    return {
        'run': run,
        'video_filename': Path(data.get('video') or '').name,
        'subsample_count': len(subsamples),
        'sampled_context_frames_total': sum(int(s.get('sampled_context_frames') or 0) for s in subsamples),
        'candidate_count': total,
        'reviewed': reviewed,
        'pending': total-reviewed,
        'review_progress_percent': round(reviewed / total * 100, 1) if total else 0,
        'in_count_window': sum(c['in_count_window'] for c in candidates),
        'strong': sum(_float(c['max_confidence']) >= .30 for c in candidates),
        'additional': sum(_float(c['max_confidence']) < .30 for c in candidates),
        'decisions': {key: counts.get(key, 0) for key in DECISIONS},
        'per_sample': per_sample,
        'candidates': candidates,
        'confirmed_fish_abundance': None,
        'abundance_status': 'PENDING_DUPLICATE_RESOLUTION_AND_PROTOCOL_VALIDATION',
        'review_queue_available': review_csv.is_file(),
        'validation_metrics': _validation_metrics(folder),
        'warnings': [
            'FISH decisions count reviewed candidate tracks, not independent fish.',
            'Confidence and HIGH priority do not confirm species or abundance.',
            'Count-window candidate peaks are provisional and cannot be summed across time.',
        ],
    }


def _float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _validation_metrics(folder: Path):
    # Explicit metrics only; never infer precision/recall from candidate confidence.
    path = folder / 'validation' / 'metrics.json'
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(obj, dict) or not all(k in obj for k in ('precision', 'recall', 'sample_size')):
            return None
        return {k: obj[k] for k in ('precision', 'recall', 'sample_size', 'note') if k in obj}
    except (ValueError, OSError):
        return None


@router.get('/results', include_in_schema=False)
def results_home():
    return FileResponse(RESULTS_PAGE, media_type='text/html')


@router.get('/api/runs/{run}/results')
def results_json(run: str):
    return _report(run)


@router.get('/api/runs/{run}/results.json')
def export_json(run: str):
    result = _report(run)
    return Response(content=json.dumps(result, indent=2, ensure_ascii=False), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="clipsift_{run}_results.json"'})


@router.get('/api/runs/{run}/results.csv')
def export_csv(run: str):
    report = _report(run)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=['subsample_index', 'track_id', 'max_confidence', 'priority',
                                             'in_count_window', 'review_decision', 'review_notes'])
    writer.writeheader()
    writer.writerows(report['candidates'])
    return Response(content='\ufeff' + out.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="clipsift_{run}_results.csv"'})
