# NOAA Puget Sound Nearshore Fish 2017-2018 (LILA BC)

- Record: https://lila.science/datasets/noaa-puget-sound-nearshore-fish (also Mendeley Data, per the paper)
- Paper: Farrell et al., Sci Data 10:799 (2023), https://doi.org/10.1038/s41597-023-02557-6 (CC BY 4.0 article). Data collection: Ferriss et al. 2021, Aquaculture Environment Interactions 13:439-54.
- Direct files used (GCP, no login): https://storage.googleapis.com/public-datasets-lila/noaa-psnf/noaa_estuary_fish-images.zip and ...-annotations-2023.08.19.zip
- Licence: CDLA-Permissive-1.0 (LILA page: "released under the Community Data License Agreement (permissive variant)"), https://cdla.io/permissive-1-0/. Permissive: research and commercial use fine, shipped model fine; main obligation is keeping the licence text with redistributed data. Please also cite the paper.

## What is on disk (8.9 GB total)
- noaa_estuary_fish-images.zip: the full 7.69 GB image set (77,739 JPEGs, 1920x1080), integrity tested OK (unzip -t), size matches server.
- annotations/noaa_estuary_fish-2023.08.19.json (COCO Camera Traps JSON; 77,689 images, 115,295 annotation rows).
- images/ + subset_low_medium_vis.json: extracted subset, 21,623 images (1.77 GB).

## Labels: BOXES (confirmed in the JSON)
Bounding boxes [x,y,w,h] in pixels on 67,990 objects. Caveat: LILA text says labelling was done at image level, so the class is image-driven. Categories: empty, fish, crab, fish_or_crab, unknown. (LILA prose says "fish_and_crab"; the JSON name is actually fish_or_crab.) There is no species label. All annotation rows with category empty (47,305) have no box.
Full-set annotation rows (counted from JSON): empty 47,305 (no box); fish 56,158; crab 5,285; fish_or_crab 5,927; unknown 620 (67,990 boxes).

## Water clarity field (useful)
Each image has `visibility` (low/medium/high), `habitat_type` (6 values), `filter` (bool, magenta green-blocking cap; 44,770 of 77,689 images) and `location` (10). Visibility is constant within each deployment (checked: 0 of 859 deployments mixed). Full set: low 21,805 / medium 32,510 / high 23,374 images; 251 / 361 / 247 deployments.

## Subset choice
All animal-containing frames from every low- and medium-visibility deployment (19,391 frames), plus 2,232 empty frames (about 10%) sampled evenly through time within each deployment. 612 deployments, all 10 locations, kept grouped by deployment. Subset: low 7,983 images, medium 13,640. Boxes in subset: fish 42,560; crab 2,827; fish_or_crab 3,429; unknown 454 (49,270 boxes total, plus 2,232 empty rows). High-visibility images stay in the zip only.
Note: empties are subsampled, so frames within a deployment are not contiguous for empties; animal frames are complete.

## Split key
Deployment = file_name with the last two '_' tokens removed (e.g. SD11_227_6_26_2017). Frames within a deployment are near-duplicate video samples, so split by deployment at minimum; for stricter leakage-free splits use `location` (10 sites) or site prefix (SD##).

## Looked at (3 frames, boxes drawn)
Low-visibility frames are extreme: pink/magenta haze (the filter cap) or grey-green haze, very low contrast. Boxes land on the right places but the animals are barely visible even to a human (a crab at bottom-right of a pink frame; a small fish near the bottom of a grey frame; a tiny object in a blurry orange frame). Sample frames with boxes: scratchpad s0.jpg, s1.jpg, s2.jpg.

## Known problems
- 77,739 JPEGs vs 77,689 JSON images: 50 JPEGs have no annotation entry.
- Authors state crabs are under-labelled at sediment/eelgrass sites (small, camouflaged); crab is a small class (~5%).
- Strong colour cast from the magenta filter on ~58% of images; ours is grey haze, so colour augmentation needed.
- Image-level class semantics (fish_or_crab / unknown) are noisy for detector training; consider merging to one "animal" class or dropping unknown.
- Pacific NW (Puget Sound), not Nova Scotia; no green crab (Hemigrapsus and juvenile Metacarcinus instead).
- Images are frames sampled from video, no video files.

## Fit: High (for turbid/fixed-camera/boxes/fish+crab). Low-vis set is the closest to our haze, a bit harder than our target; crab count is modest.
