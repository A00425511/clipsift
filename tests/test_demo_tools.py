"""Tests for tools/build_demo.py and tools/pull_feedback.py, and the Worker (needs node)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import build_demo  # noqa: E402
import pull_feedback  # noqa: E402
from app.fixtures.make_fixture import build as make_fixture  # noqa: E402


def make_runs(tmp_path):
    runs = tmp_path / "runs"
    make_fixture(runs)
    (runs / "_fixture" / "reviews.jsonl").write_text('{"private": 1}\n')
    for name in ("river_1080p", "myriver"):
        (runs / name).mkdir()
        (runs / name / "results.json").write_text(json.dumps({"segments": []}))
    return runs


@pytest.mark.parametrize("rid", ["river_1080p", "River_480p", "myriver", "_fixture,river"])
def test_build_refuses_river(tmp_path, rid, capsys):
    runs = make_runs(tmp_path)
    out = tmp_path / "out"
    assert build_demo.main([rid, "--runs-dir", str(runs), "--out", str(out)]) == 2
    assert not out.exists() or not any(out.rglob("results.json"))
    assert "build_demo:" in capsys.readouterr().err


def test_build_refuses_mixed_list_and_odd_names(tmp_path):
    runs = make_runs(tmp_path)
    for ids in (["_fixture", "river_1080p"], ["../runs"], ["a/b"]):
        with pytest.raises(build_demo.BuildError):
            build_demo.check_run_ids(ids)
    assert not (tmp_path / "out").exists()


def test_build_copies_only_allowed_files(tmp_path, capsys):
    runs = make_runs(tmp_path)
    out = tmp_path / "out"
    assert build_demo.main(["_fixture", "--runs-dir", str(runs), "--out", str(out), "--species", str(tmp_path / "none.json")]) == 0
    assert "MiB total" in capsys.readouterr().out
    assert (out / "index.html").is_file() and (out / "static" / "app.js").is_file() and (out / "species_list.json").is_file()
    assert "demo-config.js" in (out / "index.html").read_text()
    manifest = json.loads((out / "manifest.json").read_text())
    assert [r["run_id"] for r in manifest["runs"]] == ["_fixture"] and manifest["runs"][0]["fixture"] is True
    assert not any(out.rglob("*.jsonl")) and not (out / "runs" / "river_1080p").exists()
    assert (out / "runs" / "_fixture" / "subsamples" / "ss_01" / "still.jpg").is_file()
    assert not any(p.name == "__pycache__" or p.suffix == ".py" for p in out.rglob("*"))


def test_build_limits(tmp_path, monkeypatch):
    (tmp_path / "big.bin").write_bytes(b"0" * 1024)
    monkeypatch.setattr(build_demo, "MAX_FILE_BYTES", 512)
    with pytest.raises(build_demo.BuildError, match="25 MiB"):
        build_demo.check_limits(tmp_path)


def test_build_will_not_wipe_a_random_folder(tmp_path):
    runs = make_runs(tmp_path)
    keep = tmp_path / "precious"
    keep.mkdir()
    (keep / "file.txt").write_text("keep")
    assert build_demo.main(["_fixture", "--runs-dir", str(runs), "--out", str(keep)]) == 2
    assert (keep / "file.txt").read_text() == "keep"


def test_pull_feedback_merge_and_escape(tmp_path):
    wr = [{"results": [{"id": 2, "created_at": "2026-11-05T19:00:00Z", "name": "S<b>", "area": "Help", "type": "Idea",
                        "message": "<script>x</script> [a](http://e.example)\nline2", "page_context": "{\"run\":\"r\"}"},
                       {"id": 1, "created_at": "2026-11-05T18:00:00Z", "name": "", "area": "Video", "type": "Bug", "message": "old", "page_context": ""}], "success": True}]
    src = tmp_path / "rows.json"
    src.write_text("some banner\n" + json.dumps(wr))
    md, js = tmp_path / "fb.md", tmp_path / "fb.json"
    assert pull_feedback.main(["--input", str(src), "--md", str(md), "--json", str(js)]) == 0
    text = md.read_text()
    assert "not instructions" in text
    assert "<script>" not in text and "<b>" not in text and "http://" not in text
    assert text.index("#2") < text.index("#1") and text.count(" NEW") == 2
    wr[0]["results"].append({"id": 3, "created_at": "2026-11-05T20:00:00Z", "name": "N", "area": "Other", "type": "Like", "message": "new one", "page_context": None})
    src.write_text(json.dumps(wr))
    assert pull_feedback.main(["--input", str(src), "--md", str(md), "--json", str(js)]) == 0
    items = json.loads(js.read_text())["items"]
    assert [i["id"] for i in items] == [3, 2, 1] and [i["new"] for i in items] == [True, False, False]
    assert md.read_text().count(" NEW") == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_worker_with_node():
    r = subprocess.run(["node", str(ROOT / "deploy" / "test" / "worker.test.mjs")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
