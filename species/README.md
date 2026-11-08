# Species list

Builds `species_list.json`, the file the app reads. If the file is missing the app still works with an empty list and free text.

## What is here
- `seed_species.csv`: the hand-edited starter list (source: the P2 research files). Columns: scientific name, common name, group, kind (fish or invertebrate, which the species menus filter on), rank, three flags, status note, needs_status_check, local names (semicolon separated), ID notes, source note.
- `build_species_list.py`: looks up each name in WoRMS (AphiaID, English common names, synonyms as aliases) and GBIF (species match key), then writes the outputs.
- `species_list.json`: the live file. `species_list_vYYYY.MM.DD.json`: a dated copy. `species_manifest.json`: retrieval date, hash, counts and unresolved names.

## Rerun
    python3 species/build_species_list.py

Standard library only, no keys. It makes one request at a time with short pauses, so a full run takes a few minutes. If the network fails, the run continues: affected names stay in the list with null IDs and appear under `unresolved` in the manifest. Rerun later to fill them in. A rerun on the same day overwrites that day's dated copy.

## Edit the seed
Add or change rows in `seed_species.csv`, then rerun. Set flags to 1 or 0. Put a name in `local_names` (for example gaspereau) and it is always kept. Never delete a species because it is absent from records; mark it instead.

Generic rows (for example "Flounder, unidentified", "Crab, unidentified", "Unknown fish") exist so that records can be made at the lowest practicable level. They use a higher-level taxon name, and the `rank` field says which level. `rank` is an optional extra field beyond the base contract.

## Caveats
- Statuses need checking against current registries (Species at Risk Public Registry, COSEWIC, invasive lists). At-risk and invasive flags come only from what the research file states, with the status text in `id_notes`. Rows marked `needs_status_check` have not been verified. Range-expander rows are candidates only.
- `ns_status_tier` is `unknown` for every species until distribution data (OBIS, GBIF, DFO survey) is added.
- WoRMS licence terms need confirming before the list is redistributed. The research file found the licence field empty.
