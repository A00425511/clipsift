# P2: species databases, count accuracy, and questions for Coastal Action

Checked Thu 5 Nov 2026. Tags: [fetched] page or API opened; [snippet] search result only; [inference] my reasoning; [tested] I ran the call and saw the result. Not repeating the partner profile or watershed/GBIF work in the two earlier P2 files.

## Part A: species databases

### A1. Source table (all calls were small read-only GETs, no keys)

| Source | Gives | Licence | API | Offline snapshot? |
|---|---|---|---|---|
| WoRMS | Accepted names, synonyms (AphiaID), multilingual common names, marine/brackish flags, some attributes | Licence not confirmed (API record's licence field was null [tested]; WoRMS is commonly CC BY [general], check); records cite FishBase | REST, no key. [tested] AphiaRecordsByName, VernacularsByAphiaID, RecordsByVernacular all 200 | Per-call JSON only. Full dump by request. Fine for ~200 species |
| FishBase / rfishbase | Common names, depth, temperature-linked traits, ecology, some images | rfishbase code CC0 [fetched DESCRIPTION]; FishBase data licence not checked | The old ropensci web API was unreachable [tested: fishbase.ropensci.org no connection]. Current rfishbase (v5.0.4) reads parquet files from S3 via duckdb [fetched README, https://github.com/ropensci/rfishbase], which is a snapshot route; I did not download | Yes, parquet, versioned |
| GBIF | Backbone taxonomy, vernacular names (EUNIS, other sources), occurrences, media with per-record licence | Per record (CC0, CC BY, CC BY-NC) | REST, no key. [tested] species/match, occurrence/search with facets | Occurrence downloads need an account (not done). Species and facet calls are scriptable |
| OBIS | Marine occurrences, taxon match to WoRMS | Per dataset | REST. [tested] taxon, occurrence by polygon, years | Yes, per query or export |
| iNaturalist | Research-grade observations, photos with per-photo licence, common names, some conservation status | Per photo: mostly CC BY-NC variants | REST, no key, rate limited. [tested] taxa, observations | Reference images only if licence allows; keep attributions |
| ITIS | Taxonomy, TSN, common names | US Government public domain [inference, not checked] | JSON service. [tested] searchByScientificName 200 | Yes, SQLite dump exists [general] |
| DFO Maritimes RV survey | Catch data and species codes | Open Government Licence Canada [tested via open.canada.ca CKAN: "Maritimes Spring Research Vessel Survey"] | CKAN package API works | Yes. Use as a "what is caught here" prior, not for images |
| SARA / COSEWIC registry | Legal status | Not checked | Registry site loads; the API URL I tried returned 502 [tested]. Not confirmed usable | Hand-curate statuses from the registry; record the date |
| Gulf of Maine / Fishes of Atlantic Canada checklists | Checklists | Not tested | Not tested | Treat as a human review source for the tier lists |
| Atlantic invasive lists | Not reached | Not tested | Not tested | Hand-curate from DFO/NS sources; I found nothing machine-readable |

Gaps: ACCDC did not connect earlier (see p2-water-sar-data.md). I did not verify FishBase image licences or any invasive checklist.

### A2. Recommended backbone and build process
**Backbone: WoRMS AphiaID**, with GBIF key, ITIS TSN, FishBase code and iNat taxon ID as cross-references. Why: all three test species matched exactly in WoRMS and GBIF [tested], WoRMS handles synonyms and marine/brackish flags, and OBIS already uses its IDs [tested]. Freshwater species (bass, pickerel, eel in rivers) are outside WoRMS scope for some taxa, so GBIF key is the fallback [inference].

Build process (a Python script, rerunnable, outputs one versioned file):
1. **Seed list**: the tiered lists from the earlier files, plus DFO survey species (OGL).
2. **Resolve names** to AphiaID via WoRMS; reject unaccepted names, keep synonyms as aliases.
3. **Aliases**: WoRMS and GBIF vernaculars, filtered to English/French; add local names by hand (gaspereau, sea trout, "cunner/perch").
4. **Distribution tier**: OBIS/GBIF counts and last year in an NS box, per species. Counts for tier 1 or 2; absent = tier 3 watch, never deleted.
5. **Traits**: FishBase parquet snapshot (depth, temperature) when available.
6. **Flags**: at-risk (SARA/COSEWIC, hand-entered with source date), invasive (hand-curated), range-expander candidate (rule: recent records north of historical range or on the watch list).
7. **Images**: iNat/GBIF media filtered at image level. Keep CC0, CC BY, CC BY-SA. CC BY-NC is a decision for the team: fine for an internal tool, not for anything redistributed. Drop all rights reserved and NC-ND. Store licence, author, URL per image.
8. **Freeze**: write `species_list_vYYYY.MM.DD.json` plus a manifest (source query dates, source versions, hash). Never edit in place; changes create a new version.

### A3. Sample record schema
```json
{
  "schema": "1.0", "list_version": "2026.11.05",
  "aphia_id": 126436, "gbif_key": 8084280, "itis_tsn": 164712,
  "scientific_name": "Gadus morhua", "authority": "Linnaeus, 1758",
  "common_names": {"en": ["Atlantic cod"], "aliases": ["codfish","scrod (juvenile)"]},
  "habitat": {"marine": true, "brackish": true, "freshwater": false},
  "ns_status": {"tier": 1, "obis_records_box": 200261, "last_year": null},
  "flags": {"at_risk": [{"body":"COSEWIC","status":"unverified","source":"<url>","checked":"2026-11-05"}],
            "invasive": false, "range_expander": false},
  "id_notes": "confusable with pollock, haddock; needs expert if <N px",
  "images": [{"url":"...","licence":"CC BY","author":"...","source":"iNaturalist","id":"..."}],
  "sources": [{"name":"WoRMS","retrieved":"2026-11-05"}]
}
```

### A4. Test on 3 species [tested 5 Nov]
| Field | Atlantic cod | American eel | Black sea bass (warm-water arrival, from the partner file's "plausible" list) |
|---|---|---|---|
| AphiaID / GBIF key | 126436 / 8084280 | 158562 / 5212956 | 159348 / 2387483 |
| WoRMS status, habitat | accepted; marine + brackish | accepted | accepted |
| English name from WoRMS | Atlantic cod | American eel | not read |
| ITIS TSN | 164712 | not read | not read |
| GBIF records, "Nova Scotia" | 103 | 330 | 1 (of 25 for Canada; the NS record is isolated) |
| OBIS records, 43-47N, 67-59W box | 200,261 | 39,228 | 10 |
| iNat research-grade in NS | 60 (1 with open licence) | 352 (21 with CC BY/CC0/CC BY-SA) | 1 (0 open) |
| Default iNat photo licence | CC BY-NC-SA | CC BY-NC | CC BY-NC-SA |
| Status flag | iNat shows IUCN Vulnerable; COSEWIC not checked | COSEWIC Threatened 2012 [snippet, partner file]; not rechecked | none; watch list |

What the test showed:
- Names and IDs resolve cleanly and cross-link. The pipeline works for these three.
- GBIF "stateProvince" counts are low and inconsistent (103 cod in NS versus 200k in OBIS), so GBIF-by-province is a weak distribution test; use polygons and OBIS for marine species [inference].
- **Open-licensed images are scarce.** Only 1 of 60 cod and 21 of 352 eel NS observations pass an open filter, and the sea bass has none locally. Plan for a thin image library, fill from GBIF (cod in Canada: 241 stills, 196 CC BY-NC, 25 CC BY, 20 CC0 [tested]), and treat Coastal Action's own labelled frames as the best reference set.
- Black sea bass has almost no NS evidence. That fits the earlier finding that warm-water strays are rare, and it means the "range-expander" flag needs a human source, not just record counts.

## Part B: stills versus video counts

Search access was limited (PMC blocked fetches; several papers seen in snippets only). Numbers below are labelled with setting. Treat all as to-verify.

### B1. Evidence
| Topic | Finding | Setting / tag |
|---|---|---|
| MaxN bias | MaxN related to true abundance as a power function, not linearly; saturates at high density; sensitive to schooling behaviour and video length | Simulations and SE US reef fish (Schobernd et al. 2014; Campbell et al. 2015 Fisheries Research 170:125-133); Stobart et al. 2015 PLoS ONE (Mediterranean). [snippet] https://sedarweb.org/documents/s41rd19-examining-the-utility-of-alternative-video-monitoring-metrics-for-indexing-reef-fish-abundance |
| MeanCount | Averages counts over many snapshots; linear in abundance, but Campbell reported lower proportion-positive and higher CV (less precise) | Same sources. [snippet] https://sedarweb.org/documents/sedar45-rd05-comparison-of-relative-abundance-indices-calculated-from-two-methods-of-generating-video-count-data |
| MaxIND | Counting distinct individuals gave 2.4x and 1.1x MaxN for two reef species; 1.4x for great barracuda | Sherman et al. 2018 (tropical reef); barracuda 2025 J Fish Biol. [snippet] |
| Imperfect detection | Both metrics are biased by detection (e.g. low visibility); neither gives absolute abundance | 2025 ASFB abstract. [snippet] https://asfb-2025.p.asnevents.com.au/days/2025-08-19/abstract/128347 |
| Frames read | Number of frames read affects count accuracy and precision; tradeoff with effort | NMFS Fishery Bulletin, SE US BRUV. [snippet only, numbers not obtained] |
| Observers | Observer bias negligible for assemblage and per-species counts, but sampling variability (detection, fish movement) often exceeded site and transect variability | Galapagos reef video transects, Bruneel et al. 2022 PLoS ONE. [fetched] https://ideas.repec.org/a/plo/pone00/0271043.html |
| Sonar contrast | Viewer agreement on individual lamprey often low | DIDSON sonar, Keefer et al. 2017. [snippet] https://complete.bioone.org/journals/Northwest-Science/volume-91/issue-1/046.091.0106/Inter-Observer-Bias-in-Fish-Classification-and-Enumeration-Using-Dual/10.3955/046.091.0106.full |
| Turbidity | ID and measurement limited above ~6 NTU in Ontario rivers; turbidity limited ID in Mid-Atlantic shoals | [snippet] https://udspace.udel.edu/handle/19716/36317 |
| Model vs human | Mask R-CNN MaxN 1.5% (video) and 7.8% (video) above experts and citizen scientists respectively; F1 about 92 | Luderick, Queensland seagrass, clear-ish estuaries, Ditria et al. [fetched] https://www.biorxiv.org/content/10.1101/805796v1 |
| Model vs human, snapper | Model MaxN correlated 0.72-0.9 with manual, underestimated at high abundance; model-assisted humans reached 0.96 | Frontiers Mar Sci 2025. [snippet] |

Not found: published fatigue curves, a defensible number of stills to match a video count, or a species-ID agreement percentage. I will not invent them. Double counting: only seen as the motivation for MaxN/MaxIND; no dedicated study found.

### B2. What this means for the tool
- **Report three metrics**, not one: MaxN (comparable with the literature), MeanCount over fixed-interval stills (better linearity), and a distinct-individuals estimate where tracking allows. Always show the frame/time of MaxN so a human can check it.
- **Stills interval**: no evidence-based number for NS. Defensible default: every 10 s for the primary count, labelled provisional, with a sensitivity check on 5 s, 10 s, 30 s using the validation clips. Choose the interval where MeanCount stops changing [inference]. Short-lived or fast fish (gaspereau, silversides) need denser sampling; rely on motion detection to add frames.
- **Uncertainty**: report a range, not a point. Use bootstrap over sampled frames for MeanCount, and a model-confidence band for ID. Add a visibility score per clip (the five-point turbidity scale from the Florida Keys presentation is a cheap option) and flag low-visibility clips as "counts are minima".
- **Honest framing**: counts are relative indices, not abundance. Say so on screen.

### B3. Validation protocol (student team, by Sunday)
**Sample**: 10 clips, 5 minutes each from Coastal Action footage, mixed clear and turbid. If no footage arrives, use public footage and say so.
1. **Two or more humans** independently annotate each clip in a spreadsheet: for each fish, timestamp, species (or "unknown"), count per 10 s frame. Time each person.
2. **Human-human agreement** first: this is the ceiling. Compute per-clip count difference, MaxN agreement, and species ID agreement (percent and Cohen's kappa on the frames both marked).
3. **Consensus set**: humans reconcile disagreements, leaving a "reference" plus a list of frames that stayed contested.
4. **Run the tool** (Layer 0 stills + grid, then Layer 1 detector if ready) on the same stills.
5. **Compare tool to each human and to consensus**, using the same metrics, and report tool-vs-human next to human-vs-human.
6. **Stratify** by visibility (clear vs turbid) and by abundance (0, 1-3, 4+). Report where it breaks, especially the high-abundance underestimate seen in the snapper study.
7. **Review time**: minutes of human review per clip with and without the tool's suggestions. This is the business number.

**Good result**: the tool differs from consensus about as much as one human differs from another (inside the ceiling), and human-with-tool review is faster than annotating alone. Published reference points only for context, setting in brackets: F1 about 92 for one species [seagrass, Queensland]; correlation 0.72-0.9 unassisted and 0.96 assisted [snapper, Frontiers 2025]. For turbid NS footage, expect lower; the team should report its own number plus the human ceiling instead of chasing those.

Caveat to say out loud: 10 clips is a pilot with wide uncertainty, not proof.

## Part C: 8 questions about old footage and counts
1. What are the video files: camera model, resolution, frame rate, codec, and are the GoPro clips split into chapters (~1 hour each)?
2. How were counts recorded: spreadsheet, paper, image-software notes? Is one fish ever recorded as one row, or only totals per still?
3. Is anything time-stamped (video time of the still, wall-clock time, tide state)? Are GPS or site fields attached to each clip?
4. Which sites, dates, habitats and deployments are covered, and how many clips per site? Are fixed-mount, dropped or towed deployments mixed?
5. Were the stills and the grid overlays kept, or only the totals? What grid size was used?
6. How did you pick which still to count (random, interval, "best looking", a visible fish)?
7. How was species uncertainty logged: "unknown", "likely X", "fish sp.", or silently dropped? Who resolved disagreements?
8. Did more than one person ever count the same clip, and do you have any such pairs we can use as the human-agreement benchmark?

## Failed or weak
PMC blocked (Schobernd full text); Bacheler frame numbers not obtained (redirect); Campbell, Stobart, Sherman details are snippet-level; no fatigue or species-ID agreement figures found; DFO RV species list, Gulf of Maine checklist, invasive lists and COSEWIC API not tested; FishBase data licence not checked.
