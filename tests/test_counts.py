import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clipsift import protocol as proto
from clipsift.config import load_config, config_hash
from clipsift.qc import percent_difference, qc_flags
from clipsift.schema import Detection
from clipsift.stages import get_backend
from clipsift.stages.layer1 import BasicCounter, IouTracker, iou, nms
import numpy as np


def det(t, x, y=0, w=10, h=10):
    return Detection(t, [x, y, w, h], 0.9, None, "test")


def test_tracker_and_counter():
    cfg = load_config()
    frames = [[det(0.0, 0), det(0.0, 100)], [det(0.5, 2), det(0.5, 102)], [det(1.0, 4)], [det(1.5, 5), det(1.5, 300)]]
    tracks = IouTracker(cfg).track(frames)
    assert len(tracks) == 2  # the lone box at x=300 is dropped (one point)
    dets = [d for f in frames for d in f]
    c = BasicCounter(cfg).count(tracks, dets, [0.0, 0.5, 1.0, 1.5])
    assert c.maxn == 2 and c.maxn_time_s == 0.0 and c.unique_tracks == 2
    assert c.mean_count == pytest.approx((2 + 1) / 2)  # first sample in each 1 s bin: 0.0 -> 2, 1.0 -> 1


def test_counter_empty():
    c = BasicCounter(load_config()).count([], [], [0.0, 0.5])
    assert c.maxn == 0 and c.mean_count == 0.0 and c.unique_tracks == 0


def test_iou_and_nms():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou([0, 0, 10, 10], [20, 20, 5, 5]) == 0.0
    xyxy = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], float)
    assert nms(xyxy, np.array([0.9, 0.8, 0.7]), 0.5) == [0, 2]


def test_percent_difference_named_and_flags():
    assert percent_difference(10, 10) == 0 and percent_difference(0, 0) == 0
    assert percent_difference(10, 12) == pytest.approx(2 / 11 * 100)
    pc = load_config()["protocol"]
    assert qc_flags(5, pc)["recount"] is False and qc_flags(7, pc)["recount"] is True


def test_window_and_subsamples():
    pc = load_config()["protocol"]
    s, e = proto.analysis_window(1200, pc)
    assert (s, e) == (60, 960)
    ts = proto.subsample_times(s, e, pc)
    assert len(ts) == 15 and ts[0] == 60
    s2, e2 = proto.analysis_window(1200, pc, 100, 700)
    assert proto.analysis_window(2147, pc, 120)[1] == 120 + pc["window_length_s"]   # a later start keeps the 15 minute length
    assert (s2, e2) == (100, 700)
    qc = proto.pick_qc(15, pc)
    assert 6 <= len(qc) <= 12


def test_name_parsing_and_grouping():
    p = Path("/d/2026/Summer/Sept 10/T1/STAT 2/GX010221_T1@1217pm.MP4")
    info = proto.parse_names([p])
    assert info["transect"] == "T1" and info["stat"] == "STAT 2" and info["year"] == 2026
    assert info["season"] == "summer" and info["video_id"] == "GX0221_T1"
    g = proto.group_chapters([Path("GX020221_T1@1226pm.MP4"), Path("GX010221_T1@1217pm.MP4"), Path("GX010300_T1.MP4")])
    assert list(g["0221"][0].name).count("1") and g["0221"][0].name.startswith("GX01") and len(g) == 2


def test_layer2_stubs_and_2b_gate():
    cfg = load_config()
    with pytest.raises(PermissionError):
        get_backend("classifier", "layer2b_cloud_compare_stub", cfg)
    cfg["cloud"]["enable_2b"] = True
    with pytest.raises(NotImplementedError):
        get_backend("classifier", "layer2b_cloud_compare_stub", cfg)
    with pytest.raises(NotImplementedError):
        get_backend("detector", "layer2a_detector_stub", cfg)
    with pytest.raises(NotImplementedError):
        get_backend("counting_model", "point_density_stub", cfg)


def test_onnx_missing_model_message():
    cfg = load_config()
    with pytest.raises(FileNotFoundError, match="detector.onnx.model_path"):
        get_backend("detector", "onnx", cfg)
    cfg["detector"]["onnx"]["model_path"] = "models/does_not_exist.onnx"
    with pytest.raises(FileNotFoundError, match="model_path"):
        get_backend("detector", "onnx", cfg)


def test_config_hash_changes():
    a, b = load_config(), load_config(overrides={"sample_fps": 3.0})
    assert config_hash(a) != config_hash(b) and config_hash(a) == config_hash(load_config())
