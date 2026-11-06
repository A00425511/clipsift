# P2 (Coastal Action): leads for training/test footage

Researched Fri 6 Nov 2026. Nothing downloaded. Tags: [search] = seen in a web-search or YouTube-search result only, not opened or watched; [ours] = measured on files in this folder. Licences were NOT checked unless stated. Per the 5 Nov note, development use of public/copyrighted footage is allowed; the shipped product must stay local.

## What our references look like [ours]
| File | Spec | Notes |
|---|---|---|
| Coastal Footage/T1-STAT2 411.MP4 | 4K HEVC, 29.97 fps, 35.8 min, 8.4 Mbps | Fixed camera on a transect line, near-zero visibility (grey haze, white pipe/line, silt bottom). The target domain. |
| Training Videos/30 mins+ of a English River (Jack Perks) | 1080p, 25 fps, 34.9 min | Fixed, green, moderate clarity, many small fish. Much clearer than Coastal's. |
| Brackish (Community Fish Detection) | ~10 s AVI clips, 5 folders (crab, fish-big, fish-school, fish-small-shrimp, jellyfish), 178 MB | Short clips, fixed harbour camera. Good for fine-tuning start, bad for long-clip behaviour (drift, tracking over minutes). |

The gap to fill: **long (20+ min), fixed camera, turbid/low-contrast, cold temperate water, crabs + small fish + the odd larger fish.**

## Tier 1: closest to the brief (Nova Scotia / Atlantic). Mostly need a contact, not a download
| Lead | Why it fits | Access |
|---|---|---|
| **Innovasea + Nova Scotia Power, White Rock fishway (Gaspereau River)**. Optical cameras on the fish ladder and bypass ran spring 2022 and into fall; ~918k fish counted; validated against manual counts of recorded video [search: [CBC](https://www.cbc.ca/news/canada/nova-scotia/ai-fish-counting-prototype-at-nsp-hydro-dam-1.6562508), [Water Power Mag](https://www.waterpowermagazine.com/analysis/tagless-technology-for-fish-tracking-10676132)] | Fixed camera, NS fish, hours of video with human counts to score against. Not turbid-sediment like ours, but the same species mix as the partner cares about (gaspereau, salmon). | Not public. Ask organisers whether Coastal Action or Innovasea can share a sample. Longshot, highest value. |
| **DFO Gaspereau alewife camera counts 2003-06** (same fishway; hand counts fill camera outages) [search: [DFO PDF](https://waves-vagues.dfo-mpo.gc.ca/library-bibliotheque/109235.pdf)] | Evidence that archived video exists. | DFO/Acadia (ACER) hold it, if at all. |
| **FORCE/Dalhousie cabled subsea platform, Minas Passage** (ADCP + live-stream camera + hydrophones; data shared via CIOOS) [search: [FORCE](https://fundyforce.ca/document-collection/marine-fish-monitoring-at-the-tidal-energy-demonstration-site-minas-passage)] | Local, fixed, extremely turbid. Closest water to our footage. | Unconfirmed whether video is archived. Check fundyforce.ca and the CIOOS Atlantic catalogue (Coastal Action already publishes there). Reports say video is hard to use in those currents, so expect poor footage. |
| **Ocean Networks Canada Holyrood Bay (NL) observatory**, SubC time-lapse camera; Oceans 3.0 API (`onc` Python package) lists and downloads archived camera files with a free-account token [search: [Holyrood](https://theshoreline.ca/2021/03/25/holyroods-seafloor-observatory-will-give-public-a-look-at-life-underwater/), [onc client](https://pypi.org/p/onc)] | The only Atlantic cabled fixed camera I found with a download route. Also ONC Pacific fixed cams. | Public per ONC's data policy [search, terms text not read]. Cadence is short bursts (5 min per hour on one camera), not continuous. Check terms. |
| **DFO Lower Bay of Fundy drift-camera dataset**, 150 transects, HD + periodic 4K, 2016-17 [search: [open.canada.ca](https://open.canada.ca/data/en/dataset/e736c0f0-b19e-4842-903d-28bfc756d48a)] and **Quoddy URCHIN video transects** [search: [Mendeley](https://data.mendeley.com/datasets/gf3nj3chv2)] | Local seabed/crab/fish scenes with species annotations. | Camera moves, so weaker for static-camera training; fine as test imagery. Quoddy full videos are "on Canada's Open Data Portal." Licence not confirmed. |
| DFO Port Joli (NS) drop-camera survey [search: [report](https://publications.gc.ca/site/eng/9.836885/publication.html)], DFO eelgrass sidescan+video NB [search: [open.canada.ca](https://open.canada.ca/data/en/dataset/6454594e-c8f9-41c4-801a-db125b8a8875)] | NS eelgrass/benthic. | Moving cameras, low priority. |

## Tier 2: public datasets with fixed cameras (usable now, labels included)
| Dataset | Why | Caveat |
|---|---|---|
| **USGS Great Herring Pond, MA**: juvenile river herring (alewife), underwater camera Jun-Nov 2017, 19,498 labelled frames + 189 expert-counted frames [search: [data.gov](https://catalog-beta.data.gov/dataset/data-used-to-test-a-video-monitoring-and-computational-system-for-estimating-juvenile-fish)] | Same Atlantic species as NS gaspereau. Has expert counts, which matches our "validate against counts" plan. | Pond, not turbid estuary. |
| **EyeSea / PNNL, Wells Dam fish ladder (Columbia R.)** with bounding boxes [search: [PNNL](https://data.pnnl.gov/group/nodes/dataset/12978)] | Hours of fixed-camera video, box labels, download offered. | Pacific species, ladder window geometry. |
| **Moreton Bay BRUV, low visibility** (secchi 2-5 m), 1080p GoPro, train + ~6.5 GB test set [search: [ecosyste.ms](https://science.ecosyste.ms/projects/7532)] | Explicitly turbid, GoPro, fixed rig. Best match to our visibility. | Subtropical species. |
| **Tweed River estuary (AU)**, action cams, varying tide and clarity, 4,281 images [search: [Frontiers](https://www.frontiersin.org/articles/10.3389/fmars.2021.629485)] | Estuary, murky. | Mostly one species. |
| **Puget Sound shellfish-farm GoPro**, fish and crab species, 77,739 images, on LILA BC [search: [Sci Data](https://www.nature.com/articles/s41597-023-02557-6)] | Has crabs (our hard case) in cold temperate water. | Mostly stills sampled from video. |
| FishTrack23 [search: [WACV](https://openaccess.thecvf.com/content/WACV2024/papers/Dawkins_FishTrack23_An_Ensemble_Underwater_Dataset_for_Multi-Object_Tracking_WACV_2024_paper.pdf)], MFT25 [search: [arXiv](https://arxiv.org/html/2507.06400v3)], SFISHTRACK [search: [Nature Sci Data](https://www.nature.com/articles/s41597-026-07786-z)] | Tracking sets, if we want MaxN/unique-track tests. | Mostly clear water. |
| UNH Great Bay eelgrass: 380 short video clips [search: [openpolar](https://openpolar.no/Record/ftuninhampshire:oai:scholars.unh.edu:thesis-2414)] | Northern New England estuary. | Short clips, unlabelled. |
| MIT Sea Grant / Woodwell "FishEye" river herring: 1,435 labelled clips from Coonamessett, Ipswich, Santuit rivers [search: [MIT](https://news.mit.edu/index%2ephp/2026/augmenting-citizen-science-computer-vision-fish-monitoring-0325)] | Very on-target (alewife, 24/7 fixed cameras, varying clarity). | I found no data release. Email the authors. |

Avoid or down-weight: DeepFish (authors note daytime, low-turbidity only), Fish4Knowledge (320x240).

## Tier 3: YouTube long-form, like the Jack Perks sample
Found by running YouTube searches in the browser pane. Titles and durations are from results; I did not watch them, so "static camera" is a guess from the title.

**Nova Scotia / Atlantic Canada**
- Underwater Halifax channel: First Chain Lake, Kearney Lake, Mouth of Sackville River (2 parts), Mouth of Shubenacadie Canal, Northwest Arm, DeWolf Park boat launch. All GoPro, 1 to 5 min each, tiny channel. Local brackish/estuary/lake scenes but short. Possibly the channel owner has longer raw files; worth a message from a team member. [search] https://www.youtube.com/results?search_query=Underwater+Halifax+GoPro
- Nova Scotia Nature in 360, "Underwater River 360, Shallow", 25:59 (https://www.youtube.com/watch?v=uIZQdujEpjs). 360 format, needs reprojection. [search]
- Jeremy of New Scotland, freshwater fish NS, 4:59 (https://www.youtube.com/watch?v=Lx0RMrdNUsI). [search]
- Cape Breton Lobster, StAnnsBanks BRUV showcase, 1:41 (https://www.youtube.com/watch?v=CsYaWvyvHhg), plus "St. Anns Bank" clips. A real NS BRUV, short. [search]
- Cape Breton Diver S2E4 Gooseberry Cove, 27:46 (https://www.youtube.com/watch?v=dQ_WJ2gL_WE). Diver, not fixed. [search]
- Newfoundland Unwritten Ep. 5, camera under 3 Atlantic salmon pools, 7:06 (https://www.youtube.com/watch?v=Bjj8KJcwE0A). [search]
- Gaspereau/alewife run clips: Quispamsis NB 1:39 (https://www.youtube.com/watch?v=XCyw2gi-Jp8), Gaspereau 360 4:35 (https://www.youtube.com/watch?v=vkgAOzA5xrs), Damariscotta Mills ASMR 10:29 (https://www.youtube.com/watch?v=8KAh0YR9USU), GMRI Alewife Run 360 2:05. Short. [search]

**Long (30 min+), fixed or near-fixed; mostly not local**
- TylersReelFishing, 1 HOUR underwater bass, St. Lawrence River / Lake Ontario, 1:05:27 (https://www.youtube.com/watch?v=XoPSF_6lSnY). Same genre as the sample, cooler Canadian water. [search]
- Country Life Relaxation, Babbling Brook "Under Brook II", trout, 1:31:30 (https://www.youtube.com/watch?v=dbjOVC4Ulmw). [search]
- Explore Oceans "Beluga Boat Underwater Cam" archived streams, 1.5 to 4 h each, murky Churchill River estuary, e.g. https://www.youtube.com/watch?v=KegS2FKK7d8 (3:50:01). Fixed cam, turbid, but mostly belugas, few fish. Good for false-positive/negative tests on murk. [search]
- Explore Bears underwater salmon cam highlights 2024, 52:26 (https://www.youtube.com/watch?v=20CS5eB93ps). Fixed, salmon, glacial water. Live stream also exists. [search]
- Fish-ladder live cams: Rocky Reach (Chelan PUD), Bowmanville (Central Lake Ontario Conservation), Umpqua. These are live streams; recording needs a screen/stream capture. [search]
- Deeply Restful Kelp Forest, 8:00:29 (https://www.youtube.com/watch?v=G7LPE2PC6Y0). Cold-water kelp, but clean and likely edited. [search]

**Crab-specific** (our known hard case): CatchCam green crab on creel pot (0:14 and 0:56), Cunners pursue green crab 1:22 (https://www.youtube.com/watch?v=_QVYP9o9Leg), Stone Living Lab (Halifax Harbour area) green crab fight 0:18. All short. [search]

## Not found
- No long, fixed, turbid, NS underwater video on YouTube or open-data portals. The closest are Innovasea/DFO (fishway) and FORCE (turbid, fixed), both behind a contact.
- The web-search tool does not index YouTube well; the results above came from YouTube's own search, so coverage is uneven. A person searching by hand will find more (suggested terms: "fish cam", "river cam hours", "Bras d'Or", "Margaree", "LaHave", "Medway", "Mersey").

## Suggested order
1. **Ask the organisers/mentor** about Innovasea/NS Power White Rock fishway clips and about CIOOS/FORCE video. Highest value, costs one question.
2. **Download now** (free, labelled): USGS Great Herring Pond, Moreton Bay BRUV, EyeSea Wells Dam. Check licence on each page first.
3. **ONC Oceans 3.0**: make a free token and pull a few hours from any fixed camera as a long-clip stress test.
4. **YouTube**: pull the 1-hour St. Lawrence video, one Explore beluga stream and the Katmai highlights as test footage; message the Underwater Halifax owner.

## Update 6 Nov: vetting results
Added after the first pass above; the older text is unchanged and is partly superseded. Facts come from the SOURCE.md files in `RBC HubHacks/Footage Sources/` and the counts made on the downloaded files.

| Lead | Result |
|---|---|
| **Puget Sound (LILA BC)** | Downloaded. Licence CDLA-Permissive-1.0 (cite Farrell et al. 2023). Full set 77,739 JPEGs (7.69 GB); 21,623-image low/medium-visibility subset extracted (49,270 boxes: fish 42,560, crab 2,827, fish_or_crab 3,429, unknown 454; plus 2,232 empty frames with no boxes). Boxes confirmed, no species labels. Frames only, no video. Fit High; magenta filter cast on about 58% of the full set. |
| **Tweed / Tallebudgera (PANGAEA)** | Downloaded. CC-BY-4.0 (cite Ditria et al. 2021). 4,280 JPGs (the article's 4,281 appears to count a CSV header), 9,429 boxes (luderick 9,304, bream 125), 138 source clips, no crabs. Fit Medium: seagrass, clearer and warmer than our target. The published split leaks one clip; our own splits are in `Footage Sources/splits`. |
| **EyeSea (PNNL)** | Not downloaded. Registration required (Globus-hosted tar). Default licence CC0 unless the dataset says otherwise. Jacob must register personally. |
| **Moreton Bay BRUV** | Not downloaded. No licence stated anywhere; data sit behind a password printed in the README (entering it breaks our no-credentials rule). Needs permission from the author. |
| **Atlantic open data** | Nothing downloadable today. DFO Lower Bay of Fundy (OGL-Canada) is tables only; Quoddy URCHIN (CC BY 4.0) has no video online yet; the CIOOS Atlantic catalogue has no video; ONC needs Jacob's account and token (licence mixed, Holyrood not confirmed). FORCE is the likeliest contact for NS fixed-camera video (judgement, nobody contacted). |

Changes to the plan: the "Download now" step in the suggested order is done for Puget Sound and Tweed, blocked for EyeSea and Moreton Bay. These public sets are for training and development checks only. The final test must remain Coastal Action's own labelled frames. Catalogue rows A2-A5, B4, B6, C1, C2 were updated to match.

**6 Nov 2026 (later), USGS Great Herring Pond (catalogue row A1):** the release is tables only. Jacob emailed Dr. Roy about the underlying files. Dr. Roy has replied and copied a PhD student on the project who may be able to help. Follow-up is in progress; nothing received yet.
