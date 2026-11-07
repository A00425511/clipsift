# ClipSift — Final Source Review and Handoff

**Scope:** User-supplied `ClipSift_Final_Source.zip` received 2026-11-06. This report documents a static audit of the supplied code; it is not a fresh live run of the model or web application.

## Confirmed in this audit

- 35 archive members were extracted; 20 Python files parse successfully with `ast.parse`.
- Embedded JavaScript in all four HTML pages passes Node.js syntax checking.
- Four routes/pages exist: Videos, Subsamples, Human Review, Results, plus local API and help assets.
- `src/clipsift/detector.py` uses `CLIPSIFT_MODEL_PATH`, defaulting to `models/cfd-small.pth` relative to the project; RF-DETR Small, CPU, threshold 0.03, NMS 0.50 unchanged.
- `scripts/build_review_queue_v2.py` creates evidence from original source frames, not previously annotated context clips; stores clean crop and single-box full-frame images.
- API review decisions are kept in `outputs/<run>/review_v2/review_decisions.json`, distinct from generated review CSV; saving a decision is not fish count confirmation.
- No model weight or video data files included in the submitted archive; `.gitignore` excludes typical model/video/output extensions.
- No obvious embedded API-key/password assignments were identified by a simple textual scan. This is not a formal security audit.

## Documentation issues corrected in this reviewed package

- Replaced outdated root `README.md` that described only the clean-evidence patch and contained developer-specific Windows paths.
- Documented full end-to-end workflow, local-only constraints, reproducible execution commands with placeholders, and outstanding review limitations.

## Still outstanding before group merge / public release

1. **Access and comparison:** Group repository not yet accessible to the developer; do not overwrite other teammates' work. Inspect branches and existing files first.
2. **Dependency reproducibility:** `requirements.txt` is a pinned snapshot from one environment and includes platform-sensitive Torch dependencies. Verify installation in a clean environment before declaring plug-and-play support.
3. **Security:** FastAPI analysis endpoint accepts arbitrary existing local video paths and launches resource-intensive processing. It is **localhost-only**; do not publicly host it without authentication, path restrictions, quotas and security review.
4. **Licensing/privacy:** Confirm permission to distribute model checkpoint and survey videos, and whether derived evidence imagery/reviewer data may be shared. Do not ship actual footage or model weights by default.
5. **Metrics:** Candidate peaks, track counts, FISH review labels, and reviewed candidate totals are not validated independent fish abundance. Compare with fully annotated footage before reporting biological counts.
6. **Reproducibility:** The 4-page flow, model inference and review saving were tested on the user's Windows release folder, but **not** reproduced from scratch in this audit runtime.
7. **Run portability:** Analysis JSON references absolute original video paths. Moving run outputs across machines requires relinking those videos; clean evidence generation requires original source frames.
8. **Artifact integrity:** Preserve `review_decisions.json` separately if human decisions need retention; outputs are excluded from Git archives.
9. **Integration:** GitHub Pages alone cannot execute the local FastAPI API. Choose hosted backend or a clearly disclosed offline/precomputed frontend demo.

## Suggested team demo sequence

1. Open Videos; select an existing local source and timestamp.
2. Show Subsamples center image, exact time/source frame, context and count windows.
3. Open candidate gallery and contrast high-priority proposals with confirmed labels.
4. Open Focused Review; inspect clean crop and source-frame single-box image, save human decision.
5. Refresh Results; show persisted review progress, export, and the pending independent abundance state.
6. Show Help and explicitly identify research limitations.

## Test evidence from prior user run (not rerun in this static audit)

- Independent release-folder web UI served all four pages on port 8766.
- RF-DETR Small loaded and analyzed `test diff.avi` at 00:16 with 17 HIGH peak candidates and 20 REVIEWABLE peak candidates, not confirmed fish counts.
- Reviewer decisions persisted after refresh and appeared in Results.
- Clean crops and focused reviewer UI subsequently displayed in the user's browser.
