# Architecture and pipeline

The local FastAPI server in `app/local_api.py` hosts four pages and launches `scripts/analyze_full_video.py` for user-selected local files. Each timestamp yields a 10-second analysis context (±5 s) with a provisional 1-second central count window. The RF-DETR Small checkpoint produces candidate bounding boxes (confidence threshold 0.03, NMS 0.50). ByteTrack links detections. V5 counting heuristics group reviewable candidate tracks and suppress some same-frame duplicate events. A generated JSON contains per-sample observations and candidate metadata; `build_review_queue_v2.py` creates crops for reviewers. Human decisions persist in `outputs/<run>/review_v2/review_decisions.json`. The Results page reports review completion, not validated fish abundance.

The Strong/Additional grouping uses *maximum track confidence* at 0.30 and is a user-interface prioritization aid, not an automatic fish classification. Static equipment may score highly and overlapping real fish may be distinct. The review queue is mandatory before drawing conclusions.

This architecture is a **prototype**: jobs are held in memory, no authentication or external deployment is implemented, and the app is intended to listen on localhost only.
