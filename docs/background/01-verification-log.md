# Verification log (orchestrator's independent checks, 5 Nov 2026)

Checked directly against the live source, separately from the agents that made the claim.

## Confirmed
| Claim | Result |
|---|---|
| NS Province $1.2M over two years to BCCNS, including a digital repository (Feb 2024) | Confirmed on news.novascotia.ca |
| Dal community dialogue; "a future African Nova Scotian Community Archive" is still a conversation | Confirmed on dal.ca (article dated 16 Jun 2026) |
| NSCC Team 2 won 2025 with FoodSafe NS, $2,500; "innovation, professionalism and creativity" quote | Confirmed on nscc.ca |
| 2026 prizes $2,500 and $1,000, Early Talent interviews | Confirmed on cbu.ca |
| Black Loyalist collection added to Canada Memory of the World Register | Confirmed on cp24.com |
| Coastal Action based in Mahone Bay; homepage has no mention of video or cameras | Confirmed for the homepage only. That does not prove they have no video work |
| Umbra: 400k+ holdings, 1,000+ institutions, 250 identical-title example, LCSH gaps, aggregation vs respect des fonds | Confirmed on items.ssrc.org |
| AIMS: 4,000 h video, about 12,000 analyst hours per year (about 3:1, Australian BRUVS) | Confirmed in the Frontiers 2022 PDF |
| Innovasea Ocean Aware "90 percent" in early trials; White Rock Dam field test | Confirmed in the May 2022 release. Company claim, early trial, partly sonar-based. Not comparable to optical video in turbid water |
| Fishial: MIT, 866 classes, 93.22% | Confirmed on GitHub. Own test set only |
| MegaFishDetector: MIT card, YOLOv5-based | Confirmed on Hugging Face |
| BioCLIP 2: MIT | Confirmed on Hugging Face |
| Piccolo et al.: scene structure explains cross-site loss more than turbidity | Confirmed in the arXiv abstract only |
| DalSpace API: 187 Africville, 80 "Black Loyalists" | Reproduced |
| data.novascotia.ca "Book of Negroes", 1783: 3,009 rows, NS Open Government Licence | Reproduced |
| Archeion OAI-PMH live | Reproduced |
| Internet Archive: 49 Africville items | Reproduced |
| Canadiana robots.txt disallows ClaudeBot, GPTBot | Reproduced. Respect this |

## Corrected in the reports
- $200M federal funding: the agent had it as undated. The article is dated 8 Jan 2026. BCCNS as venue remains snippet-only.
- VIAME licence: the agent cited a personal fork. Core is BSD-3 with some restrictive optional add-ons; DIVE is Apache-2.0.

## Still unconfirmed: check before saying aloud or depending on it
- Brackish dataset licence. CC BY 4.0 came from a search snippet. The AAU page states no licence; Roboflow and Kaggle pages did not render for scripts. Check in a browser.
- Whether MegaFishDetector weights inherit AGPL from YOLOv5.
- Current BCCNS leadership (Russell Grosse, Mervyn Broome) and Coastal Action staff.
- "50+ historic communities" count.
- Saint Mary's "Connecta" 2025 claim. Conflicts with NSCC result; likely different problem statement or panel, but that is a guess.
- Whether the 2026 rubric and format match 2025. Submission format is unknown.
- Roughly 60% of source tags across the research files are [snippet] (search result only), not opened pages. Treat those as leads.

## Review fixes to p2-concepts.md
- Motion filter now sets clips aside instead of dropping them, with a random human audit, so silent misses are measurable.
- Review-time test redesigned as a split, swapped comparison. The draft had one person review the same clips twice.
- Removed an unused input (c) from the value model; marked year-one basis.
- Labelled "412 clips, 38 with activity" as illustrative. Removed a reference to a sheet that doesn't exist.
- Dropped a question asking whether Coastal Action is the partner (already known). Added the Fishial detector to the licence flag.

## Review fixes to p1-concepts.md
- Demo bug: the persona's Africville search could not reach Archeion (0 Africville results). Step 4 now uses "Underground Railroad".
- Feasibility: Archeion's OAI feed has no keyword filter and robots.txt sets a 60 second delay (tested). Rescoped to a hand-picked set of 20 to 30 records; Internet Archive moved up to third API source.
- Added a score row for the recommended combination, which the draft recommended but didn't score (12/15, judgement).

## Note on the concept scores
Scores are agent judgement, for comparing options within one problem only. They are not predictions of what judges will award.

## Superseded by launch notes (02-launch-notes.md)
- "Coastal Action has no evident video programme": superseded. They use GoPro video and manual review. The homepage simply doesn't mention it.
- "No public BCCNS catalogue": superseded in part. BCCNS reports using CollectiveAccess and has some NovaMuse items, though Jacob could not find CollectiveAccess records.
- 3:1 analyst hours placeholder: replaced for Coastal Action by the rep's spoken figure of 6 to 7 hours per video hour (partner estimate, not measured).

## New-lead checks (5 Nov, after launch notes)
- NS Water Resources Data Portal launched with the 28 May 2026 release; portal says it is not definitive and station data may not reflect nearby conditions. Confirmed. Whether this is what the rep meant is unconfirmed.
- 1:10,000 NS Tertiary Watersheds: OGL-NS, CSV/GeoJSON/SHP, modified 14 Oct 2026. Confirmed.
- ACCDC rare-species dataset on GBIF, CC BY 4.0. Confirmed on GBIF. accdc.ca did not connect, so its sensitive-location rules are unverified.
- GoPro GPMF has accelerometer, gyro, GPS, and HERO12 has no GPS. Confirmed. GB per hour and frames per hour arithmetic confirmed. Chapter sizes are conflicting snippets.
- All local processing times are estimates, not measurements. Added two review notes: proxy downscaling may erase cryptic movement; 4K HEVC decode could take longer than estimated.
- No controlled study was found showing motion beating single-frame detection on camouflaged underwater animals. Treat the movement feature as following the partner's practice, not as proven.

## NovaMuse and CollectiveAccess checks (5 Nov)
- ANSM page: NovaMuse shows 288,000+ objects, 322,000 images (page undated). ANSM Co-op membership provides CollectiveAccess and NovaMuse. Confirmed.
- CollectiveAccess OAI-PMH provider has public_access_settings, privileged_access_settings, privileged_networks and a query restriction. Confirmed in official docs.
- CollectiveAccess web service needs login token and respects restrictions "where possible". Confirmed. "Where possible" means test it, don't assume it.
- bccns.com page sitemap shows no archive, catalogue or collections page. Confirmed by keyword filter.
- novamuse.ca shows a robot check to scripts. Not bypassed. Its terms, record fields and institution filter were not read by any script. A person browsing normally can check.
- Orchestrator inference, unconfirmed: BCCNS's CollectiveAccess may be the shared ANSM Co-op system behind NovaMuse. If so, one ANSM conversation could cover many NS museums.

## Review fixes to revised concepts
- p1: visibility must be enforced at index build time. The draft's client-side filter would have shipped "not listed" records in a public JSON file.
- p1: restored the dropped Q&A step; limited it to open-listing records.
- p2: added a team handling rule for shared footage until the policy is seen.

## Development phase rule (Jacob, 5 Nov)
Early footage confirmed by the team as public access, with no AI limits for design and training. Local-only and policy limits apply to the shipped product. The earlier team handling rule is withdrawn. This is the team's confirmation; nothing here has been seen in writing from Coastal Action.

## Official PDF vs the plan (5 Nov)
Problem wording matches the slide. The Limitations section changes the reason for the local constraint from data handling to environmental concerns, and makes local AI conditional on hardware, guidelines and an open-source model.
Withdrawn: the orchestrator's chat suggestion that using heavy cloud AI would be a good pitch angle. It suits this partner poorly.

## Energy footprint checks (5 Nov)
- Nova Scotia Power table: 527.9 (2025), 502.3 (2024), 450.6 (2023). Confirmed; based on sales, includes imports. Unit assumed g/kWh from the agent's report.
- Luccioni et al.: per 1,000 inferences, object detection 0.038 kWh, image classification 0.007, image generation 2.907. Confirmed. 2023 models and hardware, so these don't transfer directly to ClipSift.
- CodeCarbon fallback (TDP, threads x 4 W, 85 W) confirmed. It's an estimate on most desktops; a wall meter gives the headline number.
- Worked example arithmetic confirmed: about 11 to 99 g CO2e per video hour, on assumed wattage. Not measured.
- Coal share of 44% (2022): source did not load for checking. Do not quote.
- Whether classical image processing counts as AI under their guidelines is unknown. Ask.

## Direction change (Jacob, 5 Nov)
Footprint metering, run-summary carbon lines and the wall-meter owner are removed from the plan. research/p2-environmental-footprint.md stays as background only. The orchestrator keeps one short Q&A line because the Limitations section is in the official statement.

## Training, Layer 2, species and count checks (5 Nov)
- PushupBench: best frontier model 42.1% exact accuracy, repetition counting. Confirmed. Pushups, not fish; a warning sign only.
- FishDetector-R1: 30% lower MAE on DeepFish, sparse point labels. Confirmed in abstract. Research code.
- SAM 3: 848M parameters, CUDA GPU required, SAM 3.1 released 27 Mar 2026. Confirmed. Licence is the custom SAM License, not a standard open-source licence: acceptable for Layer 2 and development, not assumed acceptable for "open-source" Layer 1. Licence terms not fully read; read before reuse, including any terms on derived models.
- Gemini docs: about 100 tokens/s default, about 300 high, 1 fps default. Confirmed. Token prices not verified.
- WoRMS API: cod 126436, American eel 158562, black sea bass 159348. Reproduced.
- rfishbase uses parquet on S3 with duckdb. Confirmed.
- Ditria et al.: MaxN 1.5% and 7.8% higher vs experts and citizen scientists on video; F1 92.3%. Confirmed in abstract. Single setting (Queensland); don't transfer.
- Campbell et al. 2015: paper exists; the MaxN power-function and MeanCount linear claims were not visible on the page read. Treat as a lead.
- Label-count figures (300 to 1,000 frames) are the agent's inference; no published minimum found.

## Review fixes to the three-layer plan
- Demo: Layer 2 is shown as a pre-computed, labelled proof of concept. Sam no longer switches it on, since it doesn't ship.
- One labelled set serves both the benchmark and the validation protocol.
- "Current desktop" changed to "32GB desktop target".
- Q&A line reworded: no energy claim, because none was measured.

## Scope correction (Jacob, 5 Nov)
Earlier plans over-read the Limitations section by treating any learned model as restricted. Corrected reading: the concern is generative AI in large data centres. A small local task-specific model is the core of the product. Layer 1 should not be off by default.

## Hardware checks for Matt's email (5 Nov)
- Ryzen 7 7700X: AMD lists DDR5 only; Socket AM5 doesn't support DDR4. So "32GB DDR4" with a 7700X won't work. Confirmed.
- RTX 3060: NVIDIA lists 12 GB and 8 GB variants. Confirm the 12 GB version when buying.
- 30-40B model: weights alone are about 15-20 GB at 4-bit (arithmetic), more than 12 GB VRAM, so it would need offloading to system RAM and run slower. Small vision models fit comfortably.
- GTX 770: Kepler, compute capability 3.0. Current deep learning stacks are unlikely to support it [inference, not tested]. Treat the current PC as CPU-only.

## Prototype skeleton checks (5 Nov)
- 49 automated tests pass (pipeline, app, species).
- Orchestrator ran synthetic clip through pipeline, export and the review app in a browser: results load, context clip plays, dots land in the correct cells, feed the count field and save to point_labels.jsonl. No console errors.
- Not tested on real video yet. Motion thresholds flagged every segment on the synthetic clip, so expect tuning on real footage. The Layer 1 model is a non-ML stand-in until real weights are added.
- Dot extraction: per-cell counts equal the written totals in both written examples, but only in cells with written totals. Elsewhere it picks up seabed texture (for example 58 in one cell, 567 black dots in another image). Usable only with human checking.
- Red ellipses were extracted on most marked frames.

## River footage trial (5 Nov, Jacob's M4 Pro Mac; YouTube clip, English river, watermarked (c) Jack Perks Wildlife Media)
Private local trial only. Not to be published or used for training without permission.
- 1080p H.264 (about 4.5 Mbps) and 640x360 copies, 34:55 long, 15 minute window. Run time 123 s and 45 s. Mac timings, not Coastal's PC.
- Layer 1 used the motion stand-in, not a real model. Auto fish counts per point about 11 to 45 (MeanCount about 30.1 at 1080p, 28.5 at low res); tracks 14,512 and 13,251. These are noise from surface ripples and weed. Not a measure of accuracy, and the resolution comparison says nothing about fish detection yet.
- Motion filter marked all 900 s active; nothing set aside. Visibility score flat at about 0.78, so it isn't discriminating. Both need work on real footage.
- Difference view visibly highlights fish in some frames, on an orchestrator spot check of four frames.
- Next: region masks (surface, fixed weed), stronger persistence filters, and a real detector.

## Team demo deploy (5 Nov)
https://clipsift-demo.svenska-tillsammans-cloud.workers.dev, Cloudflare Worker with static assets and D1 database clipsift-feedback, behind a team code. Sample data only: _fixture and synthetic_demo. Checked live: no code returns 401 for pages, files and the API; right code works; range requests return 206 after a Worker fix; video plays and seeks; feedback sent from the live form appears through tools/pull_feedback.py. Test notes removed. Team code is in clipsift/deploy/.team_key. Tested in Chromium-based pane only, not on a real iPhone.

## Demo moved to Pages (5 Nov)
Now at https://clipsift-demo.pages.dev, on classic Cloudflare Pages via --force, because newer Wrangler redirects new Pages projects into Workers. Same feedback database and team code. Checked live: all tested paths return 401 without the code; wrong code 401; right code works; range requests 206; video plays and seeks; feedback reaches D1. Old workers.dev address now only redirects here. Hash deployment URLs weren't reachable yet when tested. Not tried on a real iPhone.

## Coastal video trial (5 Nov): T1-STAT2 411.MP4
4K HEVC, 29.97 fps, 35:47, about 8.4 Mbps, GPMF telemetry; camera clock reads 2016, so its date can't be trusted. Same recording as the marked T1 STAT 2 screenshots (35:47 in the VLC bar).
- Pipeline ran end to end on real 4K footage: 324 s for a 15 minute window on Jacob's M4 Pro, using about 2,200 CPU seconds. Coastal's Ryzen 5 5500 will be slower; not measured.
- Filename parser got transect T1 but not STAT from 'T1-STAT2'. Needs a fix.
- Default window landed 1:00 to 16:00; Coastal's marked points for this video are at 14:00 and 22:00, so window choice needs confirming.
- Motion filter set aside 21 of 40 segments, so it behaves far better than on the river clip, but 29 segments flagged low visibility. Stand-in auto MeanCount was 0.13 per point.
- Frame timing matters: the dotted enhanced 22:00 image matches video time 1320.30 (correlation 0.87); the unmarked 22:00 image matches 1321.10. Fish move visibly between them, so VLC display times aren't exact enough for labels. Match frames by image.
- 103 hand dots transferred to the clean 4K frame, aligned on the seabed (ECC 0.959), dots confirmed on fish by eye in the area viewed. Saved in clipsift/labels/verified/.
- First baseline: simple background subtraction, one frame: recall 0.16 to 0.44 and precision about 0.17 to 0.19 at usable thresholds. One frame only; a baseline, not a model result. Most false hits are seabed and light beams. Not good enough for schools.
- Fish are about 120 px long at 4K with faint contrast, far larger than the earlier 30 px estimate from downscaled screenshots.

## Demo with real footage (5 Nov)
Live at https://clipsift-demo.pages.dev: two 2.5 minute 1080p sections of T1-STAT2 411 (20:30 to 23:00; 13:00 to 15:30), points every 15 s for demo only, Layer 0 so no automatic counts. Jacob confirmed this footage may go in the team demo. Gate, range requests, video playback and stills checked live. Team brief republished; PDFs with the coded link are in this folder and aren't published.

## Community Fish Detector test (5 Nov)
See detector-test/RESULTS.md. Includes a correction: the simple background baseline was about chance level. Brackish licence: LILA lists CC BY-SA 4.0. Feedback: 2 notes in the database as of this check (Ali, gina).

## Label mode and detector integration (6 Nov, early)
- Live at https://clipsift-demo.pages.dev/label: 100 frames from T1-STAT2 411, every 20 s from 1:00 to 34:00, blind double labelling, shared in D1. Checked live through the API and the real page; test rows removed.
- Community Fish Detector is the default Layer 1 backend (Nano, 512 tiles, candidates at 0.05). Reproduced 73 boxes, recall 0.45, precision 0.63 through the integrated code.
- Candidates at 0.05 give about 50 boxes on a frame that looks empty (pole, seabed, noise), so the suggested count uses 0.1. An empty-looking frame still gets about 10. A movement check is logged for testing.
- Timings on the M4 Pro: 711 s for a 15 minute window with segment detection. Mac CPU only: Nano about 6.4 s per frame, Medium with CLAHE about 17.8 s. Not Coastal's PC.
- Demo run coastal_school_model shows suggested counts of 24 to 114 per point; these are untrained suggestions, not validated.
