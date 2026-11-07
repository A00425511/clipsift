# ClipSift — teammate handoff and release checklist

## Confirmed local workflow

1. **Videos**: Select a local video path and sampling timestamp, then invoke the local Python pipeline. This is not general browser upload.
2. **Subsamples**: Inspect source video name, timestamp, center frame, 10-second context, central 1-second counting interval, and candidate evidence gallery.
3. **Human Review**: Inspect image and surrounding video evidence. Record FISH, EQUIPMENT, BACKGROUND, INVERTEBRATE, or UNCERTAIN decisions; unresolved duplicates are not independent fish.
4. **Results**: Inspect review progress, provisional candidate stats, and exports. Final abundance remains pending duplicate reconciliation.
5. **Help**: User-facing glossary and instructions are in the local UI.

## AI architecture

Source video → timestamp protocol and frame extraction → RF-DETR Small fish proposals → NMS → ByteTrack association → candidate prioritization, overlap checks → evidence crops → human review → export. Strong evidence (track max confidence ≥ 0.30) is a queue ordering aid, **not** confirmation. The 1-second count window is provisional and should not be presented as a validated ecological protocol.

## Validation snapshot (small development samples only)

- First 10 annotated frames: TP=30, FP=80, FN=6; precision=27.3%, recall=83.3% at 0.5 IoU.
- Next 10 annotated frames: TP=17, FP=50, FN=1; precision=25.4%, recall=94.4% at 0.5 IoU.
- These are **frame-level box matching**, not unique-fish abundance, species-level accuracy, or independent-video validation. Annotations and evaluator should be peer-reviewed before publicly presenting numeric claims.

## Group integration rules

- Keep the current local working directory independent from the group's Git checkout.
- Once invited, clone the group repository into a **different folder**; inspect its frameworks, frontend, workflows and licensing before any file copying.
- Implement integration on a dedicated branch. Submit a PR; require team review before merge.
- Do not publish original videos, checkpoints, trained weights, personal file paths, `.venv`, `outputs`, review data or credentials without explicit permission.
- GitHub Pages is static and cannot run local FastAPI or access a judge's `localhost`; select local-demo, hosted-API, or clearly labelled precomputed-demo mode.
- Provide offline setup documentation: Python version, requirements, how to provide weights under license, commands to run server, and expected outputs.

## Demonstration story (team-facing)

"ClipSift helps reviewers examine underwater survey recordings. It samples short video windows at user-specified timestamps and uses a detector and tracker to propose possible fish observations. A central-frame dashboard anchors every result to the original video. Reviewers can see the evidence, reject false positives such as equipment, and export decisions. We intentionally separate proposed candidates from verified fish counts: duplicate identities and uncertain observations are routed for review. Our early frame-level tests reveal both useful sensitivity and false positives, motivating human-in-the-loop review."

## Still needed

- Confirm all pages and navigation on a clean machine.
- Full automatic generation of candidate crops for every new run, including error handling.
- Track-level duplicate reconciliation and validated abundance rules.
- Independent-data benchmark and evaluator validation.
- Team repository access and deployment decision.
