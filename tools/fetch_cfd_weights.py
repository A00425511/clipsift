"""Download the Community Fish Detector weights into models/ and check their sha256.

    python tools/fetch_cfd_weights.py              # all three files
    python tools/fetch_cfd_weights.py --variant nano
    python tools/fetch_cfd_weights.py --check      # verify files already in models/, download nothing

Source: GitHub release 2026.07.06-release of filippovarini/community-fish-detector.
This is the only script that touches the network for weights; the pipeline never downloads anything.
The expected sha256 values were computed from the copies Jacob tested (5 Nov 2026), not taken from the
release page, so a mismatch means the file differs from the tested one.

LICENCE CAVEATS (read before any use beyond a student prototype)
- The model code comes through the rfdetr package, which is Apache 2.0.
- The community-fish-detector repository states no licence for the weights.
- The training data is mixed and includes some non-commercial sources.
Ask Coastal Action and the repository owner before relying on these weights for anything shared or
commercial. Do not describe them as openly licensed.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
TAG = "2026.07.06-release"
BASE = f"https://github.com/filippovarini/community-fish-detector/releases/download/{TAG}/"
FILES = {
    "medium": ("cfd-rf-detr-medium-1024-2026.03.24.cp-011.20260706-release.pth", 134920337,
               "2e94814c7a9318aa2e98e5f6b866ceebe0b5b8f92e6fccb912e7e334a7913911"),
    "nano": ("cfd-rf-detr-nano-640-2026.02.02.cp-011.20260706-release.pth", 122056633,
             "e3eac301b778e251c3826eae247cc783e1f2dab3fd71a18de92bf3e8999c6f10"),
    "small": ("cfd-rf-detr-small-1024-2026.06.06.cp-016.20260706-release.pth", 127327589,
              "da078e3cbd7120f5e1880c66723b21e62acad7260adddc4ac7f32fe1468aa49a"),
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path, expected: str) -> bool:
    return path.is_file() and sha256_of(path) == expected


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(dest)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--variant", choices=sorted(FILES), action="append", help="repeat for several; default all")
    ap.add_argument("--check", action="store_true", help="only verify files already in models/")
    ap.add_argument("--models-dir", default=str(MODELS))
    a = ap.parse_args(argv)
    out = Path(a.models_dir)
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for v in a.variant or sorted(FILES):
        name, size, digest = FILES[v]
        dest = out / name
        if verify(dest, digest):
            print(f"ok       {v}: {name} (sha256 matches)")
            continue
        if a.check:
            print(f"MISSING or WRONG  {v}: {name}")
            bad += 1
            continue
        print(f"download {v}: {name} ({size / 1e6:.0f} MB) from {BASE}")
        try:
            download(BASE + name, dest)
        except Exception as ex:  # network errors vary
            print(f"  failed: {ex}", file=sys.stderr)
            bad += 1
            continue
        if verify(dest, digest):
            print("  sha256 matches")
        else:
            print(f"  sha256 MISMATCH, deleting {dest.name}. Do not use this file.", file=sys.stderr)
            dest.unlink()
            bad += 1
    print("\nLicence caveats: code is Apache 2.0 via rfdetr; the repo states no licence for the weights;"
          "\ntraining data is mixed and includes some non-commercial sources. Check before wider use.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
