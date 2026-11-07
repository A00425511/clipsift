"""Run: python tests/test_protocol.py [optional_video_path]"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clipsift.protocol import (parse_timestamp, build_windows,
                                   read_video_metadata, load_timestamps_csv)


def run():
    assert parse_timestamp('22:00') == 1320.0
    assert parse_timestamp('01:02:03.5') == 3723.5
    assert parse_timestamp('17.8') == 17.8
    windows = build_windows(['0:02', '22:00'], duration_seconds=2147.28)
    assert windows[0].context_start_seconds == 0.0
    assert windows[0].context_end_seconds == 7.0
    assert windows[0].count_start_seconds == 1.5
    assert windows[0].count_end_seconds == 2.5
    assert windows[1].context_start_seconds == 1315.0
    assert windows[1].context_end_seconds == 1325.0
    assert windows[1].counts_at(1320.0)
    assert not windows[1].counts_at(1321.0)
    csv_path = ROOT / 'config' / 'subsample_points_example.csv'
    if csv_path.is_file():
        print('CSV timestamps:', load_timestamps_csv(csv_path))
    print('Protocol unit tests PASSED')
    if len(sys.argv) > 1:
        metadata = read_video_metadata(sys.argv[1])
        print('Video metadata:', metadata)
        point = min(1320.0, metadata.duration_seconds / 2)
        for w in build_windows([point], metadata.duration_seconds):
            print('Example window:', w)


if __name__ == '__main__':
    run()
