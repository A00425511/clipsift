# ClipSift — Team Walkthrough and Demo Script

## 1. Problem and goal
Manual review of long underwater survey recordings is time-consuming. ClipSift is a **human-in-the-loop candidate discovery and review tool**; it supports inspection and traceability rather than claiming fully autonomous validated abundance.

## 2. Inputs and sampling
A reviewer provides a local video path and protocol timestamps (for example `14:04` = 14 minutes 4 seconds). For each subsample, the prototype analyzes a nominal 10-second context (five seconds before/after) and records a provisional central 1-second count window. The source frame index and center still link results back to the original file. Actual timestamps may be clipped at video boundaries.

## 3. AI components
The RF-DETR Small checkpoint generates fish-like candidate boxes; NMS removes overlapping proposals. ByteTrack links frame-level observations over time. Candidate summaries, same-frame duplicate analysis and simple evidence audit signals help organize review. A track is not necessarily a distinct fish; equipment, backgrounds, stationary animals and overlapping schools complicate interpretation.

## 4. Candidate evidence
`HIGH` and `REVIEW` are internal candidate-priority statuses; `Strong evidence` (maximum track confidence ≥ 0.30) and `Additional evidence` are interface sorting categories. None mean verified fish. The model proposal threshold remains 0.03. In-count-window markers indicate temporal relevance to the provisional count interval.

## 5. Demonstration — practical sequence
1. Start the local API (`python -m uvicorn app.local_api:app --host 127.0.0.1 --port 8765`).
2. Open **Videos** and demonstrate selecting a video already present on the machine and a sample timestamp. CPU analysis may be slow; for timed demos have an approved precomputed run ready.
3. Open **Subsamples** and explain source video name, stable subsample ID, exact center time/frame, center still and analysis/count windows.
4. Open the **candidate evidence gallery**. Point out count-window membership and Strong/Additional filters. Explain confidence versus actual fish identity.
5. Open a candidate in **Human Review**; inspect visual evidence, assign a human class and note, save and refresh to verify persistence.
6. Open **Results** to show counts of candidates, decisions, incomplete reviews and exports. Say **confirmed independent abundance remains pending duplicate reconciliation**.
7. Open **User Guide** to show judges what each metric means and what to examine.

## 6. Team ownership discussion
- Data/protocol: sampling timestamps and interpretation of count window.
- ML: detector and inference consistency.
- Tracking/counting: ByteTrack and duplicate-event logic.
- Backend: API, evidence export and decision persistence.
- Frontend/product: four pages, filters, deep links and help.
- Evaluation: annotation and metrics; claim limitations.

## 7. Evaluation — what can be said
Two selected 10-frame development examples yielded previously reported TP/FP/FN of 30/80/6 and 17/50/1 at IoU ≥ 0.50. This indicates useful retrieval of some fish candidates but many extra boxes. These are not independent test results, nor an estimate of animal abundance. Avoid saying accuracy is 80–100% or claiming automatic fish confirmation.

## 8. Judge-friendly 75-second script
“ClipSift helps reviewers find and assess possible fish observations in underwater videos. We choose a video and protocol time, then the AI samples a short context and proposes candidate detections. The Subsamples page shows the exact time and source frame, so every suggestion can be traced to the recording. We prioritize stronger visual evidence without deleting weaker candidates. A reviewer examines crops and nearby frames, labels fish or non-fish, and saves that decision. The Results page separates machine proposals from reviewed evidence; we do not present track IDs as verified fish counts. Our next step is to validate on independent footage and reconcile duplicate fish tracks.”

## 9. Open issues
True browser upload, clean-install packaging, API hosting outside localhost, duplicate-aware independent count, formal protocol validation, independent-video evaluation, footage/checkpoint licensing, and final integration into the team's GitHub codebase.
