"""Command-line entry point for ClipSift V6 protocol-aware analysis."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clipsift.protocol import (
    read_video_metadata, build_windows, load_timestamps_csv,
)
from src.clipsift.pipeline import analyze_window


def main():
    parser = argparse.ArgumentParser(description="Analyze protocol subsamples in a full survey video")
    parser.add_argument("video", help="Full input video path")
    choices = parser.add_mutually_exclusive_group(required=True)
    choices.add_argument("--timestamps", nargs="+", help='e.g. --timestamps "22:00" "30:00"')
    choices.add_argument("--csv", help="CSV with timestamp column")
    parser.add_argument("--context", type=float, default=5.0, help="Seconds either side (default 5)")
    parser.add_argument("--count-window", type=float, default=1.0, help="Centered counting duration (default 1)")
    parser.add_argument("--fps", type=float, default=5.0, help="Target analysis FPS (default 5)")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "v6"))
    parser.add_argument("--save-clips", action="store_true", help="Save annotated context MP4 files")
    parser.add_argument("--dry-run", action="store_true", help="Print windows without loading the model")
    args = parser.parse_args()

    metadata = read_video_metadata(args.video)
    timestamps = args.timestamps if args.timestamps is not None else load_timestamps_csv(args.csv)
    windows = build_windows(
        timestamps, metadata.duration_seconds,
        context_radius_seconds=args.context,
        count_window_seconds=args.count_window,
    )
    print(f"Video: {metadata.width}x{metadata.height}, {metadata.fps:.4f} FPS, "
          f"{metadata.duration_seconds:.2f}s")
    for i, w in enumerate(windows, 1):
        print(f"Subsample {i}: point={w.timestamp_seconds:.2f}s "
              f"context=[{w.context_start_seconds:.2f}, {w.context_end_seconds:.2f}] "
              f"count=[{w.count_start_seconds:.2f}, {w.count_end_seconds:.2f})")
    if args.dry_run:
        print("Dry run: no inference performed")
        return

    # Initialize model once, but create a fresh tracker for each independent window.
    from src.clipsift.detector import FishDetector
    from src.clipsift.tracker import FishTracker

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    detector = FishDetector()
    results = []
    for i, window in enumerate(windows, 1):
        print(f"Processing subsample {i}/{len(windows)} ...", flush=True)
        clip_path = output_dir / f"subsample_{i:03d}_context.mp4" if args.save_clips else None
        result = analyze_window(
            metadata, window, detector, FishTracker,
            target_fps=args.fps, output_video=clip_path,
        )
        results.append(result)
        print(f"  Count-window HIGH candidates: {result['max_high_candidates_in_count_window']}; "
              f"REVIEWABLE: {result['max_reviewable_candidates_in_count_window']} "
              "(not confirmed fish)", flush=True)

    summary = {
        "version": "ClipSift V6 prototype",
        "video": metadata.path,
        "protocol_note": "Provisional 1s count window; human review required",
        "subsamples": results,
    }
    json_path = output_dir / "subsamples_v6.json"
    with json_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)

    csv_path = output_dir / "review_queue_v6.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        fields = ["subsample_timestamp_seconds", "count_start_seconds", "count_end_seconds",
                  "max_high_candidates_in_count_window", "max_reviewable_candidates_in_count_window",
                  "status", "confirmed_fish_count", "context_video"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow({name: result.get(name) for name in fields})
    print(f"Saved JSON: {json_path}")
    print(f"Saved review CSV: {csv_path}")
    print("Candidate peaks are NOT validated abundance. Human confirmation is required.")


if __name__ == "__main__":
    main()
