# P2 comparables: automated fish video monitoring (Coastal Action)

Tags: [fetched] opened the page; [snippet] search result only; [inference] my reasoning; [unverified] could not confirm. Research done 5 Nov 2026. No sign-ups or downloads.

## 1. Landscape table

| Tool | What it does | Users | Cost / licence | Mode | Input | Accuracy claim (source) | Small-NGO relevance |
|---|---|---|---|---|---|---|---|
| VIAME + DIVE (Kitware, NOAA-funded) | Fish detect/classify/track, plus web annotator with model training | Fisheries scientists | VIAME core BSD-3, some optional add-ons more restrictive (LICENSE.txt in VIAME/VIAME, checked by orchestrator); DIVE annotator repo Kitware/dive is Apache-2.0 (GitHub API, checked); web app at viame.kitware.com [snippet] | Cloud web, desktop, self-host | Optical video, stereo | NOAA says AI video surveys raise efficiency; no single number I verified. https://www.fisheries.noaa.gov/feature-story/increasing-efficiency-video-surveys-artificial-intelligence [snippet] | Highest. Free, proven, but generic and not tuned to NS turbid water. Most teams could use it as the backbone. |
| CoralNet (UCSD) | Web point-count annotation of benthic images; trains a classifier from your labels | Reef/benthic ecologists | Free, open source [fetched] https://coralnet.ucsd.edu/about/ | Cloud | Still images | None on page. Export formats not described. | Medium. Still images and benthos, not fish video. Pattern (annotate a few, auto-label the rest) is worth copying. |
| ReefCloud (AIMS) | Reef image analysis | Reef managers | [unverified] | Cloud | Images | [unverified] | Low. Not reached. |
| Fishial.ai | General fish ID model, public code | Anglers, aquarium, researchers | Free portal; API and terms [unverified] | Cloud, mobile | Still photos | No independent figures found. 2022 hobbyist review called it "a total failure". https://divemagazine.com/scuba-diving-news/fishial-ai-artificial-intelligence-fish-id [snippet] | Low-medium. Photo-based, trained mostly on clear images. A hecklable weak baseline for turbid water. |
| Ocean Aware / Innovasea tagless detection (Dartmouth NS; DeepSense, NS Power) | Real-time count and species classify, sonar plus optical plus AI | Hydro dams, wind and tidal, aquaculture | Commercial; price not public | Edge at site, plus Fathom software | Imaging sonar and optical | "90 percent" early trial; tested at White Rock dam, Gaspereau River. https://www.innovasea.com/wp-content/uploads/2026/01/Innovsea-PR-Tagless-Fish-Detection-5-11.pdf [snippet, 2022 release]. CBC noted optical is limited in the open ocean. | Most local comparable, but enterprise-priced. Shows demand and that the NS problem is real. |
| Echofilter (DeepSense, Dalhousie; FORCE) | Cleans echosounder data (removes bubbles/seabed); human checks output | FORCE technologists | Not stated | Desktop/UI | Echosounder | No accuracy given; saves "more than half" of the 70-80 hrs per 24 hrs of data. https://fundyforce.ca/news-and-updates/2021-03-26/ai-software-developed-in-n-s-provides-glimpse-into-wild-and-murky-bay-of-fundy-cbc-news [fetched] | High as a model: AI proposes, human verifies, in murky Fundy water. Sonar, not video. |
| Dalhousie/Innovasea Mitacs project | Multi-model fish detection near infrastructure (CNN, optical flow + YOLO classifier) on DIDSON sonar | Industry | Research | Research | Sonar | Not stated. https://www.mitacs.ca/our-projects/integrating-multiple-deep-learning-models-to-track-and-classify-at-risk-fish-species-near-commercial-infrastructure/ [fetched] | Shows academic work uses YOLO plus motion detection. Potential mentor source. |
| Salmon Vision (Wild Salmon Center, SFU, BC First Nations) | Counts and IDs salmon at weirs from video | Stewardship groups | Not found | Edge + cloud [inference] | Optical | About 90% coho, 80% sockeye (CBC); >95% at two weirs (WSC). Figures differ by what was measured. https://www.cbc.ca/1.7007573 ; https://wildsalmoncenter.org/2022/12/14/how-were-fixing-a-key-data-gap-for-fisheries-managers/ [snippet] | High as a story: community-led, small team, human-in-loop. Fixed weir camera, easier than NS tidal sites. |
| Riverwatcher (Vaki, Biomark) | Infrared fish counter in a channel | River operators | Hardware; one 2016 Scottish study put capital near £95k (vendor-cited) [snippet] | Edge | Infrared silhouette | Vendor >98%; independent Big Qualicum test >95% below 500 fish/hr, 76% above 1,500 fish/hr; turbidity affected counts in NSW. https://www.riverwatcher.is/riverwatcher-scores-high/ [snippet] | Shows incumbent's weakness (crowding, turbidity). Not video, not for open habitat. |
| EventMeasure + GlobalArchive (BRUVS) | Manual annotation of baited video, and a repository with standard tables | Marine researchers, Australia-led | EventMeasure is paid software [inference]; GlobalArchive is a data portal | Desktop plus cloud | Optical | n/a (manual) | High for data design. Some GlobalArchive datasets are published to OBIS and GBIF with WoRMS-matched taxa. https://obis.org/dataset/12f19598-cd7a-4b6e-a26a-633a338606e2 [snippet] |
| Ocean Networks Canada SeaTube / Digital Fishers | Web video annotation with WoRMS taxonomy; volunteers count live feeds | Scientists, public | Public data portal [inference] | Cloud | Optical, deep sea | Sablefish study: trained humans beat the algorithm; all groups close to the expert. https://archimer.ifremer.fr/doc/00369/47978/ [snippet] | Medium. Good UX reference; Pacific, deep, clear water. |
| FishSense (UCSD) | Low-cost handheld depth camera for fish length | Reef researchers | Student/academic, open pieces | Edge (Raspberry Pi) | Optical + depth | Not verified. https://e4e.ucsd.edu/fishsense [snippet] | Low for ID; interesting for length. |
| Google X Tidal / Aquabyte | Camera tracking of farmed fish (Tidal); similar for Aquabyte [inference] | Salmon farms | Commercial/internal | Edge + cloud | Optical, pens | Not found. https://www.irishtimes.com/business/technology/finding-nemo-google-parent-invents-fish-recognition-system-1.4190189 [snippet] | Low. Aquaculture, not wild habitat. Aquabyte page not reached. |
| Mystic River herring (MyRWA, Zooniverse, MIT/Sea Grant) | Motion-triggered fish-ladder video; volunteers count clips; later deep learning | Watershed NGO, volunteers | Volunteer-run | Cloud | Optical | Coonamessett study counted 42,510 herring, matching human estimates. https://news.mit.edu/index%2Ephp/2026/augmenting-citizen-science-computer-vision-fish-monitoring-0325 [snippet] | Highest NGO analogue. Same pattern: motion clips, human validation, AI later. |
| Spyfish Aotearoa (Zooniverse, NZ) | Volunteers classify fish in BRUV clips | NZ DOC, public | Free | Cloud | Optical | n/a https://zooniverse.org/projects/victorav/spyfish-aotearoa/about/faq [snippet] | Medium. Confirms clip-level review works. |
| iNaturalist | Photo ID with community validation | Public | Free | Cloud | Photos | Not checked | Low for video; possible source of NS fish photos [inference]. |

Not reached or not found: Acadia/FORCE optical work (FORCE uses echosounders and tagging [snippet]), Ocean Sonics, COVE, NSCC, Ocean Tracking Network, Aquabyte, ReefCloud, Fish Track. Treat them as unknown.

Coastal Action itself: South Shore NGO, Mahone Bay, teams include Species at Risk, Watersheds and Coastal & Marine; I saw no mention of fish video on its homepage. https://coastalaction.org [fetched]

## 2. The gap

[inference] from the above:
- Free tools (VIAME/DIVE, CoralNet) are generic and need ML skill to train and host. Commercial ones (Innovasea, Riverwatcher, Tidal) are fixed-site and priced for utilities.
- Nothing seen is tuned to NS conditions: tidal turbidity, bubbles, kelp and sediment clutter, and a species list shifting with climate.
- The costliest step for a small NGO is human review of hours of mostly empty footage. Echofilter and the Mystic River project both converge on the same pattern: AI triages, a person confirms.
- Missing: an "open-set" answer to unexpected species (flag as unknown rather than force a wrong label), a living regional species list, and a one-click export that matches what funders and DFO ask for.

## 3. User workflow study (field technician)

[inference] unless noted.
1. Upload: drag a folder of clips (SD card dump) with site, date, tide stage, camera ID. Keep metadata entry to a few fields; prefill from file timestamps.
2. Pre-filter: motion/activity detection drops empty clips. Show "412 clips, 38 with activity".
3. Review: a queue of candidate detections as thumbnails with a box, species guess, confidence, and a clip scrub bar. Sort by lowest confidence first.
4. Correct: one-key accept, relabel from a picklist of NS species, "unknown fish", "not a fish" (bubble, kelp), merge duplicates of the same fish across frames.
5. Quality flags: visibility rating per clip so counts can be read against conditions.
6. Export: per-survey summary and raw detections.

Outputs funders or DFO may want [inference, not verified with DFO; confirm with mentors]:
- Species counts per survey and per site/date, with method and visibility notes, and the share reviewed by a human.
- CSV with a clear column dictionary.
- Darwin Core occurrence file (occurrenceID, scientificName, scientificNameID as WoRMS LSID, eventDate, decimalLatitude/Longitude, individualCount, basisOfRecord = MachineObservation or HumanObservation, identificationVerificationStatus, samplingProtocol, recordedBy), plus an event table, ready for OBIS/GBIF. Precedent: GlobalArchive BRUVS datasets reached OBIS [snippet].
- A short PDF summary for a board or funder. Note max-N (highest simultaneous count) is a common convention in video surveys [inference] to avoid double-counting; worth offering.

## 4. Possible next-step partners (all UNCONFIRMED; none contacted, none verified to want involvement)
- DeepSense / Dalhousie (Echofilter, Mitacs fish-sonar work) [fetched above]
- Innovasea, Dartmouth (Ocean Aware) [snippet]
- FORCE, Halifax/Parrsboro area [snippet]
- Acadia University (ACER) [snippet]
- Ocean Supercluster (funded Ocean Aware) [snippet]
- DFO Maritimes; OBIS Canada [inference, no page opened]
- COVE, Ocean Sonics, NSCC, Mi'kmaw Conservation Group (named in a FORCE report [snippet]): relevance unverified.

## 5. Feature-pattern table (2.5-day POC)

| Pattern | Who does it | Copy in 2.5 days? | Why |
|---|---|---|---|
| Motion/activity pre-filter to skip empty footage | MyRWA motion camera; Echofilter-style triage | Yes | Cheap (frame differencing), directly cuts staff cost, easy to demo with numbers. |
| Human-in-the-loop review queue sorted by confidence | Echofilter, Salmon Vision, VIAME/DIVE | Yes | Core of the story; mostly UI work. |
| Pretrained detector (YOLO etc.) on a public dataset | Nearly everyone | Yes, but not as the pitch | Needed baseline; everyone has it. |
| Unknown / "not a fish" class and abstain threshold | Rare | Yes | Answers the invasive/unexpected species and bubble/kelp problems directly. |
| Darwin Core + WoRMS export | GlobalArchive/OBIS datasets | Yes | Small, concrete, and shows funder awareness. |
| Active learning (corrections retrain model) | CoralNet, DIVE | Partial | Fake it with logged corrections and a retrain button mock; real retrain risks the time budget. |
| Visibility/turbidity quality score per clip | Almost none seen | Yes | Simple image metrics (contrast, blur); explains confidence and survey reliability. |
| Sonar fusion | Innovasea, Dalhousie | No | No data or hardware in 2.5 days. |
| Real-time edge counting | Innovasea, Riverwatcher | No | Hardware and field tests. |
| Stereo length measurement | FishSense, VIAME | No | Needs calibrated rigs. |
| Crowd volunteer review | Zooniverse projects | No | Mention as a roadmap item only. |

## 6. Five ways to stand out from teams all doing YOLO on a public dataset

1. Lead with the workflow, not the model: show hours of footage reduced to a short review queue, with the time-saved number from your own demo.
2. Build for NS water: simulate or find turbid, bubbly footage, and report accuracy by visibility band, not one headline number. Be honest where it fails.
3. Open-set handling: an "unfamiliar fish" flag plus a regional watchlist (tropical vagrants, invasives) that Coastal Action can edit without code, tackling the outdated species list.
4. Funder-ready output: one click to a Darwin Core file and a per-survey summary, citing the OBIS/GlobalArchive precedent.
5. Cost realism: cheap hardware assumptions (GoPro-class camera, laptop, free tools), a total cost-of-ownership comparison against Riverwatcher/Innovasea-class systems, and a clear note on what you did not validate. Judges reward feasibility and honest limits.

## 7. Caveats
- Most sources are 2020-2023; the Innovasea and Salmon Vision status in 2026 is unknown.
- Accuracy numbers come from press and vendor material and measure different things; do not compare them directly.
- I did not find Coastal Action's current video methods; ask at the Fri 2:00pm mentor meeting what footage, camera, and species list they have.
