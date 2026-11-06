# P2 (Coastal Action): data and models for a weekend fish detection / ID / counting POC

Researched Thu 5 Nov 2026. Tags: [fetched] page opened; [status] HTTP code check only (page exists, content not read); [snippet] search result only; [inference] my reasoning, not a fact. Link status: 200 means the URL resolved on 5 Nov.

## Bottom line

- No public dataset matches cold, turbid Nova Scotia water with fish labels. Every public set is tropical, reef, aquarium, river sonar, or deep-sea. [inference] Domain shift is the central risk, and the honest pitch is "pipeline + human review queue that creates the missing local labels", not "accurate NS fish counter".
- Best weekend stack: generic fish detector (MegaFishDetector or Fishial detector) -> tracker -> open-vocabulary species suggestion (BioCLIP 2) -> "unknown / flag for human" queue. Humans' corrections become training labels.
- Hard dependency: a few minutes of actual Coastal Action video. Ask the mentor on Fri 6 Nov. Without it, the demo runs only on out-of-domain footage.

## Datasets

| Dataset | Size / annotation | Licence | Environment | Fit for NS cold turbid | Access |
|---|---|---|---|---|---|
| Brackish (Aalborg) | 89 videos, 14,674 images on Roboflow copy (12,444 with objects); boxes in YOLO/COCO; 6 classes (fish, small fish, crab, shrimp, jellyfish, starfish) [snippet] | CC BY 4.0 per Roboflow copy [snippet]; check Kaggle page | Limfjorden, Denmark: cold temperate, brackish, turbid | Best proxy. Few species (fish is one class) | [vap.aau.dk](https://vap.aau.dk/the-brackish-dataset/) 200; [Kaggle](https://www.kaggle.com/datasets/aalborguniversity/brackish-dataset) 200; [Roboflow](https://public.roboflow.com/object-detection/brackish-underwater) |
| BrackishMOT | Tracking extension of Brackish. I did not verify it | unverified | same fjord | Useful for counting evaluation if it exists | Not checked. Search needed |
| FathomNet | Community image + bounding box DB, mostly deep-sea ROV (MBARI). Counts not confirmed: the page was JS-rendered and the stats endpoint 404'd [fetched] | Terms not confirmed. Check before reuse | Pacific deep sea, some others | Species-level labels but wrong habitat | [database.fathomnet.org](https://database.fathomnet.org) 200; [fathomnet-py](https://github.com/fathomnet/fathomnet-py) 200; [models](https://github.com/fathomnet/models) 200 |
| DeepFish | ~39.8k frames, 20 habitats, tropical Australia; classification, counting, localisation [snippet] | Not found | Tropical, mostly clear | Weak | [site](https://alzayats.github.io/DeepFish/) 200; [paper](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9184594/) |
| OzFish | ~80k crops, 500+ species, ~45k boxes on 1,800 frames [snippet] | CC BY 3.0 AU (per AODN record) [snippet] | Western Australia BRUVs | Weak; useful for pretraining | [CSIRO](https://data.csiro.au/collection/csiro:38878) 200 |
| NOAA Labeled Fishes in the Wild | Not verified. Used by MegaFishDetector training [fetched] | NOAA, likely public domain, unverified | US waters incl. Pacific | Unknown | My guessed URL 404'd. Find via the MegaFishDetector links |
| Caltech Fish Counting (CFC) | 1,567 sonar sequences, 7 cameras, 3 rivers (AK, WA); 516k boxes, 8,254 tracked fish, 16.7 hours [snippet] | Not found | Sonar, grayscale, river | Not video, but a real counting benchmark and shows turbidity-proof sensing | [repo](https://github.com/visipedia/caltech-fish-counting) 200; [paper](https://arxiv.org/pdf/2207.09295) |
| FishNet Open Images (Kay) | 86,029 images, 34 classes, fishing-vessel cameras [snippet] | Not found | On-deck, not underwater | Low. Note the ICCV 2023 "FishNet" is a different dataset; I did not verify it | [arXiv 2106.09178](https://arxiv.org/abs/2106.09178v1) |
| AQUA20 | 8,171 images, 20 classes, on Hugging Face [snippet] | Not found | Mixed | Low | Search needed |
| SEAMAPD21 | Reef fish fine-grained set, CVPR-FGVC 2021 [snippet]; size unconfirmed | unknown | Gulf of Mexico reef | Low | Not verified |
| SUIM | Semantic segmentation of underwater scenes (not fish-specific) | unverified | Mixed | Low | [GitHub](https://github.com/xahidbuffon/SUIM) 200; UMN host 403 |
| Fish4Knowledge | Taiwan reef video | unverified | Tropical | Low | fish4knowledge.eu did not respond. Unreachable |
| Roboflow Universe fish sets | Many small community sets, mixed quality | Per-set, often CC BY 4.0, some unspecified | Mixed | Search for "turbid", "river", "salmon", "herring" | universe.roboflow.com returned 403 to curl (bot block, probably fine in a browser) |
| LifeCLEF fish | Not checked | - | - | - | Not checked |
| iNaturalist / GBIF | Live API check: GBIF Canada still images of Atlantic cod 241, bluefish (a warm-water arrival) 7 [fetched, API]. iNat Atlantic cod with CC-BY/NC/CC0 photos: 1,161 worldwide | Per-photo CC licences; filter out "all rights reserved" and NC for any product use | Mostly above-water or aquarium | Useful for BioCLIP species checks and reference galleries, not for detector training | api.gbif.org and api.inaturalist.org both answer |
| Ocean Networks Canada | FAIR, open data via Oceans 3.0, SeaTube annotation tool [snippet] | Terms not confirmed | Mostly Pacific (Saanich Inlet, Barkley); Atlantic minimal | Not a weekend source | [data.oceannetworks.ca](https://data.oceannetworks.ca) 200 |
| FORCE / Acadia (Bay of Fundy) | Public work is mostly hydroacoustic and acoustic tagging; I found no public video dataset [snippet]. FORCE 2024 report mentions an Innovasea AI fish-monitoring project [snippet] | - | Minas Passage, extreme turbidity | Directly relevant, but ask the mentor | [2024 report](https://tethys.pnnl.gov/publications/environmental-effects-monitoring-program-annual-report-2024) |
| YouTube / BRUV clips | Searchable, none vetted | YouTube terms plus uploader copyright. Do not scrape or train/redistribute. Use only with the uploader's permission or CC licence | - | Possible for a private demo clip only | - |

Not found: any public NOAA Northeast or Ocean Tracking Network fish video set. OTN is acoustic telemetry. Say "not found", not "does not exist".

Most relevant paper: [Piccolo et al., arXiv 2601.13975](https://arxiv.org/abs/2601.13975) (Jan 2026, CC BY 4.0) [fetched]. It covers invasive-species monitoring in Arctic and Atlantic waters and finds cross-site detector loss is explained more by scene layout, crowding and context than by haze. No dataset or code link was visible.

## Models and tools

| Tool | Use | Licence / note | Link |
|---|---|---|---|
| MegaFishDetector (WARP lab, FathomNet) | Generic "fish" boxes; YOLOv5-based; trained on OzFish, FathomNet, VIAME FishTrack, NOAA Puget Sound, DeepFish, NOAA LFW; no accuracy numbers on the card [fetched] | MIT on the card, but the YOLOv5 base is Ultralytics AGPL, so check what the weights inherit [inference] | [HF](https://huggingface.co/FathomNet/megafishdetector) |
| Fishial.ai | Detector (YOLO-based), classifier (DINOv2+ViT, 866 species, 93.22% on its own test set), segmenter; Colab notebook [fetched] | Repo MIT [fetched]. The 93% is a within-distribution figure | [repo](https://github.com/fishial/fish-identification) 200 |
| Ultralytics YOLO | Easiest training and export | AGPL-3.0 [fetched]. Modified versions served over a network must publish source. A hackathon POC is fine; flag it if a product is intended. Alternatives: RT-DETR ([repo](https://github.com/lyuwenyu/RT-DETR) 200, Apache-2.0 per my recollection, unverified) | [ultralytics](https://github.com/ultralytics/ultralytics) |
| Grounding DINO / OWLv2 | Zero-shot "fish" boxes, no training | OWLv2 is on HF; check licences. Expect misses and false positives on algae and kelp [inference] | [GDINO](https://github.com/IDEA-Research/GroundingDINO), [OWLv2](https://huggingface.co/google/owlv2-base-patch16-ensemble) |
| SAM 2 | Mask propagation; good for tracking a few clicked fish | Apache-2.0 per my recollection, unverified | [repo](https://github.com/facebookresearch/sam2) 200 |
| BioCLIP 2 | Zero-shot species from names plus similarity scores; ViT-L/14, MIT, trained on TreeOfLife-200M (~214M images, 952k taxa). Card warns of bias toward well-represented species [fetched]. Newer 2.5 version listed on the card | MIT | [HF](https://huggingface.co/imageomics/bioclip-2) |
| DINOv2 | Embeddings for similarity search, clustering unknowns, active learning | [repo](https://github.com/facebookresearch/dinov2) 200 | |
| ByteTrack / BoxMOT | Cheap multi-object tracking | [ByteTrack](https://github.com/ifzhang/ByteTrack) 200; [boxmot](https://github.com/mikel-brostrom/boxmot) 200. BoxMOT licence not checked, likely AGPL | |
| VIAME | Kitware annotation + detection + tracking GUI; underwater heritage | [repo](https://github.com/Kitware/VIAME) 200. Heavy install; likely too much for a weekend [inference] | |
| VLM second pass (Claude, etc.) | Ask "is this a fish, what family, is the view too blurry to say?" on crops flagged low-confidence | Cost and privacy per call. VLM species answers are unreliable on blurry crops [inference] | |

## Turbidity handling and the evidence

- Options: CLAHE (trivial, OpenCV), dark channel prior, Sea-thru (needs depth maps, impractical for a weekend), learned enhancers, background subtraction (useful for static cameras with tidal flow, but moving kelp and sediment trigger it).
- Evidence is mixed. One 2026 study reports CLAHE best among six scenarios with YOLOv11 [snippet, [IPB](https://journal.ipb.ac.id/jtpk/article/download/66223/34246)]. A 2024 Applied Intelligence paper found MSRCR among effective fixes for cross-domain loss and also warns random splits overstate accuracy [snippet, [Springer](https://link.springer.com/doi/10.1007/s10489-024-06224-0)]. Other work argues fixed enhancement can hurt detection and prefers end-to-end training [snippet]. Piccolo et al. argue scene structure matters more than haze [fetched, qualitative].
- Practical rule [inference]: treat enhancement as a toggle. Run A/B on your own 50 labelled frames. Report whichever wins. Do not claim enhancement helps.

## Counting

- MaxN = the maximum number of fish visible in any single frame. Conservative, standard in BRUV work, immune to ID switches, but undercounts anything passing through (tidal flow) and says nothing about unique fish.
- Tracked unique count = number of distinct tracks. Better for flow-through sites, but ID switches and fragmentations inflate it, and occlusion by algae splits tracks. Double counting is the headline failure: one fish leaving and re-entering a turbid frame counts twice.
- Report both, plus a human count, and show the gap.
- Metrics: detection mAP@0.5 and recall (recall matters most because misses are silent); count error as MAE and signed bias per clip; HOTA/IDF1 only if you annotate track IDs for a short clip (CFC uses MOT-style evaluation [snippet]). [inference] Use recall at a fixed precision and per-clip count error as headline numbers.

## Compute [inference]

| Task | Laptop CPU | Apple silicon (MPS) | Free Colab / Kaggle T4 |
|---|---|---|---|
| YOLO-small inference at 640px | ~2 to 8 fps | ~20 to 60 fps | 100+ fps |
| BioCLIP 2 ViT-L on crops | ~1 to 3 crops/s | ~10 to 20 crops/s | 50+ crops/s |
| Fine-tune YOLO-small on ~2k images | impractical | hours, fragile | ~20 to 60 min |
| SAM 2 video | too slow | possible, slow | fine for short clips |
| Grounding DINO / OWLv2 | slow | slow | okay for sampled frames |

Sample video at 2 to 5 fps rather than processing every frame.

## Recommended POC pipelines

**Tier 1, safe (about 1 day).** Fishial or MegaFishDetector + ByteTrack, run on Brackish test videos plus any Coastal Action clips; BioCLIP 2 zero-shot over a Gulf of Maine/NS checklist plus an "unknown" threshold; Streamlit review UI. Output: MaxN and unique count per clip with confidence. Risks: unknown recall on NS footage; Brackish "fish" is a single class; BioCLIP ranks blurry crops poorly.

**Tier 2, ambitious (about 2 days).** Tier 1 plus fine-tune a small detector on Brackish + 100 to 300 team-labelled frames from local or similar footage; CLAHE toggle A/B; DINOv2 embeddings to cluster unknown crops; a VLM second pass on flagged crops. Risks: tiny labelled set, overfit, labeller time; AGPL if using Ultralytics.

**Tier 3, stretch (if everything works).** Active learning loop: reviewer corrections written back as YOLO-format labels, retrain, show before/after recall on a held-out video from a different date or site. Add SAM 2 for masks on size estimates. Risks: will not be statistically meaningful in a weekend; present it as a demonstration of the loop only.

**Unknown handling.** Three outcomes per track: known species (BioCLIP margin over runner-up and absolute similarity both above thresholds), "fish, species unknown", or "unclear / not a fish". Anything below thresholds, any species on a "warm-water/invasive watch list" and anything with track length under N frames goes to the review queue. Pick thresholds on the held-out set, not by eye.

**Human review queue -> labels.** Reviewer sees best crop + 3 candidate species + "unknown". Each decision writes: crop, box, track ID, species, reviewer, timestamp. Confirmed items become training data; "unknown" items become a new-species candidate list for Coastal Action biologists. This also addresses the outdated species list problem.

## What NOT to claim

- No accuracy figure for Nova Scotia water unless measured on held-out local video from a different site or date. Never quote a figure from a public benchmark (including Fishial's 93.22%) as the system's accuracy.
- No species-level claim for rare, invasive or tropical arrivals: public data hardly contains them, and BioCLIP is biased toward common taxa.
- No "replaces human review" or cost-saving figure without measured review time.
- No random-split results (leakage across frames of one video).
- Do not say tracked counts equal abundance. They are index counts, under detection and tracking error.
- Do not claim enhancement improves detection unless your own A/B shows it.

## Unreachable or unverified

Fish4Knowledge site; NOAA LFW and FathomNet counts/licences; BrackishMOT; LifeCLEF; SEAMAPD21 and AQUA20 details; CFC/DeepFish licences; Roboflow Universe (403 to curl); SUIM host; licences of SAM 2, RT-DETR, BoxMOT. Check each before reuse.
