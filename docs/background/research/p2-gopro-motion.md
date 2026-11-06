# P2 (Coastal Action): GoPro footage, motion cues and local processing

Researched Thu 5 Nov 2026. Tags: [fetched] opened; [snippet] search result only; [inference] my reasoning; [notes] Jacob's launch notes. GoPro's support page would not load, so GoPro numbers are orders of magnitude. Constraint from 02-launch-notes.md: **everything runs locally on a 32GB desktop with a basic, unknown GPU, under an in-house data/AI policy we have not seen.**

## 1. GoPro facts

- **Chaptering.** Recordings split at about 4GB on FAT32 or cards of 32GB or less; one source says newer cameras on exFAT reach about 12GB, another says the cap is firmware [snippet: [havecamerawilltravel](https://havecamerawilltravel.com/gopro/gopro-split-video-files/), [trekview](https://www.trekview.org/blog/join-gopro-chaptered-split-video-files-preserve-telemetry/)]. A "1 hour clip" may be several files; sort by name and stitch. Ask the camera model and settings.
- **Size.** GB/hour = Mbps x 0.45 (arithmetic). Top bitrate is about 120 Mbps [snippet], so up to 54 GB/hour; 1080p at 30 to 60 Mbps would be 13 to 27 GB/hour [inference, guessed bitrate]. HEVC vs H.264 at the same bitrate gives the same size; HEVC gives better quality per bit [inference].
- **Telemetry (GPMF).** Metadata track with accelerometer (~200 Hz), gyro, GPS, UTC time. GPS5 on HERO5 to 11, GPS9 on HERO11, and "No GPS receiver in HERO12" [fetched: [gpmf-parser](https://gopro.github.io/gpmf-parser/)]. No GPS underwater anyway. Useful: IMU spikes flag camera shake; time stamps build the timeline.
- **Frame rates** (24 to 240 fps) matter only for decode cost, since we sample 2 to 5 fps [inference].

## 2. Motion cues for cryptic animals

| Method | Good at | Fails on |
|---|---|---|
| Frame differencing | Cheapest | Slow animals, flicker, shake |
| MOG2 / KNN (OpenCV) | Small blobs, static camera | Sway, sediment; absorbs a still crab into background |
| Temporal median background | Robust, no tuning, feeds a difference view | Needs relative movement |
| Motion history image | One-image path and direction | Noisy scenes |
| Optical flow (Farneback) | Direction and speed (compare to current) | Slower, noisy in murk |

- **Evidence.** I found no controlled study showing motion beating single-frame detection on camouflaged underwater animals. Indirect: Fish4Knowledge found kernel-density background models best of the classical set, with false-alarm post-filtering [snippet: [Springer](https://link.springer.com/10.1007/978-3-319-30208-9_9)]; motion is usually paired with appearance [snippet: [Salman et al.](https://www.scribd.com/document/726622398/fsz025)]; background subtraction often degrades when other background objects move [snippet: [MIT Sea Grant](https://seagrant.mit.edu/wp-content/uploads/2024/05/IEEE_Oceans_Paper_Fish_Localization.pdf)]. The partner's crab anecdote [notes] is our best first-hand evidence.
- **NS water [inference].** Kelp: periodic fixed-location motion, so long median background and a "always moving" mask. Sediment: many small blobs drifting together, so filter by size and by direction matching the current. Shake: global shift; compensate or skip, cross-check with gyro.
- **Cheap filters:** minimum blob area; present in 3+ consecutive samples; plausible centroid track; reject flow aligned with current; skip high-shake frames. Expose each as a slider.
- **Difference view:** worth it. Show frame beside |frame minus median| tinted, or a looping clip with moving pixels outlined; it copies their "showed up when it moved" trick. Eulerian magnification also amplifies kelp, noise and shake and is slow: overkill [inference]. Future work only.

## 3. Grid counting

Partner method is only "still, then grid-based tagging count" [notes]; ask for an example sheet. Related published methods (not fetched, verify): quadrat/point counts, and MaxN (maximum count of a species in any one frame, used in BRUV work) [inference]. To compare with what they trust: configurable N x M grid on stills, click-to-tag per cell, accept detector boxes into cells, export per-still counts and per-segment MaxN in their sheet's layout, and show tool vs reviewer counts on stills they have already counted.

## 4. Contrast: human vs detector

Helps a human: local contrast, gamma lift, channel stretch (red is absorbed first [inference]). Helps a detector: unclear; one study found CLAHE best of six scenarios with YOLOv11 [snippet via p2-data-models], but test raw vs enhanced on real footage. Viewer: client-side sliders (contrast, brightness, gamma, saturation, CLAHE toggle, reset) applied to display only, never the stored original, shared by still, loop and difference view, and saved with each review record.

## 5. Local scale and cost [inference throughout]

| Sampling | Frames per 1 hour |
|---|---|
| 2 fps | 7,200 |
| 5 fps | 18,000 |

Target: 32GB desktop, CPU-only or modest GPU (4 to 8GB VRAM, exact card unknown).

| Stage (cheapest first) | CPU-only | Modest GPU |
|---|---|---|
| 1. Decode once to a 720p proxy + sampled frames | 10 to 40 min at modest settings; 4K HEVC on an older CPU could approach real time, 60+ min (orchestrator note). Measure on their PC | 5 to 15 min if hardware decode works |
| 2. Motion filter on 640 px frames (MOG2 / median / flow) | 2 to 10 min | same (CPU stage) |
| 3. Small detector (YOLO-nano/small class, ONNX or OpenVINO) on active segments only, say 10 to 20% of frames | 5 to 20 min | 1 to 3 min |
| 4. Species suggestion on tracked crops only (tens to hundreds of crops) | 1 to 5 min | under 1 min |

Total roughly 20 to 75 min CPU-only (longer, perhaps 90+ min, for 4K HEVC on an older CPU), 10 to 30 min with a modest GPU, per video hour. **Overnight batch is a sensible operating model:** drop the day's clips in, queue them, review the next morning. It also hides the slow decode, needs no live demo compute, and saves per-chunk results so a crash does not restart a recording. For the presentation, pre-process one hour and show the saved results plus a live scrub.

**Models that fit:**
- Detector: a small YOLO-class or RT-DETR-small model exported to ONNX (ONNX Runtime) or OpenVINO for Intel CPUs. Ultralytics is AGPL-3.0 [fetched in p2-data-models]; fine locally for a POC, flag for products.
- Species: BioCLIP 2 ViT-L/14 [fetched in p2-data-models] is heavy (~300M parameters, my recollection) but only runs on crops, so it is feasible even on CPU (about 1 s per crop, inference). A smaller CLIP-style model or the earlier BioCLIP ViT-B is a lighter fallback; I did not verify its specs.
- **Drop:** SAM 2 (heavy, not needed for counting), cloud VLM second pass (footage would leave the PC), Grounding DINO (heavy, weak on algae and kelp per p2-data-models, needs GPU).

**HEVC decode.** Cannot assume hardware decode: it depends on the GPU, drivers and ffmpeg build, and a basic or integrated GPU may lack it [inference]. Fallback: ffmpeg software decode once into an H.264 720p proxy (use `-skip_frame` or `fps` filter to sample), then everything downstream reads the proxy. Test on their machine early.

**Proxy resolution risk (orchestrator note).** Downscaling to 720p and 640 px can erase exactly the small, faint movement the rep described with the crab. Keep the original files untouched, pull review stills and loops from the original at the flagged time, and test motion detection at proxy vs higher resolution on a clip with a known cryptic animal before fixing the proxy size.

**Data policy.** No partner footage leaves the PC: no upload, cloud API, or telemetry from libraries. Pin model weights to local files so it runs offline. Cloud GPUs (Colab) are at most a development aid on non-partner data (Brackish), and only if their policy allows even that.

## 6. ClipSift changes

1. **Unit = one long recording** (stitched chapters), shown as a timeline strip of segments with motion score, detections and flags (shake, murk), not a clip folder. Headline: "1 recording, N segments of interest".
2. **Review view per segment:** best still with grid and tags; 3 to 6 s looping clip; difference-view toggle; contrast sliders; keys accept / reject / unknown / next.
3. **Two paths merged:** detector for fish, motion proposals for cryptic animals; motion-only hits labelled "movement, unidentified", never dropped. Add a "spot-check" that shows a random 5% of unflagged time.
4. **Time-saving claim:** show measured compute time (overnight, unattended) and reviewer minutes against the rep's 6 to 7 hours [notes], plus recall on a human-labelled slice. No ratio until a real reviewer time is measured.
5. **Packaging:** a local app (Python backend + browser UI on localhost), one installer-free folder, no internet needed.

## 7. Testing without real footage

Ask the mentor on Fri 6 Nov for one GoPro recording (even 10 minutes, ideally with a known cryptic animal), one tagged grid sheet, camera model and settings, and the desktop's CPU/GPU. Fallback: Brackish video (cold, turbid, static) plus synthetic stress tests (sway texture, sediment particles, shake, a low-contrast moving blob), labelled synthetic in the pitch. Run the same pipeline on any MP4, and time it on a 16GB or 32GB machine without a discrete GPU to prove the local numbers.
