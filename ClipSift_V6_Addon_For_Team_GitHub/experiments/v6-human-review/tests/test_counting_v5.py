"""Fast, model-free smoke tests for migrated ClipSift V5 counting module."""
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.clipsift.counting import (
    CandidateCollector, TrackSummary, rank_candidate,
    remove_same_frame_duplicates,
)

assert [rank_candidate(TrackSummary(1, 5, .45, .2)),
        rank_candidate(TrackSummary(2, 2, .18, .12)),
        rank_candidate(TrackSummary(3, 1, .05, .04))] == ["HIGH", "REVIEW", "LOW"]

first = {"track_id": 1, "confidence": .9, "bbox": [10, 10, 30, 30]}
second = {"track_id": 2, "confidence": .8, "bbox": [11, 11, 31, 31]}
kept, removed = remove_same_frame_duplicates([first, second])
assert len(kept) == 1 and kept[0]["track_id"] == 1
assert len(removed) == 1 and removed[0]["track_id"] == 2

collector = CandidateCollector()
for f in range(3):
    data = SimpleNamespace(tracker_id=[1, 2], confidence=[.6, .55],
                           xyxy=[[10, 10, 30, 30], [11, 11, 31, 31]])
    collector.update(data, timestamp=f * .2, frame_index=f)
result = collector.finalize(width=1920, height=1080)
assert result["raw_track_count"] == 2
assert result["max_high_before_dedup"] == 2
assert result["max_high_after_dedup"] == 1
assert result["same_frame_duplicate_events_removed"] == 3
print("V5 counting migration smoke test PASSED")
print("Raw tracks:", result["raw_track_count"])
print("Max HIGH before/after dedup:", result["max_high_before_dedup"], result["max_high_after_dedup"])
print("Duplicate events removed:", result["same_frame_duplicate_events_removed"])
