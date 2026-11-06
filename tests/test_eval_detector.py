import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import eval_detector as ev


def _frame(boxes, scores, dots, width=1000):
    return {"boxes": boxes, "scores": scores, "dots": np.array(dots, float), "width": width}


def test_perfect_boxes_beat_chance_and_count_error_is_signed():
    dots = [(100 + 40 * i, 300) for i in range(10)]
    boxes = [[x - 10, 290, x + 10, 310] for x, _ in dots]
    r = ev.score_frames([_frame(boxes, [0.9] * 10, dots)], 0.05)
    assert r["recall"] == 1 and r["precision"] == 1 and r["count_error"] == 0
    assert r["chance_recall"] < 0.5
    r = ev.score_frames([_frame(boxes + [[900, 290, 920, 310]], [0.9] * 11, dots)], 0.05)
    assert r["count_error"] == 1 and r["precision"] < 1


def test_threshold_sweep_and_chance_always_printed():
    dots = [(100, 300), (200, 300)]
    boxes = [[90, 290, 110, 310], [190, 290, 210, 310]]
    rows = ev.sweep([_frame(boxes, [0.9, 0.04], dots)], [0.03, 0.05])
    assert [r["boxes"] for r in rows] == [2, 1]
    text = ev.format_table(rows)
    assert "CHANCE" in text and "count error" in text


def test_each_box_is_used_once_and_strict_is_tighter():
    dots = [(100, 100), (105, 100)]
    assert ev.match_hits([[90, 90, 110, 110]], dots) == 1
    assert ev.match_hits([[60, 60, 100, 100]], [(105, 105)], **ev.STRICT) == 0  # outside, centre 35 px away
    assert ev.match_hits([[60, 60, 100, 100]], [(105, 105)], **ev.LENIENT) == 1
