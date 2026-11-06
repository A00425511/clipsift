# P2 research: NS water release, species-at-risk data, and a site-aware species shortlist

Checked Thu 5 Nov 2026. Tags: [fetched] page or API opened; [snippet] search result only; [inference] my reasoning.

## 1. The likely provincial release (unconfirmed which one the rep meant)

| Rank | Candidate | Date | URL | Why it fits or doesn't |
|---|---|---|---|---|
| 1 | Water Resources Data Portal | Launched with the 28 May 2026 news release [fetched] | https://novascotia.ca/water-resources-data-portal/ | Best fit. Pulls groundwater, river, lake, water quality and weather data into one place, which matches "data isn't centralized". Interactive maps and charts [fetched]. |
| 2 | Sustainable Communities Challenge Fund, water-shortage round (about $6.3M) | Release 28 May 2026; closes 23 Jul 2026 [fetched] | https://news.novascotia.ca/en/2026/05/28/new-supports-help-communities-adapt-drought-conditions | Funding, not data. Launched the portal in the same release. Could be what the rep meant by "released". |
| 3 | 1:10,000 Tertiary and Secondary Watershed datasets | Secondary record modified 14 Oct 2026 [fetched API] | https://ouvert.canada.ca/data/dataset/ae6e6074-4321-09ee-cec1-a7d111de95bc | An open dataset, not a release. Good watershed layer for the tool. |
| 4 | Nova Scotia Water Conditions Report 2025 | Dated 15 Apr 2026 [snippet] | https://novascotia.ca/drought-and-water-shortages/docs/water-conditions-report-2025.pdf | A report on 2025 conditions. Not a data product. |
| 5 | Water for Life strategy | Undated, older [snippet] | https://novascotia.ca/nse/water.strategy/docs/WaterStrategy_Watersheds.of.Nova.Scotia.pdf | Probably not the "new" item. |

I did not find a 2026 provincial water strategy. A search of news.novascotia.ca turned up no watershed-named release. I did not confirm the portal's launch date beyond the release's wording.

## 2. Sources for species at risk and fish by watershed

| Source | What it gives | Format | Licence | Key needed? | Test result |
|---|---|---|---|---|---|
| DFO / Species at Risk Public Registry | Legal status (SARA, COSEWIC) by species | Web pages | Not checked | No | Both pages returned 200 [fetched]. Status list needs scraping or manual entry. |
| ACCDC (Atlantic Canada Conservation Data Centre) | Rare and at-risk records, including by watershed | Web, data request | Records re-published on GBIF as CC BY 4.0 [fetched API] | Not checked | accdc.ca did not connect (three attempts). Sensitive-location masking: [inference] ACCDC usually generalises locations, not verified. Check its policy before using. |
| NS watersheds (ouvert.canada.ca, 1:10,000) | Tertiary and secondary watershed polygons | CSV, GeoJSON [fetched API] | Open Government Licence, NS [fetched] | No | package_show returned 200. Use this for the watershed join. |
| data.novascotia.ca (Socrata) | Provincial layers, e.g. water features | JSON, GeoJSON, CSV | Open data (licence not checked) | No | /resource/fpca-jrmt.json returned 200 with geometry [fetched]. The catalog search returned non-NS results, so I did not find an NS watershed set that way. |
| GBIF occurrences | Species records by province | JSON API | Per record (CC BY, CC0, or CC BY-NC) [fetched] | No | Salmo salar in Nova Scotia: 287 records [fetched API]. Mostly citizen science; sampling is uneven. |
| OBIS | Marine occurrence records | JSON API v3 | Per dataset | No | Returned 200, about 14.9M records globally [fetched]. Marine only. |
| open.canada.ca (CKAN) | Dataset catalogue | CKAN API | OGL-Canada | No | package_search returned 200. The species-at-risk query gave 78 hits, mostly unrelated; the watershed query gave 1,824. Needs filtering. |
| Atlantic DataStream | Water data hub (Atlantic) | Web | Not checked | Not checked | Homepage returned 200. No API tested. |

## 3. A site-aware species shortlist

Flow: the user picks a survey site (lat/long or a map point). The tool finds the tertiary watershed (ouvert layer), then pulls GBIF and OBIS records and ACCDC rare-species records within that polygon, with a buffer to allow for estuary mixing. The output is a ranked shortlist with three tiers:

1. Recorded in this watershed.
2. Recorded nearby (adjacent watershed).
3. Warm-water or invasive watch list, with no local record. These are shown as "unexpected, review", never removed.

Each species with a SARA or COSEWIC status gets a flag. Every row shows its record count and last-recorded year.

**What could go wrong**
- **Out-of-range species are the target.** The partner's worry is tropical and invasive species arriving. A filter that drops species with no local record would hide exactly those. Tier 3 has to exist, and the UI must say that absence is not evidence of absence.
- **Sparse and biased data.** Records cluster near roads, harbours and wharves. A river with no records may be unsampled, not fish-free.
- **Old records.** Shortlist ranking can rest on decades-old sightings. Show the year.
- **Boundary errors.** Watershed polygons do not match tidal, estuary or turbidity zones. Marine (OBIS) and freshwater records need different buffers.
- **Sensitive locations.** ACCDC data may be generalised or withheld. The tool must not imply precision it lacks.
- **Licence limits.** GBIF records vary by licence (some CC BY-NC). Check each before any public use.
- **Legal flags, not clearances.** A SARA flag does not make a survey safe. SARA s. 32 covers killing, harming or capturing listed species, so the tool should not assume handling is allowed.

## Summary for the orchestrator (under 150 words)

The rep's "water something" most likely means the Water Resources Data Portal, launched with the 28 May 2026 news release. It pulls groundwater, river, lake, water quality and weather data together. This is unconfirmed. The open-data endpoints work without a key: NS watersheds (OGL-NS), GBIF, OBIS and CKAN. ACCDC's own site did not connect, so its access limits remain unverified. The shortlist should keep out-of-range species visible as a separate tier, since they are the ones the partner most wants to catch.

## Claims most worth independent checking
1. Portal launch date and name: https://news.novascotia.ca/en/2026/05/28/new-supports-help-communities-adapt-drought-conditions
2. Portal contents and "not definitive" caveat: https://novascotia.ca/water-resources-data-portal/
3. Watershed dataset licence and formats: https://ouvert.canada.ca/data/dataset/ae6e6074-4321-09ee-cec1-a7d111de95bc
4. ACCDC rare-species dataset on GBIF, CC BY 4.0: https://api.gbif.org/v1/dataset?q=atlantic%20canada%20conservation%20data%20centre
5. ACCDC sensitive-location policy (not checked): https://accdc.ca/

## Failed to reach
- accdc.ca (no connection, three attempts).
- Licences for DFO registry, Atlantic DataStream and data.novascotia.ca.
- Portal download formats and API (not stated on the page).
