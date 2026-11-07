"""Local-only evidence gallery status and safe repair for existing V6 runs."""
from __future__ import annotations
import csv
import subprocess
import sys
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (ROOT / 'outputs').resolve()
_jobs = {}
_lock = threading.Lock()


def _run(name: str) -> Path:
    if not name or not all(c.isascii() and (c.isalnum() or c in '-_') for c in name):
        raise HTTPException(400, 'Invalid run name')
    p = (OUTPUTS / name).resolve()
    if not p.is_relative_to(OUTPUTS):
        raise HTTPException(400, 'Invalid run')
    return p


def _csv(run: str) -> Path:
    return _run(run) / 'review_v2' / 'candidate_review_queue.csv'


@router.get('/api/runs/{run}/gallery-status')
def gallery_status(run: str):
    p = _run(run)
    if not (p / 'subsamples_v6.json').is_file():
        raise HTTPException(404, 'Analysis results missing')
    dest = _csv(run)
    with _lock:
        status = dict(_jobs.get(run, {}))
    rows = 0
    images = 0
    if dest.is_file():
        with dest.open(encoding='utf-8-sig', newline='') as f:
            for item in csv.DictReader(f):
                rows += 1
                image = item.get('evidence_image', '')
                if image:
                    path = Path(image)
                    if not path.is_absolute():
                        path = ROOT / path
                    if path.resolve().is_relative_to(p) and path.is_file():
                        images += 1
    return {'run': run, 'ready': dest.is_file(), 'rows': rows, 'images': images,
            'status': status.get('status', 'ready' if dest.is_file() else 'missing'),
            'error': status.get('error', '')}


def _build(run: str, path: Path):
    try:
        builder = ROOT / 'scripts' / 'build_review_queue_v2.py'
        if not builder.is_file():
            raise RuntimeError('Missing scripts/build_review_queue_v2.py')
        result = subprocess.run([sys.executable, str(builder), str(path / 'subsamples_v6.json')],
                                cwd=ROOT, text=True, capture_output=True, timeout=900)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-1800:])
        if not _csv(run).is_file():
            raise RuntimeError('Builder finished without candidate_review_queue.csv')
        with _lock:
            _jobs[run] = {'status': 'completed', 'error': ''}
    except Exception as exc:
        with _lock:
            _jobs[run] = {'status': 'error', 'error': str(exc)[:1800]}


@router.post('/api/runs/{run}/prepare-gallery', status_code=202)
def prepare_gallery(run: str):
    path = _run(run)
    if not (path / 'subsamples_v6.json').is_file():
        raise HTTPException(404, 'Run analysis first')
    with _lock:
        if _jobs.get(run, {}).get('status') == 'running':
            return {'status': 'running', 'run': run}
        _jobs[run] = {'status': 'running', 'error': ''}
    threading.Thread(target=_build, args=(run, path), daemon=True).start()
    return {'status': 'running', 'run': run}
