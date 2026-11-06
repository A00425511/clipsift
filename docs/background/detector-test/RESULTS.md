# Community Fish Detector test, 5 Nov 2026

Out-of-the-box test, no fine-tuning, on one frame: T1-STAT2 411 at 22:00.3, a dense school, with 103 fish dots placed by Coastal Action. Run on Jacob's M4 Pro Mac.

**Read this as a first signal.** It's one frame, thresholds were picked on that same frame, and it says nothing about crabs, other sites, or low-visibility water.

## Results
A match means a dot falls in or near a box. "Chance" is the same number of boxes placed at random in the same area, averaged over 30 tries. Strict matching needs the dot inside the box or within 25 px of its centre.

| Setup | Boxes | Recall | Precision | Strict recall / precision | Chance recall / precision |
|---|---|---|---|---|---|
| Nano, no enhancement, 512 tiles, threshold 0.05 | 73 | 0.45 | 0.63 | 0.41 / 0.58 | 0.20 / 0.28 |
| Nano, no enhancement, 512 tiles, threshold 0.03 | 178 | 0.70 | 0.40 | 0.61 / 0.35 | 0.37 / 0.22 |
| Medium, CLAHE, 512 tiles, threshold 0.05 | 133 | 0.61 | 0.47 | 0.51 / 0.40 | 0.31 / 0.24 |
| Medium, CLAHE, 512 tiles, threshold 0.03 | 328 | 0.82 | 0.26 | 0.65 / 0.20 | 0.61 / 0.19 |
| Medium, no enhancement, 768 tiles, threshold 0.05 | 39 | 0.26 | 0.69 | 0.23 / 0.62 | 0.11 / 0.28 |

The 0.03 Medium row is close to chance, so don't use it.

## What we learned
- Whole-frame use finds almost nothing: recall 0.02 or less at threshold 0.1 for Small and Medium, and 0.01 for Nano.
- Tiling at full resolution is the biggest gain.
- Confidence is very low on this water: few detections above 0.2. On the repo's own sample images it scored about 0.9, so the code works and the gap is the domain.
- Small was not better than Nano or Medium on this frame.
- CLAHE helped Medium, not Nano. Background flattening didn't help.
- Time: about 2 to 7 s per frame on this Mac. Coastal's PC isn't measured.
- Checkpoints were inspected before loading: tensors only, no executable references.

## Correction
The earlier simple background baseline (recall 16% to 44%, precision about 18%) was not compared with chance. Chance precision here is about 19% to 28%, so that method was no better than random placement. It should be described that way.

## Next
Fine-tune on labelled Coastal frames. The low confidence with boxes on real fish suggests fine-tuning has room to help, but that's unproven. Needs more labelled frames, boxes made from dots, and a held-out test from different video.

## Tougher controls, 6 Nov
Prompted by a human review of the demo showing many boxes on seafloor and the PVC pipe. Nano, 512 tiles, strict matching: dot inside the box or within 25 px of its centre. Dots are from 22:00.303.

| Boxes from | Threshold | Boxes | Hits | Precision |
|---|---|---|---|---|
| The labelled frame | 0.05 | 68 | 35 | 0.51 |
| The labelled frame | 0.1 | 26 | 16 | 0.62 |
| 1 s earlier | 0.05 | 74 | 3 | 0.04 |
| 1 s later | 0.05 | 89 | 8 | 0.09 |
| 2 to 20 s away | 0.05 | 51 to 220 | 6 to 30 | 0.09 to 0.16 |
| Same boxes moved 150 to 400 px | 0.05 | about 66 | about 9, range 1 to 15 | about 0.13 |
| Same boxes moved 150 to 400 px | 0.1 | about 24 | about 3, range 0 to 8 | about 0.14 |

Only counts boxes in the labelled midwater area. Boxes on the seabed were excluded, so this says nothing against the human review finding that the model flags seafloor and the pipe.

Reading: in midwater on this frame the matches are real, not luck, because they vanish when the frame moves by one second. Separately, false boxes on the seabed and pipe are real too. Both are true. Still one frame.
