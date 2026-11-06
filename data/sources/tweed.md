# Tweed River / Tallebudgera luderick and bream footage (Ditria et al. 2021)

**Verdict:** downloaded (full dataset, 3.7 GB on disk). Vetting passed with caveats.

## Identity and citation
- Record: PANGAEA dataset, "Annotated video footage for automated identification and counting of fish in unconstrained marine environments", https://doi.pangaea.de/10.1594/PANGAEA.926930 (DOI registered 2021-04-20; PANGAEA page lists it as published 2021-01-22).
- Article: Ditria, Connolly, Jinks, Lopez-Marcano (2021), Frontiers in Marine Science 8, https://www.frontiersin.org/articles/10.3389/fmars.2021.629485
- The article's data availability statement only says "online repositories" and gives the PANGAEA DOI. PANGAEA is the real repository. No GitHub copy was needed, though the annotation metadata says the same data is at github.com/globalwetlands/luderick-seagrass (not visited).

## Licence
- CC-BY-4.0 (PANGAEA page): https://creativecommons.org/licenses/by/4.0/
- Paraphrase: free to use, share and adapt, including commercially, if credit is given to the authors. The JSON `licenses` block also says CC BY 4.0.
- Fit for a shipped model: yes, commercial use allowed. Attribution is required. No share-alike.

## What is downloaded (all in this folder)
- `Fish_automated_identification_and_counting.zip` (3,703,803,276 bytes, sha256 43457dae…eeba). Full PANGAEA download, `unzip -t` clean. Contains the annotation files plus a nested `luderick-seagrass.zip` holding the 4,280 JPG frames (3.70 GB uncompressed). (Update 6 Nov: the nested image zip has since been extracted; see images/ below.)
- `extracted/Fish_automated_identification_and_counting/`: the 10 annotation/metadata files from the outer zip (annotation_counts, dataset_images, and the all / jack_evans_a / jack_evans_b / tallebudgera CSV and JSON pairs). The nested `luderick-seagrass.zip` stays inside the outer zip and was not copied here.
- `manifest.json`.
- Subset: none. Whole dataset taken. Update 6 Nov: all 4,280 JPGs are extracted flat to `images/` (4,280 files, 3,704,816,695 bytes, counted from disk; names match `luderick_seagrass_all.json` exactly).

## Counts (counted from the files)
- Images: **4,280** JPG, 1920x1080. The article says 4,281; the metadata CSV has 4,281 lines including its header, so the article figure appears to count the header. Images and annotation IDs match exactly across zip, CSV and JSON.
- Annotations: **9,429** boxes (COCO JSON, `bbox` = [x, y, w, h] in pixels, `area` = w*h, verified on all boxes). 0 zero-size boxes, 0 images without boxes, max 18 boxes per image.
- Classes: luderick 9,304 (id 1), bream 125 (id 0). Only two fish classes; no crabs.
- Source clips: **138** (counted from filename prefixes). 79 clips have `_5fps_` frame names (3,078 frames); 59 clips use a different name pattern with frame numbers stepping by 200 or 400 (1,202 frames). The 5 fps claim therefore holds only for part of the set.
- Total video seconds: not determinable from the files. The 3,078 `_5fps_` frames are about 616 s at 5 fps; the other 1,202 frames have no known rate, so the total is left null in the manifest.
- Cameras: one model throughout, "Haldex Sports Action Cam HD 1080p". Habitat: seagrass for all frames.

## Label format
- COCO JSON (`luderick_seagrass_all.json`, plus per-subset JSONs) and CSV (`luderick_seagrass_*.csv`, with a `segmentation` polygon column).
- `dataset_images.csv` is the per-image metadata: file_name, height, width, lat, lon, camera, dataset, suggested_use, deployment, date, habitat.
- `annotation_counts.csv` gives per-subset counts.

## Split and grouping (for leakage-free splits)
- Splits in the data: `train` = Jack Evans A (2,673 images; 6,649 luderick, 53 bream); `test` = Jack Evans B (843 images; 1,632 luderick, 29 bream); `novel_test` = Tallebudgera (764 images; 1,023 luderick, 43 bream).
- Groups: `deployment` plus date gives **18** physical deployments. Deployment numbers repeat across Jack Evans A and B, so group on deployment+date (or on deployment within dataset) rather than on deployment alone.
- **Leakage found:** clip `2205_Luderick_25.mov` (deployment 15, 22/05/2019) appears in both train (40 frames, Jack Evans A) and test (71 frames, Jack Evans B). Re-split on deployment+date, or drop that clip from one side, before using these splits.
- There is no per-video column. The clip identity is only the filename prefix, so the clip-to-deployment mapping is derived from the filename.

## Water clarity (from looking at frames)
- Viewed 3 annotated frames with boxes drawn: `04C1_Luderick_5.mov_5fps_000256` (Jack Evans A), `2205_Luderick_57.mov_5fps_000014` (Jack Evans B), `20190618_11.mov_5fps_000008` (Tallebudgera). Rendered copies of 6 frames are in the scratchpad folder, not in this source folder.
- Scenes are shallow seagrass beds with green-blue water, moderate haze, and sandy patches. Fish are mid-water, and several are small or faint. Visibility is much better than the silt-bottom, grey-haze, near-zero-visibility target. Site is subtropical (southeast Queensland), not cold temperate.
- Box check: in the 3 frames I viewed, boxes sit on fish. Some visible fish in the frames were not boxed, so there are probably missed labels.

## Known problems
- Only two classes; bream is 1.3% of boxes, too few to train on.
- Cross-split clip leakage (above).
- Frame sampling is inconsistent (5 fps for some clips, a 200-frame stride for others).
- Boxes overhang the image edge by up to 2 px in 17 cases. Harmless, but clip them when training.
- I did not verify species labels. The fish in `20190618_11` is labelled luderick and looks silvery; worth checking the bream labels.
- Metadata says `dataset` is "Jack Evans A/B" and "Tallebudgera", which are site names inside the Tweed and Tallebudgera estuaries. The camera deployments were in seagrass only.

## Fit for our target: **Medium**
- Good: real action-camera footage, fixed-ish camera, 1080p, 9.4k boxes, 18 deployments to split on, CC-BY allows a shipped model.
- Gaps: no crabs; seagrass, not silt bottom; much clearer than the target; warm water. Useful as more fish-detection training data and as a clarity-variation set, not as a match for the Nova Scotia footage.
