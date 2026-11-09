# ClipSift Results Dashboard — team guide

## Purpose
Summarize existing V6 runs and human-review progress without equating track IDs to fish abundance.

## Workflow
1. In **Videos**, select a local video and sampling timestamp; run AI. This is not a cloud upload.
2. In **Subsamples**, inspect the original center frame, context and provisional count windows, and candidate evidence gallery.
3. In **Human Review**, label observations and save decisions. A saved FISH label is a reviewed *track*, not proof of an independent fish.
4. In **Results**, select the run; review completion metrics, decisions, and per-subsample statistics, then export candidate CSV or structured JSON.

## Definitions
- **Candidate track:** sequence of linked detections across sampled frames; may be fish, equipment, background or duplicate.
- **Strong evidence:** maximum confidence of the track >= 0.30; this is a UI priority and is not a fish classification.
- **Count window:** provisional central one-second counting window.
- **Peak HIGH:** maximum concurrent high-priority candidates within the count window. Do not sum peaks across time.
- **Reviewed:** candidate with a nonempty saved reviewer decision; UNCERTAIN still means reviewed, not confirmed.
- **Confirmed abundance:** *not calculated* until track duplication is resolved and the counting protocol validated.
- **Validation:** precision/recall need independently labelled frames. They are not calculated from confidence scores.

## Data and endpoints
`GET /results?run=<run>`; `GET /api/runs/<run>/results`; `GET /api/runs/<run>/results.csv`; `GET /api/runs/<run>/results.json`.

Reads `outputs/<run>/subsamples_v6.json` and, if present, `outputs/<run>/review_v2/review_decisions.json`. The review queue CSV is optional for summary, but is necessary to show images and save reviews in the existing interface.

If an independently generated validation report is placed at `outputs/<run>/validation/metrics.json` with `precision`, `recall`, `sample_size`, and optional `note`, it can appear on Results. No validation data is invented by the dashboard.

**Security:** These are local-only endpoints. Do not deploy the current API as a public server without authentication, path controls, and deployment hardening. Keep `.venv`, original videos, model weights, full outputs, and personal machine paths out of Git.
