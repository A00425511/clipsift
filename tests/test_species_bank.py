"""Tests for the species bank: flag logic on made-up tracks, and the app routes."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.fixtures.make_fixture import build  # noqa: E402
from app.server import create_app  # noqa: E402
from clipsift import species_bank as sb  # noqa: E402


def obs(i, box, conf=0.5):
    return {"frame_index": i, "timestamp": i / 5, "confidence": conf, "bbox": box}


def track(point, tid, boxes, status="review_candidate"):
    return {"track_id": tid, "status": status, "frames_seen": len(boxes), "max_confidence": 0.5,
            "observations": [obs(i, b) for i, b in enumerate(boxes)]}


def sample(ts, tracks):
    return {"subsample_timestamp_seconds": ts, "candidate_tracks": tracks}


MOVING = [[10 + 40 * i, 50, 70 + 40 * i, 80] for i in range(8)]
STILL = [[200, 200, 260, 230]] * 8


def test_low_priority_tracks_are_left_out():
    v6 = {"subsamples": [sample(60, [track(1, 0, MOVING), track(1, 1, MOVING, "low_priority_candidate")])]}
    assert [t["id"] for t in sb.read_tracks(v6)] == ["p001_t0000"]


def test_movement_ratio_separates_moving_from_still():
    assert sb.movement_ratio([obs(i, b) for i, b in enumerate(MOVING)]) > 1
    assert sb.movement_ratio([obs(i, b) for i, b in enumerate(STILL)]) == 0


def test_fixed_objects_marked_for_repeats_stillness_and_size():
    v6 = {"subsamples": [sample(60 * n, [track(n, 0, [[300, 300, 360, 340], [340, 300, 400, 340],
                                                      [380, 300, 440, 340]] * 2)]) for n in range(3)]
          + [sample(300, [track(9, 1, MOVING), track(9, 2, STILL), track(9, 3, [[0, 0, 900, 900]] * 8)])]}
    tracks = sb.read_tracks(v6)
    sb.mark_fixed(tracks, 1000, 1000)
    reasons = {t["id"]: t["fixed_reason"] for t in tracks}
    assert "separate points" in reasons["p001_t0000"]
    assert reasons["p004_t0001"] is None
    assert reasons["p004_t0002"] == "Barely moved during the clip"
    assert "too much" in reasons["p004_t0003"]


def merged_input(*tracks_):
    tracks = sb.read_tracks({"subsamples": [sample(60, list(tracks_))]})
    for t in tracks:
        t.update(fixed_reason=None, images={"crop": t["id"] + ".jpg"}, time_s=1.0, view_score=1.0)
    return tracks


def test_two_tracks_on_one_animal_become_one_item():
    near = [[b[0] + 8, b[1], b[2] + 8, b[3]] for b in MOVING]
    merged = sb.merge_views(merged_input(track(1, 0, MOVING), track(1, 1, near)))
    assert len(merged) == 1 and len(merged[0]["other_views"]) == 1


def test_a_track_that_picks_up_straight_after_another_is_merged():
    first = [track(1, 0, MOVING[:4]), track(1, 1, MOVING[4:])]
    first[1]["observations"] = [obs(i + 4, b) for i, b in enumerate(MOVING[4:])]
    assert len(sb.merge_views(merged_input(*first))) == 1


def test_fish_passing_each_other_stay_separate():
    crossing = [[10 + 40 * (7 - i), 50, 70 + 40 * (7 - i), 80] for i in range(8)]
    assert len(sb.merge_views(merged_input(track(1, 0, MOVING), track(1, 1, crossing)))) == 2


def test_an_animal_is_not_hidden_because_one_track_touched_the_pipe():
    near = [[b[0] + 8, b[1], b[2] + 8, b[3]] for b in MOVING]
    tracks = merged_input(track(1, 0, MOVING), track(1, 1, near))
    tracks[0]["fixed_reason"] = "Same place at 5 separate points"
    merged = sb.merge_views(tracks)
    assert len(merged) == 1 and merged[0]["fixed_reason"] is None


def test_something_new_at_a_usual_spot_is_kept():
    tracks = sb.read_tracks({"subsamples": [sample(60, [track(1, 0, STILL)])]})
    tracks[0]["background_match"] = 0.1   # for example a crab resting where the seabed is normally bare
    sb.mark_fixed(tracks, 1000, 1000)
    assert tracks[0]["fixed_reason"] is None


def test_background_match_tells_a_new_object_from_the_usual_view():
    rng = np.random.default_rng(1)
    usual = cv2.GaussianBlur(rng.integers(0, 255, (180, 320), dtype=np.uint8), (0, 0), 3)
    frame = cv2.cvtColor(usual, cv2.COLOR_GRAY2BGR)
    box = [100, 60, 200, 120]
    assert sb.background_match(frame, box, usual) > 0.95
    changed = frame.copy()
    cv2.ellipse(changed, (150, 90), (40, 20), 0, 0, 360, (10, 10, 10), -1)
    assert sb.background_match(changed, box, usual) < 0.6


def test_too_few_sightings_are_not_called_still():
    tracks = sb.read_tracks({"subsamples": [sample(60, [track(1, 0, STILL[:3])])]})
    sb.mark_fixed(tracks, 1000, 1000)
    assert tracks[0]["fixed_reason"] is None


def test_flags_always_say_why_and_never_name_a_species():
    items = [{"bbox": [0, 900, 40 + 10 * i, 960], "fixed_reason": None, "oddness": float(i)} for i in range(10)]
    sb.assign_flags(items, 1000)
    assert all(len(i["flags"]) == len(i["reasons"]) for i in items)
    assert all("near_seabed" in i["flags"] for i in items)
    assert "unusual" in items[-1]["flags"] and "small_in_frame" in items[0]["flags"]


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "clip.avi"
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5, (640, 360))
    assert out.isOpened()
    for i in range(12):
        frame = np.full((360, 640, 3), 120, np.uint8)
        cv2.rectangle(frame, (20 + 30 * i, 100), (80 + 30 * i, 130), (30, 30, 30), -1)
        out.write(frame)
    out.release()
    return path


@pytest.fixture()
def env(tmp_path, video):
    build(tmp_path)
    species = tmp_path / "species.json"
    species.write_text(json.dumps([
        {"scientific_name": "Carcinus maenas", "common_names": ["European green crab"],
         "flags": {"invasive": True, "at_risk": False}, "id_notes": "Needs checking."},
        {"scientific_name": "Gadus morhua", "common_names": ["Atlantic cod"], "flags": {"invasive": False}}]))
    app = create_app(tmp_path, species_path=species, aliases_path=tmp_path / "a.jsonl")
    run = tmp_path / "_fixture"
    boxes = [[20 + 30 * i, 100, 80 + 30 * i, 130] for i in range(12)]
    v6 = run / "subsamples_v6.json"
    v6.write_text(json.dumps({"video": str(video), "subsamples": [sample(1, [track(1, 0, boxes)])]}))
    bank = sb.build_bank(v6, run / "species_bank")
    return app.test_client(), run, bank


R = "/api/runs/_fixture/species_bank"


def test_build_writes_images_and_no_tracks_data(env):
    _, run, bank = env
    item = bank["items"][0]
    assert bank["counts"] == {"tracks": 1, "candidates": 1, "to_review": 1, "fixed_objects": 0}
    assert "clip" in item["images"] and 0 <= item["clip_offset_s"] <= 2.5
    assert "observations" not in item
    for name in item["images"].values():
        assert (run / "species_bank" / "files" / name).is_file()


def test_missing_video_stops_the_build(tmp_path):
    v6 = tmp_path / "v.json"
    v6.write_text(json.dumps({"video": str(tmp_path / "gone.mp4"), "subsamples": []}))
    with pytest.raises(FileNotFoundError):
        sb.build_bank(v6, tmp_path / "out")


def test_run_without_bank_says_so(tmp_path):
    build(tmp_path)
    client = create_app(tmp_path, aliases_path=tmp_path / "a.jsonl").test_client()
    assert client.get(R).get_json() == {"available": False}
    assert client.post(R + "/decisions", json={}).status_code == 404


def test_page_and_images_are_served(env):
    client, _, bank = env
    assert client.get("/species_bank.html").status_code == 200
    images = bank["items"][0]["images"]
    assert client.get(f"{R}/files/{images['crop']}").mimetype == "image/jpeg"
    clip = client.get(f"{R}/files/{images['clip']}", headers={"Range": "bytes=0-99"})
    assert clip.status_code == 206 and clip.mimetype == "video/mp4"
    for bad in ("..%2Fbank.json", "bank.json", "x.jpg"):
        assert client.get(f"{R}/files/{bad}").status_code == 404


def decide(client, bank, **kw):
    body = {"item_id": bank["items"][0]["id"], "outcome": "species", "species": "Gadus morhua", "reviewer": "Sam"}
    return client.post(R + "/decisions", json={**body, **kw})


def test_flagged_species_is_recorded_with_its_status(env):
    client, _, bank = env
    res = decide(client, bank, species="Carcinus maenas", life_stage="juvenile")
    assert res.status_code == 201
    row = res.get_json()
    assert row["species_flags"] == ["invasive"] and row["status_note"] == "Needs checking."
    assert row["life_stage"] == "juvenile"


def test_latest_decision_wins_and_appears_in_the_csv(env):
    client, _, bank = env
    decide(client, bank)
    decide(client, bank, outcome="not_animal", species="")
    item_id = bank["items"][0]["id"]
    assert client.get(R).get_json()["decisions"][item_id]["outcome"] == "not_animal"
    text = client.get(R + ".csv").get_data(as_text=True)
    assert "not_animal" in text and "Gadus" not in text
    assert "'" not in text   # empty cells stay empty


@pytest.mark.parametrize("change", [{"item_id": "nope"}, {"outcome": "fish"}, {"species": ""},
                                    {"life_stage": "old"}, {"reviewer": ""}])
def test_bad_decisions_are_refused(env, change):
    client, run, bank = env
    assert decide(client, bank, **change).status_code == 400
    assert not (run / "species_bank" / "decisions.jsonl").exists()


def test_decisions_do_not_change_saved_counts(env):
    client, run, bank = env
    before = client.get("/api/runs/_fixture/saved").get_json()
    decide(client, bank)
    assert client.get("/api/runs/_fixture/saved").get_json() == before
