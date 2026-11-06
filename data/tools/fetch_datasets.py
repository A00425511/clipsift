#!/usr/bin/env python3
"""Fetch the ClipSift training images (Puget Sound + Tweed) and unpack only the
images named in our train/val/test split files.

Standard library only. Python 3.9+. Works on Windows and macOS.

Examples
  python data/tools/fetch_datasets.py                       # everything
  python data/tools/fetch_datasets.py --only tweed          # just the smaller set
  python data/tools/fetch_datasets.py --zip-dir D:\\zips     # zips already on disk
  python data/tools/fetch_datasets.py --check               # verify only, no download

Result layout under --dest (this matches "image_root" inside each split file):
  <dest>/Puget Sound LILA/images/<file>.jpg
  <dest>/Tweed Estuary/images/<file>.jpg
  <dest>/splits/<six split>.json
Exit code is 0 on success and non-zero on any failure.
"""
import argparse
import gzip
import hashlib
import io
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

# --------------------------------------------------------------------------
# Facts taken from the source manifests (Footage Sources/*/manifest.json).
# --------------------------------------------------------------------------
DATASETS = {
    "puget": {
        "label": "Puget Sound (NOAA, via LILA BC)",
        # Exact URL from Puget Sound LILA/SOURCE.md
        "url": "https://storage.googleapis.com/public-datasets-lila/noaa-psnf/noaa_estuary_fish-images.zip",
        "zip_name": "noaa_estuary_fish-images.zip",
        "zip_folder": "Puget Sound LILA",
        "bytes": 7694934801,
        "sha256": "a3d4472658bd6e094724d0e47bc45c740bbf680977e2321abe148320f43eed75",
        "member_prefix": "JPEGImages/",     # images sit in this folder inside the zip
        "image_root": "Puget Sound LILA/images",
        "splits": {"train": 17260, "val": 1737, "test": 2626},   # image counts
        "img_gb": 1.8,                       # unpacked images (1,770,964,091 bytes)
    },
    "tweed": {
        "label": "Tweed / Tallebudgera luderick (PANGAEA)",
        # Tweed SOURCE.md and manifest.json record only the DOI. The direct file link was
        # read from the PANGAEA record page https://doi.pangaea.de/10.1594/PANGAEA.926930
        "url": "https://download.pangaea.de/dataset/926930/files/Fish_automated_identification_and_counting.zip",
        "zip_name": "Fish_automated_identification_and_counting.zip",
        "zip_folder": "Tweed Estuary",
        "bytes": 3703803276,
        "sha256": "43457dae66a7061906aa6a19d4a3be1c5d81eb0de0b908eb0b16cb0d1d50eeba",
        "inner_zip": "Fish_automated_identification_and_counting/luderick-seagrass.zip",
        "member_prefix": "",                 # frames sit at the top level of the nested zip
        "image_root": "Tweed Estuary/images",
        "splits": {"train": 2994, "val": 643, "test": 643},
        "img_gb": 3.7,                       # unpacked images (3,704,816,695 bytes)
    },
}
USER_AGENT = "clipsift-fetch/1.0 (student hackathon data fetch)"
CHUNK = 1024 * 1024


class Fail(Exception):
    pass


def say(msg=""):
    print(msg, flush=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def default_dest():
    repo = Path(__file__).resolve().parents[2]      # data/tools/fetch_datasets.py -> repo root
    return repo.parent / "Footage Sources"


def split_gz_dir():
    return Path(__file__).resolve().parents[1] / "splits"


def human(n):
    return "%.2f GB" % (n / 1e9) if n >= 1e9 else "%.1f MB" % (n / 1e6)


def sha256_file(path):
    h = hashlib.sha256()
    total = path.stat().st_size
    done = 0
    last = time.time()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
            done += len(b)
            if time.time() - last > 10:
                say("  checking... %d%%" % (100 * done // max(total, 1)))
                last = time.time()
    return h.hexdigest()


def safe_target(root, name):
    """Return root/name only if it is a plain relative path that stays inside root."""
    if not name or "\\" in name or ":" in name or name.startswith("/"):
        raise Fail("unsafe file name refused: %r" % name)
    parts = PurePosixPath(name).parts
    if any(p in ("..", ".", "") for p in parts):
        raise Fail("unsafe file name refused: %r" % name)
    target = (root / Path(*parts)).resolve()
    root_r = root.resolve()
    if root_r != target and root_r not in target.parents:
        raise Fail("path escapes destination, refused: %r" % name)
    return target


def load_split_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Splits
# --------------------------------------------------------------------------
def write_splits(dest):
    src = split_gz_dir()
    out = dest / "splits"
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.json.gz"))
    if len(files) != 6:
        raise Fail("expected 6 split files in %s, found %d" % (src, len(files)))
    for gz in files:
        with gzip.open(gz, "rb") as fi:
            data = fi.read()
        target = out / gz.name[:-3]
        if not (target.exists() and target.read_bytes() == data):
            target.write_bytes(data)
    say("Split files written to %s" % out)


def names_for(dest, key):
    names = []
    for s in DATASETS[key]["splits"]:
        p = dest / "splits" / ("%s_%s.json" % (key, s))
        if not p.exists():
            raise Fail("missing split file %s (run without --check first)" % p)
        d = load_split_file(p)
        if d.get("image_root") != DATASETS[key]["image_root"]:
            raise Fail("%s has image_root %r, expected %r" % (p.name, d.get("image_root"), DATASETS[key]["image_root"]))
        names.extend(i["file_name"] for i in d["images"])
    if len(set(names)) != len(names):
        raise Fail("duplicate image names across %s splits" % key)
    return names


# --------------------------------------------------------------------------
# Download with resume
# --------------------------------------------------------------------------
def download(url, part, expected, label):
    attempts = 0
    while True:
        have = part.stat().st_size if part.exists() else 0
        if have > expected:
            part.unlink()
            have = 0
        if have == expected:
            return
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        if have:
            req.add_header("Range", "bytes=%d-" % have)
            say("  resuming %s at %s of %s" % (label, human(have), human(expected)))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:
                    say("  server ignored the resume request; starting again")
                    have = 0
                mode = "ab" if have else "wb"
                got = have
                last_pct = -1
                with open(part, mode) as f:
                    while True:
                        b = r.read(CHUNK)
                        if not b:
                            break
                        f.write(b)
                        got += len(b)
                        pct = 100 * got // expected
                        if pct >= last_pct + 5:
                            last_pct = pct
                            say("  %s: %d%% (%s)" % (label, pct, human(got)))
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            attempts += 1
            if attempts > 8:
                raise Fail("download of %s keeps failing (%s). Run the same command again to resume." % (label, e))
            say("  connection problem (%s); retrying in %ds" % (e, min(5 * attempts, 30)))
            time.sleep(min(5 * attempts, 30))
            continue
        size = part.stat().st_size
        if size == expected:
            return
        attempts += 1
        if attempts > 8:
            raise Fail("download of %s ended at %d bytes, expected %d" % (label, size, expected))
        say("  stopped early at %s; retrying" % human(size))


def get_zip(key, dest, zip_dir, keep):
    """Return (path_to_verified_zip, downloaded_by_us)."""
    ds = DATASETS[key]
    path = None
    if zip_dir is not None:
        for cand in (zip_dir / ds["zip_name"], zip_dir / ds["zip_folder"] / ds["zip_name"]):
            if cand.exists():
                path = cand
                break
        if path is None:
            raise Fail("%s not found in %s" % (ds["zip_name"], zip_dir))
        downloaded = False
    else:
        dl = dest / "_downloads"
        dl.mkdir(parents=True, exist_ok=True)
        path = dl / ds["zip_name"]
        if not (path.exists() and path.stat().st_size == ds["bytes"]):
            part = dl / (ds["zip_name"] + ".part")
            say("Downloading %s (%s) ..." % (ds["label"], human(ds["bytes"])))
            download(ds["url"], part, ds["bytes"], ds["zip_name"])
            part.replace(path)
        downloaded = True
    if path.stat().st_size != ds["bytes"]:
        raise Fail("%s is %d bytes, expected %d" % (path, path.stat().st_size, ds["bytes"]))
    say("Checking %s (sha256) ..." % path.name)
    got = sha256_file(path)
    if got != ds["sha256"]:
        if downloaded:
            path.unlink()
        raise Fail("sha256 mismatch for %s: got %s, expected %s%s" % (
            path.name, got, ds["sha256"], " (file deleted, run again)" if downloaded else ""))
    say("  size and sha256 match.")
    return path, downloaded


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def extract_from(zf, dest_root, names, prefix, label):
    index = {i.filename: i for i in zf.infolist()}
    missing = [n for n in names if prefix + n not in index]
    if missing:
        raise Fail("%d images named in the splits are not in the %s zip (first: %s)" % (len(missing), label, missing[0]))
    n_new = n_skip = 0
    for k, name in enumerate(names, 1):
        info = index[prefix + name]
        target = safe_target(dest_root, name)
        if target.exists() and target.stat().st_size == info.file_size:
            n_skip += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".part")
        with zf.open(info) as src, open(tmp, "wb") as out:
            shutil.copyfileobj(src, out, CHUNK)
        tmp.replace(target)
        n_new += 1
        if k % 2000 == 0:
            say("  %s: %d of %d" % (label, k, len(names)))
    say("  %s: %d extracted, %d already there." % (label, n_new, n_skip))


def extract_dataset(key, dest, zip_path):
    ds = DATASETS[key]
    names = names_for(dest, key)
    root = dest / ds["image_root"]
    root.mkdir(parents=True, exist_ok=True)
    say("Unpacking %d %s images ..." % (len(names), key))
    with zipfile.ZipFile(zip_path) as outer:
        if "inner_zip" not in ds:
            extract_from(outer, root, names, ds["member_prefix"], key)
            return
        info = outer.getinfo(ds["inner_zip"])
        if info.compress_type == zipfile.ZIP_STORED:
            with outer.open(info) as f:                  # seekable, read in place
                with zipfile.ZipFile(f) as inner:
                    extract_from(inner, root, names, ds["member_prefix"], key)
        else:                                            # unusual: unpack the nested zip first
            tmp = dest / "_downloads" / "inner.zip.tmp"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            with outer.open(info) as src, open(tmp, "wb") as out:
                shutil.copyfileobj(src, out, CHUNK)
            try:
                with zipfile.ZipFile(tmp) as inner:
                    extract_from(inner, root, names, ds["member_prefix"], key)
            finally:
                tmp.unlink()


# --------------------------------------------------------------------------
# Final check
# --------------------------------------------------------------------------
def check(dest, keys):
    problems = []
    grand = 0
    say("")
    say("Check of %s" % dest)
    for key in keys:
        ds = DATASETS[key]
        root = dest / ds["image_root"]
        for s, expect in ds["splits"].items():
            p = dest / "splits" / ("%s_%s.json" % (key, s))
            if not p.exists():
                problems.append("missing split file %s" % p)
                continue
            d = load_split_file(p)
            imgs = d["images"]
            absent = 0
            empty = 0
            for im in imgs:
                try:
                    t = safe_target(root, im["file_name"])
                except Fail as e:
                    problems.append(str(e))
                    continue
                if not t.is_file():
                    absent += 1
                elif t.stat().st_size == 0:
                    empty += 1
            ok = len(imgs) - absent - empty
            grand += ok
            flag = "ok" if (absent == 0 and empty == 0 and len(imgs) == expect) else "PROBLEM"
            say("  %-6s %-5s images in split %5d, found %5d, boxes %6d  [%s]" % (
                key, s, len(imgs), ok, len(d["annotations"]), flag))
            if len(imgs) != expect:
                problems.append("%s_%s has %d images, expected %d" % (key, s, len(imgs), expect))
            if absent:
                problems.append("%s_%s: %d images missing from %s" % (key, s, absent, root))
            if empty:
                problems.append("%s_%s: %d empty (0-byte) image files" % (key, s, empty))
    say("  Total images present: %d" % grand)
    if problems:
        raise Fail("check failed:\n  - " + "\n  - ".join(problems[:20]))
    say("All images named in the splits are present.")


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Download and unpack the ClipSift training images.")
    ap.add_argument("--dest", type=Path, default=default_dest(),
                    help='where to put the data (default: a "Footage Sources" folder beside the repo)')
    ap.add_argument("--only", choices=("puget", "tweed", "all"), default="all", help="which dataset (default: all)")
    ap.add_argument("--zip-dir", type=Path, default=None, help="folder that already holds the zip file(s); skips the download")
    ap.add_argument("--keep-zips", action="store_true", help="keep downloaded zips after unpacking")
    ap.add_argument("--check", action="store_true", help="only check that every split image exists; change nothing")
    a = ap.parse_args(argv)
    keys = ["puget", "tweed"] if a.only == "all" else [a.only]
    dest = a.dest.expanduser().resolve()
    try:
        if sys.version_info < (3, 9):
            raise Fail("Python 3.9 or newer is needed (you have %s)" % sys.version.split()[0])
        if a.check:
            check(dest, keys)
            return 0
        say("Destination: %s" % dest)
        dest.mkdir(parents=True, exist_ok=True)
        write_splits(dest)
        if a.zip_dir is None:
            running = peak = 0.0
            for k in keys:                      # datasets are handled one after the other
                zgb = DATASETS[k]["bytes"] / 1e9
                peak = max(peak, running + zgb + DATASETS[k]["img_gb"])
                running += DATASETS[k]["img_gb"] + (zgb if a.keep_zips else 0)
            need = int(peak + 1)
            free = shutil.disk_usage(dest).free / 1e9
            if free < need:
                raise Fail("not enough disk space: about %d GB needed, %.0f GB free at %s" % (need, free, dest))
        for key in keys:
            zpath, downloaded = get_zip(key, dest, a.zip_dir.expanduser().resolve() if a.zip_dir else None, a.keep_zips)
            extract_dataset(key, dest, zpath)
            if downloaded and not a.keep_zips:
                zpath.unlink()
        dl = dest / "_downloads"
        if dl.is_dir() and not any(dl.iterdir()):
            dl.rmdir()
        check(dest, keys)
        return 0
    except Fail as e:
        say("")
        say("ERROR: %s" % e)
        return 1
    except zipfile.BadZipFile as e:
        say("")
        say("ERROR: a zip file is damaged (%s). Delete it and run again." % e)
        return 1
    except KeyboardInterrupt:
        say("\nStopped. Run the same command again to carry on where it left off.")
        return 130
    except OSError as e:
        say("")
        say("ERROR: file problem: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
