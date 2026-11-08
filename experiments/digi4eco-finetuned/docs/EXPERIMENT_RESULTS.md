# ClipSift Fine-Tuned RF-DETR — Experimental Results

## Overview

We fine-tuned the pretrained Community Fish Detector
(RF-DETR Small) using DIGI4ECO underwater fish annotations.

This is an experimental fish detector, not a validated
automatic fish-counting solution.

## Training Configuration

- Base model: Community Fish Detector, RF-DETR Small
- Training framework: RF-DETR 1.12.0
- Training GPU: NVIDIA Tesla T4
- Training images: 331 (Ancona and SmartBay2)
- Validation images: 120 (SmartBay1)
- Test images: 50 (OBSEA)
- Training epochs: 5
- Model input resolution: 512
- Fish classes: 1
- Training checkpoint: cfd-small.pth

## OBSEA Test Results

50 images with 460 annotated fish boxes.

| Metric | Original | Fine-Tuned |
|---|---:|---:|
| mAP@50 | 49.82% | 55.87% |
| mAP@50:95 | 18.15% | 27.49% |
| mAP@75 | 4.98% | 24.79% |
| Precision | 66.24% | 73.27% |
| Recall | 45.22% | 48.26% |
| F1 | 53.75% | 58.19% |

Precision, recall and F1 are reported by RF-DETR's
confidence-threshold sweep.

The fine-tuned checkpoint improved performance over
the original checkpoint under identical test settings.

## SmartBay1 Validation Results

| Metric | Original | Fine-Tuned |
|---|---:|---:|
| mAP@50 | 3.12% | 6.69% |
| Precision | 14.21% | 24.29% |
| Recall | 7.64% | 12.12% |
| F1 | 9.94% | 16.17% |

Performance varies considerably between environments.

## Coastal Action Local Test

Test frame: T1-STAT2 at 1320 seconds.

Both models used the same inference settings.

### Whole-frame inference

| Confidence | Original | Fine-Tuned |
|---|---:|---:|
| >= 0.15 | 3 | 6 |
| >= 0.30 | 1 | 2 |

### Tiled inference

1024-pixel tiles, 256-pixel overlap,
512-pixel model resolution, global NMS at 0.50.

| Confidence | Original | Fine-Tuned |
|---|---:|---:|
| >= 0.15 | 11 | 26 |
| >= 0.30 | 1 | 6 |

These are predicted candidate boxes, NOT verified fish counts.

## Experimental Tracking

Five-second Coastal Action crop at approximately 10 FPS:

- Frames processed: 50
- Candidates passed to ByteTrack: 944
- Tracked observations: 299
- Distinct candidate track IDs: 102
- Tracks with at least five observations: 19

Track identities and fish counts have not been
independently validated.

## V6 Application Integration

The fine-tuned checkpoint was successfully loaded
in the existing Windows ClipSift V6 application.

The full Videos -> Subsamples -> Human Review ->
Results workflow was tested.

Local review results:

- Reviewable candidate tracks: 16
- FISH labels: 10
- EQUIPMENT labels: 3
- BACKGROUND labels: 1
- UNCERTAIN labels: 2

These are human-reviewed candidate classifications,
not a confirmed unique-fish abundance estimate.

## Limitations

- Coastal Action precision and recall are not measured.
- The DIGI4ECO sequences may overlap with source data
  used to pretrain the original CFD model.
- Some annotations are interpolated between keyframes.
- Model performance differs significantly by scene.
- Tiling increases detections but may increase false positives.
- ByteTrack can produce fragmented or incorrect track IDs.
- Results cannot be directly compared with Adrien's YOLO
  scores without a common ground-truth benchmark.
- The model checkpoint is intentionally excluded from Git.
- Complete training reproducibility requires the data
  conversion and training scripts and compatible weights.

## Dataset Attribution

DIGI4ECO Underwater Fish Tracking Dataset (2026).

DOI: https://doi.org/10.5281/zenodo.20701225

License: CC BY 4.0

The original dataset and annotations remain the property
of their respective authors.
