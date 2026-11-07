"""The protocol workflow: profiles, visibility, the automated blind check, and the end-of-run review set."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.fixtures.make_fixture import build  # noqa: E402
from app.server import create_app  # noqa: E402
from clipsift import protocol as proto  # noqa: E402
from clipsift import qc  # noqa: E402
from clipsift import verify  # noqa: E402
from clipsift.schema import Detection  # noqa: E402

R = "/api/runs/_fixture"
LIMIT, TARGET = 6, 95


def row(counter, fish, inv=0, sid="ss_01", pass_="primary"):
    return {"subsample_id": sid, "counter": counter, "pass": pass_, "total_fish_count": fish, "invertebrate_count": inv}


@pytest.fixture()
def env(tmp_path):
    build(tmp_path)
    app = create_app(tmp_path)
    return app.test_client(), tmp_path / "_fixture"


def sample(client):
    return client.get(R + "/saved").get_json()["qc_check"]["sample"]


def count_all(client, who="Ana", fish=20):
    for s in client.get(R + "/results").get_json()["subsamples"]:
        assert client.post(R + "/subsample_reviews", json={"subsample_id": s["subsample_id"], "counter": who, "total_fish_count": fish,
                                                           "invertebrate_count": 0}).status_code == 201


def blind(client, who="Ben", fish=20, ids=None, pass_="qc_blind"):
    for sid in ids if ids is not None else sample(client):
        assert client.post(R + "/subsample_reviews", json={"subsample_id": sid, "counter": who, "pass": pass_, "total_fish_count": fish,
                                                           "invertebrate_count": 0}).status_code == 201


def test_fish_and_invertebrates_are_checked_separately():
    p = qc.assess_point([row("a", 100, 1), row("b", 100, 2)], LIMIT)
    assert p["fish_diff"] == 0 and round(p["inv_diff"], 1) == 66.7 and p["recount_needed"] is False and p["small_gap"] is True
    assert qc.assess_point([row("a", 100, 1), row("b", 100, 4)], LIMIT)["recount_needed"] is True


def test_a_small_gap_shows_its_percent_but_is_not_flagged():
    p = qc.assess_point([row("a", 2), row("b", 3)], LIMIT)
    assert p["percent_diff"] == 40 and p["recount_needed"] is False
    assert qc.assess_point([row("a", 2), row("b", 3)], LIMIT, small_gap=0)["recount_needed"] is True
    assert qc.assess_point([row("a", 40), row("b", 42)], LIMIT)["recount_needed"] is False   # 4.9%: under the limit anyway


def test_the_two_counts_are_averaged_and_a_recount_settles_a_frame():
    p = qc.assess_point([row("a", 100), row("b", 120), row("c", 118)], LIMIT)
    assert p["first_counter"] == "b" and p["second_counter"] == "c" and p["average_fish"] == 119 and p["recount_needed"] is False


def test_verdict_walks_through_every_status():
    point = lambda d: {"percent_diff": d, "recount_needed": d > LIMIT}
    v = lambda ids, pts: qc.verdict(["a", "b"], ids, pts, LIMIT, TARGET)["status"]
    assert qc.verdict([], set(), {}, LIMIT, TARGET)["status"] == "no_sample"
    assert v({"a"}, {}) == "counting"
    assert v({"a", "b"}, {"a": point(0)}) == "waiting_second"
    assert v({"a", "b"}, {"a": point(0), "b": point(40)}) == "review"
    assert v({"a", "b"}, {"a": point(5.5), "b": point(5.5)}) == "pass"   # low agreement is shown, and blocks nothing
    assert v({"a", "b"}, {"a": point(0), "b": point(2)}) == "pass"


def test_empty_frames_cannot_hide_the_frame_with_fish():
    pts = {"a": qc.assess_point([row("x", 0), row("y", 0)], LIMIT), "b": qc.assess_point([row("x", 0), row("y", 0)], LIMIT),
           "c": qc.assess_point([row("x", 20), row("y", 22)], LIMIT)}
    v = qc.verdict(["a", "b", "c"], {"a", "b", "c"}, pts, LIMIT, TARGET)
    assert v["agreement"] == 96.8 and v["n_animal_frames"] == 1 and v["animal_agreement"] == 90.5


def test_every_count_stays_listed_after_a_recount():
    p = qc.assess_point([row("Ana", 20), row("Ben", 25), row("Cy", 22)], LIMIT)
    assert [c["counter"] for c in p["counts"]] == ["Ana", "Ben", "Cy"] and round(p["all_average_fish"], 2) == 22.33
    assert p["average_fish"] == 21


def test_agreement_cannot_go_below_zero():
    assert qc.verdict(["a"], {"a"}, {"a": {"percent_diff": 200, "recount_needed": True}}, LIMIT, TARGET)["agreement"] == 0


def test_each_video_gets_its_own_random_frames():
    pc = {"qc_share": 0.1, "qc_min": 6, "qc_max": 12, "qc_seed": 4321}
    assert proto.pick_qc(15, pc, "a") == proto.pick_qc(15, pc, "a")
    assert len({frozenset(proto.pick_qc(15, pc, str(i))) for i in range(6)}) > 1


def test_interrater_totals_across_videos():
    one = [row("Ana", 10), row("Ben", 10, pass_="qc_blind")]
    two = [row("Ana", 30, sid="ss_02"), row("Ben", 20, sid="ss_02", pass_="qc_blind")]
    out = qc.interrater([one, two], LIMIT)
    pair = out["pairs"][0]
    assert (pair["a"], pair["b"], pair["frames"], pair["within"], pair["mean_percent_diff"], pair["mean_fish_gap"]) == ("Ana", "Ben", 2, 1, 20.0, 5)


def test_profiles_are_kept_once_each(env):
    c, _ = env
    assert c.get("/api/profiles").get_json()["profiles"] == []
    assert c.post("/api/profiles", json={"name": "  Ana "}).get_json()["name"] == "Ana"
    c.post("/api/profiles", json={"name": "ana"})
    c.post("/api/profiles", json={"name": "Ben"})
    assert c.get("/api/profiles").get_json()["profiles"] == ["Ana", "Ben"]
    assert c.post("/api/profiles", json={"name": ""}).status_code == 400


def test_each_person_rates_visibility_and_the_latest_counts(env):
    c, _ = env
    for who, cat in (("Ana", "<0.5 m"), ("Ben", "0.5-1.0 m"), ("Ana", "1.0-1.5 m")):
        assert c.post(R + "/visibility", json={"observer": who, "category": cat}).status_code == 201
    rows = {r["observer"]: r["category"] for r in c.get(R + "/saved").get_json()["visibility"]}
    assert rows == {"Ana": "1.0-1.5 m", "Ben": "0.5-1.0 m"}
    assert c.post(R + "/visibility", json={"observer": "Ana", "category": "murky"}).status_code == 400
    assert "Ana: 1.0-1.5 m" in c.get(R + "/export_summary.csv").get_data(as_text=True)


def test_visibility_direction_is_saved_and_exported(env):
    c, _ = env
    body = {"subsample_id": "ss_01", "counter": "Ana", "total_fish_count": 1, "invertebrate_count": 0, "visibility_change": True, "visibility_direction": "decreasing"}
    assert c.post(R + "/subsample_reviews", json=body).status_code == 201
    assert "decreasing" in c.get(R + "/export.csv").get_data(as_text=True)
    assert c.post(R + "/subsample_reviews", json={**body, "visibility_direction": "sideways"}).status_code == 400


def test_a_blind_count_must_come_from_someone_else(env):
    c, _ = env
    count_all(c)
    res = c.post(R + "/subsample_reviews", json={"subsample_id": "ss_01", "counter": "ana", "pass": "qc_blind", "total_fish_count": 3, "invertebrate_count": 0})
    assert res.status_code == 400 and "different person" in res.get_json()["error"]


def test_the_check_recommends_a_recount_then_passes(env):
    c, _ = env
    s0 = c.get(R + "/saved").get_json()["qc_check"]
    assert s0["status"] == "counting" and 1 <= s0["n_sample"] <= 12
    count_all(c)
    assert c.get(R + "/saved").get_json()["qc_check"]["status"] == "waiting_second"
    ids = sample(c)
    blind(c, ids=ids[1:])
    blind(c, ids=ids[:1], fish=30)
    saved = c.get(R + "/saved").get_json()
    assert saved["qc_check"]["status"] == "review" and saved["qc_check"]["recount"] == ids[:1]
    blind(c, who="Cy", ids=ids[:1], pass_="recount")
    saved = c.get(R + "/saved").get_json()
    assert saved["qc_check"]["status"] == "pass" and saved["qc"][ids[0]]["n_counts"] == 3


def test_meancount_uses_the_average_of_checked_frames(env):
    c, _ = env
    count_all(c, fish=20)
    ids = sample(c)
    blind(c, ids=ids, fish=21)   # 4.9% apart, so each frame is settled at 20.5
    saved = c.get(R + "/saved").get_json()
    n = saved["n_subsamples"]
    assert saved["mean_count_reviewed"] == 20 and saved["qc_check"]["status"] == "pass"
    assert saved["mean_count_final"] == round((20 * (n - len(ids)) + 20.5 * len(ids)) / n, 3)
    assert c.get("/api/progress").get_json()["videos"][0]["qc_status"] == "pass"
    assert c.get("/api/interrater").get_json()["pairs"][0]["frames"] == len(ids)


def test_home_hides_meancount_while_a_blind_count_is_due(env):
    c, _ = env
    count_all(c)
    assert c.get("/api/progress").get_json()["videos"][0]["mean_count"] is None
    blind(c)
    assert c.get("/api/progress").get_json()["videos"][0]["mean_count"] == 20


def test_species_named_in_a_recount_reach_the_summary(env):
    c, _ = env
    count_all(c)
    c.post(R + "/subsample_reviews", json={"subsample_id": "ss_01", "counter": "Ben", "pass": "recount", "total_fish_count": 20, "invertebrate_count": 0, "species_counts": {"Menidia menidia": 20}})
    text = c.get(R + "/export_summary.csv").get_data(as_text=True)
    assert "Menidia menidia" in text and "QC frames with animals" in text


def test_empty_export_cells_stay_empty(env):
    c, _ = env
    c.post(R + "/subsample_reviews", json={"subsample_id": "ss_01", "counter": "Ana", "total_fish_count": 1, "invertebrate_count": 0})
    for name in ("export.csv", "export_summary.csv"):
        text = c.get(f"{R}/{name}").get_data(as_text=True)
        assert ",'," not in text and not text.rstrip().endswith("'")


def test_typed_chapter_path_brings_its_other_parts(env, tmp_path):
    c, _ = env
    folder = tmp_path / "card"
    folder.mkdir()
    for name in ("GX010221.mp4", "GX020221.mp4", "GX010222.mp4"):
        (folder / name).write_bytes(b"x")
    res = c.post("/api/jobs", json={"path": str(folder / "GX010221.mp4"), "name": "joined", "layer": 0})
    assert res.status_code == 201 and res.get_json()["videos"] == ["GX010221.mp4", "GX020221.mp4"]


class FakeDetector:
    """One box on a marked animal, one on nothing, at every frame."""
    source = model_version = "fake"

    def detect(self, frame, t):
        w = frame.shape[1]
        s = w / 1000
        return [Detection(t=t, box=[100 * s, 100 * s, 40 * s, 40 * s], score=0.8 - t / 10000, source="fake"),
                Detection(t=t, box=[(500 + t % 300) * s, 300 * s, 40 * s, 40 * s], score=0.3, source="fake")]


@pytest.fixture()
def review(env):
    c, run = env
    results = json.loads((run / "results.json").read_text())
    W = results["recording"]["width"]
    s = W / 1000
    count_all(c, fish=2)
    for sub in results["subsamples"]:
        for x, y in ((120, 120), (800, 40)):   # the second has no box near it
            assert c.post(R + "/point_labels", json={"subsample_id": sub["subsample_id"], "counter": "Ana", "kind": "fish", "x": x * s, "y": y * s}).status_code == 201
    start, end = results["protocol"].get("window_start_s") or 0, results["subsamples"][-1]["t_s"] + 2
    out = cv2.VideoWriter(str(run / "window.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 2, (320, 180))
    for _ in range(int((end - start) * 2)):
        out.write(np.full((180, 320, 3), 90, np.uint8))
    out.release()
    cfg = {"static_filter": {"enabled": False}}
    verify.build_review_set(run, cfg, detector=FakeDetector(), total=12, log=lambda *_: None)
    return c, run


def test_review_set_mixes_its_sources(review):
    _, run = review
    bank = json.loads((run / "review_set" / "bank.json").read_text())
    assert bank["counts"]["total"] == 12 and bank["counts"]["agree"] and bank["counts"]["model_only"] and bank["counts"]["elsewhere"]
    assert {i["source"] for i in bank["items"]} == {"agree", "model_only", "elsewhere"}
    item = bank["items"][0]
    assert (run / "review_set" / "files" / item["images"]["crop"]).is_file() and item["bbox"][2] > item["bbox"][0]


def test_share_passes_on_when_a_source_runs_short():
    pool = lambda n: [{"max_confidence": i / 10} for i in range(n)]
    picked = verify.choose({"agree": pool(1), "model_only": pool(50), "elsewhere": pool(50)}, 20, "x")
    assert len(picked) == 20


def test_no_item_is_picked_twice():
    for size in range(10, 60):
        pool = [{"id": f"{size}-{i}", "max_confidence": i / 100} for i in range(size)]
        picked = verify.choose({"agree": pool, "model_only": [], "elsewhere": []}, 10, str(size))
        assert len({i["id"] for i in picked}) == len(picked) == 10


def test_source_stays_hidden_until_someone_decides(review):
    c, _ = review
    url = R + "/species_bank?set=review"
    item = c.get(url).get_json()["bank"]["items"][0]
    assert "source" not in item and "max_confidence" not in item
    res = c.post(R + "/species_bank/decisions?set=review", json={"item_id": item["id"], "outcome": "fish", "reviewer": "Ana"})
    assert res.status_code == 201
    after = next(i for i in c.get(url).get_json()["bank"]["items"] if i["id"] == item["id"])
    assert "source" in after
    assert c.get(R + "/saved").get_json()["review_set"]["done"] == 1


def test_review_set_outcomes_and_training_export(review):
    c, _ = review
    items = c.get(R + "/species_bank?set=review").get_json()["bank"]["items"]
    ok = c.post(R + "/species_bank/decisions?set=review", json={"item_id": items[0]["id"], "outcome": "equipment", "reviewer": "Ana"})
    assert ok.status_code == 201
    assert c.post(R + "/species_bank/decisions?set=review", json={"item_id": items[1]["id"], "outcome": "not_animal", "reviewer": "Ana"}).status_code == 400
    text = c.get(R + "/review_set.csv").get_data(as_text=True)
    assert "training_label" in text.splitlines()[0] and "equipment,not_animal" in text


def test_review_set_never_changes_counts(review):
    c, _ = review
    before = c.get(R + "/saved").get_json()
    item = c.get(R + "/species_bank?set=review").get_json()["bank"]["items"][0]
    c.post(R + "/species_bank/decisions?set=review", json={"item_id": item["id"], "outcome": "background", "reviewer": "Ana"})
    after = c.get(R + "/saved").get_json()
    assert before["mean_count_final"] == after["mean_count_final"] and before["latest_primary"] == after["latest_primary"]


def test_review_set_refuses_before_counting(env, monkeypatch):
    c, _ = env
    res = c.post(R + "/review_set", json={"count": 36})
    assert res.status_code == 400


def test_review_summary_lists_real_animals_the_counter_missed(review):
    c, run = review
    bank = json.loads((run / "review_set" / "bank.json").read_text())
    item = next(i for i in bank["items"] if i["source"] == "model_only")
    c.post(R + "/species_bank/decisions?set=review", json={"item_id": item["id"], "outcome": "fish", "reviewer": "Ana"})
    assert c.get(R + "/saved").get_json()["review_set"]["missed"][0]["subsample_id"] == item["subsample_id"]


def test_unknown_fish_is_not_counted_as_a_species(env):
    c, _ = env
    c.post(R + "/recording_notes", json={"species_observed": ["Actinopterygii", "Unknown fish", "Gadus morhua"]})
    row = c.get(R + "/export_summary.csv").get_data(as_text=True).splitlines()
    assert dict(zip(next(__import__("csv").reader([row[0]])), next(__import__("csv").reader([row[1]]))))["Number of species identified"] == "1"


def test_survey_date_reaches_the_job(env, tmp_path):
    c, _ = env
    video = tmp_path / "GX010999.mp4"
    video.write_bytes(b"x")
    assert c.post("/api/jobs", json={"path": str(video), "name": "dated", "date": "2025-08-27"}).status_code == 201


def test_marks_match_inside_a_box_or_nearby():
    box = Detection(t=0, box=[100, 100, 50, 50], score=0.5, source="x")
    pairs, loose, missed = verify.match([box], [{"x": 120, "y": 120}, {"x": 900, "y": 900}], 3840)
    assert len(pairs) == 1 and not loose and missed == [{"x": 900, "y": 900}]
