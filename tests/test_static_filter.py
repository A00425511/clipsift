"""Static-object filter tests. Fake detections only: no torch, no model weights."""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from clipsift import static_filter as sf
from clipsift.config import load_config
from clipsift.pipeline import recount_frames, review_priority_subsample, run, subsample_status
from clipsift.schema import Detection, Subsample, validate
from clipsift.stages import register
from clipsift.stages.cfd import CfdDetector
from make_synthetic_clip import make

W, H = 3840, 2160


def D(x, y, w=40, h=30, score=0.2, t=0.0, movement=None):
    return Detection(t=t, box=[x, y, w, h], score=score, source="cfd:nano", movement=movement)


def cfg(**over):
    return {"static_filter": over}


def pole_frames(n=10, with_pole=7, fish_moves=True):
    """n frames. A pole box sits in `with_pole` of them; one fish box wanders in every frame."""
    frames = []
    for i in range(n):
        ds = [D(1000 + 400 * i, 500 + 90 * (i % 3), t=i * 60.0)] if fish_moves else []
        if i < with_pole:
            ds.append(D(2000 + (i % 2), 900, 60, 400, t=i * 60.0))  # 1 px jitter
        frames.append((i * 60.0, ds))
    return frames


# ---------------------------------------------------------------- persistence
def test_persistent_box_is_marked_and_wandering_fish_is_not():
    fr = pole_frames()
    summ = sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    poles = [d for _, ds in fr for d in ds if d.box[2] == 60]
    fish = [d for _, ds in fr for d in ds if d.box[2] == 40]
    assert poles and all(d.static and d.static_reason == "persistent" for d in poles)
    assert fish and not any(d.static for d in fish)
    assert summ["persistence_ran"] and summ["static"] == len(poles)


def test_rare_recurrence_is_not_static_and_share_is_configurable():
    fr = pole_frames(with_pole=2)  # 2 of 10 frames = 0.2 share
    sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    assert not any(d.static for _, ds in fr for d in ds)
    sf.apply(fr, cfg(movement={"enabled": False}, persistence={"share": 0.15}), W, H)
    assert sum(d.static for _, ds in fr for d in ds) == 2


def test_different_size_at_same_place_is_not_the_same_object():
    sizes = [40, 60, 90, 130]  # neighbouring sizes overlap by IoU < 0.5, so each size recurs in only 3 of 12 frames
    fr = [(i, [D(500, 500, sizes[i % 4], sizes[i % 4], t=i)]) for i in range(12)]
    sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    assert not any(d.static for _, ds in fr for d in ds)
    fr = [(i, [D(500, 500, 40, 40, t=i)]) for i in range(10)]
    sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    assert all(d.static for _, ds in fr for d in ds)


def test_empty_frames_count_in_the_share():
    fr = [(i, [D(500, 500, t=i)] if i < 4 else []) for i in range(20)]  # 4 of 20 frames = 0.2
    sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    assert not any(d.static for _, ds in fr for d in ds)


def test_too_few_frames_skips_persistence_with_a_note():
    fr = [(i, [D(500, 500, t=i)]) for i in range(4)]
    s = sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    assert not s["persistence_ran"] and s["notes"] and not any(d.static for _, ds in fr for d in ds)


def test_camera_moved_between_deployments_adapts():
    a = [(i, [D(500, 500, 60, 400, t=i)]) for i in range(10)]
    b = [(i, [D(1700, 800, 60, 400, t=i)]) for i in range(10, 20)]
    sf.apply(a, cfg(movement={"enabled": False}), W, H)
    sf.apply(b, cfg(movement={"enabled": False}), W, H)
    assert all(d.static for _, ds in a + b for d in ds)  # no hand work for either position


def test_confident_box_is_protected_and_clearly_moving_persistent_place_is_kept():
    fr = pole_frames()
    fr[0][1][-1].score = 0.8
    fr[1][1][-1].movement = 12.0
    sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    assert not fr[0][1][-1].static  # score 0.8 >= protect_score
    assert not fr[1][1][-1].static  # persistent place, but this box moves (>= 8)
    assert fr[2][1][-1].static


def test_rerun_resets_earlier_marks():
    fr = pole_frames()
    sf.apply(fr, cfg(movement={"enabled": False}), W, H)
    n1 = sum(d.static for _, ds in fr for d in ds)
    sf.apply(fr, cfg(enabled=False), W, H)
    assert sum(d.static for _, ds in fr for d in ds) == 0 and n1 > 0


# ---------------------------------------------------------------- movement
def _still_and_bg(fish_delta=6, size=(540, 960)):
    rng = np.random.default_rng(0)
    base = rng.integers(90, 100, (*size, 3), dtype=np.uint8)
    others = [base.copy() for _ in range(6)]
    still = base.copy()
    still[100:160, 200:300] += fish_delta  # a faint fish present only in the still
    return still, others


def test_movement_score_separates_changed_from_unchanged_boxes():
    still, others = _still_and_bg()
    diff, scale = sf.movement_map(still, others, width=960)
    moving = sf.box_movement(diff, [200, 100, 100, 60], scale)
    quiet = sf.box_movement(diff, [600, 300, 100, 60], scale)
    assert moving > 4.5 and quiet < 0.5
    assert sf.box_movement(diff, [10, 10, 1, 1], scale) is None  # too small to score


def test_background_never_includes_the_target_frame():
    offs = sf.background_offsets(5.0, 1.0, 0.75)
    assert 0 not in offs and min(offs) == -5 and max(offs) == 5 and len(offs) == 10


def test_too_few_background_frames_means_not_scored_and_kept():
    still, others = _still_and_bg()
    diff, _ = sf.movement_map(still, others[:2], width=960)
    assert diff is None and sf.box_movement(diff, [0, 0, 50, 50], 1.0) is None
    d = D(100, 100, movement=None)
    sf.apply([(0, [d])] * 1, cfg(persistence={"enabled": False}), W, H)
    assert not d.static


def test_low_movement_rejects_and_cutoff_is_configurable():
    quiet, moving = D(100, 100, movement=2.0), D(300, 100, movement=4.0)
    sf.apply([(0, [quiet, moving])], cfg(persistence={"enabled": False}), W, H)
    assert quiet.static and quiet.static_reason == "no_movement" and not moving.static
    sf.apply([(0, [quiet, moving])], cfg(persistence={"enabled": False}, movement={"cutoff": 5.0}), W, H)
    assert moving.static


def test_slow_still_animal_can_be_removed_documented_limit():
    crab = D(100, 100, movement=0.8, score=0.3)  # a resting crab: nothing changes in its box
    sf.apply([(0, [crab])], cfg(persistence={"enabled": False}), W, H)
    assert crab.static  # known limit, see README: bias to keeping reduces it but cannot remove it


# ---------------------------------------------------------------- hand mask
def test_mask_polygon_rejects_pole_and_matches_by_recording(tmp_path):
    pole = [[1950, 800], [2100, 800], [2100, 1400], [1950, 1400]]
    inside, outside = D(1980, 900, 60, 200), D(300, 300)
    c = cfg(persistence={"enabled": False}, movement={"enabled": False},
            masks=[{"match": "T1-STAT2*", "polygons": [pole]}, {"match": "OTHER*", "polygons": [[[0, 0], [W, 0], [W, H]]]}])
    sf.apply([(0, [inside, outside])], c, W, H, names=["T1-STAT2 411"])
    assert inside.static and inside.static_reason == "mask" and not outside.static
    inside.static = False
    sf.apply([(0, [inside])], c, W, H, names=["somewhere else"])
    assert not inside.static


def test_mask_from_file_scales_to_frame_size(tmp_path):
    (tmp_path / "m.json").write_text(json.dumps({"width": 1920, "height": 1080,
                                                  "polygons": [[[900, 400], [1000, 400], [1000, 700], [900, 700]]]}))
    d = D(1850, 850, 100, 300)  # centre (1900, 1000) in 3840 space = (950, 500) in the 1920 drawing
    sf.apply([(0, [d])], cfg(persistence={"enabled": False}, movement={"enabled": False},
                             masks=[{"file": "m.json"}]), W, H, base_dir=tmp_path)
    assert d.static and d.static_reason == "mask"


def test_reasons_combine():
    d = D(1980, 900, 60, 200, movement=1.0)
    sf.apply([(0, [d])], cfg(persistence={"enabled": False},
                             masks=[{"polygons": [[[1900, 800], [2200, 800], [2200, 1300], [1900, 1300]]]}]), W, H)
    assert d.static_reason == "mask+no_movement"


# ---------------------------------------------------------------- schema, counts, tools
def test_detection_schema_is_backward_compatible():
    old = {"t": 1.0, "box": [1, 2, 3, 4], "score": 0.5, "track_id": None, "source": "x"}
    d = Detection.from_dict(old)
    assert d.static is False and d.static_reason is None and d.movement is None
    out = d.to_dict()
    assert out["static"] is False and set(old) <= set(out)
    d.static, d.static_reason, d.movement = True, "persistent", 1.2345
    assert Detection.from_dict(d.to_dict()) == Detection(1.0, [1.0, 2.0, 3.0, 4.0], 0.5, None, "x", True, "persistent", 1.23)


def test_static_boxes_are_hidden_from_counts_status_and_priority():
    a, b = D(0, 0, score=0.3), D(500, 500, score=0.3)
    b.static, b.static_reason = True, "persistent"
    assert sf.live([a, b]) == [a] and sf.live([b.to_dict(), a.to_dict()]) == [a.to_dict()]
    assert subsample_status({"detections": [b], "motion_near_point": False, "movement_unidentified": 0}) == "none"
    assert subsample_status({"detections": [a, b], "motion_near_point": False, "movement_unidentified": 0}) == "fish_unknown"
    c = recount_frames({0.0: [a, b], 5.0: [b]})
    assert c.maxn == 1 and c.maxn_time_s == 0.0 and c.mean_count == 0.5
    assert recount_frames({5.0: [b]}).maxn_time_s is None


def test_suggest_polygons_covers_boxes_and_make_static_mask_tool(tmp_path):
    boxes = [[2000 + j, 900, 60, 400] for j in (0, 1, 2)]
    polys = sf.suggest_polygons(boxes, W, H)
    assert len(polys) == 1
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(np.array(polys[0])).astype(np.int32)], 1)
    assert m[1100, 2030] == 1 and m[100, 100] == 0
    frames = {"width": W, "height": H,
              "frames": [{"t": i, "boxes": ([[2000, 900, 60, 400, 0.2]] if i < 8 else []) + [[300 * i % 3000, 200, 40, 30, 0.2]]}
                         for i in range(12)]}
    (tmp_path / "f.json").write_text(json.dumps(frames))
    r = subprocess.run([sys.executable, str(ROOT / "tools/make_static_mask.py"), "--boxes", str(tmp_path / "f.json"),
                        "--json", str(tmp_path / "m.json"), "--png", str(tmp_path / "m.png")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads((tmp_path / "m.json").read_text())
    assert out["width"] == W and len(out["polygons"]) == 1
    png = cv2.imread(str(tmp_path / "m.png"), cv2.IMREAD_GRAYSCALE)
    assert png.shape == (H, W) and png[1100, 2030] == 255 and png[100, 100] == 0


# ---------------------------------------------------------------- pipeline end to end, fake model
class _PoleAndFishModel:
    """Boxes only for the first tile of each frame: a fixed pole box and a fish box that jumps around."""
    device = "fake"

    def __init__(self):
        self.n = 0
        self.first = True

    def infer(self, tiles, threshold):
        out = []
        for _ in tiles:
            if self.first:
                self.first = False
                self.n += 1
                x = 5 + (self.n * 37) % 200
                out.append((np.array([[60.0, 20.0, 80.0, 120.0], [x, 150.0, x + 30.0, 180.0]]), np.array([0.3, 0.3])))
            else:
                out.append((np.zeros((0, 4)), np.zeros(0)))
        return out


@register("detector", "fake_pole_fish")
class FakePoleFish(CfdDetector):
    def __init__(self, cfg):
        super().__init__(cfg, model=_PoleAndFishModel(), weights=Path("cfd-rf-detr-nano-fake.pth"))

    def detect(self, frame, t):
        self.model.first = True
        return super().detect(frame, t)


def test_pipeline_keeps_static_boxes_but_hides_and_does_not_count_them(tmp_path_factory):
    clip = make(tmp_path_factory.mktemp("sf") / "syn.mp4", duration=60, width=480, fps=10)
    c = load_config(overrides={
        "protocol": {"trim_start_s": 2, "trim_end_s": 2, "window_length_s": 50, "interval_s": 5, "context_s": 2},
        "detector": {"cfd": {"tile_size": 256, "count_threshold": 0.1}}, "layer": 1, "detect_fps_segments": 0,
        "stages": {"detector": "fake_pole_fish"}, "static_filter": {"movement": {"enabled": False}}})
    d = run([clip], c, tmp_path_factory.mktemp("out"), log=lambda *a: None)
    r = json.loads((d / "results.json").read_text())
    assert validate(r) == []
    pole = [x for s in r["subsamples"] for x in s["auto"]["detections"] if x["box"][3] == 100]
    fish = [x for s in r["subsamples"] for x in s["auto"]["detections"] if x["box"][3] == 30]
    assert pole and all(x["static"] and x["static_reason"] == "persistent" for x in pole)  # kept, marked
    assert fish and not any(x["static"] for x in fish)
    for s in r["subsamples"]:
        a = s["auto"]
        assert a["fish_count"] == sum(1 for x in a["detections"] if not x["static"] and x["score"] >= 0.1) == 1
        assert a["status"] == "fish_unknown"


def test_pipeline_filter_off_changes_nothing(tmp_path_factory):
    clip = make(tmp_path_factory.mktemp("sf2") / "syn.mp4", duration=40, width=480, fps=10)
    c = load_config(overrides={
        "protocol": {"trim_start_s": 2, "trim_end_s": 2, "window_length_s": 30, "interval_s": 5, "context_s": 2},
        "detector": {"cfd": {"tile_size": 256}}, "layer": 1, "detect_fps_segments": 0,
        "stages": {"detector": "fake_pole_fish"}, "static_filter": {"enabled": False}})
    r = json.loads((run([clip], c, tmp_path_factory.mktemp("out2"), log=lambda *a: None) / "results.json").read_text())
    assert not any(x["static"] for s in r["subsamples"] for x in s["auto"]["detections"])
    assert all(s["auto"]["fish_count"] == 2 for s in r["subsamples"])


def test_no_torch_needed():
    code = "import sys; import clipsift.static_filter, clipsift.pipeline; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0


def test_pipeline_scores_movement_from_the_video_and_stays_valid(tmp_path_factory):
    clip = make(tmp_path_factory.mktemp("sf3") / "syn.mp4", duration=40, width=480, fps=10)
    c = load_config(overrides={
        "protocol": {"trim_start_s": 2, "trim_end_s": 2, "window_length_s": 30, "interval_s": 5, "context_s": 2},
        "detector": {"cfd": {"tile_size": 256}}, "layer": 1, "detect_fps_segments": 0,
        "stages": {"detector": "fake_pole_fish"}})  # filter on, defaults
    r = json.loads((run([clip], c, tmp_path_factory.mktemp("out3"), log=lambda *a: None) / "results.json").read_text())
    assert validate(r) == []
    dets = [x for s in r["subsamples"] for x in s["auto"]["detections"]]
    assert dets and all(("movement" in x) and "static" in x for x in dets)
    assert any(x["movement"] is not None for x in dets)
    assert "static_movement" in r["run"]["stage_runtimes_s"]
