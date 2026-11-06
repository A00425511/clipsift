import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from clipsift import cli
from clipsift.config import load_config
from clipsift.pipeline import run
from clipsift.schema import validate
from make_synthetic_clip import make

SMALL = {"protocol": {"trim_start_s": 2, "trim_end_s": 2, "window_length_s": 50, "interval_s": 10, "context_s": 2}}


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    d = tmp_path_factory.mktemp("syn")
    p = make(d / "syn.mp4", duration=60, width=480, fps=10)
    return p, json.loads(p.with_suffix(".json").read_text())


def _run(clip, tmp_path, layer):
    # motion_blob is explicit here: the default Layer 1 detector is now the CFD model backend
    cfg = load_config(overrides={**SMALL, "layer": layer, "stages": {"detector": "motion_blob"}})
    d = run([clip[0]], cfg, tmp_path, log=lambda *a: None)
    return d, json.loads((d / "results.json").read_text())


def test_layer0(clip, tmp_path):
    d, r = _run(clip, tmp_path, 0)
    assert validate(r) == []
    assert r["run"]["layer"] == 0 and r["run"]["model_version"] is None
    assert len(r["subsamples"]) == 5
    assert all(s["auto"]["fish_count"] is None for s in r["subsamples"])
    assert all(s["counts"]["maxn"] is None for s in r["segments"])
    for s in r["subsamples"]:
        for f in ("still.jpg", "diff.jpg", "context.mp4"):
            assert (d / "subsamples" / s["subsample_id"] / f).stat().st_size > 0
    for s in r["segments"]:
        if s["kind"] == "active" or s["audit_sample"]:
            assert (d / "segments" / s["segment_id"] / "loop.mp4").exists()
    assert {"subsample_media", "subsample_pass", "motion_scan"} <= set(r["run"]["stage_runtimes_s"])
    # set-aside time is recorded, never deleted: segments tile the window
    segs = r["segments"]
    assert segs[0]["start_s"] == pytest.approx(r["protocol"]["window_start_s"], abs=0.01)
    assert segs[-1]["end_s"] == pytest.approx(r["protocol"]["window_end_s"], abs=0.01)


def test_slow_blob_not_set_aside(clip, tmp_path):
    _, r = _run(clip, tmp_path, 0)
    crab = next(e for e in clip[1]["events"] if e["slow"])
    mid = (crab["start_s"] + min(crab["end_s"], r["protocol"]["window_end_s"])) / 2
    seg = next(s for s in r["segments"] if s["start_s"] <= mid <= s["end_s"])
    assert seg["kind"] == "active"


def test_layer1_motion_blob(clip, tmp_path):
    d, r = _run(clip, tmp_path, 1)
    assert validate(r) == []
    assert "standin" in r["run"]["model_version"]
    srcs = {x["source"] for s in r["segments"] for x in s["detections"]}
    assert srcs == {"motion_blob"}
    assert any(s["counts"]["maxn"] for s in r["segments"])
    assert all(s["auto"]["invertebrate_count"] is None for s in r["subsamples"])


def test_cli_and_export(clip, tmp_path):
    out = tmp_path / "runs"
    # default protocol trims 60 s from a 60 s clip: expect a clear error, not a crash
    assert cli.main(["run", str(clip[0]), "--out", str(out), "--layer", "0"]) == 1
    import yaml
    cfgp = tmp_path / "small.yaml"
    cfgp.write_text(yaml.safe_dump(SMALL))
    assert cli.main(["run", str(clip[0]), "--out", str(out), "--layer", "0", "--config", str(cfgp),
                     "--window-start", "2", "--window-end", "52"]) == 0
    run_dir = out / "syn"
    assert validate(json.loads((run_dir / "results.json").read_text())) == []
    (run_dir / "subsample_reviews.jsonl").write_text(
        json.dumps({"subsample_id": "ss_01", "counter": "A", "pass": "primary", "total_fish_count": 2,
                    "invertebrate_count": 0, "species_counts": {}, "unknown_count": 0}) + "\n"
        + json.dumps({"subsample_id": "ss_01", "counter": "B", "pass": "qc_blind", "total_fish_count": 3}) + "\n")
    assert cli.main(["export", str(run_dir)]) == 0
    import csv
    rows = list(csv.DictReader(open(run_dir / "export" / "syn_subsamples.csv")))
    assert rows[0]["Total Fish Count"] == "2" and rows[0]["QC Percent Difference"] != ""
    assert rows[1]["Total Fish Count"] == ""
    assert "not abundance" in (run_dir / "export" / "syn_columns.md").read_text()
