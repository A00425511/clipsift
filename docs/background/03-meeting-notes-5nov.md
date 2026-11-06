# Team check-in notes, Thu 5 Nov 2026 (evening)

From the meeting transcript and app feedback. Attendance in the transcript: Jacob, Ali, Adrien and Dieu Anh Tran. The transcript doesn't show Wang. Feedback signed "gina" appears to be Dieu Anh, to confirm.

## Direction
- Move from Layer 0 to a basic Layer 1 and as strong a Layer 2 as possible.
- Use a pretrained model and refine it. Training from scratch on a few frames gave poor results (Ali).
- Labelling is the shared job this weekend. Two people label the same images so agreement can be measured. Keep all frames and counts labelled so far (Ali).
- Even if counts are imperfect, pointing staff to the moments worth reviewing is already useful.
- Team meets again Fri afternoon. Fri 2:00pm mentors are RBC staff, so expect presentation, format and business advice, not fish.

## Who said they'd do what
| Person | Task |
|---|---|
| Ali | Test team frames on the Community Fish Detector; continue model work; share step list in WhatsApp |
| Adrien | Model tinkering on GitHub; repository support |
| Dieu Anh | Find more fish videos, low and high quality |
| Jacob | Labelling app idea; ask Matt about hand counts; consider emailing the river clip's owner for permission |
| Wang | Not assigned in the transcript |

Open: Ali asked for clear roles. Priorities are still to be agreed.

## Community Fish Detector (Ali's lead)
https://github.com/filippovarini/community-fish-detector
- Single class "fish". Trained on the Community Fish Detection Dataset: over 1.9 million images, over 935,000 boxes, 17 open datasets.
- Current models use RF-DETR, inference code under Apache. This avoids the AGPL question. The YOLOv12x version is deprecated and AGPL.
- Models: Nano 640 (AP .596), Small 1024 (.606), Medium 1024 (.609). The authors say AP values are only for comparing these models, so don't quote them as accuracy.
- Includes video batch inference and a sampling option.
- The training data is a mix of licences, and some have non-commercial terms. The repo shows no licence for the weights themselves. Check before shipping.
- The dataset page lists Brackish as CC BY-SA 4.0, which settles that open item.
- Fish only, so crabs and other invertebrates still need another route.
- Input size matters: 4K frames scaled to 1024 shrink a 120 px fish to about 32 px, and to about 20 px at 640. Tiling may matter more than choosing Small or Medium. To test.
- Our labels are points. Fine-tuning a box detector needs boxes made from them.
- Suggested fit: Small, or Nano if speed demands it, for Layer 1. Medium with tiling, plus heavier tools, for Layer 2a. All to be tested.

## Corrections before these reach the presentation
1. **"50 to 70% accuracy is normal, even for human reviewers" isn't supported.** The research has no such figure. The nearest numbers are correlations of 0.72 to 0.9 between a model and manual counts in a snapper study, which measure something else. Coastal's own draft QC asks for 95% agreement and under 6% difference. Don't use this line. Measure human agreement ourselves.
2. **"All the photos are from this video" doesn't match the filenames.** Only 4 of 28 are T1 STAT 2. The rest are other transects and stations from Sept 9 and 10, so they'd need their own videos.
3. **Models don't improve just by being used.** Corrections build a dataset, and a retraining step has to be run and tested. Batches are the plan, with a retrain only if the new model beats the old one on held-out video.
4. **Accuracy at 720p doesn't guarantee better results at 4K.** Test the resolution actually used.
5. **The app's count second isn't chosen from movement.** Points are at fixed intervals, per their protocol: 60 s in the protocol, 15 s in the demo.

## App backlog from the meeting and feedback
Bugs
- Contrast Reset doesn't work for Ali or Dieu Anh. To reproduce.

Requested
- Clear all marks button (Dieu Anh, in feedback too).
- Edit or remove one dot, e.g. right-click.
- Summary report of counts, seconds and species, as CSV and PDF (Ali, Dieu Anh).
- Save and reopen a full analysis (Ali).
- Windows package that needs no setup, for handoff (Ali).
- A simple label-only mode: show image, mark fish, next image, with blind double counting.
- Sharpen control and clearer image enhancement.

Confusing
- Difference image reads as a scary black and white picture. Needs a plainer label and explanation.
- Counting in the clip and again on the still feels like double work. The app should say that the still is the count and the clip is context.
- Schools: dotting 100 fish on a still works, but the flow of fish through 10 seconds raises questions.

## Questions for Coastal Action (not RBC mentors)
- How do you treat a school moving through the frame?
- Do dots or flashes count, given the two-of-four rule?
- Hand-count sheets and clean originals for the marked frames.

## Useful leads
- Adrien knows someone with a master's in marine biology who applied to Coastal Action. Possible help with species ID, unconfirmed.
- Both GitHub repos were to be made private. Check that `clipsift` was done.

## Adrien's clipsift repo, reviewed 6 Nov
Starter code, no trained model or weights yet. Nothing from Ali yet. Not uploaded: Ali's work.
Worth reusing: `training/split_by_video.py`, `training/calibrate_threshold.py` (picks a threshold for a target precision, and says so if none qualifies, which suits the undercount rule), `evaluation/evaluate.py` (count bias, MAE, bootstrap intervals, visibility and abundance groups, human vs model beside human vs human), and the ONNX CPU approach in `inference/`.
Overlaps with clipsift2: a second Flask review app.
Needs changing: training targets YOLOv8n (AGPL) and six Brackish classes, while the tested detector is RF-DETR and one fish class. Its evaluator takes CSVs in its own format, so label exports need mapping.
