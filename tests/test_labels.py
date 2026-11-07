"""Tests for blind label mode: Flask routes, make_label_set, build_demo --label-set, pull_labels, label.js helpers."""
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import build_demo  # noqa: E402
import make_label_set  # noqa: E402
import pull_labels  # noqa: E402
from app.server import create_app  # noqa: E402

SET = "t1"


def make_set(root: Path, set_id=SET, n=3, width=1000, height=500):
    d = root / set_id
    (d / "frames").mkdir(parents=True)
    (d / "clips").mkdir()
    (d / "diff").mkdir()
    frames = []
    for i in range(n):
        fid = f"f{i}"
        (d / "frames" / f"{fid}.jpg").write_bytes(b"\xff\xd8jpg" + bytes(50))
        (d / "clips" / f"{fid}.mp4").write_bytes(bytes(range(100)))
        (d / "diff" / f"{fid}.jpg").write_bytes(b"\xff\xd8diff" + bytes(50))
        frames.append({"frame_id": fid, "time_s": 60 + 20 * i, "width": width, "height": height,
                       "frame_url": f"/label_sets/{set_id}/frames/{fid}.jpg", "clip_url": f"/label_sets/{set_id}/clips/{fid}.mp4",
                       "diff_url": f"/label_sets/{set_id}/diff/{fid}.jpg", "clip_start_s": 55 + 20 * i, "clip_length_s": 10.0, "clip_count_s": 5.0})
    (d / "manifest.json").write_text(json.dumps({"set_id": set_id, "video": "x.MP4", "frames": frames}))
    return d


@pytest.fixture()
def client(tmp_path):
    sets = tmp_path / "label_sets"
    make_set(sets)
    app = create_app(tmp_path / "runs", species_path=tmp_path / "s.json", aliases_path=tmp_path / "a.jsonl",
                     label_sets_dir=sets, labels_path=tmp_path / "labels.jsonl")
    return app.test_client(), tmp_path


def save(c, **kw):
    body = {"set": SET, "frame": "f0", "name": "Jacob", "points": [{"x": 10, "y": 20, "kind": "fish"}], "seconds": 5}
    body.update(kw)
    return c.post("/api/labels", json=body)


def test_label_page_and_files(client):
    c, _ = client
    assert c.get("/label.html").status_code == 200
    assert c.get("/static/label.js").status_code == 200 and c.get("/static/label.css").status_code == 200
    assert c.get("/label_sets/index.json").get_json() == {"sets": [SET]}
    assert c.get(f"/label_sets/{SET}/manifest.json").get_json()["frames"][0]["frame_id"] == "f0"
    assert c.get(f"/label_sets/{SET}/frames/f0.jpg").status_code == 200
    assert c.get(f"/label_sets/{SET}/diff/f0.jpg").status_code == 200   # the Movement view image
    r = c.get(f"/label_sets/{SET}/clips/f0.mp4", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206 and r.headers["Content-Range"] == "bytes 10-19/100" and r.data == bytes(range(10, 20))
    for bad in (f"/label_sets/{SET}/frames/../manifest.json", f"/label_sets/{SET}/frames/nope.jpg", f"/label_sets/{SET}/other/f0.jpg", "/label_sets/..%2fx/manifest.json"):
        assert c.get(bad).status_code in (400, 404)


def test_main_app_links_to_label_page():
    html = (ROOT / "app" / "static" / "index.html").read_text()
    assert 'href="/label.html"' in html and "Label fish" in html
    page = (ROOT / "app" / "static" / "label.html").read_text()
    assert "http://" not in page and "https://" not in page and "style=" not in page  # no inline styles: CSP


def test_save_read_back_upsert_and_case(client):
    c, tmp = client
    assert save(c).status_code == 200
    assert c.get(f"/api/labels/mine?set={SET}&frame=f0&name=jacob").get_json()["points"] == [{"x": 10, "y": 20, "kind": "fish"}]
    assert c.get(f"/api/labels/mine?set={SET}&frame=f0&name=Ali").get_json() == {"exists": False}
    assert save(c, name="JACOB", points=[{"x": 1, "y": 2, "kind": "invertebrate"}]).status_code == 200
    mine = c.get(f"/api/labels/mine?set={SET}&frame=f0&name=Jacob").get_json()
    assert mine["points"] == [{"x": 1, "y": 2, "kind": "invertebrate"}] and mine["exists"] is True
    st = c.get(f"/api/labels/status?set={SET}&name=Jacob").get_json()
    assert st["counts"] == {"f0": 1} and st["mine"]["f0"]["state"] == "done" and st["total"] == 3


def test_species_and_views_are_cleaned_and_read_back(client):
    c, tmp = client
    pts = [{"x": 1, "y": 2, "kind": "fish", "species": "  Gadus \x07 morhua\n "}, {"x": 3, "y": 4, "kind": "invertebrate", "species": "   "},
           {"x": 5, "y": 6, "kind": "fish", "species": None}, {"x": 7, "y": 8, "kind": "fish"}]
    assert save(c, points=pts, views=["clip", "frame", "movement", "frame"]).status_code == 200
    mine = c.get(f"/api/labels/mine?set={SET}&frame=f0&name=Jacob").get_json()
    assert mine["points"][0] == {"x": 1, "y": 2, "kind": "fish", "species": "Gadus morhua"}
    assert all("species" not in p for p in mine["points"][1:])      # blank or null species is dropped
    assert mine["views"] == ["frame", "movement", "clip"]            # fixed order, no repeats
    assert save(c, points=[{"x": 1, "y": 1, "kind": "fish", "species": "x" * 80}]).status_code == 200   # the limit is inclusive
    assert save(c).status_code == 200 and c.get(f"/api/labels/mine?set={SET}&frame=f0&name=Jacob").get_json()["views"] == []  # older clients send none


@pytest.mark.parametrize("patch", [
    {"points": [{"x": 1, "y": 1, "kind": "fish", "species": "x" * 81}]}, {"points": [{"x": 1, "y": 1, "kind": "fish", "species": 5}]},
    {"points": [{"x": 1, "y": 1, "kind": "fish", "species": ["a"]}]},
    {"views": ["frame", "zoom"]}, {"views": "frame"}, {"views": [1]}, {"views": ["frame"] * 11},
])
def test_species_and_views_validation(client, patch):
    c, tmp = client
    assert save(c, **patch).status_code == 400
    assert not (tmp / "labels.jsonl").exists()


def test_not_fish_marks_are_validated_and_read_back(client):
    c, tmp = client
    pts = [{"x": 1, "y": 2, "kind": "not_fish", "category": "algae"}, {"x": 3, "y": 4, "kind": "not_fish"}, {"x": 5, "y": 6, "kind": "not_fish", "category": "", "species": "Gadus"},
           {"x": 7, "y": 8, "kind": "fish", "category": "algae"}]
    assert save(c, points=pts).status_code == 200
    got = c.get("/api/labels/mine?set=t1&frame=f0&name=Jacob").get_json()["points"]
    assert got == [{"x": 1, "y": 2, "kind": "not_fish", "category": "algae"}, {"x": 3, "y": 4, "kind": "not_fish"}, {"x": 5, "y": 6, "kind": "not_fish"}, {"x": 7, "y": 8, "kind": "fish"}]
    for cat in ("Algae", "weed", 5, ["algae"]):
        assert save(c, points=[{"x": 1, "y": 1, "kind": "not_fish", "category": cat}]).status_code == 400
    assert save(c, points=[{"x": 1, "y": 1, "kind": "other"}]).status_code == 400
    # only Not fish marks is an ordinary labelled frame; with No animals it is still refused
    assert save(c, points=[pts[0]], no_animals=False).status_code == 200
    assert save(c, points=[pts[0]], no_animals=True).status_code == 400
    assert save(c, points=[{"x": 1, "y": 2, "kind": "fish", "species": "Gadus morhua"}]).status_code == 200   # old labels still save and load
    assert c.get("/api/labels/mine?set=t1&frame=f0&name=Jacob").get_json()["points"] == [{"x": 1, "y": 2, "kind": "fish", "species": "Gadus morhua"}]


def test_status_is_blind(client):
    c, _ = client
    save(c)
    save(c, name="Ali", points=[{"x": 5, "y": 5, "kind": "fish"}])
    save(c, name="Ali", frame="f1", points=[], no_animals=True)
    save(c, name="Jacob", frame="f1", points=[], skipped=True)
    raw = c.get(f"/api/labels/status?set={SET}&name=Jacob").get_data(as_text=True)
    st = json.loads(raw)
    assert st["counts"] == {"f0": 2, "f1": 1} and st["team"] == {"frames_with_any": 2, "frames_with_two": 1}
    assert st["mine"]["f1"]["state"] == "skipped"
    assert "Ali" not in raw and '"x"' not in raw
    for path in ("/api/labels/all", "/api/labels/export"):
        assert c.get(path).status_code in (404, 405)
    assert c.get(f"/api/labels/mine?set={SET}&name=Jacob").status_code == 400


@pytest.mark.parametrize("patch", [
    {"frame": "nope"}, {"frame": "a/b"}, {"name": ""}, {"name": "n" * 41}, {"name": 5},
    {"points": [{"x": 1001, "y": 5, "kind": "fish"}]}, {"points": [{"x": 5, "y": 501, "kind": "fish"}]}, {"points": [{"x": -1, "y": 5, "kind": "fish"}]},
    {"points": [{"x": 1, "y": 1, "kind": "crab"}]}, {"points": [{"x": "1", "y": 1, "kind": "fish"}]}, {"points": [{"x": True, "y": 1, "kind": "fish"}]},
    {"points": "x"}, {"no_animals": True}, {"skipped": True}, {"points": [], "no_animals": True, "skipped": True},
    {"seconds": -1}, {"seconds": "5"}, {"points": [{"x": 1, "y": 1, "kind": "fish"}] * 2001},
])
def test_save_validation(client, patch):
    c, tmp = client
    assert save(c, **patch).status_code == 400
    assert not (tmp / "labels.jsonl").exists()


def test_save_unknown_set_and_limits(client):
    c, _ = client
    assert c.post("/api/labels", json={"set": "zzz", "frame": "f0", "name": "A", "points": []}).status_code in (400, 404)
    assert c.post("/api/labels", json={"set": "../x", "frame": "f0", "name": "A"}).status_code == 400
    assert c.post("/api/labels", data="not json", content_type="text/plain").status_code == 400
    assert save(c, name="n" * 40, points=[{"x": 1000, "y": 500, "kind": "fish"}] * 2000).status_code == 200  # limits are inclusive


def test_labels_file_is_append_only_json_lines(client):
    c, tmp = client
    save(c)
    save(c, seconds=9)
    lines = (tmp / "labels.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["seconds"] == 9


# ---- make_label_set ----

def test_frame_ids_and_times():
    assert make_label_set.times(60, 2040, 20)[0] == 60 and len(make_label_set.times(60, 2040, 20)) == 100
    assert make_label_set.frame_id_for("t1s2_v1", 60) == "t1s2_v1_t00060"
    assert make_label_set.frame_id_for("s", 61.5) == "s_t00061p5"


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
def test_make_label_set_end_to_end(tmp_path):
    video = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=10:duration=8", "-f", "lavfi", "-i", "sine=duration=8",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True)
    out = tmp_path / "sets"
    assert make_label_set.main([str(video), "--set", "demo_v1", "--start", "1", "--end", "6", "--every", "2.5", "--out", str(out), "--workers", "2"]) == 0
    m = json.loads((out / "demo_v1" / "manifest.json").read_text())
    assert [f["time_s"] for f in m["frames"]] == [1.0, 3.5, 6.0] or [f["time_s"] for f in m["frames"]] == [1.0, 3.5]
    f = m["frames"][0]
    assert (f["width"], f["height"]) == (1920, 1080) and f["frame_url"].endswith(".jpg") and m["video"] == "in.mp4"
    import cv2
    img = cv2.imread(str(out / "demo_v1" / "frames" / f"{f['frame_id']}.jpg"))
    assert img.shape[:2] == (1080, 1920)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,codec_type", "-of", "json", str(out / "demo_v1" / "clips" / f"{f['frame_id']}.mp4")],
                           capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)["streams"]
    assert [s["codec_type"] for s in streams] == ["video"] and streams[0]["codec_name"] == "h264" and streams[0]["width"] == 1920  # no audio, protocol width
    clip_len = float(json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(out / "demo_v1" / "clips" / f"{f['frame_id']}.mp4")],
                                              capture_output=True, text=True, check=True).stdout)["format"]["duration"])
    assert abs(clip_len - (f["clip_length_s"])) < 0.3 and f["clip_count_s"] == 1.0 and clip_len <= 10.3   # 1 s in: clamped at the video start
    d = cv2.imread(str(out / "demo_v1" / "diff" / f"{f['frame_id']}.jpg"), cv2.IMREAD_UNCHANGED)
    assert d.ndim == 2 and d.shape == (1080, 1920) and f["diff_url"].endswith(f"/diff/{f['frame_id']}.jpg")
    head = (out / "demo_v1" / "clips" / f"{f['frame_id']}.mp4").read_bytes()[:64]
    assert b"moov" in head or b"ftyp" in head


def test_make_label_set_refuses_river(tmp_path):
    with pytest.raises(ValueError):
        make_label_set.build(tmp_path / "river_1080p.mp4", "ok_v1", 0, 10, 5, tmp_path)
    with pytest.raises(ValueError):
        make_label_set.build(tmp_path / "a.mp4", "river_v1", 0, 10, 5, tmp_path)


# ---- build_demo ----

def test_build_demo_copies_label_set(tmp_path):
    runs = tmp_path / "runs"
    from app.fixtures.make_fixture import build as make_fixture
    make_fixture(runs)
    sets = tmp_path / "sets"
    d = make_set(sets)
    (d / "frames" / "stray.txt").write_text("no")
    (d / "clips" / "f0.tmp.mp4").write_bytes(b"half")
    (d / "notes.md").write_text("private")
    out = tmp_path / "out"
    assert build_demo.main(["_fixture", "--runs-dir", str(runs), "--out", str(out), "--species", str(tmp_path / "n.json"),
                            "--label-set", SET, "--label-sets-dir", str(sets)]) == 0
    base = out / "label_sets" / SET
    assert (base / "manifest.json").is_file() and (base / "frames" / "f2.jpg").is_file() and (base / "clips" / "f1.mp4").is_file()
    assert not (base / "frames" / "stray.txt").exists() and not (base / "clips" / "f0.tmp.mp4").exists() and not (base / "notes.md").exists()
    assert json.loads((out / "label_sets" / "index.json").read_text()) == {"sets": [SET]}
    assert (out / "label.html").is_file() and not (out / "static" / "label.html").exists() and (out / "static" / "label.js").is_file()
    assert (out / "_worker.js").is_file()  # the team-code gate still ships


def test_build_demo_refuses_river_label_sets(tmp_path):
    runs = tmp_path / "runs"
    from app.fixtures.make_fixture import build as make_fixture
    make_fixture(runs)
    sets = tmp_path / "sets"
    make_set(sets, "river_v1")
    out = tmp_path / "out"
    assert build_demo.main(["_fixture", "--runs-dir", str(runs), "--out", str(out), "--label-set", "river_v1", "--label-sets-dir", str(sets)]) == 2
    assert not out.exists()
    with pytest.raises(build_demo.BuildError):
        build_demo.check_label_set_ids(["../sets"])


# ---- pull_labels ----

def row(frame, who, pts, **kw):
    r = {"set_id": SET, "frame_id": frame, "labeller": who, "points_json": json.dumps(pts), "views_json": "[]", "no_animals": 0, "seconds": 7.5, "skipped": 0, "updated_at": "2026-11-06T01:00:00Z"}
    r.update(kw)
    return r


def pt(x, y, kind="fish"):
    return {"x": x, "y": y, "kind": kind}


def test_pull_labels_outputs(tmp_path):
    rows = [
        row("f0", "Jacob", [pt(100, 100), pt(500, 500), pt(900, 900, "invertebrate")]),
        row("f0", "Ali", [pt(110, 105), pt(2000, 2000)]),                     # one match within 60 px, one apart
        row("f1", "Jacob", [], no_animals=1),
        row("f1", "Ali", [], no_animals=1),
        row("f2", "Jacob", [pt(1, 1)] * 20),
        row("f2", "Ali", [pt(1, 1)] * 21),
        row("f3", "Jacob", [pt(5, 5)]),                                        # only one labeller
        row("f4", "Jacob", [], skipped=1), row("f4", "Ali", [pt(5, 5)]),      # a skip is not a label
        row("f5", "=HYPERLINK(\"http://evil\")\x07<b>x</b>", [pt(5, 5)]), row("f5", "Ali", [pt(5, 5)]),
        row("f6", "Jacob", "not json"),
    ]
    src = tmp_path / "rows.json"
    src.write_text("banner\n" + json.dumps([{"results": rows, "success": True}]))
    out = tmp_path / "team"
    assert pull_labels.main(["--input", str(src), "--out", str(out), "--label-sets-dir", str(tmp_path / "none")]) == 0
    d = out / SET
    assert {p.name for p in d.iterdir()} == {"points.csv", "negatives.csv", "unsure.csv", "coco_keypoints.json", "agreement.csv", "summary.md", "summary.json"}
    agree = {(r["frame_id"], r["labeller_a"]): r for r in csv.DictReader((d / "agreement.csv").open())}
    a = agree[("f0", "Ali")]
    assert (a["count_a"], a["count_b"], a["difference"]) == ("2", "3", "1") and a["labeller_b"] == "Jacob"
    assert float(a["percent_difference"]) == pytest.approx(40.0) and a["matched_points"] == "1"
    assert float(a["match_rate"]) == pytest.approx(0.4) and "small count" in a["note"]
    f2 = agree[("f2", "Ali")]
    assert float(f2["percent_difference"]) == pytest.approx(100 * 1 / 20.5, abs=0.01) and f2["note"] == ""
    assert agree[("f1", "Ali")]["percent_difference"] == "0.0" and agree[("f1", "Ali")]["match_rate"] == ""
    assert ("f3", "Jacob") not in agree and not any(k[0] in ("f4", "f6") for k in agree)
    s = json.loads((d / "summary.json").read_text())
    assert s["frames_labelled"] == 6 and s["frames_with_two_labels"] == 4          # f0 f1 f2 f5 have two; f3 and f4 have one
    assert s["skipped_labels"] == 1 and s["pairs_compared"] == 4
    assert s["mean_absolute_difference"] == pytest.approx((1 + 0 + 1 + 0) / 4)
    assert s["share_under_6_percent"] == pytest.approx(3 / 4)                       # f1, f2 (4.9%) and f5 are under 6%; f0 is 40%
    pts = list(csv.DictReader((d / "points.csv").open()))
    assert len(pts) == 3 + 2 + 20 + 21 + 1 + 1 + 1 + 1 and all(r["kind"] in ("fish", "invertebrate") for r in pts)
    coco = json.loads((d / "coco_keypoints.json").read_text())
    assert len(coco["annotations"]) == len(pts) and coco["annotations"][0]["keypoints"][2] == 2 and {c["name"] for c in coco["categories"]} == {"fish", "invertebrate"}
    assert any(im["no_animals_by"] for im in coco["images"])
    # untrusted names: nothing runs in a spreadsheet, no control characters, markdown is escaped
    text = (d / "points.csv").read_text() + (d / "agreement.csv").read_text()
    assert "\x07" not in text and "\n=HYPER" not in text and ",=HYPER" not in text
    md = (d / "summary.md").read_text()
    assert "<b>" not in md and "not instructions" in md and "percent difference jump" in md.replace("makes the percent difference jump", "percent difference jump")


def test_pull_labels_nothing_and_bad_input(tmp_path, capsys):
    src = tmp_path / "rows.json"
    src.write_text(json.dumps([{"results": [], "success": True}]))
    assert pull_labels.main(["--input", str(src), "--out", str(tmp_path / "o")]) == 0
    assert "No labels yet" in capsys.readouterr().out
    src.write_text("garbage")
    assert pull_labels.main(["--input", str(src), "--out", str(tmp_path / "o")]) == 1
    src.write_text(json.dumps([{"results": [row("../evil", "A", [])], "success": True}]))
    assert pull_labels.main(["--input", str(src), "--out", str(tmp_path / "o")]) == 0
    assert not (tmp_path / "evil").exists()


def test_match_radius_scales_with_image_width():
    a, b = [pt(0, 0)], [pt(50, 0)]
    assert pull_labels.match_points(a, b, 60)[0] == 1
    assert pull_labels.match_points(a, b, 30)[0] == 0
    rows = [row("f0", "Jacob", [pt(0, 0)]), row("f0", "Ali", [pt(40, 0)])]
    labels, _ = pull_labels.clean_rows(rows)
    assert pull_labels.frame_pairs(labels, 60, {(SET, "f0"): 1920})[0]["matched_points"] == 0   # radius halves on a 1920 image
    assert pull_labels.frame_pairs(labels, 60, {})[0]["matched_points"] == 1


def test_percent_difference_is_the_qc_function():
    from clipsift.qc import percent_difference
    assert pull_labels.percent_difference is percent_difference


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_label_js_helpers_with_node():
    r = subprocess.run(["node", str(ROOT / "deploy" / "test" / "label.test.mjs")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_pull_labels_species_and_views(tmp_path):
    rows = [
        row("f0", "Jacob", [dict(pt(10, 10), species="Gadus morhua"), dict(pt(50, 50), species="=cmd|' /C calc'!A0\x07 "), pt(90, 90)], views_json='["clip","frame","bogus"]'),
        row("f0", "Ali", [pt(12, 11)], views_json='["frame","movement"]'),
        row("f1", "Jacob", [pt(5, 5)]),                                  # an older row: no views_json at all
    ]
    del rows[2]["views_json"]
    src = tmp_path / "rows.json"
    src.write_text(json.dumps([{"results": rows, "success": True}]))
    out = tmp_path / "team"
    assert pull_labels.main(["--input", str(src), "--out", str(out), "--label-sets-dir", str(tmp_path / "none")]) == 0
    d = out / SET
    pts = list(csv.DictReader((d / "points.csv").open()))
    assert pts[0]["species"] == "Gadus morhua" and pts[0]["views_used"] == "frame;clip"          # canonical order, unknown names dropped
    assert pts[1]["species"].startswith("'=cmd") and "\x07" not in pts[1]["species"]              # formulas neutralised
    assert pts[2]["species"] == "" and [p["views_used"] for p in pts if p["labeller"] == "Ali"] == ["frame;movement"]
    assert [p["views_used"] for p in pts if p["frame_id"] == "f1"] == [""]
    ag = list(csv.DictReader((d / "agreement.csv").open()))[0]
    assert ag["views_a"] == "frame;movement" and ag["views_b"] == "frame;clip"
    s = json.loads((d / "summary.json").read_text())
    assert s["frames_by_view_used"] == {"frame": 2, "movement": 1, "clip": 1} and s["marks_with_species"] == 2 and s["frames_with_no_view_recorded"] == 1
    coco = json.loads((d / "coco_keypoints.json").read_text())
    attrs = [a["attributes"] for a in coco["annotations"] if a["attributes"]["labeller"] == "Jacob"]
    assert attrs[0]["species"] == "Gadus morhua" and "species" not in attrs[2]
    assert [im["views_by"] for im in coco["images"] if im["frame_id"] == "f0"] == [{"Ali": ["frame", "movement"], "Jacob": ["frame", "clip"]}]
    assert "Frames where each view was used" in (d / "summary.md").read_text()


def test_diff_function_is_shared_with_the_review_app():
    import numpy as np
    from clipsift import pipeline
    still = np.full((40, 60, 3), 100, np.uint8)
    same = [still.copy() for _ in range(5)]
    assert not pipeline.diff_from_frames(still, same).any()           # nothing moved: black
    moved = still.copy(); moved[10:20, 10:20] = 250
    d = pipeline.diff_from_frames(moved, same)
    assert d.shape == (40, 60) and d.dtype == np.uint8 and d[15, 15] > 200 and d[35, 50] == 0
    assert not pipeline.diff_from_frames(still, same[:2]).any()       # fewer than 3 frames: black, as in the review app


def test_pull_labels_not_fish(tmp_path):
    nf = lambda x, y, cat=None: dict(pt(x, y, "not_fish"), **({"category": cat} if cat is not None else {}))
    rows = [
        row("f0", "Jacob", [pt(100, 100), nf(500, 500, "algae"), nf(600, 600, "algae"), nf(700, 700, "pipe-not-listed")]),
        row("f0", "Ali", [pt(105, 100), nf(900, 900, "debris")]),
        row("f1", "Jacob", [nf(5, 5, "equipment")]),                        # only Not fish: counts as 0 animals
        row("f1", "Ali", [], no_animals=1),
        row("f2", "Jacob", [pt(1, 1)]), row("f2", "Ali", [pt(1, 1)]),       # an old-style row with no Not fish at all
    ]
    src = tmp_path / "rows.json"
    src.write_text(json.dumps([{"results": rows, "success": True}]))
    out = tmp_path / "team"
    assert pull_labels.main(["--input", str(src), "--out", str(out), "--label-sets-dir", str(tmp_path / "none")]) == 0
    d = out / SET
    ag = {r["frame_id"]: r for r in csv.DictReader((d / "agreement.csv").open())}
    assert (ag["f0"]["count_a"], ag["f0"]["count_b"], ag["f0"]["percent_difference"]) == ("1", "1", "0.0")      # Not fish never counted
    assert (ag["f1"]["count_a"], ag["f1"]["count_b"]) == ("0", "0")
    pts = list(csv.DictReader((d / "points.csv").open()))
    assert [(r["kind"], r["category"]) for r in pts if r["frame_id"] == "f0" and r["labeller"] == "Jacob"] == [("fish", ""), ("not_fish", "algae"), ("not_fish", "algae"), ("not_fish", "")]
    neg = list(csv.DictReader((d / "negatives.csv").open()))
    assert [r["category"] for r in neg] == ["algae", "algae", "", "debris", "equipment"] or sorted(r["category"] for r in neg) == ["", "algae", "algae", "debris", "equipment"]
    coco = json.loads((d / "coco_keypoints.json").read_text())
    assert {a["category_id"] for a in coco["annotations"]} <= {1, 2} and len(coco["annotations"]) == 4
    assert len(coco["not_fish_marks"]) == 5 and {c["name"] for c in coco["categories"]} == {"fish", "invertebrate"}
    s = json.loads((d / "summary.json").read_text())
    assert s["not_fish_total"] == 5 and s["not_fish_by_category"]["algae"] == 2 and s["not_fish_by_category"][""] == 1 and s["total_marks"] == 4
    assert "Not fish marks" in (d / "summary.md").read_text()


# ---- Unsure, groups, calibration ----

def test_server_unsure_kind(client):
    c, tmp = client
    pts = [{"x": 1, "y": 2, "kind": "unsure"}, {"x": 3, "y": 4, "kind": "unsure", "species": "Gadus morhua", "category": "algae"}, {"x": 5, "y": 6, "kind": "fish"}]
    assert save(c, points=pts).status_code == 200
    got = c.get(f"/api/labels/mine?set={SET}&frame=f0&name=Jacob").get_json()["points"]
    assert got == [{"x": 1, "y": 2, "kind": "unsure"}, {"x": 3, "y": 4, "kind": "unsure"}, {"x": 5, "y": 6, "kind": "fish"}]
    assert save(c, points=[pts[0]], no_animals=True).status_code == 400
    assert save(c, points=[{"x": 5000, "y": 1, "kind": "unsure"}]).status_code == 400
    assert save(c, points=[{"x": 1, "y": 1, "kind": "maybe"}]).status_code == 400
    assert save(c, points=[pts[0]]).status_code == 200          # only unsure is an ordinary labelled frame
    assert c.get(f"/api/labels/status?set={SET}&name=Jacob").get_json()["mine"]["f0"]["n_points"] == 1


def test_server_manifest_takes_calibration_from_the_file(client):
    c, tmp = client
    assert "calibration" not in c.get(f"/label_sets/{SET}/manifest.json").get_json()
    cal = tmp / "label_sets" / SET / "calibration.json"
    cal.write_text(json.dumps(["f2", "f0", "f2", "nope"]))
    assert c.get(f"/label_sets/{SET}/manifest.json").get_json()["calibration"] == ["f2", "f0"]
    cal.write_text("[]")
    assert c.get(f"/label_sets/{SET}/manifest.json").get_json()["calibration"] == []
    # status shows counts and the caller's own state only, never anyone's points
    save(c, name="Ali", points=[{"x": 321.5, "y": 454.5, "kind": "fish"}])
    raw = c.get(f"/api/labels/status?set={SET}&name=Jacob").get_data(as_text=True)
    assert "321.5" not in raw and "454.5" not in raw and json.loads(raw)["counts"] == {"f0": 1}


def test_set_calibration_command_and_build_demo(tmp_path):
    sets = tmp_path / "sets"
    make_set(sets)
    assert make_label_set.main(["--set", SET, "--out", str(sets), "--set-calibration", "f1", "f0", "f1"]) == 0
    assert json.loads((sets / SET / "calibration.json").read_text()) == ["f1", "f0"]
    assert json.loads((sets / SET / "manifest.json").read_text())["calibration"] == ["f1", "f0"]
    assert make_label_set.main(["--set", SET, "--out", str(sets), "--set-calibration", "nope"]) == 1      # not a frame in the set
    assert json.loads((sets / SET / "calibration.json").read_text()) == ["f1", "f0"]                       # unchanged
    assert make_label_set.main(["--set", SET, "--out", str(sets), "--set-calibration"]) == 0               # empty list
    assert json.loads((sets / SET / "manifest.json").read_text())["calibration"] == []
    # build_demo puts the file's list into the copied manifest, even when the manifest itself has none
    (sets / SET / "calibration.json").write_text(json.dumps({"calibration": ["f2", "f1"]}))
    runs = tmp_path / "runs"
    from app.fixtures.make_fixture import build as make_fixture
    make_fixture(runs)
    out = tmp_path / "out"
    assert build_demo.main(["_fixture", "--runs-dir", str(runs), "--out", str(out), "--label-set", SET, "--label-sets-dir", str(sets)]) == 0
    assert json.loads((out / "label_sets" / SET / "manifest.json").read_text())["calibration"] == ["f2", "f1"]
    assert not (out / "label_sets" / SET / "calibration.json").exists()
    (sets / SET / "calibration.json").write_text(json.dumps(["ghost"]))
    assert build_demo.main(["_fixture", "--runs-dir", str(runs), "--out", str(tmp_path / "out2"), "--label-set", SET, "--label-sets-dir", str(sets)]) == 2


def test_parse_times():
    assert make_label_set.parse_times("1236:1374:6")[:3] == [1236.0, 1242.0, 1248.0] and len(make_label_set.parse_times("1236:1374:6")) == 24
    assert make_label_set.parse_times("90, 30,30") == [30.0, 90.0]
    for bad in ("x", "5:1:2", "1:5:0"):
        with pytest.raises(ValueError):
            make_label_set.parse_times(bad)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
def test_make_label_set_add_keeps_existing_frames(tmp_path):
    video = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10:duration=12",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
    out = tmp_path / "sets"
    assert make_label_set.main([str(video), "--set", "demo_v1", "--start", "2", "--end", "4", "--every", "2", "--out", str(out), "--workers", "2"]) == 0
    base = out / "demo_v1"
    m0 = json.loads((base / "manifest.json").read_text())
    assert [f["group"] for f in m0["frames"]] == ["survey", "survey"]
    keep = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in base.rglob("*") if p.is_file() and p.name != "manifest.json"}
    ids0 = [f["frame_id"] for f in m0["frames"]]
    assert make_label_set.main([str(video), "--set", "demo_v1", "--add", "--times", "4,5:7:1", "--group", "school_block", "--out", str(out), "--workers", "2"]) == 0
    m1 = json.loads((base / "manifest.json").read_text())
    assert [f["frame_id"] for f in m1["frames"][:2]] == ids0 and m1["frames"][:2] == m0["frames"]            # existing frames and ids untouched
    assert [f["time_s"] for f in m1["frames"][2:]] == [5.0, 6.0, 7.0]                                         # 4 s was already there
    assert {f["group"] for f in m1["frames"][2:]} == {"school_block"} and m1["video"] == m0["video"]
    for p, (mt, data) in keep.items():
        assert p.stat().st_mtime_ns == mt and p.read_bytes() == data                                          # nothing already there was regenerated
    for f in m1["frames"][2:]:
        assert (base / "frames" / f"{f['frame_id']}.jpg").is_file() and (base / "clips" / f"{f['frame_id']}.mp4").is_file() and (base / "diff" / f"{f['frame_id']}.jpg").is_file()
    assert make_label_set.main([str(video), "--set", "demo_v1", "--add", "--times", "4", "--out", str(out)]) == 0   # nothing new: fine
    assert len(json.loads((base / "manifest.json").read_text())["frames"]) == 5
    assert make_label_set.main([str(video), "--set", "demo_v1", "--add", "--times", "99", "--out", str(out)]) == 1   # past the end


def test_make_label_set_add_old_frames_get_group_survey(tmp_path, monkeypatch):
    sets = tmp_path / "sets"
    d = make_set(sets, "s_v1", n=2)
    m = json.loads((d / "manifest.json").read_text())
    m.update({"video": "v.mp4", "video_width": 1000, "video_height": 500})
    (d / "manifest.json").write_text(json.dumps(m))
    monkeypatch.setattr(make_label_set, "probe", lambda v: {"width": 1000, "height": 500, "duration": 500.0})
    made = []
    monkeypatch.setattr(make_label_set, "make_items", lambda video, sid, ts, out, info, workers: made.append(list(ts)) or [
        {"frame_id": make_label_set.frame_id_for(sid, t), "time_s": t, "width": 1000, "height": 500} for t in ts])
    res = make_label_set.add_frames(tmp_path / "v.mp4", "s_v1", [60.0, 70.0, 80.0], sets)
    assert made == [[70.0]] and res["skipped_times"] == [60.0, 80.0]       # 60 s and 80 s are already in the fake set
    frames = json.loads((d / "manifest.json").read_text())["frames"]
    assert [f["group"] for f in frames] == ["survey", "survey", "school_block"]


def nfp(x, y, kind="unsure"):
    return {"x": x, "y": y, "kind": kind}


def test_pull_labels_unsure_ignore_regions_and_matches(tmp_path):
    rows = [
        # f0: Jacob has 2 fish and 3 unsure; Ali has 1 fish near one of Jacob's unsure marks and 1 unsure near Jacob's fish
        row("f0", "Jacob", [pt(100, 100), pt(900, 900), nfp(500, 500), nfp(2000, 2000), nfp(3000, 300)]),
        row("f0", "Ali", [pt(510, 505), nfp(105, 95)]),
        row("f1", "Jacob", [nfp(10, 10), nfp(20, 20, "not_fish")]),            # unsure + not fish only: 0 animals
        row("f1", "Ali", [], no_animals=1),
        row("f2", "Jacob", [nfp(7, 7)]),                                       # one labeller only: unsure counts as a total, not as checked
    ]
    src = tmp_path / "rows.json"
    src.write_text(json.dumps([{"results": rows, "success": True}]))
    sets = tmp_path / "sets"
    d0 = sets / SET
    d0.mkdir(parents=True)
    fr = lambda fid, t, g: {"frame_id": fid, "time_s": t, "width": 3840, "height": 2160, "group": g}
    (d0 / "manifest.json").write_text(json.dumps({"frames": [fr("f0", 1236.0, "school_block"), fr("f1", 60.0, "survey"), {"frame_id": "f2", "time_s": 80.0, "width": 3840, "height": 2160}, fr("f9", 5.0, "survey")]}))
    out = tmp_path / "team"
    assert pull_labels.main(["--input", str(src), "--out", str(out), "--label-sets-dir", str(sets)]) == 0
    d = out / SET
    assert not (d / "calibration.csv").exists()                              # no calibration frames in this set
    ag = {r["frame_id"]: r for r in csv.DictReader((d / "agreement.csv").open())}
    assert ag["f0"]["labeller_a"] == "Ali" and (ag["f0"]["count_a"], ag["f0"]["count_b"]) == ("1", "2")                   # unsure never counted
    assert (ag["f0"]["unsure_a"], ag["f0"]["unsure_b"]) == ("1", "3")
    assert (ag["f0"]["a_unsure_hits_b_animal"], ag["f0"]["b_unsure_hits_a_animal"]) == ("1", "1")
    assert ag["f0"]["group"] == "school_block" and ag["f0"]["time_s"] == "1236.0" and ag["f1"]["group"] == "survey"
    assert float(ag["f0"]["match_rate"]) == 0.0 and ag["f1"]["percent_difference"] == "0.0"
    u = list(csv.DictReader((d / "unsure.csv").open()))
    assert len(u) == 3 + 1 + 1 + 1 and {r["use"] for r in u} == {"ignore"} and float(u[0]["ignore_radius_px"]) == 60.0
    assert {r["group"] for r in u if r["frame_id"] == "f2"} == {"survey"} and {r["time_s"] for r in u if r["frame_id"] == "f0"} == {"1236.0"}
    pts = list(csv.DictReader((d / "points.csv").open()))
    assert sum(r["kind"] == "unsure" for r in pts) == 6 and all(r["group"] for r in pts)
    assert all(r["category"] == "" for r in csv.DictReader((d / "negatives.csv").open())) and len(list(csv.DictReader((d / "negatives.csv").open()))) == 1
    coco = json.loads((d / "coco_keypoints.json").read_text())
    assert len(coco["annotations"]) == 3 and {a["category_id"] for a in coco["annotations"]} <= {1, 2}                       # no unsure in the animals
    assert len(coco["ignore_regions"]) == 6 and all(r["use"] == "ignore" and r["reason"] == "unsure" and r["radius_px"] == 60.0 for r in coco["ignore_regions"])
    assert {im["frame_id"]: im["group"] for im in coco["images"]} == {"f0": "school_block", "f1": "survey", "f2": "survey"}
    assert {im["frame_id"]: im["time_s"] for im in coco["images"]}["f0"] == 1236.0
    s = json.loads((d / "summary.json").read_text())
    assert s["unsure_total"] == 6 and s["total_marks"] == 3 and s["not_fish_total"] == 1
    assert s["unsure_by_labeller"]["Ali"] == {"unsure": 1, "checked": 1, "matched": 1}
    assert s["unsure_by_labeller"]["Jacob"] == {"unsure": 5, "checked": 4, "matched": 1}     # f2 has one labeller, so its unsure is a total but not checked
    assert s["unsure_checked_against_other_labeller"] == 5 and s["unsure_matched_other_labellers_animal"] == 2 and s["unsure_match_rate"] == pytest.approx(0.4)
    assert s["frames_in_set"] == 4 and s["frames_labelled_by_group"] == {"school_block": 1, "survey": 2}
    assert s["by_labeller"]["Jacob"]["unsure"] == 5 and s["by_labeller"]["Ali"]["unsure"] == 1
    md = (d / "summary.md").read_text()
    assert "school_block" in md and "same side of any train and test split" in md and "of 4 frames in the set" in md and "ignore regions" in md


def test_pull_labels_no_split_note_without_blocks(tmp_path):
    src = tmp_path / "rows.json"
    src.write_text(json.dumps([{"results": [row("f0", "Jacob", [pt(1, 1)]), row("f0", "Ali", [pt(1, 1)])], "success": True}]))
    assert pull_labels.main(["--input", str(src), "--out", str(tmp_path / "o"), "--label-sets-dir", str(tmp_path / "none")]) == 0
    s = json.loads((tmp_path / "o" / SET / "summary.json").read_text())
    assert s["split_note"] == "" and s["frames_in_set"] is None and s["unsure_match_rate"] is None


def test_pull_labels_calibration_csv(tmp_path):
    rows = [
        row("f0", "Jacob", [pt(100, 100), pt(900, 900), nfp(500, 500), nfp(20, 20, "not_fish")], seconds=40),
        row("f0", "Ali", [pt(110, 105), pt(900, 905, "invertebrate"), pt(3000, 3000)], seconds=55),
        row("f0", "Gina", [], no_animals=1, seconds=12),
        row("f1", "Jacob", [pt(1, 1)]), row("f1", "Ali", [], skipped=1),     # a skip is not a label
        row("f2", "Jacob", [pt(1, 1)]),                                       # not a calibration frame
    ]
    src = tmp_path / "rows.json"
    src.write_text(json.dumps([{"results": rows, "success": True}]))
    sets = tmp_path / "sets"
    (sets / SET).mkdir(parents=True)
    fr = lambda fid, t: {"frame_id": fid, "time_s": t, "width": 3840, "height": 2160}
    (sets / SET / "manifest.json").write_text(json.dumps({"frames": [fr("f0", 60.0), fr("f1", 80.0), fr("f2", 100.0)], "calibration": ["f1", "f0", "ghost", "f1"]}))
    assert pull_labels.main(["--input", str(src), "--out", str(tmp_path / "o"), "--label-sets-dir", str(sets)]) == 0
    rows_out = list(csv.DictReader((tmp_path / "o" / SET / "calibration.csv").open()))
    people = {(r["frame_id"], r["labeller"]): r for r in rows_out if r["row_type"] == "person"}
    pairs = {(r["frame_id"], r["labeller"], r["other_labeller"]): r for r in rows_out if r["row_type"] == "pair"}
    assert set(people) == {("f0", "Jacob"), ("f0", "Ali"), ("f0", "Gina"), ("f1", "Jacob")}            # f2 is not calibration, Ali's skip is not a label
    j = people[("f0", "Jacob")]
    assert (j["fish"], j["invertebrate"], j["unsure"], j["not_fish"], j["animal_count"], j["seconds_on_frame"]) == ("2", "0", "1", "1", "2", "40")
    a = people[("f0", "Ali")]
    assert (a["fish"], a["invertebrate"], a["unsure"], a["animal_count"]) == ("2", "1", "0", "3") and a["calibration_order"] == "2"
    assert people[("f0", "Gina")]["no_animals"] == "1" and {r["count_spread"] for r in people.values() if r["frame_id"] == "f0"} == {"3"}
    assert people[("f1", "Jacob")]["calibration_order"] == "1" and people[("f1", "Jacob")]["count_spread"] == "0" and people[("f1", "Jacob")]["time_s"] == "80.0"
    assert set(pairs) == {("f0", "Ali", "Gina"), ("f0", "Ali", "Jacob"), ("f0", "Gina", "Jacob")}
    aj = pairs[("f0", "Ali", "Jacob")]
    assert aj["matched_points"] == "2" and float(aj["match_rate"]) == pytest.approx(0.8) and aj["fish"] == ""
    assert float(pairs[("f0", "Ali", "Gina")]["match_rate"]) == 0.0
    # a set whose calibration list is empty writes no calibration.csv
    (sets / SET / "manifest.json").write_text(json.dumps({"frames": [fr("f0", 60.0)], "calibration": []}))
    assert pull_labels.main(["--input", str(src), "--out", str(tmp_path / "o2"), "--label-sets-dir", str(sets)]) == 0
    assert not (tmp_path / "o2" / SET / "calibration.csv").exists()


def test_label_page_has_the_new_controls_and_plain_text():
    html = (ROOT / "app" / "static" / "label.html").read_text()
    js = (ROOT / "app" / "static" / "label.js").read_text()
    for needle in ('id="k-uns"', 'id="cm-to-uns"', 'id="nf-hint"', "Look at the frame", "Play the clip", "Movement view", "Find a body in the frame or clip",
                   "Stick to your own name", "at most 3 per frame", "only after you have checked both the clip"):
        assert needle in html, needle
    assert "\u2014" not in html and "\u2014" not in js


def test_archived_frames_come_from_calibration_json(tmp_path):
    from tools.pull_labels import archived_frames
    (tmp_path / "s1").mkdir()
    (tmp_path / "s1" / "calibration.json").write_text('{"calibration": ["a"], "archived": ["b", "c"]}', encoding="utf-8")
    (tmp_path / "s2").mkdir()
    assert archived_frames(tmp_path, ["s1", "s2", "s3"]) == {("s1", "b"), ("s1", "c")}
