# Model card â€” ClipSift V6 RF-DETR Small DIGI4ECO pilot v1

**Status:** Experimental. NOT validated for Coastal Action fish abundance/counts.

## Lineage
- Base: pretrained Community Fish Detector, RF-DETR Small `cfd-small.pth` (~121.4 MiB), not a from-scratch model.
- Fine-tuned in Google Colab (NVIDIA T4), RF-DETR 1.12.0, five epochs, resolution 512, training batch 2, gradient accumulation 4, learning rate 1e-5.
- DIGI4ECO data, original source: https://doi.org/10.5281/zenodo.20701225 , CC BY 4.0 (credit dataset creators when using); image boxes include interpolated CVAT labels.
- COCO conversion split by **video sequence**, sampled by frame; training Ancona (120) + SmartBay2 (211), validation SmartBay1 (120), test OBSEA (50). Train: 8,229 boxes; valid: 2,121; test: 460.
- Original CFD training-data overlap with DIGI4ECO has not been ruled out. Test results are NOT independent evidence against that possible pretraining overlap.

## OBSEA test (50 sampled frames, 460 labeled boxes; same 512-resolution evaluation)
| Metric | Original CFD | Fine-tuned pilot |
|---|---:|---:|
| mAP@50 | 0.4982 | 0.5587 |
| mAP@50:95 | 0.1815 | 0.2749 |
| mAP@75 | 0.0498 | 0.2479 |
| Precision (F1 sweep) | 0.6624 | 0.7327 |
| Recall (F1 sweep) | 0.4522 | 0.4826 |
| F1 (F1 sweep) | 0.5375 | 0.5819 |

## SmartBay1 validation (120 sampled frames, 2,121 boxes)
| Metric | Original CFD | Fine-tuned pilot |
|---|---:|---:|
| mAP@50 | 0.0312 | 0.0669 |
| mAP@50:95 | 0.0183 | 0.0346 |
| Precision | 0.1421 | 0.2429 |
| Recall | 0.0764 | 0.1212 |
| F1 | 0.0994 | 0.1617 |

## Coastal exploratory inference, NOT labeled evaluation
- T1 frame at 1320s: tiled 1024 pixels, overlap 256, model resolution 512, confidence >=0.15: original 11 candidate boxes, fine-tuned 26. Extra candidate boxes include apparent pole/background false positives.
- Cropped 1100x700 five-second clip: 10FPS, detector + ByteTrack yielded 102 distinct candidate track IDs and 19 tracks with >=5 observations. Neither metric means true fish count; tracking identity not validated.
- CLAHE image enhancement reduced candidate counts, but also removed plausible fish. Not enabled by default.

## Honest use / limitations
- No demonstrated Coastal Action precision, recall, fish abundance, or workload reduction.
- Confidence scores are not necessarily calibrated fish probabilities.
- Inference at 512 may miss small fish in whole-frame 4K; tiling is exploratory, slow on CPU.
- Local CPU checkpoint loading and V6 workflow integration were successfully tested on Windows with RF-DETR 1.11.2. Training used RF-DETR 1.12.0. Production inference speed has not been benchmarked.
- Checkpoint is stored separately; never embed it or local video in GitHub without verifying licensing and team approval.
