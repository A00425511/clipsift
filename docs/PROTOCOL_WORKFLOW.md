# ClipSift workflow: built from Coastal Action's protocol

This is the planning document for ClipSift. Where it differs from older notes, this one wins, and Coastal Action's protocol wins over this one. The protocol is a draft, so its numbers stay settings.

**The aim:** ClipSift is a dedicated app for doing the protocol. A person still reviews every count. The app removes the manual work around that review. Model suggestions sit on top and can improve later, and the workflow is useful without them.

## Old assumptions, now dropped

| Old assumption | What the protocol says | Change |
|---|---|---|
| Scan the whole video for movement and flag fish as they appear | Count fixed frames at equal intervals, then take the mean | Motion scan is off by default. The motion segment screens are gone |
| Show the most active points first | Points are systematic. Order carries no meaning | Points run in time order |
| Motion badges help the reviewer | Movement alone is not a count, and hints can sway a blind count | Motion badges removed from the point list |
| The output is detections and tracks | The output is MeanCount, species richness and a filled-in record per point | The report and exports centre on those |
| Species come from the sampled frames | Species are recorded while watching the whole window in real time | New Watch window step |

Movement view stays. It is a viewing aid for a person, like slowing the clip down, and it helped find camouflaged crabs.

## The protocol, step by step

| Protocol step | By hand today | ClipSift | Person still does |
|---|---|---|---|
| Find the video, match the file name to the Video ID, join split files | File browser and spreadsheet | Joins GoPro parts, reads transect and STAT from the name, asks for the Video ID | Confirms the Video ID |
| Set the window: drop the first and last minute, up to 4 more minutes if sediment persists, record the times | Scrub through in VLC, write down times | Shows frames at each minute to choose from, sets the 15 minute window, records it | Chooses when the sediment has settled |
| Visibility: 2 to 3 observers assign a category | Watch, compare with the pole, write down | Shows the frame with the pole and records each observer | Judges the visibility |
| Watch the window in real time, record all species and juveniles | VLC, notes | Cuts the window into one playable video beside the species list | Watches and identifies |
| Work out 15 timestamps, 60 s apart | By hand | Automatic | Nothing |
| Go to each timestamp, watch 5 s either side, slow to 0.25x | VLC seeking, the most tedious part | Each point opens ready: exact frame, 10 s clip, speeds, count second highlighted | Watches |
| Count fish and invertebrates, two of four characteristics | Marks on screenshots, spreadsheet | Dots feed the totals, grid totals, enhance presets, checklist warning | Decides what counts |
| Record counts, species, unknowns, visibility change, notes | Typing into Excel | Same fields, saved as you go | Enters what the marks cannot |
| MeanCount and species totals | Spreadsheet | Automatic | Nothing |
| QC: 6 to 12 random frames, blind second count, under 6%, recount, 95% agreement | Separate spreadsheet, by hand | Picks frames, hides first counts, calculates the difference, flags recounts | Counts blind |
| Screenshots and report | Screenshots and a document | Report with metrics and marked frames, as PDF and CSV | Reads and signs off |

The app's steps follow this order: Open video, choose your name, 1 Visibility, 2 Watch window, 3 Count points, 4 Quality check, 5 Report, 6 Check model flags (optional).

### How each step reads the protocol (7 Nov 2026)

| Step | What the protocol says | What the app does |
|---|---|---|
| 1 Visibility | Before analysing each video, 2 to 3 independent observers assign a category. Keep monitoring at each subsample, and record changes of 0.5 m or more, noting whether it's increasing or decreasing | One rating per person per video, hidden from others until they've rated. Step 3 asks at each point whether it got better or worse by 0.5 m |
| 2 Watch window | Watch the window in real time and record all species. Note juveniles, 1 or 0, per video | Whole window player, plus the 10 seconds at each point. Species present, juveniles and notes only. No counts |
| 3 Count points | Watch about 5 s either side, then count only the designated second. Record species counts if possible | The 10 second clip plays inside the picture, so people can check context while they mark. Without it the count would drift from the protocol, so it stays here rather than moving wholly to step 2 |
| 4 Quality check | 6 to 12 random frames, blind count by a second person, average the two, under 6% or recount, preferably by someone else, 95% agreement or re-annotate | All automated except the counting. The team chose to make the 6% and 95% figures advisory: they always show and never block. A frame is flagged only if it's also more than `qc_small_gap` (1) apart, since one fish is over 6% on any frame under 17 fish. Formulas stay provisional, see Parked |
| 6 Check model flags | Not in the protocol | Runs after everything else and never changes a count. Builds training data for a future detector |

**The automated counter.** On our test frames no detector was good enough to count unaided (`Model Comparison/reports/final-comparison.md`), so nothing is shown while counting. It's a prototype whose value depends on tagged data and training resources. A bank of Coastal's earlier tagged video and frames with counts and species would be the most useful start. Step 6 is how new labels get made.

## What the literature supports

All cited papers were read directly except where marked "via". PDFs are kept out of git in `2026 Problem Prep/research/papers/`. Most of this work is from warm-water or baited surveys, so it guides the design and does not transfer exactly to Nova Scotia.

| Finding | Source | What it means for ClipSift |
|---|---|---|
| MeanCount tracks true abundance roughly in a straight line. MaxN flattens out as abundance rises, which can hide real change | Schobernd 2014, Campbell 2015 | MeanCount suits long-term monitoring. It stays the main metric |
| Systematic sampling was more accurate than random for MeanCount, because fish presence clusters in time | Erickson 2023 | Evenly spaced points, never activity-based. This is why the motion-first design was wrong for counting |
| MeanCount holds up under subsampling better than MaxN: at 60 subsamples, 9% against 32% deviation | Erickson 2023 | Supports subsampling instead of reviewing everything |
| MeanCount can be less precise and underestimates how often a species is present, most of all for schooling species. 15 s reads were more robust than 30 s or 60 s | Campbell 2015 | Show the spread, and treat presence from the points with care. Species presence comes from the Watch window step |
| Species richness and MaxN should be recorded in real time if rare species matter | Erickson 2023 | Watch window step |
| Species accumulation began to level off at 15 minutes, at about 75% of species detected, and had not saturated by 60 minutes | Erickson 2023 | A 15 minute window suits common species. The report says "species observed in the window" |
| Removing schooling species raised accuracy and precision, since one missed school causes a huge error | Erickson 2023 | The report gives MeanCount per species, so schoolers can be viewed separately |
| Drop at least the first and last minute, and delay the start up to 4 minutes if sediment limits the view | Baker 2022 | This matches Coastal's window rule closely. Window start is a judgement made from the frames |
| Discard the disturbed period after deployment | Bradley 2019, also Erickson 2023 and Bacheler 2015 | Same point |
| Judge visibility from features on the seabed, not the pole's bands, which stay visible further than a fish would | Baker 2022 | The Visibility step says so. Coastal's protocol uses the tape, so this is a prompt only |
| Videos under 0.5 m visibility were not analysed | Baker 2022 | Coastal keeps a <0.5 m category. Whether to analyse those videos is Coastal's call |
| Three observers repeated visibility estimates with little variation | Baker 2022 | Supports recording 2 to 3 observers |
| Identify to the lowest practicable level | Baker 2022, Langlois 2020 | Species lists include genus and "unidentified" entries |
| Random review of 10%, reannotate below 95%, record who annotated and when, train annotators on known videos | Langlois 2020 | Where the protocol's QC comes from. Calibration frames are that training step. Langlois is written for baited stereo video |
| MeanCount can become density: area = pi x r squared x (field of view / 360) | Baker 2022 | A possible later feature, using the visibility radius and the camera's field of view underwater |
| Full annotation can take up to 13 hours per hour of video, and subsampling cut one study from 8 hours to 1 | Via Erickson | The value case for the workflow |

**How many frames?** Studies vary, and 15 is at the low end:

| Study | Video analysed | Frames | Note |
|---|---|---|---|
| Baker 2022 | 10 min | 10, random | Used for density |
| Coastal protocol | 15 min | 15, every 60 s | |
| Campbell 2015 | 20 min | 21, 41 or 81 | Every 60, 30 or 15 s. 15 s was the most robust |
| Schobernd 2014 | 20 min | About 40, every 30 s | |
| Bacheler 2015 | 20 min | CV fell quickly up to about 50 | 50 frames found 86% of species |
| Erickson 2023 | 60 min | 60, every 60 s | Accuracy fell sharply below 60. Error about 6% at 60 |

Erickson's "every 60 s" was on 60 minutes of video. The protocol keeps the 60 s interval on a 15 minute window, so it has a quarter of the frames. The earlier draft had 60 points, and its comment cites that result. ClipSift makes denser points easy: New video offers 15 points (protocol) or 60 points (every 15 s). The default stays with the protocol. More points mean more counting, which is where model suggestions could help later.

## Parked: clarifications for Coastal Action

Direct contact with Coastal is not the priority this weekend. ClipSift uses the stated defaults, each of them a setting, so nothing here blocks the build. These can go in one email to Matt, and they show what closer partner work would improve.

1. **Which second counts?** The main text says up to about 0.5 s either side of the point. The validation walk-through says start at 3:40 and stop at the start of 3:41. Default: 3:40 to 3:41, with 0.5 s tolerance shown either side.
2. **What window applies to long videos?** The protocol assumes about 20 minutes, but T1-STAT2 411 is 35:47 and Coastal's marked frames include 22:00, outside a 1:00 to 16:00 window. A comment allows up to 15 minutes removed from videos over 30 minutes. Default: the person picks the start, and the window runs 15 minutes.
3. **How many points?** Default: 15, with 60 offered.
4. **What is the percent difference formula?** It is missing from the PDF. Default: a placeholder.
5. **Does the 95% agreement use the same formula?**
6. **Where are the visibility videos?** Default: the first point's frame.
7. **What is the exact spreadsheet layout?** Default: column names from the protocol text.
8. **Context of 5 s or 10 s?** A comment suggests 10 s, for flounder. Default: 5 s.
9. **Are videos under 0.5 m visibility analysed?** Default: yes, as the protocol has that category.

**What direct partner work would add later:** hand-count sheets to validate against, clean originals of marked frames, their species ID knowledge, training with their staff, an export built on their real spreadsheet, and a test on their computer.

## Layers, restated

- **Layer 0, protocol workflow:** everything in the table above. This is the baseline product.
- **Layer 1, model flags:** off while counting. The detector runs only in step 6, after the counts are finished.
- **Layer 2, heavier models:** optional and contained.

The motion scan remains in the code as `motion_scan: true`, for anyone who wants it. It is no longer part of the workflow.

## References

- Bacheler NM, Shertzer KW (2015). Estimating relative abundance and species richness from video surveys of reef fishes. Fishery Bulletin 113:15-26.
- Baker R, et al. (2022). Underwater video as a tool to quantify fish density in complex coastal habitats. Diversity 14:50.
- Bradley M, Baker R, Nagelkerken I, Sheaves M (2019). Context is more important than habitat type in determining use by juvenile fish. Landscape Ecology 34:427-442.
- Campbell MD, Pollack AG, Gledhill CT, Switzer TS, DeVries DA (2015). Comparison of relative abundance indices calculated from two methods of generating video count data. Fisheries Research 170:125-133.
- Erickson KR, Bugnot AB, Figueira WF (2023). Optimising sampling of fish assemblages on intertidal reefs using remote underwater video. PeerJ. doi:10.7717/peerj.15426
- Langlois T, et al. A field and video-annotation guide for baited remote underwater stereo-video surveys of demersal fish assemblages. Field manual chapter, version 3.
- Schobernd ZH, Bacheler NM, Conn PB (2014). Examining the utility of alternative video monitoring metrics for indexing reef fish abundance. Canadian Journal of Fisheries and Aquatic Sciences 71(3).
