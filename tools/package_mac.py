"""Build a portable ClipSift for Apple silicon Macs: dist/ClipSift-<version>-mac.zip.

    python3 tools/package_mac.py              # needs internet the first time (Python and libraries)
    python3 tools/package_mac.py --with-model # also the fish detector: rfdetr, torch and the CFD nano weights

The zip holds its own Python (python-build-standalone), the base libraries, ffmpeg (inside imageio-ffmpeg),
the app and a double-click launcher. Nothing is installed on the computer. Work is saved in
~/Documents/ClipSift, so a new version can replace the folder without losing anything.

Only files on the allow-list below go in. Never the team code, runs, labels, footage, model weights,
deploy/ or the briefs. The build stops if the team code turns up anywhere in the package.
Without --with-model the detector is left out, and Step 6 and the after-counting guess say it isn't installed.
With it, the zip is much larger, and the CFD weights' licence must be settled before the zip leaves the team
(see README, "Licence caveats").
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clipsift import __version__  # noqa: E402

PY_TAG = "20261026"
PY_FILE = f"cpython-3.12.16+{PY_TAG}-aarch64-apple-darwin-install_only.tar.gz"
PY_URL = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PY_TAG}/{PY_FILE.replace('+', '%2B')}"
MODEL_LIBS = ["rfdetr==1.11.2"]   # the version the team tested; brings torch and torchvision
LIBS = ["opencv-python-headless", "numpy", "PyYAML", "Flask", "waitress", "imageio-ffmpeg"]

INCLUDE = [  # (source, glob) pairs, relative to the repo
    ("app", "__init__.py"), ("app", "server.py"), ("app", "jobs.py"), ("app/static", "*"),
    ("clipsift", "*.py"), ("clipsift/stages", "*.py"),
    ("config", "default.yaml"),
    ("species", "species_list.json"),
]

LAUNCHER = r'''#!/bin/bash
# Double-click to start ClipSift. It runs on this Mac only. Close this window to stop it.
cd "$(dirname "$0")" || exit 1
DATA="$HOME/Documents/ClipSift"
mkdir -p "$DATA/runs" "$DATA/videos" "$DATA/label_sets"
PY="./python/bin/python3"
export CLIPSIFT_FFMPEG="$("$PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null)"
PORT=$("$PY" -c 'import socket
for p in range(8770, 8790):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p)); print(p); break
    except OSError: pass
    finally: s.close()')
echo "ClipSift __VERSION__. Your work is saved in $DATA"
echo "Leave this window open while you use ClipSift. Close it to stop."
echo "Opening http://127.0.0.1:$PORT in your browser. Technical messages go to $DATA/clipsift.log"
echo "--- $(date) ClipSift __VERSION__ ---" >> "$DATA/clipsift.log"
PYTHONWARNINGS=ignore "$PY" -m app.server --port "$PORT" --open --runs "$DATA/runs" --videos "$DATA/videos" \
  --aliases "$DATA/local_aliases.jsonl" --labels "$DATA/local_labels.jsonl" --label-sets "$DATA/label_sets" 2>> "$DATA/clipsift.log"
echo; echo "ClipSift has stopped. If that was unexpected, the reason is at the end of $DATA/clipsift.log"
read -r -p "Press Return to close this window."
'''

README = """ClipSift __VERSION__ for Mac (Apple silicon)

ClipSift helps your team follow the fish video analysis procedure: visibility, the species watch,
count points, the blind quality check and the report. It runs on this Mac only. Videos and counts
never leave the computer, and it does not count anything for you.

To start
  1. Double-click "Start ClipSift.command". A Terminal window opens and ClipSift opens in your browser.
     The first time, macOS may say it can't check the developer: right-click the file, choose Open,
     then Open again.
  2. Choose your name, then open a video: drop it in, choose it, or paste its path. Pasting the path
     is fastest for large videos, because the file isn't copied.
  3. Leave the Terminal window open while you work. Close it to stop ClipSift.

Where your work is saved
  Documents/ClipSift. Runs, reports and copied videos are there. To update ClipSift, replace this
  folder with the new one. Your work stays where it is.

Included: Python 3.12, OpenCV, NumPy, Flask, PyYAML and ffmpeg (through imageio-ffmpeg, LGPL/GPL).
Not included: the automated fish detector. It is off in this version.
"""


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--with-model", action="store_true", help="include the fish detector and the CFD nano weights")
    a = ap.parse_args()
    build, dist = ROOT / "build", ROOT / "dist"
    name = f"ClipSift-{__version__}-mac" + ("-detector" if a.with_model else "")
    weights = sorted((ROOT / "models").glob("cfd-rf-detr-nano-640-*.pth"))
    if a.with_model and not weights:
        sys.exit("No models/cfd-rf-detr-nano-640-*.pth. Run python tools/fetch_cfd_weights.py first.")
    stage = build / name
    cache = build / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    tarball = cache / PY_FILE
    if not tarball.is_file():
        print("Downloading Python:", PY_URL)
        urllib.request.urlretrieve(PY_URL, tarball)
    print("Unpacking Python")
    with tarfile.open(tarball) as t:
        t.extractall(stage, filter="data")   # unpacks to stage/python
    py = stage / "python" / "bin" / "python3"

    print("Installing libraries")
    run([py, "-m", "pip", "install", "--quiet", "--no-cache-dir", "--disable-pip-version-check", *LIBS, *(MODEL_LIBS if a.with_model else [])])
    run([py, "-m", "pip", "uninstall", "--quiet", "-y", "pip"])   # not needed to run, saves space

    print("Copying the app")
    for folder, pattern in INCLUDE:
        for src in sorted((ROOT / folder).glob(pattern)):
            if src.is_file() and src.suffix not in (".pyc", ".jsonl") and not src.name.startswith("label."):   # label.*: team labelling page
                dest = stage / src.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
    if a.with_model:
        (stage / "models").mkdir()
        shutil.copy2(weights[-1], stage / "models" / weights[-1].name)
    launcher = stage / "Start ClipSift.command"
    launcher.write_text(LAUNCHER.replace("__VERSION__", __version__))
    launcher.chmod(0o755)
    readme = README.replace("__VERSION__", __version__)
    if a.with_model:
        readme = readme.replace("Not included: the automated fish detector. It is off in this version.",
                                "Included: the Community Fish Detector (nano). It is used only after counting: Step 6, and the\n"
                                "optional guess shown after a count is saved. It never counts for you.")
    (stage / "README.txt").write_text(readme)

    print("Checking the package")
    key_file = ROOT / "deploy" / ".team_key"
    key = key_file.read_text().strip().encode() if key_file.is_file() else b""
    for p in stage.rglob("*"):
        if p.is_file() and not p.is_symlink():
            if key and key in p.read_bytes():
                sys.exit(f"STOP: the team code is in {p}")
            ours = p.relative_to(stage).parts[0] != "python"   # Python's own files have names like driver.py
            weight = a.with_model and p.parent == stage / "models" and p.suffix == ".pth"
            if ours and not weight and ("river" in p.name.lower() or p.suffix.lower() in (".mp4", ".mov", ".pth", ".jsonl")):
                sys.exit(f"STOP: unexpected file {p}")
    check = ("import cv2, numpy, flask, yaml, imageio_ffmpeg, waitress; import app.server, clipsift.pipeline; "
             + ("import rfdetr; " if a.with_model else "") + "print('imports ok, ffmpeg at', imageio_ffmpeg.get_ffmpeg_exe())")
    run([py, "-c", check], cwd=stage,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    for junk in stage.rglob("__pycache__"):
        if "python" not in junk.relative_to(stage).parts[:1]:
            shutil.rmtree(junk)

    dist.mkdir(exist_ok=True)
    out = dist / f"{name}.zip"
    out.unlink(missing_ok=True)
    print("Zipping")
    run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(stage), str(out)])
    print(f"Done: {out} ({out.stat().st_size / 2**20:.0f} MiB)")


if __name__ == "__main__":
    main()
