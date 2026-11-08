"""Compare original and fine-tuned detector on one image; save predictions and previews.

Example:
 python scripts/compare_image.py --image F:\\...\\T1_1320s.jpg \\
  --checkpoint F:\\...\\digi4eco_best.pth --baseline F:\\...\\cfd-small.pth \\
  --mode whole --device cpu --output results\\whole
"""
from __future__ import annotations
import argparse
import csv
import gc
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clipsift_finetuned import FishDetector  # noqa: E402


def annotate(frame, detections, threshold, label):
    out = frame.copy()
    shown = 0
    for box, confidence in zip(detections.xyxy, detections.confidence):
        if confidence < threshold:
            continue
        shown += 1
        x1, y1, x2, y2 = [int(round(v)) for v in box]
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(out, f"{confidence:.2f}", (x1, max(22, y1-5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
    print(f"{label}: total candidates={len(detections)}, >= {threshold}={shown}, >=0.30={int((detections.confidence >= 0.30).sum())}")
    return out, shown


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image", required=True, type=Path)
    p.add_argument("--checkpoint", required=True, type=Path, help="Fine-tuned checkpoint_best_total.pth")
    p.add_argument("--baseline", type=Path, help="Original CFD checkpoint (optional)")
    p.add_argument("--mode", choices=("whole", "tiled"), default="whole")
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--resolution", type=int, default=512)
    p.add_argument("--tile-size", type=int, default=1024)
    p.add_argument("--overlap", type=int, default=256)
    p.add_argument("--threshold", type=float, default=0.03)
    p.add_argument("--nms", type=float, default=0.50)
    p.add_argument("--show-threshold", type=float, default=0.15)
    p.add_argument("--output", type=Path, default=Path("results") / "image_test")
    args = p.parse_args()

    if not args.image.is_file():
        p.error(f"Image not found: {args.image}")
    for ckpt in [args.checkpoint, args.baseline]:
        if ckpt is not None and not ckpt.is_file():
            p.error(f"Checkpoint not found: {ckpt}")
    frame = cv2.imread(str(args.image))
    if frame is None:
        p.error(f"OpenCV could not read: {args.image}")
    args.output.mkdir(parents=True, exist_ok=True)

    models = [("finetuned", args.checkpoint)]
    if args.baseline:
        models.insert(0, ("original", args.baseline))
    outputs = []
    report = {"image": args.image.name, "width": frame.shape[1], "height": frame.shape[0],
              "mode": args.mode, "resolution": args.resolution, "tile_size": args.tile_size,
              "overlap": args.overlap, "confidence_floor": args.threshold,
              "nms_threshold": args.nms, "display_threshold": args.show_threshold,
              "models": {}}

    for label, ckpt in models:
        print(f"Loading {label} from {ckpt} ...")
        detector = FishDetector(
            model_path=ckpt, confidence=args.threshold, nms_threshold=args.nms,
            resolution=args.resolution, device=args.device,
            tiled=args.mode == "tiled", tile_size=args.tile_size, overlap=args.overlap,
        )
        predictions = detector.detect(frame)
        annotated, n = annotate(frame, predictions, args.show_threshold, label)
        annotated_path = args.output / f"{label}_{args.mode}.jpg"
        if not cv2.imwrite(str(annotated_path), annotated):
            raise RuntimeError(f"Could not save {annotated_path}")
        with (args.output / f"{label}_{args.mode}_boxes.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["x1", "y1", "x2", "y2", "confidence", "status"])
            for box, confidence in zip(predictions.xyxy, predictions.confidence):
                writer.writerow([*[round(float(v), 2) for v in box], round(float(confidence), 5), "UNVERIFIED"])
        report["models"][label] = {
            "checkpoint_name": ckpt.name, "all_candidates_after_nms": len(predictions),
            "candidates_display_threshold": n,
            "candidates_confidence_ge_030": int((predictions.confidence >= .30).sum()),
            "confirmed_fish": None,
        }
        thumb = cv2.resize(annotated, (1200, round(frame.shape[0] * 1200 / frame.shape[1])))
        cv2.putText(thumb, f"{label} | candidates >= {args.show_threshold}: {n}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, .9, (255, 255, 255), 2)
        outputs.append(thumb)
        del detector
        gc.collect()

    if len(outputs) == 2:
        comparison = cv2.hconcat(outputs)
        cv2.imwrite(str(args.output / f"comparison_{args.mode}.jpg"), comparison)
    with (args.output / f"summary_{args.mode}.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("COMPLETE. Outputs:", args.output.resolve())
    print("These are candidate detections, NOT validated fish counts.")

if __name__ == "__main__":
    main()
