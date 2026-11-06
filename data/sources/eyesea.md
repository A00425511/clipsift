# EyeSea Underwater Video (PNNL DataHub)
Record: https://data.pnnl.gov/group/nodes/dataset/12978 (no DOI listed; no size listed)
Associated paper: "Underwater fish detection using deep learning for water power applications"
Status: NOT DOWNLOADED. Blocked by registration (rule 4).
Licence: DataHub Terms (https://data.pnnl.gov/policy) say default licence is CC0 unless a dataset licence says otherwise; no dataset-specific licence seen on the record page. Same terms say downloaders "must be registered users". Download is a single Globus-hosted .tar (12978_d072f8e31a3fede18c0b6a6d98d50042.tar), which normally needs Globus sign-in. Not tested (would require login).
Contents per record page: train_x/train_y, voith_test_x/y, wells_test_x/y, orpc_test_x/y, plus videos/ (Aquatera_VoithHydro, DCPUD_WellsDam, ORPC_Igiugig). Bounding boxes by PNNL staff. Frames/labels in Keras-style arrays, plus original video.
Sites (split group): ORPC Igiugig/Kvichak AK (glacial), Aquatera Fall of Warness (Voith tidal), Wells Dam WA.
Not verified: size, label format, class list, frame clarity (no frames viewed).
Fit: unassessed; likely Medium-High for turbidity if obtainable, but fish-only (no crabs).
Jacob must: register/sign in at data.pnnl.gov and Globus, then fetch the tar (size unknown; check against 20 GB cap).
