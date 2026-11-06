# P2 Coastal Action: build plan (planning only; nothing is built)

Rewritten 5 Nov 2026 around Jacob's latest direction. Authority: official statement, then 01-verification-log.md, then research. Tags: [official] PDF text; [notes] spoken remarks, not exact quotes; [fetched] page opened; [snippet] search result only, a lead; [inference]; [proposal]; [judgement]; [log] verification log. ClipSift and other names are working titles. We say "Coastal Action"; the PDF header reads "Blue Coastal Action".

## 1. Goal

Build a program that makes Coastal Action's MeanCount workflow fast and consistent by their own rules [proposal]. Today a person reviews the video in VLC plus basic image software, up to about 7 person-hours per video hour (Jacob's notes say 6 to 7), a spoken estimate [notes]. With the tool, more subsample points become affordable; the protocol's older draft cites an accuracy inflexion at 60 frames [protocol]. This is a proposal, and we state no time saving. The harder part is training and accuracy over time in turbid Nova Scotia water, as sites, seasons and cameras change.

## How Coastal Action counts today [protocol]

Source: the draft Video Analysis Protocol, a local document with open comments, so every number here may change [protocol]. Where it differs from the rep's spoken remarks, both are shown.

- **Setup:** stationary, unbaited remote underwater video. Results feed long-term monitoring of a living shoreline offsetting project, so comparability across years matters [protocol].
- **Metric:** MeanCount from systematic subsamples: 15 frames at 60 s intervals in a 15 minute window, in a draft [protocol]. An older draft says 60 points and cites an accuracy inflexion at 60 frames [protocol]. Which draft applies is open.
- **What is counted:** fish and invertebrates, plus species richness per video (species seen across the whole window) and whether juveniles are present [protocol].
- **Two-of-four rule:** count an organism only if at least two of four characteristics hold: shape; anatomical features; colouration or flashes; swimming behaviour or movement. When unsure, exclude, so undercounting is preferred to overcounting [protocol].
- **Visibility:** recorded in categories (under 0.5 m, 0.5 to 1.0 m, 1.0 to 1.5 m, over 1.5 m) [protocol].
- **Quality control:** a random share of annotated frames is counted a second time, blind, by another person [protocol]. The thresholds are under Count accuracy.
- **Schools:** the photos show a grid laid over the frame with one dot per fish and a total per cell. The protocol does not mention a grid [inference].

**Open discrepancies to confirm**
- Clip length: the rep said about 1 hour [notes]; the protocol says about 20 minutes [protocol]; screenshots show about 36 minutes [inference].
- Grid tagging: the rep described it [notes]; the protocol does not mention it.
- 6 to 7 hours per video hour remains a spoken estimate, not measured [notes].

## Recommended MVP [proposal]

The product is a local fish detection model plus a review app, working on one long recording at a time. It assists a person and does not replace review. The AI limit is about generative AI in big data centres, so it no longer caps the core, and this plan is more ambitious than earlier drafts.

**Must-have**
- Automatic detection, tracking and counts on a long recording as the main output (Layer 1, on by default).
- A model-ordered review queue: uncertain and disagreeing segments come first.
- Local fine-tuning from corrected frames as a real feature, not a demo-only loop, wherever the hardware allows: overnight on a GPU, or on a borrowed GPU with the weights copied over. Timing estimates remain inference.
- Species suggestions with a gallery; low-confidence cases stay "unknown" and go to human review.
- Method match: subsample points by their protocol (window, interval, one-second count), a dot tool and optional grid for schools, and the two-of-four checklist.
- Export in their sheet layout, shown beside the human count on stills they already counted.
- Manual-assist mode (Layer 0) in the same review app, as a fallback and for checking results.
- Kept safeguards: the "movement, unidentified" path, the set-aside audit of roughly 5%, and the proxy-resolution test.

**Should-have**
- Site-aware shortlist (watershed-level status only).
- Per-site calibration.
- Accuracy dashboard across model versions.

**Stretch**
- Layer 2a: bigger local vision models on a stronger local GPU or workstation, as the scale-up proof of concept.
- Layer 2b: a cloud generative vision model as an optional comparison, a team experiment in development.

**Out of scope**
- Real-time counting, sonar fusion, stereo length, and hosted generative AI in the shipped tool.

## Prototype status

A skeleton exists at RBC HubHacks/clipsift [log]: pipeline, review app with a sub-sample queue, dot and ellipse tools, QC mode, export, a species list of 42 entries, an annotation extractor, and 49 tests passing. It has not yet been tested on real video. Layer 1 uses a non-ML stand-in until real model weights are added, so nothing it counts is model accuracy. It has an off-by-default tiling option and a point-counting stub, both untested. The QC percent-difference formula is a placeholder because the PDF omits it. Commands are in clipsift/README.md.

## 2. The constraint

The PDF's Limitations section [official], quoted exactly:

"Due to environmental concerns, our use of AI is heavily restricted. At this time, we would not be able to support a publicly hosted AI model. However, we may be able to support an open-source model hosted locally, once we have the hardware to implement the system and more developed guidelines around the use of AI at Coastal Action."

The concern is major generative AI in big data centres (energy, water, optics). The shipped tool runs locally, offline, from pinned open-source files, with no hosted generative AI. The local fish detection model is the core of the product. The current PC is a Ryzen 5 5500 with 32GB RAM and a GTX 770, which we treat as CPU-only; an upgrade is planned in the near future (Matt's email, 5 Nov; see the upgrade ladder). Development is separate: the team has confirmed early footage as public access, with no AI limits for design and training (Jacob's rule; not seen in writing).

If asked about the AI limit: the concern is generative AI in big data centres. We ship a small machine learning model that runs on their desktop, with footage staying local and no hosted generative AI. A cloud generative vision model is an optional team experiment in development and isn't part of what ships. We haven't measured energy use, so we make no claim about it. Background: research/p2-environmental-footprint.md.

## What the AI limit does and doesn't cover

| What the concern is about | What we are building |
|---|---|
| Generative AI like Claude or ChatGPT | A small task-specific vision model: a local fish detection model |
| Footage sent to cloud data centres | Runs on their desktop; footage stays local |
| Large-scale compute | Assists a person, who confirms the results |

This is Jacob's reading from talking with the partner, and the PDF's wording fits it: it allows for an open-source model hosted locally. That line still mentions hardware and guidelines. Matt's email describes a planned upgrade specified to host a 30-40B parameter model, so a local model is on their roadmap. That weakens the need to ask whether a local model is acceptable, but keep one short confirmation.

Pitch line for their stakeholders: a small fish detection model on your own desktop, not a chatbot in a data centre. We make no environmental claims.

## 3. The layers [proposal]

| | Layer 0: manual-assist mode | Layer 1: local model, the core product | Layer 2a: bigger local models | Layer 2b: cloud generative vision model |
|---|---|---|---|---|
| What runs | Motion flagging, median background, difference view, contrast, grid tagging, species list. Always available as a fallback and for checking results | Local fish detection model: YOLO-small or MegaFishDetector (ONNX), ByteTrack-style tracking, BioCLIP 2 plus gallery on crops. On by default | Scale-up proof of concept: SAM 3.1 proposer and tracker, larger detectors, stronger species models, on a stronger local GPU or a workstation. Not the concern at all; the main scale-up story | Optional comparison: a frontier VLM (for example Gemini, native video at 1 fps by default [fetched]) as segment reasoner with structured output, compared, not trusted. This is the kind of tool the partner is wary of |
| For | Any staff member, any PC | Staff, as the main tool | Decision makers, to see what a stronger machine gives | The team only |
| Hardware | Current PC (Ryzen 5 5500, 32GB RAM), CPU only | Same on CPU; the planned RTX 3060 12GB would shorten runs and allow local fine-tuning | CUDA GPU for SAM 3 (848M parameters; no VRAM figure found); the planned RTX 3060 12GB may allow some experiments, untested | API in development only |
| Licence | Our code, standard libraries | Open-source weights only: BioCLIP 2 MIT [fetched]; Ultralytics AGPL-3.0 (see licence note below); MegaFishDetector card says MIT but is YOLOv5-based, inheritance unconfirmed [log] | SAM 3 has a custom SAM License. Fine for Layer 2 and development, not assumed OK for Layer 1. Terms not fully read; read before reuse, including derived models [log] | Provider terms; no footage sent without a decision |
| Shows | The workflow by hand, and a human baseline | Automatic detection, tracking, counts, species suggestions, the label loop | Recall on unseen animals, pre-labels that teach Layer 1, honest failures [inference] | Whether a generative model adds anything, honest failures |
| Status | Fallback, shared with the review app | Core product | Contained demo, not shipped | Team experiment in development, optional, not a pitch headline, not shipped |

**Licence note:** Because Layer 1 is now the product, choose the detector licence early. AGPL is workable if the tool's source goes to Coastal Action with it; RT-DETR is a possible permissive alternative (licence to verify).

Counts from VLMs are unproven. The best frontier model scored 42.1% exact accuracy counting repetitions in video (PushupBench) [fetched]. That is pushups, not fish, so a warning sign only. No turbid underwater figures exist, so Layers 2a and 2b are measured on our holdout.

**Upgrade ladder** (Coastal Action's option over time) [inference]:

| Step | Change | Unlocks |
|---|---|---|
| 0 | Current PC: Ryzen 5 5500, 32GB RAM, GTX 770 treated as CPU-only (Kepler; current deep learning stacks unlikely to support it, untested [log]) | Layer 0; Layer 1 overnight (about 20 to 75 min per video hour; 90+ for 4K HEVC on an older CPU) |
| 1 | Planned near-term upgrade: RTX 3060 12GB (confirm the 12GB version; an 8GB variant exists [log]) | Layer 1 faster (an earlier estimate for a basic 6 to 8GB GPU was about 10 to 30 min per video hour, not measured on a 3060); local fine-tuning; likely some Layer 2a experiments such as SAM 3.1, untested |
| 2 | 16 to 24GB CUDA GPU | Layer 2a: more headroom for SAM 3.1; quantised 8B open VLM |
| 3 | 48GB+ GPU or server | Layer 2a: larger open VLMs, batch teacher labelling |
| 4 | Partner agrees to a cloud API | Layer 2b: cloud generative vision model as an optional reasoner |

Timings are estimates.

**Layer 1 model plan** [proposal]

Two separate detection problems, from the photos [inference]:
1. Small schooling fish in midwater: many per frame, counted by Coastal Action with a grid and one dot per fish. Two example frames hold about 102 and 46 fish, by reading the written totals (handwriting readings need checking). Candidate: tiled detection or point-based counting, tested against plain box detection. No claim yet that either works.
2. Large camouflaged crabs on the bottom, hard to see in one still. Motion context matters: a protocol comment says flounder are missed unless moving [protocol], and the rep's crab example agrees [notes]. Candidate: a detector plus motion across the context window around each point.

Conservative rule: the protocol prefers undercounting [protocol], so a model count must follow it. Calibrate thresholds to under-count rather than over-count, and report the threshold with every count. How the model should treat the two-of-four rule is an open question for the partner.

Compute order: dense processing only inside the context windows around the subsample points comes first, which is far less video than the full window. The full-window scan comes after, for species richness.

## 4. One architecture

Stage interface: SegmentProposer, Detector, Tracker, Classifier, Counter. All write one shared JSON schema per segment (ids, times, layer, model_version, config_hash, detections, tracks with species top-k and status known, fish_unknown or unclear, counts maxn, unique and optional vlm_count, flags shake and murk, review decision, runtime). One YAML config picks `layer: 0|1|2a|2b` and per-stage backends; The app joins layers on segment_id and shows them side by side. Disagreements queue first.

Kept [proposal]:
- **Local review app** (Python backend, browser UI, no internet); **unit of work** is one long recording (stitched chapters) as a timeline of segments.
- **Review view:** still with grid; loop cut from the original; difference view (frame beside frame minus median background); display-only contrast sliders, never applied to the stored original.
- **Movement path:** unexplained motion is labelled "movement, unidentified" and reviewed, never dropped, following the crab example [notes]. No controlled study shows motion beats single-frame detection [log].
- **Proxy-resolution risk:** downscaling can erase small faint movement. Cut stills and loops from the originals, and test proxy against higher resolution on a known cryptic clip.
- **Set-aside audit:** quiet time is set aside, never deleted; a random human audit of roughly 5% makes silent misses measurable.
- **Export** in their sheet layout; run on stills they already counted and show both counts.

## 5. Training plan

Label quantities are [inference]; no published minimum for fish detection was found. Practical range: 300 to 1,000 local frames fine-tune a "fish" detector from a pretrained start; species level needs far more per class, so species stays a review-queue job.

| Route | (a) Old videos plus counts | (b) Old videos only | (c) A few manual samples |
|---|---|---|---|
| 1 | Generic detector zero-shot; score against sheets | Pre-label with detector plus motion; correct 200 to 500 frames | Pre-label; correct about 100 frames |
| 2 | Correct worst-disagreement videos | Active-learning order | Fine-tune on Brackish plus these; held-out test |
| 3 | Fine-tune; re-check against sheets | Brackish pretrain, then fine-tune | Synthetic copy-paste, never in test |
| 4 | Count-supervised (roadmap only) | Few-shot species | Few-shot only |

**Hand-count spreadsheets:** if the technician shares them (Matt's email says the technician will be asked), they are frame-level labels: a count for a known video and timestamp. This upgrades the earlier wording that treated count sheets as weak labels, pending the actual format. Use them for validation first (signed bias and mean absolute error per clip, no boxes needed), then calibration (per-site correction, thresholds), then triage (count-0 videos give true negatives; biggest disagreements are frames to label). Count-supervised training is roadmap only: FishDetector-R1 reports 30% lower MAE on DeepFish from sparse point labels [fetched abstract], but it is research code.

**Marked screenshots** [log]: the 28 marked screenshots hold weak labels. Extracted dots match the written totals in the cells that have them, but seabed texture causes false dots elsewhere (for example 58 in one cell, 567 black dots in another image), so human checking is required. Red ellipses were extracted on most marked frames. Annotated images must not be used directly for training, because a model would learn the red marks and the player bar. Pull clean frames at the same timestamps from the video where possible, and ask for clean originals.

**Pre-label then correct** is the biggest saver; filter by confidence, as unfiltered pseudo-labels bake in errors [snippet].

**Active-learning order:** frames near the threshold; detector disagreement; unlabelled embedding clusters; tool-versus-sheet disagreement; a random 10% holdout. Neighbouring frames never split across sets [inference].

**Transfer:** Brackish or MegaFishDetector weights first. Brackish's CC BY 4.0 came from a snippet and is unconfirmed; check in a browser [log]. Scene layout drives cross-site loss more than haze (Piccolo et al.) [fetched], so expect to need local frames.

**Few-shot gallery:** 5 to 20 reviewed crops per species, nearest neighbour on BioCLIP 2 or DINO embeddings; below a threshold goes to review [inference].

## 6. Accuracy over time

All [inference]. Review writes labels. Model, dataset (hash-pinned manifest) and config are versioned, never overwritten. Frozen holdouts split by video (unseen site, date or season, hard turbidity; about 20 to 30 videos or 300+ labelled frames); a "fresh" set grows each season. Tracked per version: recall at fixed precision, per-clip count bias and MAE, reviewer correction rate, unknown-species rate. Retrain triggers: correction rate up 25% relative, a new site, season or camera, turbidity shift, watch-list species. Retrain after roughly 300 to 500 corrected frames or a season, only if the candidate beats the current model on frozen and fresh sets; keep rollback. Local fine-tuning from corrected frames is a product feature: run it overnight on a GPU where the desktop has one. Otherwise train on a borrowed GPU (a free T4, about 2k images, 20 to 60 minutes) and copy the ONNX weights to the desktop. Timings are estimates.

## 7. Species system

Backbone: **WoRMS AphiaID**, cross-referenced to GBIF key, ITIS TSN, FishBase code, iNaturalist ID. Cod 126436, American eel 158562, black sea bass 159348 resolved cleanly [tested]; GBIF is the fallback for freshwater taxa. WoRMS's licence field was null in our test; confirm.

Versioned offline list, built by one rerunnable script [proposal]:
1. Seed list plus DFO survey species (OGL).
2. Resolve to AphiaID; synonyms and WoRMS and GBIF vernaculars (English, French) plus local names become aliases.
3. Distribution tier from OBIS and GBIF; absent means watch tier, never deleted.
4. Traits from the rfishbase parquet snapshot.
5. Flags: at-risk (hand-entered with date), invasive, range-expander.
6. Images filtered per image: keep CC0, CC BY, CC BY-SA; CC BY-NC is a team decision; drop the rest.
7. Freeze as species_list_vYYYY.MM.DD.json with a manifest.

Record schema: IDs (aphia_id, gbif_key, itis_tsn), scientific_name, common_names and aliases, habitat, ns_status (tier, records, last year), flags (at_risk with source and checked date; invasive; range_expander), id_notes, images (url, licence, author, source), sources with retrieval dates.

Open-licensed images are scarce [tested]: 1 of 60 NS cod and 21 of 352 NS eel observations pass an open filter; black sea bass has none. Coastal Action's reviewed frames are the best reference set. The list is editable; an "unexpected, review" tier and an unknown queue drop nothing. The site-aware shortlist is should-have; ACCDC location rules are unverified, so show watershed-level status only.

## 8. Count accuracy

Report **MaxN** (with its frame), **MeanCount** over fixed-interval stills, **tracked unique count** where tracking allows, and the **human count**. These are relative indices, not abundance.

That MaxN follows a power function of abundance is a lead: the Campbell et al. 2015 paper exists, but the claim was not visible on the page read [log]. Published figures appear only with their setting: Mask R-CNN MaxN 1.5% and 7.8% above experts and citizen scientists, F1 92.3%, one Queensland setting [fetched abstract]; snapper correlation 0.72 to 0.9 unassisted, 0.96 assisted [snippet]. They do not transfer to Nova Scotia.

**Interval:** the draft protocol uses 60 s (an older draft, 12 s) [protocol]. Follow their interval as the default; check on validation clips how MeanCount changes with more points, as a suggestion to them, not a change to their method [inference]. **Uncertainty:** report a range (bootstrap over frames for MeanCount; model-confidence band for species), score visibility per clip, and mark low-visibility clips "counts are minima". **Ceiling:** human-human agreement is the limit the tool is judged against.

**Yardstick** [protocol]: use Coastal Action's own QC numbers. A blind second count should differ by under 6% from the first, with 95% agreement (draft; the percent-difference formula is missing from the PDF). With small counts one fish can exceed 6%, so report absolute differences too. We do not claim the tool meets these.

**Validation protocol:**
1. Use the section 11 labelled set, so labelling happens once: clear and turbid mixed, public footage if none arrives, said plainly. Stretch target if time allows: 10 clips of 5 minutes.
2. Two or more humans annotate independently (timestamp, species or unknown, count per subsample point, using their rules) and time themselves.
3. Measure human-human agreement first: count difference, MaxN, species (percent, Cohen's kappa).
4. Reconcile to a consensus set.
5. Run Layer 1 on the same stills, with Layer 0 manual assist as the human baseline; compare to each human and to consensus, beside human-human.
6. Stratify by visibility and abundance (0, 1 to 3, 4+).
7. Record review minutes per clip with and without suggestions.

**Good result:** the tool differs from consensus about as much as one human differs from another, and human-with-tool review is faster than annotating alone. Expect lower than published figures on turbid footage. Ten clips is a pilot, not proof.

## 9. Value model (formula only)

The value claim is a proposal: fast and consistent MeanCount by their rules, with more subsample points affordable (the protocol's older draft cites an accuracy inflexion at 60 frames [protocol]). No time saving is stated.

Inputs: V video hours per year (Coastal Action to supply); a analyst hours per video hour today, 6 to 7, the partner's spoken estimate, not measured [notes]; b human hours per video hour with the tool, measured by us including corrections, per layer; w loaded hourly wage and S one-time setup hours (Coastal Action to supply).

Hours saved, year one = V x (a - b) - S. Cost saved = hours saved x w. Unattended compute hours are separate. No time-saving ratio and no claim of 10 minutes until measured; Jacob's 7 hours to 10 minutes is an aspiration, not a result.

## 10. Scores (our judgement) [judgement]

0 to 3 per criterion on the 2025 rubric (2026 may differ [log]); for comparing options only. Rows add up. Scores: unchanged after the 5 Nov facts (protocol, photos, hardware, skeleton).

| Option | Impact | Function | Innovation | Presentation | Execution | Total /15 |
|---|---|---|---|---|---|---|
| 0 only | 1: no automatic detection | 3: any PC | 1 | 2 | 3: no model risk | 10 |
| 0 + 1 | 3 | 3 | 2 | 3: model does the work, measured results | 2: PC speed unmeasured | 13 |
| **0 + 1 + 2a demo** | 3 | 3 | 3: path from desktop to workstation | 3 | 2 | 14 |
| 0 + 1 + 2a + 2b | 3 | 2: more to maintain | 3 | 2: optics risk with this partner | 1: two experiments can sink the core | 11 |

Recommended: 0 + 1 + 2a as a contained demo, 14 of 15. Layer 1 is the product and delivers the automation asked for, with Layer 0 as the fallback in the same app. Layer 2a adds Innovation and a scale-up story without touching the concern, but SAM 3 needs a CUDA GPU, has a custom licence and has no turbid fish evidence, so it stays time-boxed. Layer 2b is the thing the partner is wary of and adds maintenance, so it stays an optional team experiment, not a pitch headline. Innovation 3 is the most arguable score.

## 11. Sunday benchmark: build first

Layers on one labelled set, the same set the section 8 protocol uses [inference]. Layer 1 is the headline result, Layer 0 is the human baseline and Layer 2a is the ceiling comparison. Start from the clipsift skeleton (see Prototype status) rather than from scratch.
1. **Labelled set** (Fri night to Sat): 20 to 30 segments of 30 to 60 s across several videos (Coastal Action's, else Brackish and public clips). Two people label each: MaxN, unique count, boxes on 5 frames. Split by video, about 60% dev, 40% locked test. Prefer protocol-style subsample points, and score against hand counts if the technician shares them.
2. **Runner, schema, config** (Sat): the skeleton already has `run`, `export` and `evaluate` commands (count bias and MAE against a labels file). Extend `evaluate` with recall at fixed precision and runtime.
3. **Layer 1** (headline): the skeleton's Layer 1 is a non-ML stand-in, so training the first real detector is the top Friday-Saturday task. Start from off-the-shelf MegaFishDetector, ByteTrack, BioCLIP 2, fine-tuned on dev, with measured gain from corrected frames.
4. **Layer 0** (manual assist) gives the human baseline: counts and review time done by hand.
5. **Layer 2a** (ceiling): SAM 3.1 "fish" prompt on a Colab T4 (development only), same segments. **Layer 2b** (optional team experiment): one cloud generative vision model returning structured JSON, same segments.
6. **Comparison page:** layers by metrics, plus side-by-side segment view.

Report n and failures; about 25 segments is directional only.

## 12. Team plan for five

Jacob, Ali, Gina and Wang (Master of Business Analytics) and Adrien (Master of Computing and Data Analytics). Skills are unknown, so these are workstreams, not assignments.

| Workstream | Scope |
|---|---|
| Pipeline and models | Extend the clipsift skeleton (decode, motion, stage interface and schema exist): train the first real detector for Layer 1 first, then Layers 2a and 2b, evaluate script. Adrien's degree suggests a possible fit; the team decides |
| Review app and UI | Builds on the skeleton's review app (sub-sample queue, dot and ellipse tools, QC mode, export): timeline, side-by-side, list editor |
| Labelling and validation | Rules, benchmark set, validation protocol, metric tables |
| Species data | WoRMS build script, aliases, flags, images, unknown queue |
| Pitch and value | Questions and answers, value model, deck, Sam demo, submission format |

The rubric's Execution criterion mentions all members, so everyone should visibly contribute. Labelling is the shared bottleneck: everyone labels.

| When | Plan [proposal] |
|---|---|
| Fri 6 Nov | 2:00pm mentor meeting. Start from the clipsift skeleton and run it on any real clip that arrives. Top Friday-Saturday task: train the first real detector, since the skeleton's Layer 1 is a stand-in. Labelling rules, first labels. Manual-assist features come along with the review app, since they share it |
| Sat 7 Nov | Layer 1 with the first real detector working on a long recording by about midday, then the correction and fine-tuning loop and the species gallery. Layer 2 in a fixed 4-hour time box (2a first, 2b only if time remains); stop rule: if SAM 3.1 gives no tracked boxes on a test clip within 2 hours, stop and report it as not achieved. Labelling in shifts |
| Sun 8 Nov | Evaluation and validation tables. Freeze at midday. Rehearse twice. Submit before 11:59pm AST |
| Mon 9 Nov | Presentations, Innovation Hub |

## 13. Demo story (10 minutes)

User: **"Sam", a fictional Coastal Action field technician**. Pre-processed results, live scrub.
1. **Problem (1 min):** a long recording and the protocol's subsample points counted by hand.
2. **The model does the work (2):** the local fish detection model runs on a long recording; detections, tracks and counts appear on the timeline.
3. **A person confirms (1.5):** Sam works through the model-ordered review queue, with the subsample still, dot tool, loop, difference view and a "movement, unidentified" hit. Planned: use a real subsample frame with a school and a crab, if one is available.
4. **Counts in their layout (1):** export in Coastal Action's sheet layout, beside the human count.
5. **A corrected label improves the next run (1.5):** shown only if measured; otherwise described as the plan.
6. **Honest results (1.5):** measured recall and count error against the human ceiling, audit miss rate, failures.
7. **Upgrade ladder, value and next step (1.5):** the ladder, with a pre-computed Layer 2a result on the same segment, labelled as a proof of concept that isn't shipped (Layer 2b only if run, same label), then the formula and a pilot ask.

The demo stays at 10 minutes. The real-frame segment is labelled 'planned' until the frame exists.

## 14. Top 8 questions, by plan impact

1. Hand-count spreadsheets: can the technician share them, and in what format (columns, video ID, timestamp)?
2. Clean originals (no marks, no enhancement) for the 28 marked frames?
3. Which draft sampling applies: 15 frames at 60 s, or 60 points?
4. Recording length: about 20 minutes (protocol), about 36 (screenshots) or about 1 hour (rep)?
5. Are schools always dot-counted, or only sometimes?
6. Camera model and settings?
7. What should the model do with the two-of-four rule?
8. What is the 30-40B model for, and the DDR5 point (below)?

Most go to Coastal Action via the mentors. Logistics: audience; acceptable error for at-risk species; which water release the rep meant; submission format; 2026 rubric; reuse terms for footage; an existing species list. Already answered by the protocol: invertebrates are counted, and the metric is MeanCount.

**Questions to Matt: hardware note** [log]
- A Ryzen 7 7700X needs DDR5, not DDR4. The email's "32GB DDR4" with a 7700X will not work.
- Make sure of the 12GB version of the RTX 3060; an 8GB variant exists.
- A 30-40B model will not fit in 12GB VRAM at 4-bit (weights alone are about 15 to 20 GB), so it would offload to system RAM and run slowly. Small vision models fit comfortably and do not need it. Ask what the 30-40B model is for.
- The email supports that a local model is on their roadmap. This weakens the need to ask whether a local model is acceptable, but keep one short confirmation.

## 15. Things not to claim

- That we meet Coastal Action's AI policy (not seen), or that the tool is "greener".
- That the partner has approved Layer 1 (until confirmed), or that the planned upgrade is bought.
- That the tool meets the protocol's QC thresholds, or that the prototype works on real video.
- That a model count follows the conservative rule before thresholds are calibrated and tested.
- That the marked screenshots are clean labels, or any time saving.
- Any NS accuracy not measured on held-out local footage.
- That VLMs count well, that SAM 3 is open source in the Layer 1 sense, that MaxN follows a power function, or that any sampling interval is better than theirs.
- That 6 to 7 hours is measured, that 7 hours to 10 minutes is a result, or any time-saving ratio or cost saving without measured minutes.
- That timings were measured on their PC, or that motion beats stills.
- That nothing leaves the PC, unless checked with the network disabled.
- That the tool replaces human review, identifies rare or invasive arrivals, or that tracked counts equal abundance.
- That Brackish is CC BY 4.0, MegaFishDetector weights are MIT-clean, ACCDC permits showing locations, or the portal is the rep's release, until confirmed.
- "Tropical species are common" (say warm-water range-expanders); Innovasea's "90 percent" as comparable.

## Sources added 5 Nov

- Draft protocol: "Coastal Action DRAFT FFH Video Analysis Protocol.pdf", a local document in the RBC HubHacks folder (draft with open comments; no link).
- Subsample photos: "Sept 10 & 9th sub-samples", 28 marked screenshots, a local document in the RBC HubHacks folder (no link).
- Erickson et al. 2023, from the protocol references: https://peerj.com/articles/15426/ (page not opened by us).
