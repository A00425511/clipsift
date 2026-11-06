"""Build the static team demo into deploy/public/.

    python tools/build_demo.py                        # default allow-list: _fixture synthetic_demo
    python tools/build_demo.py _fixture synthetic_demo --out deploy/public

Copies app/static plus ONLY the run ids named on the command line (an allow-list), and species_list.json.
Real footage never goes in by accident: any run id containing "river" is refused, and only these files
are copied from a run: results.json (source paths trimmed to file names), stills, difference images,
clips. Review files (*.jsonl) are never copied.

Limits checked (Cloudflare Workers static assets): under 20,000 files (free plan) and every file under
25 MiB. The platform handles HTTP Range requests for video.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,127}$")  # same rule as app/server.py
DEFAULT_RUNS = ["coastal_school", "coastal_seabed", "_fixture"]
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_FILES = 20000
FORBIDDEN_WORD = "river"
RUN_FILES = {"segments": ("still.jpg", "diff.jpg", "loop.mp4"), "subsamples": ("still.jpg", "diff.jpg", "context.mp4")}
CONFIG_JS = ('// Written by tools/build_demo.py. Turns on demo mode: static reads, writes stay in this browser.\n'
             'window.CLIPSIFT_DEMO = {"base": "/", "manifest": "manifest.json", "species": "species_list.json"};\n')


class BuildError(Exception):
    pass


def check_run_ids(run_ids):
    """Refuse anything that could pull in real footage or leave the runs folder."""
    if not run_ids:
        raise BuildError("Give at least one run id.")
    seen = []
    for rid in run_ids:
        if FORBIDDEN_WORD in rid.lower():
            raise BuildError(f"Refusing run id '{rid}': ids containing '{FORBIDDEN_WORD}' are real footage and never go in the demo.")
        if not NAME_RE.match(rid):
            raise BuildError(f"Run id '{rid}' is not a plain folder name.")
        if rid not in seen:
            seen.append(rid)
    return seen


def prepare_out(out: Path, force: bool):
    if out.exists() and any(out.iterdir()):
        if not (force or (out.name == "public" and (out.parent / "wrangler.jsonc").is_file())):
            raise BuildError(f"{out} is not empty and does not look like deploy/public. Use --force to replace it.")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)


def copy_static(static: Path, out: Path):
    dest = out / "static"
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(static.iterdir()):
        if f.is_file() and not f.name.startswith(".") and f.suffix in {".js", ".css", ".html", ".svg", ".png", ".ico"} and f.name != "index.html":
            shutil.copy2(f, dest / f.name)
    html = (static / "index.html").read_text(encoding="utf-8")
    marker = '<script src="/static/app.js"></script>'
    if marker not in html:
        raise BuildError("app/static/index.html no longer has the app.js script tag; update tools/build_demo.py.")
    (dest / "demo-config.js").write_text(CONFIG_JS, encoding="utf-8")
    (out / "index.html").write_text(html.replace(marker, '<script src="/static/demo-config.js"></script>\n' + marker), encoding="utf-8")


def copy_run(runs_root: Path, rid: str, out: Path) -> dict:
    src = (runs_root / rid).resolve()
    if src.parent != runs_root.resolve() or not (src / "results.json").is_file():
        raise BuildError(f"Run '{rid}' not found in {runs_root} (no results.json).")
    data = json.loads((src / "results.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        raise BuildError(f"Run '{rid}' has an unreadable results.json.")
    rec = data.get("recording")
    if isinstance(rec, dict) and isinstance(rec.get("source_files"), list):  # no local paths on the public site
        rec["source_files"] = [Path(str(p).replace("\\", "/")).name for p in rec["source_files"]]
    dest = out / "runs" / rid
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "results.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    for folder, names in RUN_FILES.items():
        base = src / folder
        if not base.is_dir():
            continue
        for unit in sorted(base.iterdir()):
            if not unit.is_dir() or not NAME_RE.match(unit.name):
                continue
            for name in names:
                f = unit / name
                if f.is_file() and not f.is_symlink():
                    (dest / folder / unit.name).mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest / folder / unit.name / name)
    return {"run_id": rid, "fixture": (src / "FIXTURE.txt").is_file() or bool(data.get("fixture")),
            "n_segments": len(data["segments"]), "created_at": (data.get("run") or {}).get("created_at"), "error": None}


def check_limits(out: Path):
    files = [f for f in out.rglob("*") if f.is_file()]
    if len(files) >= MAX_FILES:
        raise BuildError(f"{len(files)} files is over the Cloudflare limit ({MAX_FILES} on the free plan).")
    for f in files:
        if f.stat().st_size >= MAX_FILE_BYTES:
            raise BuildError(f"{f.relative_to(out)} is {f.stat().st_size / 2**20:.1f} MiB; Cloudflare allows under 25 MiB per file.")
    return len(files), sum(f.stat().st_size for f in files)


def build(run_ids, runs_root, out, species, force=False):
    run_ids = check_run_ids(run_ids)
    out = Path(out).resolve()
    prepare_out(out, force)
    copy_static(ROOT / "app" / "static", out)
    manifest = [copy_run(Path(runs_root), rid, out) for rid in run_ids]
    (out / "manifest.json").write_text(json.dumps({"built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "runs": manifest}, indent=1), encoding="utf-8")
    sp = Path(species)
    if sp.is_file():
        shutil.copy2(sp, out / "species_list.json")
    else:
        (out / "species_list.json").write_text("[]", encoding="utf-8")
    n, total = check_limits(out)
    return manifest, n, total


def main(argv=None):
    p = argparse.ArgumentParser(description="Build the ClipSift static demo (allow-listed runs only)")
    p.add_argument("runs", nargs="*", default=DEFAULT_RUNS, help="run ids to include (default: %s)" % " ".join(DEFAULT_RUNS))
    p.add_argument("--runs-dir", default=str(ROOT / "runs"))
    p.add_argument("--out", default=str(ROOT / "deploy" / "public"))
    p.add_argument("--species", default=str(ROOT / "species" / "species_list.json"))
    p.add_argument("--force", action="store_true", help="replace --out even if it is not deploy/public")
    a = p.parse_args(argv)
    try:
        manifest, n, total = build(a.runs, a.runs_dir, a.out, a.species, a.force)
    except BuildError as e:
        print("build_demo: " + str(e), file=sys.stderr)
        return 2
    worker = ROOT / "deploy" / "src" / "worker.js"
    if worker.is_file():  # Cloudflare Pages runs this for every request, which is what applies the team-code gate
        shutil.copy2(worker, Path(a.out) / "_worker.js")
    print("Included runs: " + ", ".join(m["run_id"] for m in manifest))
    print(f"Wrote {a.out}: {n} files, {total / 2**20:.2f} MiB total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
