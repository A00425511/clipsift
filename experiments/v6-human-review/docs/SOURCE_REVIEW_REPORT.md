# Source review findings — 2026-11-06

## Scope
Reviewed the user-provided `ClipSift_Source_Review.zip` (37 entries), extracted its Python/HTML/docs/requirements files, and created this separate release-candidate copy. **No changes were made to the user's active Windows project or GitHub repository.**

## Findings in uploaded ZIP

1. `src/clipsift/detector.py` used a hard-coded `F:\SMU` model path despite successful portable tests reported for a more recent local version.
2. Both detector development scripts in `tests/` used a fixed `F:\SMU` test video path.
3. `requirements.txt` was UTF-16 and omitted `fastapi` and `uvicorn`, which the local web server imports.
4. `README.md`, `docs/architecture.md` and `docs/validation.md` were empty.
5. `scripts/build_review_queue.py` was an older unused implementation; the live app references `build_review_queue_v2.py`.
6. The app uses local filesystem paths, an unauthenticated API and in-memory jobs; it is **not** currently appropriate for a public deployment without access controls and file sandboxing.
7. No original videos, model checkpoints, generated outputs or `.venv` were included in the source ZIP (appropriate for a code handoff).

## Changes made to this release candidate

- Added `CLIPSIFT_MODEL_PATH` or default `models/cfd-small.pth` to the detector, preserving its CPU/RF-DETR thresholds and public class API.
- Added `CLIPSIFT_TEST_VIDEO` or default `data/sample.avi` to two development tests.
- Converted requirements to UTF-8 and added pinned `fastapi`/`uvicorn` to reflect actual app imports. Other dependency pins remain inherited from the uploaded development environment and need a fresh-environment install test.
- Wrote a working README and filled two technical documentation placeholders.
- Removed superseded `scripts/build_review_queue.py` from this proposed release copy; retained `build_review_queue_v2.py`.
- Removed personal drive letters from the active Videos placeholder.

## Checks actually performed

- Extracted the source archive and verified file inventory.
- Parsed all 20 Python files with `ast.parse` and found zero syntax errors.
- Inspected API routes, script dependencies, requirements encoding, model paths and docs.

## Not yet verified

- Full dependency installation on an independent computer.
- Runtime API integration and HTML navigation in a browser against this **new candidate ZIP**.
- RF-DETR inference in this sandbox (checkpoint intentionally absent).
- Authorization to publish proprietary footage/model weights.
- Compatibility with the team's private GitHub repository (access not granted).

## Next recommended check

Extract to a *separate* folder on Windows (do not overwrite the working prototype). Set `CLIPSIFT_MODEL_PATH` and `CLIPSIFT_TEST_VIDEO` to authorized existing files, start Uvicorn bound to 127.0.0.1, inspect the pages and run a detector test. Then compare the group's repo and merge with a PR, retaining the group's current code.
