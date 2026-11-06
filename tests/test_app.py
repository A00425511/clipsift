"""Tests for the review app. Uses Flask's test client and a generated fixture run."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.fixtures.make_fixture import build  # noqa: E402
from app.server import create_app, percent_difference  # noqa: E402


@pytest.fixture(scope="module")
def runs_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("runs")
    build(root)
    return root


@pytest.fixture()
def env(runs_root, tmp_path):
    species = tmp_path / "species_list.json"
    species.write_text(json.dumps([{"scientific_name": "Salmo salar", "common_names": ["Atlantic salmon"],
                                    "aliases": ["grilse"], "flags": {"at_risk": True}}]))
    aliases = tmp_path / "aliases.jsonl"
    app = create_app(runs_root, species_path=species, aliases_path=aliases)
    run = runs_root / "_fixture"
    for name in ("reviews.jsonl", "grid_tags.jsonl", "subsample_reviews.jsonl", "recording_notes.jsonl", "point_labels.jsonl"):
        (run / name).unlink(missing_ok=True)
    return app.test_client(), run, species, aliases


R = "/api/runs/_fixture"


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def test_list_runs_and_results(env):
    c, *_ = env
    runs = c.get("/api/runs").get_json()["runs"]
    assert runs[0]["run_id"] == "_fixture" and runs[0]["fixture"] is True
    res = c.get(R + "/results").get_json()
    assert res["schema_version"] == "0.2" and len(res["segments"]) == 12 and len(res["subsamples"]) == 9
    assert c.get("/api/runs/nope/results").status_code == 404
    assert c.get("/").status_code == 200


def test_static_page_has_no_external_urls():
    html = (Path(__file__).resolve().parents[1] / "app" / "static" / "index.html").read_text()
    assert "http://" not in html and "https://" not in html


def test_files_and_missing_files(env):
    c, *_ = env
    assert c.get(R + "/segments/seg_0001/still").mimetype == "image/jpeg"
    assert c.get(R + "/segments/seg_0001/diff").status_code == 200
    assert c.get(R + "/subsamples/ss_01/context").mimetype == "video/mp4"
    assert c.get(R + "/segments/seg_0011/loop").status_code == 404  # missing loop
    assert c.get(R + "/segments/seg_0012/still").status_code == 404  # missing folder
    assert c.get(R + "/subsamples/ss_06/context").status_code == 404
    assert c.get(R + "/subsamples/ss_07/diff").status_code == 404
    assert c.get(R + "/segments/seg_0001/results").status_code == 404  # not an allowed name


@pytest.mark.parametrize("path", [
    "/api/runs/..%2F/results", "/api/runs/%2e%2e/results", "/api/runs/_fixture/segments/..%2F..%2Fresults.json/still",
    "/api/runs/_fixture/segments/%2e%2e/still", "/api/runs/_fixture/segments/seg_0001/..%2Fstill.jpg",
    "/api/runs/_fixture/subsamples/..%2F/still", "/api/runs/.git/results",
])
def test_path_traversal_rejected(env, path):
    c, *_ = env
    assert c.get(path).status_code in (308, 400, 404)  # 308 = Flask tidied the path; nothing served


def test_symlink_out_of_run_blocked(env, tmp_path):
    c, run, *_ = env
    secret = tmp_path / "secret.jpg"
    secret.write_bytes(b"secret")
    link = run / "segments" / "seg_0012"
    link.mkdir(exist_ok=True)
    target = link / "still.jpg"
    try:
        target.symlink_to(secret)
    except OSError:
        pytest.skip("symlinks not available")
    try:
        assert c.get(R + "/segments/seg_0012/still").status_code == 404
    finally:
        target.unlink()
        link.rmdir()


def test_range_support(env):
    c, *_ = env
    full = c.get(R + "/segments/seg_0001/loop")
    size = len(full.data)
    r = c.get(R + "/segments/seg_0001/loop", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.data) == 100
    assert r.headers["Content-Range"] == f"bytes 0-99/{size}"
    assert full.headers.get("Accept-Ranges") == "bytes"
    r2 = c.get(R + "/subsamples/ss_01/context", headers={"Range": "bytes=-50"})
    assert r2.status_code == 206 and len(r2.data) == 50


def test_review_append_only_and_validation(env):
    c, run, *_ = env
    body = {"segment_id": "seg_0001", "decision": "confirm", "species": "Salmo salar", "count": 2,
            "reviewer": "T", "contrast_settings": {"brightness": 120, "contrast": 150, "saturation": 80, "enhance": "silhouette"}}
    assert c.post(R + "/reviews", json=body).status_code == 201
    first = (run / "reviews.jsonl").read_text()
    assert c.post(R + "/reviews", json={**body, "decision": "reject"}).status_code == 201
    text = (run / "reviews.jsonl").read_text()
    assert text.startswith(first) and len(lines(run / "reviews.jsonl")) == 2  # earlier line untouched
    assert lines(run / "reviews.jsonl")[0]["contrast_settings"]["contrast"] == 150
    assert lines(run / "reviews.jsonl")[0]["contrast_settings"]["enhance"] == "silhouette"
    bad = [{"segment_id": "seg_0001", "decision": "maybe"}, {"segment_id": "nope", "decision": "confirm"},
           {"segment_id": "../x", "decision": "confirm"}, {"segment_id": "seg_0001", "decision": "confirm", "count": -1},
           {"segment_id": "seg_0001", "decision": "confirm", "count": "3"},
           {"segment_id": "seg_0001", "decision": "confirm", "contrast_settings": {"brightness": 9999}},
           {"segment_id": "seg_0001", "decision": "confirm", "contrast_settings": {"enhance": "sparkle"}},
           {"segment_id": "seg_0001", "decision": "confirm", "note": "x" * 5000}]
    for b in bad:
        assert c.post(R + "/reviews", json=b).status_code == 400, b
    assert c.post(R + "/reviews", data="x", content_type="text/plain").status_code == 400
    assert len(lines(run / "reviews.jsonl")) == 2
    saved = c.get(R + "/saved").get_json()
    assert len(saved["reviews"]) == 2 and saved["latest_review"]["seg_0001"]["decision"] == "reject"


def test_grid_tags(env):
    c, run, *_ = env
    ok = {"segment_id": "seg_0001", "grid": [3, 6], "cell": [2, 5], "count": 1, "species": None}
    assert c.post(R + "/grid_tags", json=ok).status_code == 201
    assert c.post(R + "/grid_tags", json={**ok, "subsample_id": "ss_01", "segment_id": None}).status_code == 201
    for b in [{**ok, "cell": [3, 0]}, {**ok, "grid": [0, 4]}, {**ok, "count": 0}, {**ok, "cell": [0]}, {**ok, "grid": [99, 4]}]:
        assert c.post(R + "/grid_tags", json=b).status_code == 400, b
    assert len(lines(run / "grid_tags.jsonl")) == 2
    assert len(c.get(R + "/saved").get_json()["grid_tags"]) == 2


SUB = {"subsample_id": "ss_01", "counter": "Ana", "pass": "primary", "total_fish_count": 10,
       "invertebrate_count": 1, "species_counts": {"Salmo salar": 10}, "unknown_count": 0,
       "characteristics": ["shape", "swimming_behaviour"], "visibility_category": "0.5-1.0 m", "notes": ""}


def test_subsample_reviews_qc_and_meancount(env):
    c, run, *_ = env
    assert c.post(R + "/subsample_reviews", json=SUB).status_code == 201
    assert c.post(R + "/subsample_reviews", json={**SUB, "subsample_id": "ss_02", "total_fish_count": 20}).status_code == 201
    # blind second counter: 10+1 vs 10+4 -> clearly over the limit
    assert c.post(R + "/subsample_reviews", json={**SUB, "counter": "Ben", "pass": "qc_blind", "invertebrate_count": 4}).status_code == 201
    saved = c.get(R + "/saved").get_json()
    assert saved["mean_count_reviewed"] == 15 and saved["n_counted"] == 2 and saved["n_subsamples"] == 9
    qc = saved["qc"]["ss_01"]
    assert qc["recount_needed"] is True and qc["second_counter"] == "Ben" and qc["percent_diff"] > 6
    assert len(lines(run / "subsample_reviews.jsonl")) == 3
    bad = [{**SUB, "counter": ""}, {**SUB, "pass": "other"}, {**SUB, "total_fish_count": None}, {**SUB, "total_fish_count": -1},
           {**SUB, "characteristics": ["colour"]}, {**SUB, "visibility_category": "murky"}, {**SUB, "subsample_id": "ss_99"},
           {**SUB, "species_counts": {"x": "many"}}]
    for b in bad:
        assert c.post(R + "/subsample_reviews", json=b).status_code == 400, b
    assert len(lines(run / "subsample_reviews.jsonl")) == 3


def test_percent_difference_function():
    assert percent_difference(0, 0) == 0
    assert percent_difference(10, 10) == 0
    assert percent_difference(10, None) is None
    assert round(percent_difference(11, 14), 1) == 24.0


def test_point_labels_add_undo_append_only(env):
    c, run, *_ = env
    base = {"subsample_id": "ss_02", "counter": "Ana", "kind": "fish", "x": 120.4, "y": 200}
    a = c.post(R + "/point_labels", json=base).get_json()
    b = c.post(R + "/point_labels", json={**base, "kind": "invertebrate", "shape": "ellipse", "w": 40, "h": 20, "species": "crab"}).get_json()
    assert a["label_id"] != b["label_id"] and b["w"] == 40
    before = (run / "point_labels.jsonl").read_text()
    assert c.post(R + "/point_labels", json={"subsample_id": "ss_02", "counter": "Ana", "op": "remove", "label_id": a["label_id"]}).status_code == 201
    assert (run / "point_labels.jsonl").read_text().startswith(before)  # undo appends, never edits
    assert len(lines(run / "point_labels.jsonl")) == 3
    active = c.get(R + "/saved").get_json()["point_labels"]
    assert [l["label_id"] for l in active] == [b["label_id"]]
    bad = [{**base, "kind": "bird"}, {**base, "x": -1}, {**base, "x": "5"}, {**base, "shape": "ellipse"},
           {**base, "shape": "blob", "w": 1, "h": 1}, {**base, "counter": " "}, {**base, "subsample_id": "ss_77"},
           {"subsample_id": "ss_02", "counter": "Ana", "op": "remove", "label_id": a["label_id"]},  # already removed
           {**base, "op": "wipe"}]
    for x in bad:
        assert c.post(R + "/point_labels", json=x).status_code == 400, x
    assert len(lines(run / "point_labels.jsonl")) == 3


def test_recording_notes(env):
    c, run, *_ = env
    n = {"window_start_s": 60, "window_end_s": 540, "species_observed": ["Gasterosteus aculeatus"], "juveniles": 1,
         "visibility_by_observer": [{"observer": "Ana", "category": ">1.5 m"}], "notes": "ok"}
    assert c.post(R + "/recording_notes", json=n).status_code == 201
    assert c.post(R + "/recording_notes", json={**n, "juveniles": 2}).status_code == 400
    assert c.post(R + "/recording_notes", json={**n, "window_end_s": 10}).status_code == 400
    assert c.post(R + "/recording_notes", json={**n, "visibility_by_observer": [{"observer": "A", "category": "x"}]}).status_code == 400
    assert c.get(R + "/saved").get_json()["latest_recording_notes"]["juveniles"] == 1
    assert len(lines(run / "recording_notes.jsonl")) == 1


def test_species_list_and_local_aliases(env):
    c, _, species, aliases = env
    before = species.read_text()
    d = c.get("/api/species").get_json()
    assert d["species"][0]["scientific_name"] == "Salmo salar" and d["local_aliases"] == []
    assert c.post("/api/species/aliases", json={"alias": "silver", "maps_to": "Salmo salar"}).status_code == 201
    assert c.post("/api/species/aliases", json={"alias": "", "maps_to": "Salmo salar"}).status_code == 400
    assert c.post("/api/species/aliases", json={"alias": "x", "maps_to": None}).status_code == 400
    assert species.read_text() == before  # the list itself is never written
    assert len(lines(aliases)) == 1 and c.get("/api/species").get_json()["local_aliases"][0]["alias"] == "silver"


def test_species_missing_or_broken_gives_empty_list(runs_root, tmp_path):
    app = create_app(runs_root, species_path=tmp_path / "none.json", aliases_path=tmp_path / "a.jsonl")
    assert app.test_client().get("/api/species").get_json()["species"] == []
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    app = create_app(runs_root, species_path=broken, aliases_path=tmp_path / "a.jsonl")
    d = app.test_client().get("/api/species").get_json()
    assert d["species"] == [] and d["note"]


def test_csv_exports(env):
    c, *_ = env
    c.post(R + "/subsample_reviews", json={**SUB, "notes": "=HYPERLINK(1)"})
    c.post(R + "/reviews", json={"segment_id": "seg_0004", "decision": "unknown", "note": "+bad"})
    sub = c.get(R + "/export.csv")
    assert sub.mimetype == "text/csv"
    head, row = sub.get_data(as_text=True).splitlines()[:2]
    assert "Total fish count" in head and "Count: Salmo salar" in head and "'=HYPERLINK(1)" in row
    summ = c.get(R + "/export_summary.csv").get_data(as_text=True)
    assert "MeanCount" in summ and "Relative index" not in summ and "relative index" in summ
    seg = c.get(R + "/export_segments.csv").get_data(as_text=True)
    assert "seg_0004" in seg and "seg_0001" not in seg and "'+bad" in seg
    assert "seg_0001" in c.get(R + "/export_segments.csv?all=1").get_data(as_text=True)
    cols = c.get(R + "/export_columns.csv").get_data(as_text=True)
    assert "not abundance" in cols


def test_empty_run_exports_and_saved(runs_root, tmp_path):
    root = tmp_path / "r"
    (root / "empty").mkdir(parents=True)
    (root / "empty" / "results.json").write_text(json.dumps({"segments": []}))
    (root / "bad").mkdir()
    (root / "bad" / "results.json").write_text("{nope")
    c = create_app(root, species_path=tmp_path / "x", aliases_path=tmp_path / "a").test_client()
    runs = {r["run_id"]: r for r in c.get("/api/runs").get_json()["runs"]}
    assert runs["empty"]["n_segments"] == 0 and runs["bad"]["error"]
    assert c.get("/api/runs/bad/results").status_code == 422
    s = c.get("/api/runs/empty/saved").get_json()
    assert s["reviews"] == [] and s["mean_count_reviewed"] is None
    assert c.get("/api/runs/empty/export.csv").status_code == 200
    assert c.get("/api/runs/empty/export_summary.csv").status_code == 200
    assert create_app(tmp_path / "nonexistent").test_client().get("/api/runs").get_json()["runs"] == []


def test_feedback_route(env, runs_root):
    c, *_ = env
    fb = runs_root / "feedback.jsonl"
    fb.unlink(missing_ok=True)
    good = {"name": "Sam", "area": "Help", "type": "Idea", "message": "Add a legend <b>please</b>", "page_context": {"run": "_fixture", "view": "simple"}}
    r = c.post("/api/feedback", json=good)
    assert r.status_code == 201 and r.get_json()["ok"] is True
    saved = lines(fb)
    assert len(saved) == 1 and saved[0]["message"] == good["message"] and saved[0]["created_at"] and saved[0]["id"]
    assert saved[0]["page_context"]["run"] == "_fixture"
    for bad in ({**good, "message": ""}, {**good, "message": "x" * 2001}, {**good, "name": "n" * 61},
                {**good, "area": "Nope"}, {**good, "type": "Rant"}, {**good, "page_context": 5}):
        assert c.post("/api/feedback", json=bad).status_code == 400
    assert c.post("/api/feedback", json={**good, "message": "x" * 2000, "name": "n" * 60}).status_code == 201
    assert c.post("/api/feedback", data="x").status_code == 400  # not JSON
    n = len(lines(fb))
    assert c.post("/api/feedback", json={**good, "website": "spam"}).status_code == 201  # honeypot: accepted, not stored
    assert len(lines(fb)) == n
    assert c.get("/api/feedback").status_code == 405  # no reading feedback back through the app
    fb.unlink(missing_ok=True)


def test_model_suggestions_toggle_is_simple_view_and_off_by_default():
    static = Path(__file__).resolve().parents[1] / "app" / "static"
    html, js = (static / "index.html").read_text(), (static / "app.js").read_text()
    assert 'id="show-boxes"' not in html and "Detection boxes</label>" not in html          # replaced, not doubled
    tag = html[html.index('id="suggest-toggle"') - 30: html.index('id="suggest-toggle"') + 200]
    assert 'id="show-suggest"' in tag and "Show model suggestions" in tag and " adv" not in tag.split("id=\"show-suggest\"")[0]  # not hidden in More tools
    assert "checked" not in html[html.index('id="show-suggest"'): html.index('id="show-suggest"') + 40]
    assert "Rough suggestions. The model flags seafloor and the pipe, and isn't trained on this water." in html
    assert "boxes: false" in js and "S.boxes = false; paintSuggestToggle();" in js           # off at every run load
    assert "localStorage.setItem(\"clipsift.boxes\"" not in js and "clipsift.suggest" not in js   # never stored
    assert "cb.disabled = blocked" in js                                                      # QC mode: toggle disabled
