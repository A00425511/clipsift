# Launch session notes (Thu 5 Nov 2026 morning, from Jacob)

First-hand notes from the partner sessions. Treat as spoken remarks heard by a participant: stronger than web snippets for how the partner works today, but not exact quotes or published figures. Where this file conflicts with earlier research on the partner's current practice, this file wins.

## Coastal Action (rep's remarks)
- Current process: GoPro set to record clips of about 1 hour. They have several clips to review.
- Review is manual, mainly in VLC, plus basic image processing software.
- Fish counts, for example: take a still image, then a grid-based tagging count.
- Contrast and other basic image editing have helped, but it is "far from a perfect science".
- Effort: up to about 7 person-hours to accurately assess 1 hour of video (Jacob's notes say 6-7 hours).
- Movement matters: short clips are sometimes used to identify certain animals. Example: a crab that was very hard to notice in one still showed up more easily in a short clip because it moved.
- Data is not centralized; an "in-house data centre" was mentioned.
- The Province recently released a "water something or other" (exact name unknown).
- Species at risk in certain watersheds can be available.
- Task named: counting fish and identifying species from footage.

### Deployment constraint (added later, from Jacob)
- They want to run everything locally. They have an in-house data/AI policy, not yet shared with us.
- They would start by running the solution on a local desktop PC, not large public data-centre processing.
- The unit has 32GB RAM and a basic graphics card (exact GPU unknown). Not much compute, but considered feasible for the project.
- Implication (orchestrator): production inference must run offline on that PC. No cloud AI APIs on partner footage unless their policy allows it. Colab-style cloud GPUs are at most a development aid on non-partner data, and even that needs checking against the policy.

### Development vs shipped product (update from Jacob, 5 Nov)
- Footage the team starts with or receives from Coastal Action is public access, not protected or IP-restricted.
- For early design and model training, assume no limits on AI use: all online and public tools are allowed.
- The final shipped product must still meet the local-only constraint and their data/AI policy.
- This replaces the earlier "footage stays on team machines" proposal, and supersedes the implication note above for the development phase.

## Black Cultural Centre for Nova Scotia (rep's remarks)
- In-house archive/database. Said to be set up on CollectiveAccess.
- Notes also say "nova news"; probably NovaMuse (orchestrator's reading, unconfirmed).
- Described as public: anyone can access, but you have to know what you're looking for.
- Research and archive team enters information manually.
- Records are semi-protected; they are trying not to overly push them "out".
- Still working with manual, handwritten sources, which take time to catalogue.
- Jacob could not find CollectiveAccess records for them, and found only a few items from their physical location on NovaMuse, not well linked together.

## Brainstorm notes (Jacob's ideas, BCCNS)
- Collectively integrate information from various sites.
- Monthly newsletter, automated from program interaction, upcoming events, and so on.
- Ease of onboarding new partners: integrating manual databases and non-standard record files.

## Official Coastal Action problem statement (PDF in the RBC HubHacks folder, read 5 Nov)
Team assignment confirmed by Jacob: Coastal Action. The PDF is the highest authority on what the partner asked for. It repeats the slide, and adds a Limitations section:

"Due to environmental concerns, our use of AI is heavily restricted. At this time, we would not be able to support a publicly hosted AI model. However, we may be able to support an open-source model hosted locally, once we have the hardware to implement the system and more developed guidelines around the use of AI at Coastal Action."

What this adds or changes:
- The reason for the restriction is environmental. Earlier documents assumed a data or privacy reason.
- Publicly hosted AI is ruled out at this time.
- A local model is only a possibility, it must be open source, and it depends on hardware and guidelines that don't fully exist yet.
- "Once we have the hardware" may conflict with the rep's remark about starting on a 32GB desktop. Ask whether that PC exists today.
- Header reads "Blue Coastal Action"; earlier research found Bluenose Coastal Action Foundation, operating as Coastal Action. Use "Coastal Action".
- "Key Clients/Audience" repeats the need statement, so no audience is actually named.
- The PDF says "numeration"; the slide says "enumeration".

## Team direction from Jacob (5 Nov, latest; this sets priorities)
- Don't lean on environmental impact or optics. The rep mentioned community flak after an AI-generated Instagram photo; Jacob reads the limit as partly that reaction, not deep concern. Energy and CO2 measuring is out of the plan as negligible at this scale.
- The real project: a program, app or workflow that accurately automates the current workflow and makes it faster. Tagging stills and spot counting is a basic task a local program can support.
- The harder part is model training and accuracy over time.
- Helpful if they have old videos and count data as training reference. If not, start a model from manual samples.
- Points of interest over the project: species databases; accuracy of counts and depictions from stills and videos; similar starting tasks.
- Three layers: Layer 0 no AI; Layer 1 local basic open-source AI; Layer 2 a full-capacity model as a proof of concept of what's possible, maybe not feasible under current limits. If Coastal Action expands its AI policy or in-house compute, it can scale up to Layer 2 over time.
- Priority: build a strong functional program and prototype for Layers 0, 1 and 2.

## Team (from Jacob, 5 Nov)
Five people: Jacob, Ali, Gina and Wang (Master of Business Analytics, MBAN) and Adrien (Master of Computing and Data Analytics). Individual skills not yet stated. Ali and Jacob worked on the earlier Community Navigator practice app.

## What "use of AI" means here (from Jacob, 5 Nov; latest, overrides earlier readings)
- Coastal Action's "use of AI" refers to major generative AI models (Claude, ChatGPT and similar). The concerns are data centre energy and water use, and the public optics of an environmental charity relying on those programs and massive data centres.
- Our brainstorming tangled that up with the literal meaning of AI. A small, purpose-built machine learning model running on a local device to assist a person's hours of video review is not the same as sending a company's footage to a cloud program in a mega data centre.
- Don't overly limit the MVP where these limits don't need to apply.
- This is Jacob's reading from talking with the partner. The PDF's wording fits it (it allows for "an open-source model hosted locally"), though that line still mentions hardware and guidelines, so one plain confirmation is still sensible.

## Email from Matt, Coastal Action rep (5 Nov)
- Matt sent resources and protocols through Lawrence at HubHacks, in a SharePoint folder. Jacob is downloading a demo video, the Video Analysis Protocol and subsample photos.
- Matt will ask the technician about hand count data for comparisons.
- Current PC: Ryzen 5 5500, 32GB RAM, GTX 770.
- Planned upgrade "in the near future", spec'd to host a 30-40B parameter model: ideally Ryzen 7 7700X, 32GB DDR4 RAM, RTX 3060 12GB.
- Implication: a local model is clearly on their roadmap. This supports Jacob's reading of the AI limit.

## Coastal Action draft Video Analysis Protocol (read 5 Nov)
Full summary in clipsift/docs/background/SPEC.md, Addendum 1. Source PDF is in the RBC HubHacks folder and is a draft with open comments. Main points: metric is MeanCount from 15 frames at 60 s intervals in a 15 minute window; invertebrates are counted; include only with two of four characteristics, so undercounting is preferred; blind double-count QC with 6% and 95% thresholds; results feed long-term monitoring of a living shoreline offsetting project.
Differences from earlier remarks: the rep said about 1 hour clips, the protocol says ~20 minute videos (a screenshot shows six chapter files spanning about 12:17 to 12:59); the rep described grid tagging, which the protocol doesn't mention. Confirm both with the partner.

## Subsample photos (read 5 Nov)
28 marked screenshots in "Sept 10 & 9th sub-samples". Full notes in clipsift/docs/background/SPEC.md, Addendum 2. Grid plus one dot per fish is how they count schools. Hand-placed dots and ellipses can become training labels. Recordings shown are about 36 minutes long.
