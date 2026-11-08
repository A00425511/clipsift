"""Build a species bank for a run from V6 output.

    python tools/build_species_bank.py <subsamples_v6.json> --run runs/<run_id> [--video <original video>]

Writes <run>/species_bank/bank.json and images. Existing decisions are kept. The original video is
needed so that images are clean, and it defaults to the path stored in the V6 file.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clipsift.species_bank import build_bank  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("v6_json", type=Path)
    p.add_argument("--run", type=Path, required=True, help="run folder, for example runs/coastal_t1_stat2")
    p.add_argument("--video", type=Path)
    a = p.parse_args()
    if not a.run.is_dir():
        p.error(f"run folder not found: {a.run}")
    bank = build_bank(a.v6_json, a.run / "species_bank", a.video)
    c = bank["counts"]
    print(f"{c['tracks']} tracks merged into {c['candidates']} candidates: "
          f"{c['to_review']} to review, {c['fixed_objects']} likely fixed objects")
    print(f"Wrote {a.run / 'species_bank' / 'bank.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
