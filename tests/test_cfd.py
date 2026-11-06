"""CFD backend tests. A fake model stands in for rfdetr, so these run without torch."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from clipsift import cli
from clipsift.config import load_config
from clipsift.pipeline import (review_priority_segment, review_priority_subsample, run, subsample_status)
from clipsift.schema import Detection, Subsample, validate
from clipsift.stages import get_backend, register
from clipsift.stages import cfd
from clipsift.stages.cfd import CfdDetector, ModelUnavailable, merge_boxes, tile_boxes
from make_synthetic_clip import make


class BrightSquareModel:
    """Fake model: finds white squares in a tile, like a detector would. Score = visible share."""
    device = "fake"

    def __init__(self, full=40):
        self.calls = []
        self.full = full

    def infer(self, tiles, threshold):
        self.calls.append((len(tiles), [t.shape for t in tiles]))
        out = []
        for t in tiles:
            ys, xs = np.where(t[:, :, 0] > 250)
            if len(xs) == 0:
                out.append((np.zeros((0, 4)), np.zeros(0)))
                continue
            box = np.array([[xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]], float)
            share = (xs.max() + 1 - xs.min()) * (ys.max() + 1 - ys.min()) / (self.full * self.full)
            out.append((box, np.array([min(1.0, share)])))
        return out


def cfg_with(**cfd_over):
    return load_config(overrides={"detector": {"cfd": cfd_over}})


def make_det(model=None, weights="models/cfd-rf-detr-nano-640-test.pth", **over):
    return CfdDetector(cfg_with(**over), model=model or BrightSquareModel(), weights=Path(weights))


# ---------------------------------------------------------------- tiling
def test_tile_layout_matches_one_frame_test():
    tiles = tile_boxes(3840, 2160, 512, 0.25)
    xs = sorted({t[0] for t in tiles})
    ys = sorted({t[1] for t in tiles})
    assert xs == list(range(0, 3328, 384)) + [3328]
    assert ys[-1] == 2160 - 512 and ys[1] == 384
    assert all(t[2] - t[0] == 512 and t[3] - t[1] == 512 for t in tiles)
    assert len(tiles) == len(xs) * len(ys)


def test_tiles_cover_every_pixel_and_stay_inside():
    w, h = 1000, 700
    cover = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in tile_boxes(w, h, 256, 0.25):
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
        cover[y0:y1, x0:x1] = True
    assert cover.all()


def test_frame_smaller_than_tile_is_one_tile():
    assert tile_boxes(300, 200, 512, 0.25) == [(0, 0, 300, 200)]


# ---------------------------------------------------------------- coordinates and merging
def _frame(w=640, h=480, squares=()):
    f = np.zeros((h, w, 3), np.uint8)
    for x, y, s in squares:
        f[y:y + s, x:x + s] = 255
    return f


def test_boxes_map_back_to_original_pixels():
    det = make_det(tile_size=128, overlap=0.25, threshold=0.05)
    f = _frame(squares=[(500, 300, 40)])
    ds = det.detect(f, 1.5)
    assert len(ds) == 1
    d = ds[0]
    assert d.box == pytest.approx([500, 300, 40, 40])
    assert d.t == 1.5 and d.source == "cfd:nano" and d.track_id is None


def test_fish_cut_by_tile_edge_is_counted_once():
    # square at x=100..140 straddles the x=128 edge of the first tile; tile step is 96
    det = make_det(tile_size=128, overlap=0.25)
    ds = det.detect(_frame(squares=[(100, 200, 40)]), 0.0)
    assert len(ds) == 1
    assert ds[0].box == pytest.approx([100, 200, 40, 40])  # the whole-square view wins by score


def test_merge_uses_intersection_over_smaller_box():
    big = [0, 0, 100, 100]
    small = [40, 40, 60, 60]  # inside big: IoU is 0.04, intersection over smaller is 1.0
    assert merge_boxes([big, small], [0.9, 0.5]) == [0]
    far = [200, 200, 220, 220]
    assert sorted(merge_boxes([big, small, far], [0.9, 0.5, 0.4])) == [0, 2]
    assert merge_boxes(np.zeros((0, 4)), []) == []


def test_two_separate_fish_stay_two():
    det = make_det(tile_size=128)
    ds = det.detect(_frame(squares=[(10, 10, 40), (300, 250, 40)]), 0.0)
    assert len(ds) == 2


def test_threshold_filters_scores():
    det = make_det(tile_size=640, threshold=0.5)  # one tile, square score = 20*20/1600 = 0.25
    assert det.detect(_frame(squares=[(10, 10, 20)]), 0).__len__() == 0
    det = make_det(tile_size=640, threshold=0.2)
    assert len(det.detect(_frame(squares=[(10, 10, 20)]), 0)) == 1


def test_batching_groups_tiles():
    m = BrightSquareModel()
    det = make_det(model=m, tile_size=128, batch=4)
    det.detect(_frame(), 0)
    n = len(tile_boxes(640, 480, 128, 0.25))
    assert sum(c[0] for c in m.calls) == n and max(c[0] for c in m.calls) == 4


def test_roi_mask_skips_tiles_and_drops_boxes(tmp_path):
    import cv2
    mask = np.zeros((480, 640), np.uint8)
    mask[:, :320] = 255  # analyse the left half only
    cv2.imwrite(str(tmp_path / "roi.png"), mask)
    m = BrightSquareModel()
    det = make_det(model=m, tile_size=128, roi_mask=str(tmp_path / "roi.png"))
    ds = det.detect(_frame(squares=[(50, 50, 40), (500, 300, 40)]), 0)
    assert len(ds) == 1 and ds[0].box[0] < 320
    assert sum(c[0] for c in m.calls) < len(tile_boxes(640, 480, 128, 0.25))
    assert make_det().roi is None  # default off


def test_clahe_changes_pixels_and_none_does_not():
    rng = np.random.default_rng(0)
    f = (rng.random((64, 64, 3)) * 60 + 100).astype(np.uint8)
    assert np.array_equal(cfd.enhance(f, "none"), f)
    assert not np.array_equal(cfd.enhance(f, "clahe"), f)
    with pytest.raises(ValueError):
        cfd.enhance(f, "sharpen")


# ---------------------------------------------------------------- names, config, errors
def test_model_version_and_source_names():
    det = make_det(weights="models/cfd-rf-detr-medium-1024-2026.03.24.cp-011.20260706-release.pth",
                   variant="medium")
    assert det.model_version == "cfd-rf-detr-medium-1024-2026.03.24.cp-011.20260706-release"
    assert det.source == "cfd:medium"


def test_default_config_selects_cfd_and_motion_blob_still_works():
    cfg = load_config()
    assert cfg["stages"]["detector"] == "cfd"
    assert cfg["detector"]["cfd"]["variant"] == "nano" and cfg["detector"]["cfd"]["tile_size"] == 512
    assert cfg["detector"]["cfd"]["threshold"] == 0.05 and cfg["detect_fps_segments"] == 0.2
    mb = get_backend("detector", "motion_blob", cfg)
    assert "standin" in mb.model_version


def test_medium_clahe_preset():
    cfg = load_config(ROOT / "config" / "presets" / "cfd_medium_clahe.yaml")
    c = cfg["detector"]["cfd"]
    assert (c["variant"], c["enhancement"], c["tile_size"], c["threshold"]) == ("medium", "clahe", 512, 0.05)


def test_missing_weights_message_points_to_fetch_script(tmp_path):
    cfg = cfg_with()
    cfg["paths"]["models_dir"] = str(tmp_path)
    with pytest.raises(FileNotFoundError, match="fetch_cfd_weights.py"):
        get_backend("detector", "cfd", cfg)
    cfg = cfg_with(weights=str(tmp_path / "nope.pth"))
    with pytest.raises(FileNotFoundError, match="fetch_cfd_weights.py"):
        get_backend("detector", "cfd", cfg)


def test_missing_rfdetr_gives_clear_error(tmp_path, monkeypatch):
    w = tmp_path / "cfd-rf-detr-nano-640-x.pth"
    w.write_bytes(b"x")
    monkeypatch.setitem(sys.modules, "rfdetr", None)  # makes `import rfdetr` fail, even if installed
    with pytest.raises(ModelUnavailable, match="requirements-model.txt"):
        get_backend("detector", "cfd", cfg_with(weights=str(w), device="cpu"))


def test_cli_reports_missing_model_without_traceback(tmp_path, monkeypatch, capsys):
    clip = make(tmp_path / "c.mp4", duration=20, width=320, fps=10)
    monkeypatch.setattr(cfd, "find_weights", lambda *a, **k: (_ for _ in ()).throw(
        FileNotFoundError("No CFD weights. Run: python tools/fetch_cfd_weights.py")))
    rc = cli.main(["run", str(clip), "--out", str(tmp_path / "runs"), "--layer", "1", "--window-start", "2",
                   "--window-end", "18"])
    assert rc == 1 and "fetch_cfd_weights.py" in capsys.readouterr().err


def test_base_install_never_imports_torch_or_rfdetr():
    code = ("import sys, clipsift.stages, clipsift.pipeline; "
            "assert 'torch' not in sys.modules and 'rfdetr' not in sys.modules, 'heavy import'")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------- review order and status
def _ss(dets, motion):
    ss = Subsample("ss_01", 10, 5, 15)
    ss.auto.update(detections=dets, motion_near_point=motion, fish_count=len(dets))
    return ss


def test_review_order_mid_confidence_and_disagreement_first():
    rc = load_config()["review"]
    d = lambda s: Detection(t=0, box=[0, 0, 1, 1], score=s)  # noqa: E731
    mid = review_priority_subsample(_ss([d(0.3)], True), rc, True)
    high = review_priority_subsample(_ss([d(0.9)], True), rc, True)
    disagree = review_priority_subsample(_ss([], True), rc, True)
    quiet = review_priority_subsample(_ss([], False), rc, True)
    assert mid > high and disagree > quiet and mid > quiet
    qc = _ss([d(0.9)], True)
    qc.qc_sample = True
    assert review_priority_subsample(qc, rc, True) >= 0.95 > max(mid, disagree)


def test_status_rules():
    d = Detection(t=0, box=[0, 0, 1, 1], score=0.3)
    assert subsample_status(_ss([d], False).auto) == "fish_unknown"
    assert subsample_status(_ss([], True).auto) == "movement_unidentified"
    assert subsample_status(_ss([], False).auto) == "none"


# ---------------------------------------------------------------- pipeline with a fake model
class _AlwaysBoxModel:
    """One box at the top-left of every tile, score 0.3 (mid-confidence)."""
    device = "fake"

    def __init__(self):
        self.frames = 0

    def infer(self, tiles, threshold):
        return [(np.array([[5.0, 5.0, 25.0, 25.0]]), np.array([0.3])) for _ in tiles]


class _NothingModel:
    device = "fake"

    def infer(self, tiles, threshold):
        return [(np.zeros((0, 4)), np.zeros(0)) for _ in tiles]


@register("detector", "fake_cfd_boxes")
class FakeCfdBoxes(CfdDetector):
    def __init__(self, cfg):
        super().__init__(cfg, model=_AlwaysBoxModel(), weights=Path("cfd-rf-detr-nano-fake.pth"))


@register("detector", "fake_cfd_empty")
class FakeCfdEmpty(CfdDetector):
    def __init__(self, cfg):
        super().__init__(cfg, model=_NothingModel(), weights=Path("cfd-rf-detr-nano-fake.pth"))


SMALL = {"protocol": {"trim_start_s": 2, "trim_end_s": 2, "window_length_s": 50, "interval_s": 10, "context_s": 2},
         "detector": {"cfd": {"tile_size": 256}}, "layer": 1}


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    return make(tmp_path_factory.mktemp("cfd") / "syn.mp4", duration=60, width=480, fps=10)


def _run(clip, tmp_path, backend):
    cfg = load_config(overrides={**SMALL, "stages": {"detector": backend}})
    d = run([clip], cfg, tmp_path, log=lambda *a: None)
    return json.loads((d / "results.json").read_text())


def test_pipeline_subsample_suggestions_from_stills(clip, tmp_path):
    r = _run(clip, tmp_path, "fake_cfd_boxes")
    assert validate(r) == []
    n_tiles = len(tile_boxes(r["recording"]["width"], r["recording"]["height"], 256, 0.25))
    assert r["run"]["model_version"] == "cfd-rf-detr-nano-fake"
    for s in r["subsamples"]:
        a = s["auto"]
        assert a["fish_count"] == n_tiles == len(a["detections"])
        assert a["invertebrate_count"] is None
        assert {x["source"] for x in a["detections"]} == {"cfd:nano"}
        assert all(len(x["box"]) == 4 and 0 < x["score"] <= 1 for x in a["detections"])
        assert a["status"] == "fish_unknown"
    assert r["summary"]["mean_count_auto"] == n_tiles
    assert r["summary"]["mean_count_reviewed"] is None  # a suggestion is never a final count
    rt = r["run"]["stage_runtimes_s"]
    assert {"subsample_detect", "segment_detect", "subsample_media", "motion_scan"} <= set(rt)


def test_pipeline_segment_pass_is_sparse(clip, tmp_path):
    r = _run(clip, tmp_path, "fake_cfd_boxes")
    n_tiles = len(tile_boxes(r["recording"]["width"], r["recording"]["height"], 256, 0.25))
    active = [s for s in r["segments"] if s["kind"] == "active"]
    assert active
    for s in active:
        dur = s["end_s"] - s["start_s"]
        frames = len({x["t"] for x in s["detections"]})
        assert 1 <= frames <= int(dur * 0.2) + 1          # at most one frame per 5 s, not every sample
        assert len(s["detections"]) == frames * n_tiles
        assert s["status"] == "fish_unknown" and s["tracks"] == []
        assert s["counts"]["unique_tracks"] is None and s["counts"]["maxn"] == n_tiles


def test_pipeline_motion_without_detections_stays_movement_unidentified(clip, tmp_path):
    r = _run(clip, tmp_path, "fake_cfd_empty")
    active = [s for s in r["segments"] if s["kind"] == "active"]
    assert active and all(s["status"] == "movement_unidentified" for s in active)  # never dropped
    assert all(s["auto"]["fish_count"] == 0 and s["auto"]["detections"] == [] for s in r["subsamples"])
    assert r["summary"]["mean_count_auto"] == 0
    assert {s["auto"]["status"] for s in r["subsamples"]} <= {"movement_unidentified", "none"}


# ---------------------------------------------------------------- real model smoke test
def _real_available():
    try:
        import rfdetr  # noqa: F401
    except Exception:
        return False
    try:
        cfd.find_weights({"variant": "nano"}, ROOT / "models")
    except FileNotFoundError:
        return False
    return (ROOT / "labels/verified/T1-STAT2_411_t1320.303.png").is_file()


@pytest.mark.skipif(not _real_available(), reason="rfdetr or CFD weights not available")
def test_real_model_smoke():
    import cv2
    img = cv2.imread(str(ROOT / "labels/verified/T1-STAT2_411_t1320.303.png"))
    crop = img[250:1000, 1500:2600]
    det = get_backend("detector", "cfd", load_config(overrides={"detector": {"cfd": {"device": "cpu"}}}))
    ds = det.detect(crop, 0.0)
    assert det.source == "cfd:nano" and det.model_version.startswith("cfd-rf-detr-nano")
    assert len(ds) > 0  # a dense school region; the one-frame test found many boxes here
    h, w = crop.shape[:2]
    for d in ds:
        x, y, bw, bh = d.box
        assert -1 <= x and -1 <= y and x + bw <= w + 1 and y + bh <= h + 1 and 0.05 <= d.score <= 1
