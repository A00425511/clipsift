import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clipsift.evaluate import evaluate, format_report, parse_time
from test_pipeline_schema import make_results


def write(tmp, rows):
    p = tmp / "labels.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return p


def results_file(tmp):
    r = make_results()
    r.protocol["interval_s"] = 8
    r.subsamples[0].auto["fish_count"] = 4
    r.segments[0].counts.maxn = 3
    p = tmp / "results.json"
    p.write_text(json.dumps(r.to_dict()))
    return p


def test_parse_time():
    assert parse_time("14:00") == 840 and parse_time("1:02:03") == 3723 and parse_time("90") == 90


def test_subsample_rows(tmp_path):
    lab = write(tmp_path, [{"Video ID": "GX0221_T1", "Timestamp": "0:03", "Total Fish Count A": 6, "Total Fish Count B": 5}])
    rep = evaluate(results_file(tmp_path), lab)
    assert rep["kind"] == "subsample"
    assert rep["model"]["bias"] == -2 and rep["model"]["mae"] == 2
    assert rep["human_vs_human"]["bias_a_minus_b"] == 1
    assert any("Small sample" in n for n in rep["notes"])
    assert "signed bias" in format_report(rep)


def test_segment_rows_and_unmatched(tmp_path):
    lab = write(tmp_path, [{"recording_id": "r", "start_s": 2, "end_s": 4, "maxn": 1, "count": 1},
                           {"recording_id": "r", "start_s": 50, "end_s": 60, "maxn": 1, "count": 1}])
    rep = evaluate(results_file(tmp_path), lab)
    assert rep["kind"] == "segment" and rep["maxn"]["bias"] == 2 and rep["n_unmatched_label_rows"] == 1


def test_null_model_values_skipped(tmp_path):
    r = make_results()
    r.protocol["interval_s"] = 8
    p = tmp_path / "r.json"
    p.write_text(json.dumps(r.to_dict()))
    lab = write(tmp_path, [{"Video ID": "GX0221_T1", "Timestamp": "3", "Total Fish Count": 6}])
    rep = evaluate(p, lab)
    assert rep["model"]["n"] == 0 and rep["n_model_missing"] == 1
