import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clipsift.schema import (Counts, Detection, Flags, Recording, Results, Run, Segment, SpeciesGuess,
                             Subsample, Track, validate)


def make_results():
    seg = Segment("seg_0001", 1.0, 5.0, detections=[Detection(1.5, [1, 2, 3, 4], 0.5, 1, "motion_blob")],
                  tracks=[Track(1, 1.5, 2.0, 2, [SpeciesGuess("fish_unknown", 0.0)])],
                  counts=Counts(1, 1.5, 0.5, 1), flags=Flags(True, False))
    ss = Subsample("ss_01", 3.0, 1.0, 5.0)
    ss.auto["points"] = [[1.0, 2.0, 0.9]]
    res = Results(Recording("r", ["a.mp4"], 10.0, 30.0, 640, 360, video_id="GX0221_T1", year=2026),
                  Run(1, "m", "abc", "2026-01-01T00:00:00+00:00", 2.0, 1.0, {"x": 0.5}),
                  [seg], protocol={"window_start_s": 1.0, "window_end_s": 9.0}, subsamples=[ss])
    res.compute_summary()
    return res


def test_round_trip():
    d = make_results().to_dict()
    assert validate(d) == []
    d2 = Results.from_dict(json.loads(json.dumps(d))).to_dict()
    assert d == d2


def test_validate_catches_problems():
    d = make_results().to_dict()
    bad = copy.deepcopy(d)
    bad["segments"][0]["kind"] = "nope"
    bad["segments"][0]["detections"][0]["box"] = [1, 2, 3]
    del bad["subsamples"][0]["auto"]["fish_count"]
    bad["schema_version"] = "0.1"
    errs = " | ".join(validate(bad))
    assert "kind" in errs and "box" in errs and "fish_count" in errs and "schema_version" in errs


def test_nulls_allowed_for_counts():
    d = make_results().to_dict()
    d["segments"][0]["counts"] = {"maxn": None, "maxn_time_s": None, "mean_count": None, "unique_tracks": None}
    assert validate(d) == []
