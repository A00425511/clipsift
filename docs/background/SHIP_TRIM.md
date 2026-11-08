# What to trim before shipping ClipSift to Coastal (audit, 8 Nov 2026)

**Archived 8 Nov 2026 (1.4.2).** All of it is done (1.4.0). Open items moved to `../BACKLOG.md`.

**Status, 8 Nov 2026 (1.4.0):**
- **Done:** items 1 to 3 and 5 to 11. Feedback and Label fish are kept on the team site only. The segment screen is removed from the app, and the server still reads old runs.
- **Item 4 is kept:** the team plans to ship with the detector (`tools/package_mac.py --with-model`). Step 6 still says the detector isn't installed in a build without it.
- **Before the detector zip goes to Coastal:** settle the licence for the CFD weights.

This audit looked at the local app as packaged in `ClipSift-1.3.0-mac.zip`, for parts that were built for the team, the trials or the retired motion scan and that a Coastal user doesn't need. Nothing here has been changed yet.

- **Keep on the team site:** the team site is a separate build (`tools/build_demo.py`). It can keep the team tools, such as Feedback and Label fish.
- **Remove or hide in the shipped app:** these items should go in the local app and the package. The packaged app runs on a Coastal PC with no detector.

## Remove from the shipped app

| # | Item | Where | Why it's there | Why it can go | Suggestion |
|---|---|---|---|---|---|
| 1 | **Feedback** button and dialog | Top bar. `index.html` feedback-dlg, `app.js` openFeedback/sendFeedback, `POST /api/feedback` | Collecting feedback in the trials and on the team site | Locally it writes to `runs/feedback.jsonl` on the PC, and nobody collects that file. Coastal staff would type into a box that goes nowhere. | Hide it in the local app. Put a contact line in Help instead, such as "Problems or ideas: email ...". |
| 2 | **Label fish** link and the labelling page | Top bar under More tools. `label.html`, `label.js` (981 lines), `/label_sets/*`, `/api/labels*` | The team's blind labelling for model training data | It isn't part of Coastal's protocol, and the package ships no label sets, so it opens empty. | Drop it from the local app and the package. |
| 3 | **Segment review mode** (motion scan era) | Segment items in the point list, the "Counts and decision" panel (Confirm / Reject / Unknown / Second look, Add local name), `export_segments.csv`, `/api/runs/<id>/segments`, `/reviews`, `/grid_tags`, SEG_COLS in `app.js` | The original motion-scan workflow, now retired | Segments are only made at layer 1 or higher. The app always runs layer 0, so this can't be reached. | Remove the UI and routes. Keep `clipsift/stages` if anyone still uses the command line. |
| 4 | **Step 6 tab when no detector is installed** | Steps bar "6 Check model flags", `species_bank.html` | Checking model flags for training data | The package has no detector, so the tab only says "The fish detector isn't installed". It's a whole step that does nothing. | Hide the tab, and its mention in Help, unless `detector_ready`. The model guess tick box already hides itself this way. |

## Simplify (redundant or leftover from testing)

| # | Item | Why | Suggestion |
|---|---|---|---|
| 5 | **More tools** button | Once Label fish is gone, it only hides the brightness, contrast and saturation sliders and the grid's Rows and Columns boxes. A whole mode switch for two small things is more confusing than useful. The trial staff didn't know what it did. | Remove the toggle. Put the sliders in a small "Adjust picture" fold-out by Enhance, and the grid size in a fold-out by Grid. |
| 6 | **Bigger picture** button and V key, beside the new **Layout** menu | Both make the picture largest. It was added before the Layout menu existed. | Keep V as a quick toggle. Drop the button, or rename it "Largest picture" so it matches the menu. |
| 7 | **Classic** layout | It was only kept as a fallback. Fit to screen does the same job on large screens. | Drop it after a few people have tried Fit to screen. |
| 8 | **"Every 15 s"** in the setup dialog's Count points list | It was for the 3-minute trial clips. Custom spacing covers it now. | Keep only "Every 60 s (protocol)" and "Custom spacing". |
| 9 | **Open another video** button | It does the same as the ClipSift name at the top left: both go to the home screen. | Keep one. The label "Open another video" is the clearer of the two. |
| 10 | **Flask development-server warning** in the Terminal window | The packaged launcher shows a red "WARNING: This is a development server..." message. It's harmless for one user on one PC, but it looks alarming to staff. | Hide it in the launcher, or serve with `waitress` (pure Python, small). |
| 11 | **Windows example path** on the home screen (`E:\Fish and Fish Habitat Monitoring\...`) | This is Coastal's real drive layout, which is right on their PCs, but it reads oddly on a Mac. | Choose the example by operating system, or keep it for the Windows build only. |

## Already fine (team site only, or hidden when not needed)

- **Demo-only parts:** the demo banner, "Clear my demo counts" and DemoData only switch on for the team site.
- **Model guess** tick box: it hides itself without a detector.
- **Change window or spacing:** it's hidden on the team site and after QC.

## Keep

These are all part of Coastal's procedure or make it easier to follow:
- the timeline
- the Video picker in the top bar
- "How closely people agree" on the home screen
- Help and the tour
- Movement view
- Enhance
- Layout
- the report and CSVs

## If the trims are made

Items 1 to 4 remove about 1,200 lines of code: `label.js`, most of the segment code in `app.js`, and the label and segment routes in `server.py`. Some tests cover the segment and label routes. Remove or update those tests in the same change. Then rebuild the package with `python3 tools/package_mac.py` and add a CHANGELOG entry.
