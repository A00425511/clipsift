"""Check whether the working V6 detector can load new checkpoint without modifying V6."""
import argparse
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--v6-source", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--image", type=Path, required=True)
    args = p.parse_args()
    if not args.checkpoint.is_file() or not args.image.is_file():
        p.error("Checkpoint or image missing")
    src = args.v6_source / "src"
    if not (src / "clipsift" / "detector.py").is_file():
        p.error("V6 source not found: expected src/clipsift/detector.py")
    sys.path.insert(0, str(src))
    import cv2
    from clipsift.detector import FishDetector
    img = cv2.imread(str(args.image))
    if img is None:
        p.error("Could not read image")
    model = FishDetector(model_path=args.checkpoint)
    pred = model.detect(img)
    print("V6 COMPATIBILITY OK")
    print("Candidates after NMS (confidence >=0.03):", len(pred))
    print("Candidates >=0.15:", int((pred.confidence >= 0.15).sum()))
    print("No V6 source files were modified")

if __name__ == "__main__":
    main()
