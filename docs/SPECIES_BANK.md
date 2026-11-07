# Species bank: plan and first version

A second look for species, after counting. ClipSift pulls clear images of moving candidates into one place so a person can identify them, flag juveniles and catch invasive or unexpected species. The model never names a species. A person does.

Since 1.0.0 the app's step 6 builds a separate review set (`clipsift/verify.py`, `review_set/` in the run folder) on the same page, opened with `?set=review`. It mixes model and counter sources for training data. The V6 species bank below stays available for runs that have V6 output.

## Where it fits the protocol

Coastal's protocol asks reviewers to watch the window, record all species at the lowest practicable level, and note whether juveniles are present. That step depends on spotting a short, rare appearance in real time. The bank backs it up with images that can be paused and compared.

The bank stays outside the count:

- It opens after counting, because model hints can sway a blind count.
- It doesn't change any count, MeanCount or the watch window species list.
- Anything a person identifies here is saved and exported separately.

## How it works

1. Ali's V6 finds and tracks candidates around chosen times in the video.
2. `tools/build_species_bank.py` merges overlapping tracks of the same animal, picks the clearest view, and saves a close crop, the full frame and a 5-second clip.
3. It sets aside likely fixed objects. These stay visible under their own filter and are never deleted.
4. It raises flags that set the review order, and each flag says why.
5. A reviewer opens `/species_bank.html`, can hold the frame to play 2.5 seconds either side, then picks a species or another outcome and sets the life stage.
6. If the species is listed as invasive, at risk or a possible range expander, the page shows that status and asks for expert confirmation.
7. Decisions go to `species_bank/decisions.jsonl` in the run folder, and can be downloaded as CSV.

## What the flags mean

| Flag | Raised when | What it can't tell you |
|---|---|---|
| Likely fixed object | It repeats at several points or barely moves, and the spot looks as it normally does | A still animal that looks like the usual background could be hidden, so spot-check this filter |
| Unusual | It looks least like the other candidates in this video | Algae and debris also look unusual. It doesn't mean rare |
| Near seabed | It's low in the frame | Only a prompt to check for crabs and flatfish |
| Small in frame | It's among the smallest moving candidates | One camera gives no distance, so small can mean far away. This is not a juvenile detector |

## First test

Run on one video, T1-STAT2 411, using V6 output for 18 points. These thresholds were set by looking at that same video, so this shows the idea works. It doesn't measure accuracy.

| Measure | Result |
|---|---|
| Tracks from V6 | 124 |
| Candidates after merging repeat views of one animal | 106 |
| Left to review | 56 |
| Set aside as likely fixed objects | 50. A visual check of a near-identical earlier pass showed almost all were pipe, cable tie or a seabed hollow |
| Crab at 21:40 | 4 tracks merged into 1 candidate, 3rd in the review order |
| Crab at 24:20 | 1 candidate, 34th of 56, with no flag |

The first filter hid the 21:40 crab because it sat beside the pipe. Comparing each candidate with the normal view of that spot fixed this, and that case is now covered by a test.

## Limits

- V6's detector is trained for fish. It found both known crab moments we checked, but it isn't a crab detector, and we have no estimate of how many crabs it misses.
- Faint fish are often missed, because V6 is tuned to the clearest candidates. That suits species review, but the bank can't show what the detector never found.
- The bank only covers the times V6 ran on. Rare species outside those times won't appear until V6 runs across the whole watch window.
- Species statuses in `species/species_list.json` still need checking against current registries.
- The team demo site is static, so the bank needs the local app.

## Next steps

1. Run V6 across the whole watch window, then rebuild the bank. At about 7 seconds per 10-second stretch on CPU, a 15-minute window should take around 10 minutes.
2. Add a button that copies confirmed species into the watch window list, so nothing changes without a person choosing it.
3. Show confirmed flagged species and any juveniles in the report.
4. Handle schools: one box can cover several fish, and many fish look alike. This needs its own approach.
5. Ask Coastal which species they most want flagged, and whether photos of this quality would satisfy them.
6. Link the same animal across separate points. Merging only works within one 10-second stretch for now.
7. Use the confirmed images later as labelled training data for species identification.
