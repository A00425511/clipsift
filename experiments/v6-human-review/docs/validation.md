# Validation: preliminary, not production metrics

Two development-video annotations were collected from five context/count-window frames in each of two scenes (10 frames per evaluation). At IoU≥0.50 and one-to-one box matching:

| Evaluation | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| First sample | 30 | 80 | 6 | 27.3% | 83.3% |
| Second sample | 17 | 50 | 1 | 25.4% | 94.4% |

These figures were reported from hand-annotated frame comparisons in the project's development workflow and have not been independently revalidated in this release audit. They measure frame-level candidate-box overlap, **not** track-unique fish count, species identity, or generalization to unseen surveys. The videos were also used during development, so treat them as illustrative only. Do not advertise these values as accuracy on new video. Using confidence ≥0.30 for review-priority sorting appeared to reduce displayed false positives in those samples, but changing thresholds would require held-out validation.

Future evaluation should use fully independent, permission-cleared survey clips and consistent annotation instructions; separately measure detection AP, precision-recall, reviewer workload, unique-individual counts, and inter-annotator agreement.
