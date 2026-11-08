"""Check local paths and environment without running expensive inference."""
import argparse
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--baseline", type=Path)
    args = p.parse_args()

    import torch
    print("Python environment:")
    for name in ("rfdetr", "supervision", "opencv-python", "torch", "trackers"):
        try:
            print(f"  {name}: {version(name)}")
        except PackageNotFoundError:
            print(f"  {name}: NOT INSTALLED")
    print("  CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("  GPU:", torch.cuda.get_device_name(0))
    print("  CPU inference supported: yes (possibly slow)")
    for label, file in (("Fine-tuned checkpoint", args.checkpoint), ("Test image", args.image), ("Baseline checkpoint", args.baseline)):
        if file is not None:
            exists = file.is_file()
            print(f"  {label}: {'OK' if exists else 'MISSING'} | {file}")
            if not exists:
                raise SystemExit(2)
    print("PREFLIGHT OK. Next: run compare_image.py")

if __name__ == "__main__":
    main()
