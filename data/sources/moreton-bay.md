# Moreton Bay low-visibility BRUV (Lopez-Marcano et al.) - NOT DOWNLOADED (vetting: licence unclear + password gate)

- Record: https://github.com/slopezmarcano/dataset-fish-detection-low-visibility (default branch gh-pages; README read 6 Nov 2026)
- Zenodo DOI 10.5281/zenodo.5238512 = 3 KB code snapshot only (licence tag "other-open"), contains no data. Project site: https://slopezmarcano.github.io/automated-fish-detection-in-low-visibility/
- Citation: Lopez-Marcano S, Roe T, Kitchingman M, Jinks E, Connolly R. "An annotated dataset for automated detection and counting of estuarine fish in poor visibility conditions" (CITATION.cff). Data collected by Moreton Bay Environmental Education Centre; AI for Earth grant. README asks for an acknowledgement sentence.
- Licence: NONE stated for the data. GitHub API license=null, no LICENSE file (404), README has no terms. Only a request to cite/acknowledge. Gate failed: not downloaded.
- Access: data sit on Griffith ownCloud shares (research-storage.griffith.edu.au) behind a password that the README prints. Entering it is against our no-credentials rule, so not attempted.
- From README (not verified in files):
  - Train: 555 MB of IMAGES (no raw video), annotations 19 MB CSV + COCO JSON, v7, 8,696 annotated images; >65,000 annotations stated (table sums to ~65k), 19 classes. Bounding boxes [x,y,w,h] AND polygon segmentation masks.
  - Species (annotations): Eastern Striped Grunter 14,631; Yellowfin Bream/Tarwhine 11,872; Paradise Threadfin Bream 10,658; Australasian Snapper 9,489; Smallmouth Scad 7,067; Smooth Golden Toadfish 5,014; Blue Catfish 2,411; Blue Swimmer Crab 847 (a crab class); others small (Gunthers Wrasse 603, Pinkbanded Grubfish 502, ...). 4 "targeted" species are better annotated.
  - Test: 6.5 GB, unannotated whole videos ("12 hour" total per README), ground truth = CSV of manual MaxN per species per video, for the 4 target species.
  - Visibility: poor/fair, secchi 2-5 m, standard baited rig, GoPro 1080p, 2017-21.
  - Video length: not stated. 12 h over 6.5 GB suggests many clips; per-video length unknown, so 20+ min unconfirmed.
  - Split group field: not documented; would have to be derived from filenames/video IDs.
- Fit: High on paper (turbid, fixed GoPro, boxes, crab class, MaxN), but blocked.
- Next step: get licence clarity and permission from Sebastian Lopez-Marcano (Griffith/CSIRO), using the contact link in the dataset's README. Do not download the files until that is settled.
