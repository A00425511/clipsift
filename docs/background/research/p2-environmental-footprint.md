# P2 Coastal Action: environmental footprint case for ClipSift (research, 5 Nov 2026)

Tags: [fetched] opened and seen; [snippet] search result only; [inference] my reasoning. Weak sourcing is flagged.

## 1. Why environmental groups restrict AI
- Main published concerns: electricity, data-centre water cooling, emissions, hardware. The IEA puts data centres at about 415 TWh in 2024 (about 1.5% of world electricity), heading to about 945 TWh by 2030 [snippet] https://www.iea.org/reports/energy-and-ai/executive-summary
- GAO (2025) says generative AI's environmental effects are unclear because firms rarely report energy and water [snippet] https://www.gao.gov/products/GAO-25-107172
- Nonprofit guidance (Blackbaud): energy first, water second; advice is to track your own use and pick smaller models [snippet] https://blog.blackbaud.com/?p=34765
- Canadian example: WWF-Canada's GenAI policy keeps humans deciding and says it is tracking Copilot Chat use to calculate and offset its footprint. That is measurement, not a ban [snippet] https://wwf.ca/genai-public-disclosure-statement/
- I found no published Canadian environmental NGO policy that bans AI outright, and none from the Suzuki Foundation, Ecojustice or CPAWS (not found, not proof they don't exist). Coastal Action's policy is stricter than the one example I found.
- [inference] These concerns are about large cloud generative models. A small local detector is a different thing, but the team has to show that, not assume it.

## 2. Measuring it
| Tool | Facts | Fit |
|---|---|---|
| CodeCarbon | MIT licence [fetched] https://github.com/mlco2/codecarbon. Measures CPU, GPU, RAM only; not display, disk, cooling. Estimates, not meter readings. | Good for per-stage logging |
| Wall plug-in meter | Measures the whole PC, including idle. No software. | Best for the headline number |
| AI Energy Score (Hugging Face) | H100 GPU energy only, relative star ratings [snippet] https://huggingface.github.io/AIEnergyScore | Use to pick a model, not to measure the PC |

CodeCarbon details [fetched] https://docs.codecarbon.io/latest/explanation/methodology/:
- Reads RAPL on Linux (AMD since kernel 5.8) and Energy Meter Interface on Windows 11 bare metal. Otherwise it estimates from CPU load and the CPU's TDP. Unknown CPU falls back to 85 W.
- The docs call the load curve "plausible defaults, not measurements". RAM is a rough per-DIMM guess. NVIDIA GPUs are read directly; no fallback otherwise.
- Offline: I could not confirm it. The docs list an `OfflineEmissionsTracker` with a country code, and bundled local data files [snippet] https://docs.codecarbon.io/parameters.html. Test it before relying on it.
- Without a GPU or RAPL access, its numbers are estimates with no stated error. An independent study found it gave occasional negative energy values against a wattmeter [snippet] https://arxiv.org/pdf/2302.00967

**Best for a weekend team:** a wall meter (about $20-30, price [inference]) on the test PC, reading idle watts then load watts. Optionally CodeCarbon for the per-stage split, labelled as an estimate. Carbontracker found GPU-only accounting underestimates total energy [snippet] https://arxiv.org/pdf/2007.03051, which supports using the wall.

## 3. Local numbers
- Nova Scotia Power system intensity: 2025 = 527.9, 2024 = 502.3, 2023 = 450.6 g CO2e/kWh [fetched] https://www.nspower.ca/clean-energy/air-emissions-reporting. This includes imports, and it is a utility figure, not ECCC.
- ECCC National Inventory Report (Annex 13 intensity table) value: not reached. Older federal sources: 660 g/kWh in 2022 [snippet] https://neb-one.gc.ca/nrg/ntgrtd/mrkt/nrgsstmprfls/ns-eng.html. Use the NSP number, cite the year, and note that it varies by year.
- Coal share of generation: 44% in 2022 (NIR-based) and 23% renewables [fetched] https://www.canada.ca/en/services/environment/weather/climatechange/climate-plan/clean-electricity/overview-nova-scotia.html. A commentary claims coal fell to 33% in Q1 2024; secondary, unverified [snippet].
- Desktop draw: no source found. [inference] Typical office desktop: 40-60 W idle, 100-150 W at full CPU load; with a modest discrete GPU, 150-250 W. Wall meter replaces these guesses.

**Formula:** kWh per video hour = (average wall watts under load / 1000) x (processing minutes / 60). kg CO2e = kWh x grid intensity (kg/kWh). Subtract idle watts if you want only the added load.

**Worked example [inference], all inputs assumed:**
| Case | Watts | Time | kWh | kg CO2e at 0.528 |
|---|---|---|---|---|
| CPU only | 100-150 | 20-75 min | 0.03-0.19 | 0.02-0.10 |
| Modest GPU | 150-250 | 10-30 min | 0.025-0.125 | 0.013-0.066 |
So roughly 10-100 g CO2e per video hour. The 20-75 minute figures come from p2-concepts.md and are estimates, not measurements.

## 4. Small models vs large ones
Luccioni, Jernite, Strubell, "Power Hungry Processing" (FAccT 2024) [fetched] https://arxiv.org/html/2311.16863v3. Energy per 1,000 inferences, A100 GPU, no batching:
| Task | kWh per 1,000 |
|---|---|
| Image classification | 0.007 |
| Object detection | 0.038 |
| Image captioning | 0.063 |
| Text generation | 0.047 |
| Image generation | 2.9 (mean) |
- [inference] Per frame, a detector costs about 38 Wh per 1,000 frames. A video hour at 2-5 fps is 7,200-18,000 frames, so about 0.27-0.7 kWh if every frame ran on an A100. This is higher than my wall-clock example. The gap shows these figures do not transfer: A100 vs a basic desktop GPU, no batching, unknown model sizes. Say both numbers exist and measure your own.
- Paper excludes training, water, embodied emissions. Its own conclusion is that generative models cost far more than task-specific ones.
- Training a small detector: I found no measured kWh figure for a small detector. Do not quote one. Log it yourself (GPU hours x watts) if you train on Colab.

## 5. The human-comparison angle
- [inference] Partly fair, mostly a stretch. A person at 6-7 hours uses a desktop plus monitor, about 50-100 W, so 0.3-0.7 kWh, 0.16-0.37 kg CO2e per video hour. ClipSift is of the same order, maybe lower. It is not "ten times greener".
- It also adds model development (training, pre-labelling with big models) that the human does not, and humans still review flagged segments, so the review time falls but does not reach zero.
- The honest claim: the run is small, measured, and comparable to or below manual review. The stronger argument is staff time, not carbon. Avoid "net-negative".

## 6. What counts as "AI"
- EU AI Act Art. 3(1) and OECD (2024 update): a machine-based system that "infers" outputs from input. The Commission's guidelines (2025) are reported to place simple rule-based systems outside it [snippet] https://www.orrick.com/en/Insights/2025/04/EU-Commission-Clarifies-Definition-of-AI-Systems. I could not read the PDF text myself.
- OECD memo: https://oecd.ai/en/ai-publications/explanatory-memorandum-on-the-updated-oecd-definition-of-an-ai-system [snippet]
- Canada: Treasury Board's Directive on Automated Decision-Making covers systems that make or support decisions [snippet] https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=32592. It applies to federal bodies, not to Coastal Action.
- [inference] Frame differencing, background subtraction, CLAHE: fixed algorithms, no learned weights, likely outside. The detector and species classifier: learned, likely inside. A tracker (ByteTrack) uses a learned detector plus rules. Coastal Action's own definition governs.

## What to say in the pitch
- We designed around the limits in your problem statement: runs on your desktop, offline, no hosted AI.
- Most of the work is classical image processing; one small, open-source detector runs only on active segments.
- We will give you a measured kWh and kg CO2e per video hour from a wall meter, with the formula so you can redo it.
- At Nova Scotia's 2025 grid (528 g/kWh), our estimate is tens of grams per video hour [inference until measured].
- It is a proof of concept; training used cloud tools once, and we report that cost separately.

## What not to say
- "Green AI" or "carbon neutral".
- "Ten times less energy than manual review".
- Any CodeCarbon number without saying it is an estimate.
- Colab or A100 figures as the PC's figures.
- That our setup meets your AI policy; we have not seen it.

## Questions for the mentor
1. Which of your policy's concerns matters most (energy, water, vendor emissions, hardware purchase), and does it count classical image processing as AI?
2. Does the 32GB desktop exist today, and may we put a wall meter on it?
3. Would you accept a one-off development training run in the cloud if its cost is reported, or must training also be local?
