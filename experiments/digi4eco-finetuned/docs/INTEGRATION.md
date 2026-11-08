# Integration options

- **Safest, immediate:** Set `CLIPSIFT_MODEL_PATH` to experimental checkpoint in a fresh shell when launching original V6, as explained in README. V6 `src/clipsift/detector.py` reads it when imported. Do not edit existing files.
- **Standalone:** `scripts/compare_image.py` and `src/clipsift_finetuned/detector.py` provide a drop-in `FishDetector.detect(frame_bgr)` adapter with optional tiling. They return `supervision.Detections`.
- **Team integration:** Team's Flask app and V6 FastAPI have distinct data contracts. Integrate via a tested detection adapter / common JSON schema, not by blindly copying files.
- **Known limitation:** Global NMS at IoU 0.50 may leave near-duplicate tile boxes; tracking is not automatic verification.
- **No trained checkpoint in git:** point teammates to an approved internal weight download location and document SHA256 for reproducibility.
