"""New video workflow: choosing a video, processing it in the background, opening the run."""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.fixtures.make_fixture import build  # noqa: E402
from app.jobs import build_command, last_error, read_progress, safe_run_name  # noqa: E402
from app.server import create_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def env(tmp_path):
    runs, videos = tmp_path / "runs", tmp_path / "videos"
    runs.mkdir(); videos.mkdir()
    build(runs)
    app = create_app(runs, aliases_path=tmp_path / "a.jsonl", videos_dir=videos)
    return app.test_client(), runs, videos


def test_run_names_are_safe():
    assert safe_run_name("T1-STAT2 411") == "T1-STAT2_411"
    assert safe_run_name("GX010221_T1@1217pm") == "GX010221_T1_1217pm"
    assert safe_run_name("...") == "video"


def test_command_carries_video_id_and_interval():
    cmd = build_command(["a.mp4"], "runs", "x", 0, video_id="T1 411", interval=15, python="py")
    assert cmd[-4:] == ["--video-id", "T1 411", "--interval", "15"]


def test_command_has_window_only_when_set():
    cmd = build_command(["a.mp4"], "runs", "x", 1, python="py")
    assert cmd[:5] == ["py", "-u", "-m", "clipsift", "run"] and "--window-start" not in cmd
    assert build_command(["a.mp4"], "runs", "x", 0, 60, 120, python="py")[-4:] == ["--window-start", "60", "--window-end", "120"]


def test_progress_reads_as_plain_words():
    assert read_progress([])["text"] == "Starting"
    lines = ["plan: 15 points", "subsample ss_03 at 180.0s"]
    p = read_progress(lines)
    assert p["text"] == "Point 3 of 15" and 5 < p["percent"] < 70
    assert read_progress(lines + ["window video"])["text"] == "Making the window video"
    assert read_progress(lines + ["motion scan: 4 segments"])["percent"] == 80
    assert read_progress(lines + ["motion scan: 4 segments", "segment media 2 of 4"])["text"] == "Cutting movement clips, 2 of 4"


def test_failed_job_shows_the_error_line():
    assert last_error(["a", "Error: cannot open video", "b"]) == "Error: cannot open video"


def test_chapters_show_as_one_video(env):
    c, _, videos = env
    for n in ("GX010221_T1.MP4", "GX020221_T1.MP4", "river.mov", "notes.txt", "half.mp4.part"):
        (videos / n).write_bytes(b"x")
    d = c.get("/api/videos").get_json()
    assert sorted(len(v["files"]) for v in d["videos"]) == [1, 2]


def test_upload_needs_the_header_a_video_name_and_keeps_existing_files(env):
    c, _, videos = env
    h = {"X-ClipSift-Upload": "1"}
    assert c.put("/api/videos/upload?name=a.mp4", data=b"abc").status_code == 400
    assert c.put("/api/videos/upload?name=a.exe", data=b"abc", headers=h).status_code == 400
    assert c.put("/api/videos/upload?name=../../a.mp4", data=b"abc", headers=h).status_code == 200
    assert (videos / "a.mp4").read_bytes() == b"abc" and not list(videos.glob("*.part"))
    assert c.put("/api/videos/upload?name=a.mp4", data=b"zzz", headers=h).status_code == 400
    assert (videos / "a.mp4").read_bytes() == b"abc"


def test_jobs_refuse_bad_input(env):
    c, _, videos = env
    (videos / "a.mp4").write_bytes(b"x")
    bad = [{}, {"video": "missing.mp4"}, {"path": "/no/such/file.mp4"}, {"path": str(ROOT / "README.md")},
           {"video": "a.mp4", "name": "../evil"}, {"video": "a.mp4", "name": "_fixture"}, {"video": "a.mp4", "layer": 2},
           {"video": "a.mp4", "window_start": 100, "window_end": 50}, {"video": "a.mp4", "window_start": "soon"}]
    for b in bad:
        assert c.post("/api/jobs", json=b).status_code == 400, b


def wait_for(c, job_id, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        j = next(x for x in c.get("/api/jobs").get_json()["jobs"] if x["id"] == job_id)
        if j["status"] not in ("queued", "running"):
            return j
        time.sleep(0.3)
    raise AssertionError("job did not finish")


def test_broken_video_fails_with_a_message(env):
    c, _, videos = env
    (videos / "broken.mp4").write_bytes(b"not a video")
    j = wait_for(c, c.post("/api/jobs", json={"video": "broken.mp4", "layer": 0}).get_json()["id"])
    assert j["status"] == "failed" and j["error"]


def test_real_video_runs_and_opens(env, tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    from make_synthetic_clip import make
    c, runs, videos = env
    make(videos / "clip one.mp4", duration=20, width=320, fps=8)
    (videos / "clip one.json").unlink(missing_ok=True)
    r = c.post("/api/jobs", json={"video": "clip one.mp4", "layer": 0, "window_start": 2, "window_end": 18, "video_id": "T9 STAT1", "interval": 5})
    assert r.status_code == 201 and r.get_json()["name"] == "clip_one"
    j = wait_for(c, r.get_json()["id"])
    assert j["status"] == "done", j
    assert "clip_one" in [x["run_id"] for x in c.get("/api/runs").get_json()["runs"]]
    r = json.loads((runs / "clip_one" / "results.json").read_text())
    assert r["subsamples"] and r["segments"] == []                       # no motion pass by default
    assert r["recording"]["video_id"] == "T9 STAT1" and r["protocol"]["interval_s"] == 5
    assert c.get("/api/runs/clip_one/window").status_code == 200         # the window video to watch
    pv = c.post("/api/videos/preview", json={"video": "clip one.mp4"}).get_json()
    assert pv["duration_s"] > 19 and pv["frames"] == []                  # too short for minute marks
    assert c.post("/api/jobs", json={"video": "clip one.mp4", "layer": 0}).status_code == 400   # saved counts stay safe


def test_recut_replaces_points_before_counting_and_versions_after(env, tmp_path):
    """Change window or spacing: before counting the new points replace the old ones, keeping visibility and
    watch notes. After counting it makes a new version, so no count loses the frame it was made on."""
    sys.path.insert(0, str(ROOT / "tools"))
    from make_synthetic_clip import make
    c, runs, videos = env
    make(videos / "recut.mp4", duration=24, width=320, fps=8)
    first = c.post("/api/jobs", json={"video": "recut.mp4", "layer": 0, "window_start": 2, "window_end": 22, "interval": 5})
    done = wait_for(c, first.get_json()["id"])
    assert done["status"] == "done", done
    R = "/api/runs/recut"
    before = len(c.get(R + "/results").get_json()["subsamples"])
    c.post(R + "/visibility", json={"observer": "Ana", "category": "1.0-1.5 m", "at_s": 7.5})
    c.post(R + "/recording_notes", json={"species_observed": [], "none_seen": True, "notes": "kept"})
    r = c.post(R + "/recut", json={"window_start": 2, "window_end": 22, "interval": 10})
    assert r.status_code == 201 and r.get_json()["opens"] == "recut" and r.get_json()["new_version"] is False
    j = wait_for(c, r.get_json()["id"])
    assert j["status"] == "done" and j["name"] == "recut", j
    res = c.get(R + "/results").get_json()
    assert res["protocol"]["interval_s"] == 10 and len(res["subsamples"]) < before and res["recording"]["recording_id"] == "recut"
    saved = c.get(R + "/saved").get_json()
    assert saved["visibility"][0]["at_s"] == 7.5 and saved["latest_recording_notes"]["notes"] == "kept"
    assert (runs / ".replaced").is_dir() and not (runs / "recut__recut").exists()
    assert "recut__recut" not in [x["run_id"] for x in c.get("/api/runs").get_json()["runs"]]
    # once counted, a re-cut becomes a new version and the original stays as it was
    sid = res["subsamples"][0]["subsample_id"]
    c.post(R + "/subsample_reviews", json={"subsample_id": sid, "counter": "Ana", "total_fish_count": 1, "invertebrate_count": 0})
    r = c.post(R + "/recut", json={"window_start": 2, "window_end": 22, "interval": 5})
    assert r.get_json()["opens"] == "recut_v2" and r.get_json()["new_version"] is True
    assert wait_for(c, r.get_json()["id"])["status"] == "done"
    assert c.get("/api/runs/recut_v2/saved").get_json()["visibility"][0]["observer"] == "Ana"
    assert c.get(R + "/saved").get_json()["n_counted"] == 1 and c.get("/api/runs/recut_v2/saved").get_json()["n_counted"] == 0
    assert c.post(R + "/recut", json={"interval": 2}).status_code == 400
