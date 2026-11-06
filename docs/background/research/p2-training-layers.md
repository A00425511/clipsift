# P2 (Coastal Action): training with few labels, accuracy over time, Layer 2, three-layer architecture

Researched Thu 5 Nov 2026. Tags: [fetched] page opened; [snippet] search result only; [inference] my reasoning. Builds on p2-data-models.md and p2-gopro-motion.md (datasets, MaxN, CLAHE, compute table not repeated). Development use of any tool is allowed per Jacob's 5 Nov update; only the shipped Layer 0/1 must be local.

## 1. Training with few labels

**Evidence on label counts (thin, say so).** I found no source giving a minimum for fish detection. Anchors: Ultralytics recommends at least 1,500 images and 10,000 instances per class for a from-scratch dataset [snippet: [Ultralytics Academy](https://academy.ultralytics.com/courses/dataset-readiness-for-yolo)]. Its annotation guide estimates a 5 to 10x throughput gain from model-proposed labels plus human correction [snippet, same site]. A marine study found YOLO pseudo-labelling then correcting was much faster than labelling ~500 images from scratch [snippet: [arXiv 2003.00836](https://arxiv.org/pdf/2003.00836)]. A vendor doc fine-tuned a COCO-pretrained YOLOv11 on 638 underwater images (anecdotal, 40% to 80% accuracy) [snippet: [anote](https://docs.anote.ai/navalx_matb_defense_tech/evaluate.html)]. A fish classifier hit 85% with 50 images per class on Fish4Knowledge [snippet: [Springer](https://link.springer.com/article/10.1007/s10489-020-02154-9)]. [inference] Practical range: 300 to 1,000 local frames fine-tune a "fish" detector from a pretrained start; species-level needs far more per class, which is why species stays a review-queue job.

**Counts are weak labels.** Four uses, in order of value [inference unless cited]:
1. **Validation (do this first).** Run the pipeline on each counted video; compare MaxN and unique-track count to the sheet. Report signed bias and MAE per clip. Needs zero boxes.
2. **Calibration.** Fit a per-site correction (e.g. detector count x factor) and tune the confidence threshold to minimise count error on counted clips.
3. **Triage for labelling.** Videos with count 0 supply cheap true negatives (algae, kelp, sediment hard negatives). Videos where tool count and sheet disagree most are the highest-value frames to label.
4. **Count-supervised training.** Research exists: LOOC trains localisation from counts only [snippet: [arXiv 2007.01837](https://arxiv.org/abs/2007.01837)]; FishDetector-R1 trains an MLLM plus SAM 2 for fish detect/segment/count from point labels, reporting 30% lower MAE on DeepFish [fetched abstract: [arXiv 2512.05996](https://arxiv.org/abs/2512.05996)]. Both are research code and too risky for 2.5 days. Present as roadmap.

Matching to MaxN: the sheet's count is probably per video or per period, not per frame (ask). A sheet count c only bounds the video's MaxN loosely, so use it as a check, not a frame label [inference].

**Ranking by data situation**

| Rank | (a) Old videos + count sheets | (b) Old videos, no counts | (c) A few manual samples only |
|---|---|---|---|
| 1 | Pretrained generic detector zero-shot; score against sheets (validation + calibration) | Pre-label with generic detector + motion proposals; human corrects 200 to 500 frames | Pre-label the samples with generic detector; correct; ~100 frames |
| 2 | Pre-label and correct frames from the worst-disagreement videos | Active learning order (below) | Fine-tune on Brackish + those frames; measure on a held-out sample |
| 3 | Fine-tune detector on corrected frames; re-check against sheets | Brackish pretrain, then fine-tune on corrected frames | Copy-paste synthetic (below) |
| 4 | Count-supervised training (roadmap only) | Few-shot species via embeddings | Few-shot via embeddings only |

**Other routes**
- **Pre-label then correct:** biggest saver. Sources of proposals: MegaFishDetector or Fishial, Grounding DINO/OWLv2 ("fish"), SAM 3 text prompt (section 3). Filter by confidence; unfiltered pseudo-labels bake in errors [snippet: [theneuralbase](https://theneuralbase.com/yolo/learn/advanced/pseudo-labeling-with-existing-model/)].
- **Active learning, order to label** [inference, standard practice]: (1) frames where detector confidence sits near threshold; (2) frames where two detectors disagree; (3) DINOv2/DINOv3 embedding clusters with no labelled member (diversity); (4) videos where the count disagrees with the sheet; (5) a random 10% for an unbiased holdout. Sample at most 1 frame per second per video and never put neighbouring frames in different splits.
- **Transfer:** start from Brackish (cold, turbid; CC BY 4.0 per Roboflow copy [snippet via p2-data-models]) or MegaFishDetector weights, then fine-tune on local frames. Piccolo et al. (arXiv 2601.13975) say cross-site loss is driven by scene layout more than haze, so expect to need local frames regardless.
- **Few-shot species:** keep a gallery of 5 to 20 reviewed crops per species; classify by nearest neighbour on BioCLIP 2 or DINO embeddings; below a similarity threshold goes to review. No retraining needed, so it improves the minute a reviewer confirms a crop [inference].
- **Synthetic / copy-paste:** cut reviewed fish crops (or SAM masks) and paste on empty-water frames with blur, haze and colour shift. Cheap to try; it helps with rare classes but I found no fish-specific figure. Label as synthetic and never put synthetic frames in the test set [inference].

## 2. Accuracy over time

Simple scheme a small NGO can run [inference throughout]:
- **Review writes labels.** Every accept, reject, box fix, species change is stored (crop, box, species, reviewer, model version, video ID, site, date, water clarity score).
- **Versioned everything.** `model-vN` + `dataset-vN` (a manifest of frame IDs and labels, hash-pinned) + `config`. Never overwrite. Plain folders and a CSV manifest beat MLOps tools for this team; DVC or Git LFS is optional.
- **Frozen holdout.** Hold out whole videos, never frames: one set by unseen site, one by unseen date or season, one hard-turbidity set. About 20 to 30 videos or 300+ labelled frames total, human-counted. Never train on them; add new ones each season to a separate "fresh" set.
- **Metrics tracked each version:** recall at fixed precision, per-clip count bias and MAE, reviewer correction rate (corrections per hour of video, the number that falls if the model improves), and an unknown-species rate.
- **Drift triggers:** correction rate up 25% relative, a new site, a new season, a new camera, turbidity bucket shift, or watch-list species appearing.
- **When retraining pays off** [inference]: after roughly 300 to 500 newly corrected frames or one season, and only if the candidate beats the current model on the frozen holdout and the fresh set. Otherwise keep reviewing; embedding galleries absorb new species without retraining. Always keep rollback.
- **Where retraining happens if the PC is modest:** fine-tuning a small YOLO takes 20 to 60 min on a free T4 for ~2k images (p2-data-models, inference). So train on a rented/borrowed GPU (university lab, Colab for non-sensitive footage, a few hours of cloud GPU), then copy the ONNX weights to the PC; policy may bar cloud training on partner data, so ask. Or overnight on the desktop's GPU if it has 6GB+ VRAM [inference]. Inference-only on the PC is the default.

## 3. Layer 2 options (state as of Nov 2026)

| Option | Adds | Cost / hardware | Licence | Weakness |
|---|---|---|---|---|
| **Gemini family** (docs list 3.x and "4" models, agentic video mode) | Native video, 1 fps default, ~100 tokens/s at low res, ~300 at high; 1M-token context: up to 3 h low-res or 1 h high-res [fetched: [docs](https://aistudio.google.com/docs/video-understanding)]. Reasoning over a segment, open-vocabulary "what is this" | One video hour is ~360k to 1.08M tokens by that rate; price per token not verified. Blogs claim about $0.11/hour on Flash at low res [snippet, unverified: [Fora Soft](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/real-cost-of-ai-in-video-products-gemini-openai-pricing)]. [inference] Budget a few dollars per hour | API only | 1 fps misses fast fish; counts unreliable (below) |
| **Claude** | Strong image reasoning; the vision docs describe image input only, no native video; send sampled frames or crops. Docs say counts are approximate and worse with many small objects [fetched: [vision docs](https://platform.claude.com/docs/en/build-with-claude/vision)] | Image tokens per frame; cost per frame stated on the page | API | Same |
| **GPT family** | Frames-as-images; I did not check current video support or price | Not verified | API | Not verified |
| **Qwen3-VL (open)** | Image + video, long context; Apache-2.0 per aggregators [snippet: [Kanaries](https://docs.kanaries.net/articles/qwen3-vl)]. 235B variant ~471 GB of weights [snippet]; smaller sizes (e.g. 8B) fit a 16 to 24 GB GPU quantised [inference] | Local; no per-use cost | Apache-2.0 [snippet, verify] | Same VLM counting weakness |
| **InternVL3.5 (open)** | Similar; 8B listed at ~6 GB VRAM at Q4 [snippet: [bestllmfor](https://bestllmfor.com/catalog/internvl-35-8b/)] | Local | Apache-2.0 per one catalogue [snippet] | Unverified on video |
| **SAM 3 / 3.1** | Open-vocabulary text-prompted detection + masks + video tracking with IDs [snippet: [arXiv 2511.16719](https://arxiv.org/pdf/2511.16719)]. 848M params; needs CUDA GPU (CUDA 12.6+, no VRAM figure); SAM 3.1 added faster multi-object tracking on 27 Mar 2026 [fetched: [repo](https://github.com/facebookresearch/sam3)] | Local, mid-range GPU or better; Colab T4 plausibly works [inference] | Custom "SAM License"; text not read, check [fetched] | Not tested on turbid fish by me; likely to hallucinate on algae [inference] |
| **Grounding DINO / OWLv2** | Open-vocabulary boxes | Local GPU | See p2-data-models | Misses and false alarms on algae and kelp [inference] |
| **DINOv3** | Better embeddings for gallery matching and clustering | Local | Custom Meta licence, "Built with DINOv3" notice, termination clause [snippet: [Meta](https://ai.meta.com/resources/models-and-libraries/dinov3-license)]; DINOv2 is the Apache option | Features, not a detector |
| **BioCLIP 2 / 2.5** | Species names zero-shot; 2.5 card exists but I could not open it (HTTP 401) | Local, CPU ok on crops | MIT (BioCLIP 2) | Bias toward common taxa; poor on blurry crops |

**Is a frontier VLM any good at counting?** Mostly no, for video and for fine-grained fish.
- PushupBench (Apr 2026): best frontier model got 42.1% exact accuracy counting repetitions in video; the authors say VLMs recognise actions but struggle to count them [fetched: [arXiv 2604.23407](https://arxiv.org/abs/2604.23407)].
- VCBench (Mar 2026) reports weak world-state tracking in streaming counting [snippet: [arXiv 2603.12703](https://arxiv.org/html/2603.12703v1)].
- Image counting: VLMs are competitive on open-set counting but compared with specialised counters only in images [snippet: [Moonlight review](https://www.themoonlight.io/review/assessing-the-visual-enumeration-abilities-of-specialized-counting-architectures-and-vision-language-models)].
- Species: GPT-4o scored 17.9% on frequent and 1.2% on rare species in FishNet++ zero-shot [snippet: [Moonlight review](https://www.themoonlight.io/review/fishnet-analyzing-the-capabilities-of-multimodal-large-language-models-in-marine-biology)]; deep-sea set J-EDI QA gave GPT-4o 39%, o1 50% [snippet].
- I found no published zero-shot VLM counting figures on turbid underwater video. Treat VLM counts as unproven until measured on our holdout.

**Recommended Layer 2 stack** [inference]: SAM 3.1 (text prompt "fish", tracked IDs) as proposer + tracker; BioCLIP 2 + DINO gallery for species; a frontier VLM (Gemini for native video, Claude/GPT on frames) as a *segment reasoner* that returns structured JSON (visible fish count, species guess, confidence, "unclear") and is compared, not trusted. Layer 2 should demonstrate: (1) zero-label start (no training data needed); (2) better recall on unseen species and cryptic animals; (3) auto-generated pre-labels that feed Layer 1 training, so Layer 2 is a teacher and Layer 1 the cheap student; (4) honest numbers on where it fails. It should not claim to beat Layer 1 on counts unless the benchmark says so.

## 4. One architecture for three layers

**Stage interface** (Python protocols; each takes and returns the shared schema):
`SegmentProposer(video) -> [Segment]`, `Detector(frames) -> [Detection]`, `Tracker(detections) -> [Track]`, `Classifier(crops) -> [SpeciesGuess]`, `Counter(tracks) -> CountResult` (MaxN and unique).

| Stage | Layer 0 (no AI) | Layer 1 (local small AI) | Layer 2 (full capacity) |
|---|---|---|---|
| Proposer | Median/MOG2 motion + grid | Motion + low-conf detector | SAM 3.1 concept prompt or VLM scan of keyframes |
| Detector | Manual boxes/grid tags | YOLO-small / MegaFishDetector, ONNX | SAM 3.1 / Grounding DINO / VLM |
| Tracker | Manual or IoU linker | ByteTrack | SAM 3.1 tracker |
| Classifier | Reviewer picks from species list | BioCLIP 2 + gallery | Gallery + VLM reasoning |
| Counter | MaxN from manual tags | MaxN + unique, with uncertainty | Same, plus VLM segment count |

**Shared schema** (JSON per segment): `video_id, segment_id, t_start, t_end, layer, model_version, config_hash, detections[{t, box, score}], tracks[{id, frames, species_topk[{name, score}], status: known|fish_unknown|unclear}], counts{maxn, unique, vlm_count?}, flags{shake, murk}, review{reviewer, decision, time}, runtime_s`.

**Config:** one YAML, `layer: 0|1|2`, plus per-stage backend names and thresholds. Layer 2 backends are plug-ins that fail gracefully if unavailable. Results go to `results/{layer}/{video}/{segment}.json`.

**Side-by-side comparison:** because all layers write the same schema for the same `segment_id`, the UI joins on `segment_id` and shows three columns: boxes overlaid on the same still, counts, species, runtime, and agreement flag. Disagreements are queued first for review (also the best active-learning pool).

**Hardware and upgrade ladder** [inference; match to p2-gopro-motion compute]

| Step | Hardware | Unlocks |
|---|---|---|
| 0 | Current 32GB desktop, CPU only | Layer 0 plus Layer 1 at ~20 to 90 min per hour of video, overnight batch |
| 1 | + basic 6 to 8GB GPU | Layer 1 in 10 to 30 min/hour; local fine-tuning of small YOLO |
| 2 | + 16 to 24GB GPU | SAM 3.1 locally (needs CUDA); 8B open VLM quantised; Layer 2 teacher mode offline |
| 3 | 48GB+ GPU or small server | Larger Qwen-VL class models, batch teacher labelling |
| 4 | Cloud API (policy permitting) | Gemini/Claude/GPT as segment reasoner; no hardware |

## 5. Fastest honest benchmark (by Sunday)

Build first, in order:
1. **Labelled set** (Fri night to Sat): 20 to 30 short segments (30 to 60 s) across several videos from Coastal Action if provided, else Brackish test videos plus a few public clips. Two people label per segment: human MaxN, human unique count, boxes on 5 frames each. Split by video: ~60% dev, ~40% locked test. Record the label time per segment.
2. **Runner + schema + config** (Sat): one script `run(layer, video)` writing the shared JSON, and one `evaluate` script computing recall at fixed precision, count bias/MAE, runtime, and cost, per layer, on the locked test set.
3. **Layer 0 baseline:** motion proposals + manual tags. This sets the floor and the human time.
4. **Layer 1:** off-the-shelf MegaFishDetector + ByteTrack + BioCLIP 2 zero-shot; then a fine-tune on the dev set if time allows.
5. **Layer 2:** SAM 3.1 text prompt on a Colab T4 (dev only) + one frontier VLM prompted for structured JSON on the same segments.
6. **Comparison page:** one table (layers x metrics) and one side-by-side segment view.

Report n, per-clip errors, and failure examples. With ~25 segments the results are directional only (a wide interval); say so [inference]. Do not quote public-benchmark accuracy as ours.

## Not confirmed
BioCLIP 2.5 card (401); SAM 3 licence terms; official Gemini/GPT per-token prices and GPT video support; Qwen3-VL and InternVL licences and hardware (aggregator sources only); any zero-shot VLM count result on turbid underwater video; GPU/CPU of the partner PC.
