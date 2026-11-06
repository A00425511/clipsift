# Prior HubHacks work: what carries over to 2026

Read-only audit. No existing files were changed.

## 1. Community Navigator repo: what exists and what to reuse

- **Stack:** plain HTML, CSS and vanilla JS. No framework, build step, server, database or CDN (checked the three HTML pages for external URLs). Python prep uses pandas, numpy, scipy and requests, with no requirements file (install line is in `docs/GAP_FINDER.md`). Git: `main` is pushed; `gap-finder` exists locally only.
- **Deployment:** live on Cloudflare Pages (`community-navigator-hubhacks.pages.dev`, per `brief.html`). The README says "Use my location" needs GitHub Pages. Not tested.
- **Offline:** all data is precomputed into `js/gap_data.js` (about 2 MB) and `js/street_data.js`. The map is SVG with no tiles. The app runs from a double-clicked `index.html` except "Use my location". An offline zip sits in the RBC HubHacks folder.
- **Features:** Find Food (address, tap or location, plus day and time; lists open, reachable programs, otherwise the next opening). Partner Insights (gap map with three layers, neighbourhood drill-down, top-gaps table, two pilot options, cost calculator). A synthetic dashboard labelled "Next phase". A 2-minute guided tour. A judge-prep page.
- **Reuse for Problem 1 (search hub):** `js/services.js` (10-category resident schema, a seed for a common metadata model); the precompute-then-look-up pattern; the offline SVG map; `build_street_data.py` for address search; `tour.js` as a backup demo. The "index, don't copy, label the source" stance matches the brief. From the HRM scan, the African Nova Scotian Communities boundaries and Building Symbols (libraries, community centres) could seed Nova Scotia location views. HRM-only data is a narrow base for a national hub.
- **Reuse for Problem 2 (fish video review):** no computer vision exists in the repo. Transferable: `config.py` as one assumptions file, a "where every number comes from" table, a known-limits list, single-file offline delivery, and running the heavy model once and shipping results.

## 2. Pitch and judge-prep lessons (any problem)

- Open with one sentence that names the gap and the fix (the PITCH_PLAN one-liner is the model).
- Put a source table on screen or in the deck. Label every estimate as a placeholder.
- Name the limits before a judge does. Keep Q&A answers to one sentence, with an "if pushed" fallback.
- Rehearse one fixed demo path. Keep a recorded tour as the offline backup.
- Check contested statistics before reuse. The pitch uses 26.2% food insecurity for NS (2024). The Food Insecurity data sheet in Prep Info gives 7.3% for NS, which appears to be a narrower measure (missing meals). Pick one measure and name it.

## 3. Team-role framework (Session 1) and AI guidance

- **Five work areas,** each with one owner and a backup: Business (research, finance), Product (planning, prototype), Design and media (visuals, video), Validation (testing, checks), Pitch and delivery (story, coordination). One person can cover several areas.
- **Handoffs** name the current file, what was checked, what is still uncertain and the next action.
- **AI guidance to keep:**
  - Match the tool to the task, and test the output rather than the preview: does it open on the venue computer, offline, logged out?
  - Ask before choosing a tool: can we edit the result, does a viewer need an account, does it work offline?
  - A good brief (goal, audience, inputs, output, constraints, acceptance test) carries most of the work.
  - Review notes need a timestamp, the visible problem and acceptable fixes. In the example, an automated check covered only still frames, so a person had to watch the motion.
  - Keep passwords and keys out of the team folder. Budget is illustrative (US$40 per team in the deck).

## 4. Submission and logistics

**Known** (kickoff deck, shared brief, faculty sheet):
- Launch Thu 5 Nov, in person, downtown Halifax. Build Fri to Sun, virtual. Submission 11:59 pm AST Sun 8 Nov. Presentations Mon 9 Nov, in person at the RBC Halifax Innovation Hub, Bedford.
- Mentors give two virtual meetings, with more by arrangement.
- 2025 format: up to 10 minutes presenting and 5 minutes Q&A, panels of up to 5 teams. The 2025 rubric has five criteria scored 0 to 3 (15 total).

**Unknown:**
- Submission format (files, repo link, deck length, video requirement).
- Whether the 2026 rubric and timing match 2025.
- What each community partner expects.
- Source conflicts: mentors are "40+" in the kickoff deck and "50+" in the faculty sheet.

## 5. Team composition

- **Ali:** built the Community Navigator prototype. A transcript calls the repo "set up by Ali for our team's RBC hubhacks." The pitch plan gives Ali the merge and deploy task.
- **Jacob:** built the Food Gap Finder data pipeline and the Partner Insights pages. The shared brief calls him an MBAN student. One transcript reads as if he coordinates the MBAN groups, so confirm.
- **Unassigned in the pitch plan:** data checker, business/MBAN, presenter, plus the everyone role for mock Q&A.
- **2026 members and skills:** not found in any transcript or document. Today's session refers only to "our group."
