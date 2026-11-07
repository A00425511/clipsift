"""ClipSift review app: a small local Flask server.

Run from the project root:  python -m app.server --runs runs --port 8765

Reads the run folder contract in docs/SPEC.md directly (no pipeline import).
All writes are append-only JSON lines. Original footage is never touched.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import hashlib
import re
import shutil
import subprocess
import sys
import uuid
import threading
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory

from clipsift import protocol as proto
from clipsift import qc as qcm
from clipsift.cli import VIDEO_EXT, _expand
from clipsift.qc import percent_difference

from .jobs import JobQueue, safe_run_name

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
DEFAULT_SPECIES = PROJECT_ROOT / "species" / "species_list.json"
DEFAULT_ALIASES = APP_DIR / "local_aliases.jsonl"
DEFAULT_LABEL_SETS = PROJECT_ROOT / "label_sets"
DEFAULT_LABELS = APP_DIR / "local_labels.jsonl"

NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,127}$")  # run and segment ids
SEGMENT_FILES = {"still": "still.jpg", "diff": "diff.jpg", "loop": "loop.mp4"}
MIME = {"still": "image/jpeg", "diff": "image/jpeg", "loop": "video/mp4"}
DECISIONS = {"confirm", "reject", "unknown", "needs_second_look"}
SLIDERS = ("brightness", "contrast", "saturation")
ENHANCE_PRESETS = ("off", "light", "strong", "silhouette")   # keep in step with app/static/display.js
PREVIEW_MINUTES = (1, 2, 3, 4, 5)   # the protocol's window start: 1 minute, up to 4 more
LONG_VIDEO_MINUTES = ((25 * 60, (7.5, 10)), (30 * 60, (12.5, 15)))   # comments in the draft allow more on long videos
SUB_FILES = {"still": "still.jpg", "diff": "diff.jpg", "context": "context.mp4"}
SUB_MIME = {"still": "image/jpeg", "diff": "image/jpeg", "context": "video/mp4"}
PASSES = {"primary", "qc_blind", "recount"}
VISIBILITY_DIRECTIONS = ("increasing", "decreasing")
CHARACTERISTICS = ("shape", "anatomical_features", "colouration_or_flashes", "swimming_behaviour")
VISIBILITY = ("<0.5 m", "0.5-1.0 m", "1.0-1.5 m", ">1.5 m")
# Defaults only. The run's own results.json "protocol" block wins. Draft protocol, so all configurable.
QC_DEFAULTS = {"qc_max_percent_diff": 6, "qc_agreement": 95, "qc_small_gap": 1, "qc_share": 0.10, "qc_min": 6, "qc_max": 12, "qc_seed": 4321}
# Blind label mode. Same rules as deploy/src/worker.js: keep the two in step.
LABEL_SET_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]{0,39}$")
LABEL_FRAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,79}$")
LABEL_MAX_POINTS = 2000
LABEL_MAX_BODY = 400000
LABEL_NAME_MAX = 40
LABEL_MAX_SECONDS = 86400
LABEL_KINDS = ("fish", "invertebrate", "unsure", "not_fish")   # unsure: might be an animal, never counted; no species or category
LABEL_NOT_FISH_CATEGORIES = ("algae", "debris", "equipment", "seabed", "bubbles", "other")   # keep in step with worker.js and label.js
LABEL_VIEWS = ("frame", "movement", "clip")   # views used on a frame, kept for later analysis
LABEL_SPECIES_MAX = 80
LABEL_PRESET_NAMES = ("Jacob", "Ali", "Gina", "Wang", "Adrien")
BANK_OUTCOMES = ("species", "not_animal", "cant_tell", "needs_expert")
REVIEW_OUTCOMES = ("fish", "invertebrate", "equipment", "background", "cant_tell", "needs_expert")
BANK_NAMED = ("species", "fish", "invertebrate")   # outcomes that can carry a species name
BANK_SETS = {"species_bank": "species_bank", "review": "review_set"}
TRAINING_LABEL = {"species": "fish_or_invertebrate", "fish": "fish", "invertebrate": "invertebrate",
                  "equipment": "not_animal", "background": "not_animal", "not_animal": "not_animal"}
PROFILE_NAME_MAX = 60
REVIEW_SET_SIZES = (30, 36, 40)
BANK_LIFE_STAGES = ("adult", "juvenile", "unknown")
BANK_FILE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,80}\.(jpg|mp4)$")
FEEDBACK_AREAS = ("Counting", "Video", "Timeline", "Help", "Layout", "Other")
FEEDBACK_TYPES = ("Bug", "Confusing", "Idea", "Like")


def active_point_labels(rows):
    """Resolve the append-only point_labels.jsonl: adds minus later removes (undo)."""
    live, order = {}, []
    for r in rows:
        lid = r.get("label_id")
        if r.get("op") == "remove":
            live.pop(lid, None)
        elif isinstance(lid, str):
            live[lid] = r
            order.append(lid)
    return [live[i] for i in order if i in live]


CSV_COLUMNS = [
    ("recording_id", "Recording folder name."),
    ("segment_id", "Segment id from results.json."),
    ("start_s", "Segment start, seconds from the start of the recording."),
    ("end_s", "Segment end, seconds."),
    ("kind", "active, or set_aside (no activity found, time is kept)."),
    ("audit_sample", "true if this set-aside segment was picked at random as a check."),
    ("status", "Model status: known, fish_unknown, unclear, movement_unidentified, none."),
    ("motion_score", "Motion score from the pipeline. Blank means not computed."),
    ("visibility_score", "Visibility score from the pipeline. Blank means not computed."),
    ("flag_shake", "true if camera shake was flagged."),
    ("flag_low_visibility", "true if low visibility was flagged."),
    ("review_priority", "Higher means it was shown earlier in the queue."),
    ("model_maxn", "Model MaxN: the most fish seen in one frame. A relative index, not abundance. Blank means not computed."),
    ("model_mean_count", "Model mean fish per sampled frame. A relative index, not abundance. Blank means not computed."),
    ("model_unique_tracks", "Number of separate fish tracks. A relative index, not abundance. Blank means not computed."),
    ("decision", "Reviewer decision: confirm, reject, unknown, needs_second_look."),
    ("species", "Species the reviewer entered. Blank if none."),
    ("species_free_text", "true if the species was typed and is not in the species list. Check these."),
    ("count", "Fish count the reviewer entered. A relative index, not abundance."),
    ("note", "Reviewer note."),
    ("reviewer", "Reviewer name as typed."),
    ("reviewed_at", "When the latest decision was saved (UTC)."),
    ("n_decisions", "How many decisions were saved for this segment. Only the latest is shown here."),
    ("n_grid_tags", "How many grid cell tags were saved for this segment."),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BadInput(ValueError):
    pass


def clean_str(value, field, max_len, allow_empty=True):
    if value is None:
        if allow_empty:
            return None
        raise BadInput(f"{field} is required")
    if not isinstance(value, str):
        raise BadInput(f"{field} must be text")
    value = value.strip()
    if not value and not allow_empty:
        raise BadInput(f"{field} is required")
    if len(value) > max_len:
        raise BadInput(f"{field} is too long (max {max_len})")
    return value or None


def clean_int(value, field, lo, hi, allow_none=True):
    if value is None:
        if allow_none:
            return None
        raise BadInput(f"{field} is required")
    if isinstance(value, bool) or not isinstance(value, int):
        raise BadInput(f"{field} must be a whole number")
    if not lo <= value <= hi:
        raise BadInput(f"{field} must be between {lo} and {hi}")
    return value


def clean_pair(value, field, lo, hi):
    if not isinstance(value, list) or len(value) != 2:
        raise BadInput(f"{field} must be two numbers")
    return [clean_int(v, field, lo, hi, allow_none=False) for v in value]


def create_app(runs_dir="runs", species_path=None, aliases_path=None, label_sets_dir=None, labels_path=None, videos_dir=None) -> Flask:
    app = Flask(__name__, static_folder=str(APP_DIR / "static"), static_url_path="/static")
    runs_root = Path(runs_dir).resolve()
    species_file = Path(species_path) if species_path else DEFAULT_SPECIES
    aliases_file = Path(aliases_path) if aliases_path else DEFAULT_ALIASES
    label_sets_root = Path(label_sets_dir).resolve() if label_sets_dir else DEFAULT_LABEL_SETS.resolve()
    labels_file = Path(labels_path) if labels_path else DEFAULT_LABELS
    videos_root = Path(videos_dir).resolve() if videos_dir else (PROJECT_ROOT / "videos")
    jobs = JobQueue(runs_root, PROJECT_ROOT)
    write_lock = threading.Lock()
    app.config.update(RUNS_ROOT=runs_root, SPECIES_FILE=species_file, ALIASES_FILE=aliases_file, LABEL_SETS_ROOT=label_sets_root, LABELS_FILE=labels_file)

    # ---- helpers -----------------------------------------------------------
    def run_dir_for(run_id: str) -> Path:
        if not NAME_RE.match(run_id):
            abort(400, "Bad run name")
        path = (runs_root / run_id).resolve()
        if path.parent != runs_root or not path.is_dir():
            abort(404, "Run not found")
        return path

    def load_results(run_dir: Path) -> dict:
        path = run_dir / "results.json"
        if not path.is_file():
            abort(404, "This run has no results.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            abort(422, "results.json could not be read")
        if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
            abort(422, "results.json is missing its segments list")
        return data

    def read_jsonl(path: Path) -> list:
        rows = []
        if not path.is_file():
            return rows
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue  # skip a half-written line instead of failing
                if isinstance(obj, dict):
                    rows.append(obj)
        return rows

    def append_jsonl(path: Path, obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        with write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)

    def json_body() -> dict:
        if not request.is_json:
            raise BadInput("Send JSON (Content-Type: application/json)")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadInput("Body must be a JSON object")
        return data

    def known_segment(results: dict, segment_id) -> dict:
        if not isinstance(segment_id, str) or not NAME_RE.match(segment_id):
            raise BadInput("segment_id is missing or invalid")
        for seg in results["segments"]:
            if isinstance(seg, dict) and seg.get("segment_id") == segment_id:
                return seg
        raise BadInput("segment_id is not in this run")

    def clean_settings_from(settings):
        settings = settings or {}
        if not isinstance(settings, dict):
            raise BadInput("contrast_settings must be an object")
        out = {}
        for key in SLIDERS:
            if key in settings:
                v = settings[key]
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 300:
                    raise BadInput(f"{key} must be a number from 0 to 300")
                out[key] = v
        if "enhance" in settings:
            if settings["enhance"] not in ENHANCE_PRESETS:
                raise BadInput("enhance is not a known preset")
            out["enhance"] = settings["enhance"]
        return out

    def known_subsample(results, subsample_id):
        if not isinstance(subsample_id, str) or not NAME_RE.match(subsample_id):
            raise BadInput("subsample_id is missing or invalid")
        for ss in results.get("subsamples") or []:
            if isinstance(ss, dict) and ss.get("subsample_id") == subsample_id:
                return ss
        raise BadInput("subsample_id is not in this run")

    @app.errorhandler(BadInput)
    def on_bad_input(err):
        return jsonify(error=str(err)), 400

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(422)
    def on_http_error(err):
        return jsonify(error=getattr(err, "description", "Error")), err.code

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; media-src 'self'; "
            "style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---- pages -------------------------------------------------------------
    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html", max_age=0)

    @app.get("/label.html")
    def label_page():
        return send_from_directory(app.static_folder, "label.html", max_age=0)

    @app.get("/species_bank.html")
    def species_bank_page():
        return send_from_directory(app.static_folder, "species_bank.html", max_age=0)

    # ---- runs --------------------------------------------------------------
    @app.get("/api/runs")
    def list_runs():
        out = []
        if runs_root.is_dir():
            for d in sorted(runs_root.iterdir(), key=lambda p: p.name):
                if not d.is_dir() or not NAME_RE.match(d.name) or not (d / "results.json").is_file():
                    continue
                info = {"run_id": d.name, "fixture": (d / "FIXTURE.txt").is_file(),
                        "n_segments": None, "created_at": None, "error": None}
                try:
                    data = json.loads((d / "results.json").read_text(encoding="utf-8"))
                    info["n_segments"] = len(data.get("segments") or [])
                    info["created_at"] = (data.get("run") or {}).get("created_at")
                    info["fixture"] = info["fixture"] or bool(data.get("fixture"))
                except (OSError, ValueError, AttributeError, TypeError):
                    info["error"] = "results.json could not be read"
                out.append(info)
        return jsonify(runs=out)

    @app.get("/api/runs/<run_id>/results")
    def get_results(run_id):
        return jsonify(load_results(run_dir_for(run_id)))

    def serve_unit(run_id, folder, unit_id, kind, files, mimes):
        run_dir = run_dir_for(run_id)
        if not NAME_RE.match(unit_id) or kind not in files:
            abort(404, "No such file")
        path = (run_dir / folder / unit_id / files[kind]).resolve()
        if run_dir not in path.parents or not path.is_file():  # also blocks symlinks out of the run
            abort(404, "File not found")
        # conditional=True gives HTTP Range (206) so video seeking works.
        resp = send_file(path, mimetype=mimes[kind], conditional=True, max_age=0)
        resp.headers["Accept-Ranges"] = "bytes"
        return resp

    @app.get("/api/runs/<run_id>/segments/<segment_id>/<kind>")
    def segment_file(run_id, segment_id, kind):
        return serve_unit(run_id, "segments", segment_id, kind, SEGMENT_FILES, MIME)

    @app.get("/api/runs/<run_id>/subsamples/<subsample_id>/<kind>")
    def subsample_file(run_id, subsample_id, kind):
        return serve_unit(run_id, "subsamples", subsample_id, kind, SUB_FILES, SUB_MIME)

    # ---- reviews and tags --------------------------------------------------
    @app.post("/api/runs/<run_id>/reviews")
    def post_review(run_id):
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        data = json_body()
        known_segment(results, data.get("segment_id"))
        decision = data.get("decision")
        if decision not in DECISIONS:
            raise BadInput("decision must be one of: " + ", ".join(sorted(DECISIONS)))
        clean_settings = clean_settings_from(data.get("contrast_settings"))
        free_text = data.get("species_free_text", False)
        if not isinstance(free_text, bool):
            raise BadInput("species_free_text must be true or false")
        species = clean_str(data.get("species"), "species", 200)
        record = {
            "segment_id": data["segment_id"],
            "decision": decision,
            "species": species,
            "species_free_text": bool(free_text and species),
            "count": clean_int(data.get("count"), "count", 0, 100000),
            "note": clean_str(data.get("note"), "note", 2000) or "",
            "reviewer": clean_str(data.get("reviewer"), "reviewer", 100) or "",
            "at": now_iso(),
            "model_version": (results.get("run") or {}).get("model_version"),
            "contrast_settings": clean_settings,
        }
        append_jsonl(run_dir / "reviews.jsonl", record)
        return jsonify(record), 201

    @app.post("/api/runs/<run_id>/grid_tags")
    def post_grid_tag(run_id):
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        data = json_body()
        if data.get("subsample_id") is not None:
            sub = known_subsample(results, data.get("subsample_id"))
            seg = {"still_time_s": sub.get("t_s")}
            unit = {"subsample_id": data["subsample_id"]}
        else:
            seg = known_segment(results, data.get("segment_id"))
            unit = {"segment_id": data["segment_id"]}
        grid = clean_pair(data.get("grid"), "grid", 1, 50)
        cell = clean_pair(data.get("cell"), "cell", 0, 49)
        if cell[0] >= grid[0] or cell[1] >= grid[1]:
            raise BadInput("cell is outside the grid")
        t = data.get("time_s", seg.get("still_time_s"))
        if t is not None and (isinstance(t, bool) or not isinstance(t, (int, float)) or t < 0):
            raise BadInput("time_s must be a number of seconds, 0 or more")
        record = {
            **unit,
            "time_s": t,
            "grid": grid,
            "cell": cell,
            "species": clean_str(data.get("species"), "species", 200),
            "count": clean_int(data.get("count", 1), "count", 1, 10000, allow_none=False),
            "reviewer": clean_str(data.get("reviewer"), "reviewer", 100) or "",
            "at": now_iso(),
        }
        append_jsonl(run_dir / "grid_tags.jsonl", record)
        return jsonify(record), 201

    @app.post("/api/runs/<run_id>/subsample_reviews")
    def post_subsample_review(run_id):
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        data = json_body()
        known_subsample(results, data.get("subsample_id"))
        counter = clean_str(data.get("counter"), "counter", 100, allow_empty=False)
        pass_ = data.get("pass", "primary")
        if pass_ not in PASSES:
            raise BadInput("pass must be one of: " + ", ".join(sorted(PASSES)))
        if pass_ == "qc_blind":
            earlier = {(r.get("counter") or "").lower() for r in read_jsonl(run_dir / "subsample_reviews.jsonl")
                       if r.get("subsample_id") == data["subsample_id"] and r.get("pass") == "primary"}
            if counter.lower() in earlier:
                raise BadInput("A blind second count has to come from a different person.")
        species_counts = data.get("species_counts") or {}
        if not isinstance(species_counts, dict) or len(species_counts) > 200:
            raise BadInput("species_counts must be an object of name: count")
        clean_species = {}
        for name, n in species_counts.items():
            key = clean_str(name, "species name", 200, allow_empty=False)
            clean_species[key] = clean_int(n, "species count", 0, 100000, allow_none=False)
        vis = data.get("visibility_category")
        if vis is not None and vis not in VISIBILITY:
            raise BadInput("visibility_category must be one of: " + ", ".join(VISIBILITY))
        vchange = data.get("visibility_change")
        if vchange is not None and not isinstance(vchange, bool):
            raise BadInput("visibility_change must be true, false or empty")
        direction = data.get("visibility_direction")
        if direction is not None and direction not in VISIBILITY_DIRECTIONS:
            raise BadInput("visibility_direction must be increasing, decreasing or empty")
        chars = data.get("characteristics") or []
        if not isinstance(chars, list) or any(c not in CHARACTERISTICS for c in chars):
            raise BadInput("characteristics must be from: " + ", ".join(CHARACTERISTICS))
        free = data.get("free_text_species") or []
        if not isinstance(free, list) or len(free) > 200:
            raise BadInput("free_text_species must be a list")
        free = [clean_str(f, "free_text_species", 200, allow_empty=False) for f in free]
        record = {
            "subsample_id": data["subsample_id"],
            "counter": counter,
            "pass": pass_,
            "total_fish_count": clean_int(data.get("total_fish_count"), "total_fish_count", 0, 100000, False),
            "invertebrate_count": clean_int(data.get("invertebrate_count"), "invertebrate_count", 0, 100000, False),
            "species_counts": clean_species,
            "unknown_count": clean_int(data.get("unknown_count", 0), "unknown_count", 0, 100000, False),
            "total_species": clean_int(data.get("total_species", len(clean_species)), "total_species", 0, 1000),
            "visibility_category": vis,
            "visibility_change": vchange,
            "visibility_direction": direction,
            "characteristics": sorted(set(chars)),
            "free_text_species": free,
            "notes": clean_str(data.get("notes"), "notes", 2000) or "",
            "at": now_iso(),
            "model_version": (results.get("run") or {}).get("model_version"),
            "contrast_settings": clean_settings_from(data.get("contrast_settings")),
        }
        append_jsonl(run_dir / "subsample_reviews.jsonl", record)
        return jsonify(record), 201

    @app.post("/api/runs/<run_id>/recording_notes")
    def post_recording_notes(run_id):
        run_dir = run_dir_for(run_id)
        load_results(run_dir)
        data = json_body()

        def secs(field):
            v = data.get(field)
            if v is None:
                return None
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or v > 86400:
                raise BadInput(f"{field} must be seconds, 0 or more")
            return v

        species = data.get("species_observed") or []
        if not isinstance(species, list) or len(species) > 300:
            raise BadInput("species_observed must be a list")
        juv = data.get("juveniles")
        if juv not in (None, 0, 1) or isinstance(juv, bool):
            raise BadInput("juveniles must be 0, 1 or empty")
        vis_rows = []
        for row in data.get("visibility_by_observer") or []:
            if not isinstance(row, dict) or row.get("category") not in VISIBILITY:
                raise BadInput("each visibility entry needs an observer and a valid category")
            vis_rows.append({"observer": clean_str(row.get("observer"), "observer", 100, allow_empty=False),
                             "category": row["category"]})
        record = {
            "window_start_s": secs("window_start_s"),
            "window_end_s": secs("window_end_s"),
            "species_observed": [clean_str(x, "species", 200, allow_empty=False) for x in species],
            "juveniles": juv,
            "none_seen": data.get("none_seen") is True,
            "visibility_by_observer": vis_rows,
            "notes": clean_str(data.get("notes"), "notes", 2000) or "",
            "reviewer": clean_str(data.get("reviewer"), "reviewer", 100) or "",
            "at": now_iso(),
        }
        if (record["window_start_s"] is not None and record["window_end_s"] is not None
                and record["window_end_s"] <= record["window_start_s"]):
            raise BadInput("window end must be after window start")
        append_jsonl(run_dir / "recording_notes.jsonl", record)
        return jsonify(record), 201

    @app.post("/api/runs/<run_id>/visibility")
    def post_visibility(run_id):
        """One observer's visibility category for the video. Each person rates on their own."""
        run_dir = run_dir_for(run_id)
        load_results(run_dir)
        data = json_body()
        if data.get("category") not in VISIBILITY:
            raise BadInput("category must be one of: " + ", ".join(VISIBILITY))
        record = {"observer": clean_str(data.get("observer"), "observer", 100, allow_empty=False), "category": data["category"],
                  "notes": clean_str(data.get("notes"), "notes", 500) or "", "at": now_iso()}
        append_jsonl(run_dir / "visibility.jsonl", record)
        return jsonify(record), 201

    def visibility_rows(run_dir, notes):
        """The latest rating per observer, including any typed in by older versions of the app."""
        latest = {}
        for row in (notes[-1].get("visibility_by_observer") or [] if notes else []):
            latest[row.get("observer")] = {"observer": row.get("observer"), "category": row.get("category")}
        for row in read_jsonl(run_dir / "visibility.jsonl"):
            latest[row.get("observer")] = row
        return list(latest.values())

    def finite(v, field, lo, hi):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise BadInput(f"{field} must be a number from {lo} to {hi}")
        return v

    @app.post("/api/runs/<run_id>/point_labels")
    def post_point_label(run_id):
        """Append one dot, ellipse or box (op add), or an undo (op remove). Coordinates in original pixels."""
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        data = json_body()
        ss = known_subsample(results, data.get("subsample_id"))
        counter = clean_str(data.get("counter"), "counter", 100, allow_empty=False)
        op = data.get("op", "add")
        path = run_dir / "point_labels.jsonl"
        if op == "remove":
            lid = data.get("label_id")
            mine = [r for r in active_point_labels(read_jsonl(path)) if r.get("subsample_id") == ss["subsample_id"]]
            if not any(r.get("label_id") == lid for r in mine):
                raise BadInput("label_id is not an active label for this point")
            record = {"op": "remove", "label_id": lid, "subsample_id": ss["subsample_id"], "counter": counter, "at": now_iso()}
        elif op == "add":
            kind = data.get("kind")
            if kind not in ("fish", "invertebrate", "unsure"):   # unsure: never counted, and carries no species
                raise BadInput("kind must be fish, invertebrate or unsure")
            shape = data.get("shape", "point")
            if shape not in ("point", "ellipse", "box"):
                raise BadInput("shape must be point, ellipse or box")
            record = {"op": "add", "label_id": "pl_" + uuid.uuid4().hex[:12], "subsample_id": ss["subsample_id"],
                      "time_s": data.get("time_s", ss.get("t_s")), "x": finite(data.get("x"), "x", 0, 100000),
                      "y": finite(data.get("y"), "y", 0, 100000), "shape": shape, "kind": kind,
                      "species": None if kind == "unsure" else clean_str(data.get("species"), "species", 200), "counter": counter, "at": now_iso()}
            if record["time_s"] is not None:
                finite(record["time_s"], "time_s", 0, 86400)
            if shape != "point":
                record["w"] = finite(data.get("w"), "w", 0.5, 100000)
                record["h"] = finite(data.get("h"), "h", 0.5, 100000)
        else:
            raise BadInput("op must be add or remove")
        append_jsonl(path, record)
        return jsonify(record), 201

    def qc_sample_ids(results):
        """The frames picked for the blind check. Runs made before the pick was recorded get one now."""
        subs = sorted([x for x in results.get("subsamples") or [] if isinstance(x, dict)], key=lambda x: x.get("t_s") or 0)
        marked = [x["subsample_id"] for x in subs if x.get("qc_sample")]
        if marked:
            return marked
        pc = {**QC_DEFAULTS, **(results.get("protocol") or {})}
        picks = proto.pick_qc(len(subs), pc, (results.get("recording") or {}).get("recording_id") or "")
        return [x["subsample_id"] for i, x in enumerate(subs) if i in picks]

    def qc_and_means(results, sub_reviews):
        """Latest first count per point, every blind comparison, the app's recommendation, and MeanCount."""
        pc = {**QC_DEFAULTS, **(results.get("protocol") or {})}
        limit, target = pc["qc_max_percent_diff"], pc["qc_agreement"]
        primary, seconds = {}, {}
        for r in sub_reviews:
            sid = r.get("subsample_id")
            if r.get("pass") == "primary":
                primary[sid] = r
            elif r.get("pass") in ("qc_blind", "recount"):
                seconds.setdefault(sid, {})[(r.get("counter") or "").lower()] = r   # the latest row per person
        qc = {sid: qcm.assess_point([primary[sid], *rows.values()], limit, pc["qc_small_gap"]) for sid, rows in seconds.items() if sid in primary}
        check = qcm.verdict(qc_sample_ids(results), set(primary), qc, limit, target)
        fish = [r.get("total_fish_count") for r in primary.values() if r.get("total_fish_count") is not None]
        final = {sid: (qc[sid]["average_fish"] if sid in qc else r.get("total_fish_count"))
                 for sid, r in primary.items()}   # the protocol averages the two blind counts of a checked frame
        final = {k: v for k, v in final.items() if v is not None}
        return {
            "latest_primary": primary,
            "qc": qc,
            "qc_check": check,
            "qc_agreement": check["agreement"],
            "qc_agreement_target": target,
            "n_counted": len(primary),
            "n_subsamples": len(results.get("subsamples") or []),
            "mean_count_reviewed": round(sum(fish) / len(fish), 3) if fish else None,
            "final_fish": final,
            "mean_count_final": round(sum(final.values()) / len(final), 3) if final else None,
        }

    @app.get("/api/runs/<run_id>/saved")
    def get_saved(run_id):
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        reviews = read_jsonl(run_dir / "reviews.jsonl")
        tags = read_jsonl(run_dir / "grid_tags.jsonl")
        sub_reviews = read_jsonl(run_dir / "subsample_reviews.jsonl")
        notes = read_jsonl(run_dir / "recording_notes.jsonl")
        latest = {}
        for r in reviews:  # file order is time order, so the last one wins
            if isinstance(r.get("segment_id"), str):
                latest[r["segment_id"]] = r
        return jsonify(reviews=reviews, latest_review=latest, grid_tags=tags,
                       subsample_reviews=sub_reviews,
                       point_labels=active_point_labels(read_jsonl(run_dir / "point_labels.jsonl")), recording_notes=notes,
                       latest_recording_notes=notes[-1] if notes else None,
                       visibility=visibility_rows(run_dir, notes), review_set=review_set_state(run_dir),
                       **qc_and_means(results, sub_reviews))

    def review_set_state(run_dir):
        """How far the end-of-run review has got. Sources stay out of this until a person has decided."""
        bank = load_bank(run_dir, "review_set")
        if bank is None:
            return None
        decided = bank_decisions(run_dir, "review_set")
        done = {i: d for i, d in decided.items() if any(x.get("id") == i for x in bank["items"])}
        by_source = {}
        for item in bank["items"]:
            d = done.get(item.get("id"))
            if d:
                row = by_source.setdefault(item.get("source"), {"animal": 0, "not_animal": 0, "unclear": 0})
                label = TRAINING_LABEL.get(d.get("outcome"))
                row["not_animal" if label == "not_animal" else "animal" if label else "unclear"] += 1
        return {"total": len(bank["items"]), "done": len(done), "by_source": by_source, "created_at": bank.get("created_at"),
                "model": (bank.get("source") or {}).get("model")}

    # ---- people: profiles, and how closely they agree across videos ----------
    profiles_file = runs_root / "profiles.jsonl"

    @app.get("/api/profiles")
    def get_profiles():
        names = {}
        for row in read_jsonl(profiles_file):
            names[str(row.get("name")).lower()] = row.get("name")
        return jsonify(profiles=sorted(names.values(), key=str.lower))

    @app.post("/api/profiles")
    def add_profile():
        name = clean_str(json_body().get("name"), "name", PROFILE_NAME_MAX, allow_empty=False)
        name = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", name)).strip()
        if not any(str(r.get("name")).lower() == name.lower() for r in read_jsonl(profiles_file)):
            append_jsonl(profiles_file, {"name": name, "at": now_iso()})
        return jsonify(name=name), 201

    def each_run():
        if runs_root.is_dir():
            for d in sorted(runs_root.iterdir(), key=lambda p: p.name):
                if d.is_dir() and NAME_RE.match(d.name) and (d / "results.json").is_file():
                    yield d

    @app.get("/api/interrater")
    def get_interrater():
        return jsonify(qcm.interrater([read_jsonl(d / "subsample_reviews.jsonl") for d in each_run()], QC_DEFAULTS["qc_max_percent_diff"]))

    @app.get("/api/progress")
    def get_progress():
        """A line per video for the home screen."""
        out = []
        for d in each_run():
            try:
                results = json.loads((d / "results.json").read_text(encoding="utf-8"))
                info = qc_and_means(results, read_jsonl(d / "subsample_reviews.jsonl"))
            except (OSError, ValueError, AttributeError, TypeError):
                continue
            rec = results.get("recording") or {}
            out.append({"run_id": d.name, "video_id": rec.get("video_id") or d.name, "fixture": bool(results.get("fixture")) or (d / "FIXTURE.txt").is_file(),
                        "created_at": (results.get("run") or {}).get("created_at"), "n_counted": info["n_counted"], "n_subsamples": info["n_subsamples"],
                        "qc_status": info["qc_check"]["status"], "mean_count": info["mean_count_final"]})
        return jsonify(videos=out)

    # ---- new videos: pick or add a video, then process it in the background ----
    def inbox_entries():
        """Videos in the videos folder. GoPro chapters of one video are one entry."""
        if not videos_root.is_dir():
            return []
        files = [f for f in _expand([videos_root]) if not f.name.endswith(".part")]
        groups = proto.group_chapters(files)
        entries = [paths for key, paths in groups.items() if key != "_other"]
        entries += [[p] for p in groups.get("_other", [])]
        return [{"id": paths[0].name, "files": [p.name for p in paths], "size": sum(p.stat().st_size for p in paths),
                 "suggested_name": safe_run_name(paths[0].stem), "paths": paths} for paths in entries]

    def paths_from(data):
        """The files for a job: an entry in the videos folder, or a typed path to a file or a folder of chapters."""
        chosen, typed = data.get("video"), data.get("path")
        if chosen:
            hit = next((e for e in inbox_entries() if e["id"] == chosen), None)
            if hit is None:
                raise BadInput("That video is no longer in the videos folder.")
            return hit["paths"]
        if not isinstance(typed, str) or not typed.strip():
            raise BadInput("Choose a video first.")
        target = Path(typed.strip().strip('"')).expanduser()
        if not target.exists():
            raise BadInput("No file or folder at that path.")
        files = _expand([target])
        if not files or any(f.suffix.lower() not in VIDEO_EXT for f in files):
            raise BadInput("That path is not a video, or a folder holding videos.")
        number = proto.video_number(target) if target.is_file() else None
        if number:   # the other parts of a split GoPro video sit beside it
            return [f for f in sorted(target.parent.iterdir()) if f.suffix.lower() in VIDEO_EXT and proto.video_number(f) == number]
        groups = proto.group_chapters(files)
        if target.is_dir() and (len(groups) > 1 or len(groups.get("_other", [])) > 1):
            raise BadInput("That folder holds more than one video. Give the path to one video.")
        return next(iter(groups.values()))

    def detector_ready():
        return importlib.util.find_spec("rfdetr") is not None and any((PROJECT_ROOT / "models").glob("cfd-rf-detr-*.pth"))

    @app.post("/api/videos/browse")
    def browse_for_video():
        """Open this computer's own file picker, so a large video can be used where it sits, without copying it."""
        json_body()
        if sys.platform == "darwin":
            cmd = ["osascript", "-e", 'POSIX path of (choose file with prompt "Open a video" of type {"public.movie"})']
        else:
            cmd = [sys.executable, "-c", "import tkinter as t;from tkinter import filedialog as f;r=t.Tk();r.withdraw();r.attributes('-topmost',True);"
                   "print(f.askopenfilename(title='Open a video',filetypes=[('Video','*.mp4 *.MP4 *.mov *.MOV *.m4v *.avi *.mkv')]))"]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            return jsonify(path=None, unavailable=True)
        path = done.stdout.strip()
        if done.returncode and "-128" not in done.stderr and sys.platform == "darwin":   # -128 means the person pressed Cancel
            return jsonify(path=None, unavailable=True)
        return jsonify(path=path or None)

    @app.get("/api/videos")
    def list_videos():
        entries = [{k: v for k, v in e.items() if k != "paths"} for e in inbox_entries()]
        return jsonify(videos=entries, folder=str(videos_root), detector_ready=detector_ready())

    @app.put("/api/videos/upload")
    def upload_video():
        # The custom header stops another website from sending a file here: browsers refuse it without our say-so.
        if request.headers.get("X-ClipSift-Upload") != "1":
            raise BadInput("Upload header missing")
        name = re.sub(r'[\x00-\x1f\\/:*?"<>|]', "_", Path(request.args.get("name", "")).name).strip()
        if not name or name.startswith(".") or Path(name).suffix.lower() not in VIDEO_EXT:
            raise BadInput("Choose a video file (mp4, mov, m4v, avi or mkv).")
        videos_root.mkdir(parents=True, exist_ok=True)
        dest, part = videos_root / name, videos_root / (name + ".part")
        if dest.exists():
            raise BadInput("A video with that name is already in the folder. Pick it from the list.")
        size = request.content_length or 0
        if size and shutil.disk_usage(videos_root).free < size + 1_000_000_000:
            raise BadInput("Not enough free disk space for that video.")
        try:
            with open(part, "wb") as f:
                shutil.copyfileobj(request.stream, f, 4 * 1024 * 1024)
            if size and part.stat().st_size != size:
                raise BadInput("The upload stopped early. Try again.")
            part.replace(dest)
        finally:
            part.unlink(missing_ok=True)
        return jsonify(id=name, suggested_name=safe_run_name(dest.stem))

    @app.post("/api/videos/preview")
    def video_preview():
        """Small frames at each candidate window start, so a person can see when the sediment settles."""
        import cv2
        from clipsift.video import Timeline, resize_to_width
        paths = paths_from(json_body())
        stamp = "|".join(f"{p}:{p.stat().st_size}:{p.stat().st_mtime}" for p in paths)
        key = hashlib.sha256(stamp.encode("utf-8")).hexdigest()[:16]
        folder = runs_root / ".jobs" / "preview" / key
        folder.mkdir(parents=True, exist_ok=True)
        line = Timeline(paths)
        minutes = list(PREVIEW_MINUTES)
        for longer_than, extra in LONG_VIDEO_MINUTES:
            if line.duration_s > longer_than:
                minutes += extra
        frames = []
        for m in minutes:
            t = m * 60
            if t >= line.duration_s - 60:
                continue
            out = folder / f"{int(t)}.jpg"
            if not out.is_file():
                frame = line.get_frame(t)
                if frame is None:
                    continue
                cv2.imwrite(str(out), resize_to_width(frame, 480), [cv2.IMWRITE_JPEG_QUALITY, 80])
            frames.append({"t_s": t, "url": f"/api/videos/preview/{key}/{int(t)}.jpg"})
        names = proto.parse_names([str(p) for p in paths])
        return jsonify(duration_s=line.duration_s, frames=frames, names=names, parts=[p.name for p in paths],
                       suggested_name=safe_run_name(paths[0].stem))

    @app.get("/api/videos/preview/<key>/<name>")
    def video_preview_image(key, name):
        if not re.fullmatch(r"[0-9a-f]{16}", key) or not re.fullmatch(r"\d+\.jpg", name):
            abort(404, "Not found")
        path = runs_root / ".jobs" / "preview" / key / name
        if not path.is_file():
            abort(404, "Not found")
        return send_file(path, mimetype="image/jpeg")

    @app.get("/api/runs/<run_id>/window")
    def window_video(run_id):
        path = run_dir_for(run_id) / "window.mp4"
        if not path.is_file():
            abort(404, "No window video for this run")
        return send_file(path, mimetype="video/mp4", conditional=True)

    @app.get("/api/jobs")
    def list_jobs():
        return jsonify(jobs=jobs.list())

    @app.post("/api/jobs")
    def add_job():
        data = json_body()
        paths = paths_from(data)
        name = clean_str(data.get("name"), "name", 100) or safe_run_name(paths[0].stem)
        if not NAME_RE.match(name):
            raise BadInput("Use only letters, numbers, dots, dashes and underscores in the name.")
        if (runs_root / name / "results.json").exists() or jobs.busy_with(name):
            raise BadInput("A run with that name already exists. Choose another name, so its saved counts stay safe.")
        layer = data.get("layer", 0)
        if layer not in (0, 1):
            raise BadInput("layer must be 0 or 1")
        if layer == 1 and not detector_ready():
            raise BadInput("The fish detector is not installed here. Turn it off to process without it.")
        def seconds(key):
            v = data.get(key)
            if v is None or v == "":
                return None
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v < 1e6:
                raise BadInput(f"{key} must be a number of seconds")
            return v
        ws, we = seconds("window_start"), seconds("window_end")
        if ws is not None and we is not None and we <= ws:
            raise BadInput("The window must end after it starts.")
        interval = seconds("interval")
        if interval is not None and not 5 <= interval <= 600:
            raise BadInput("interval must be between 5 and 600 seconds")
        video_id = clean_str(data.get("video_id"), "video_id", 100) or None
        year = clean_int(data.get("year"), "year", 1990, 2100)
        meta = {"transect": clean_str(data.get("transect"), "transect", 40), "stat": clean_str(data.get("stat"), "stat", 40),
                "year": year, "season": clean_str(data.get("season"), "season", 40)}
        return jsonify(jobs.add(name, paths, layer, ws, we, video_id, interval, meta)), 201

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel_job(job_id):
        json_body()
        if not jobs.cancel(job_id):
            raise BadInput("That job is not running.")
        return jsonify(ok=True)

    # ---- species -----------------------------------------------------------
    @app.get("/api/species")
    def get_species():
        species, note = [], None
        if species_file.is_file():
            try:
                data = json.loads(species_file.read_text(encoding="utf-8"))
                species = [s for s in data if isinstance(s, dict)] if isinstance(data, list) else []
            except (OSError, ValueError):
                note = "Species list could not be read. Free text still works."
        return jsonify(species=species, local_aliases=read_jsonl(aliases_file), note=note)

    @app.post("/api/species/aliases")
    def add_alias():
        data = json_body()
        alias = clean_str(data.get("alias"), "alias", 100, allow_empty=False)
        maps_to = clean_str(data.get("maps_to"), "maps_to", 200, allow_empty=False)
        record = {"alias": alias, "maps_to": maps_to, "at": now_iso()}
        append_jsonl(aliases_file, record)  # never touches species_list.json
        return jsonify(record), 201

    # ---- species bank: images for a person to identify. Never touches counts. ----
    def bank_folder():
        """Which set a request means: the V6 species bank, or the end-of-run review set."""
        name = request.args.get("set") or "species_bank"
        if name not in BANK_SETS:
            abort(404, "No such set")
        return BANK_SETS[name]

    def load_bank(run_dir, folder="species_bank"):
        path = run_dir / folder / "bank.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            abort(422, "bank.json could not be read")
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            abort(422, "bank.json is missing its items list")
        return data

    def bank_decisions(run_dir, folder="species_bank"):
        latest = {}
        for row in read_jsonl(run_dir / folder / "decisions.jsonl"):
            latest[row.get("item_id")] = row   # the last decision on an item wins
        return latest

    def species_flags(name):
        """Flags and status note for a chosen species, matched on its scientific name."""
        try:
            data = json.loads(species_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return [], ""
        for s in data if isinstance(data, list) else []:
            if isinstance(s, dict) and s.get("scientific_name") == name:
                return sorted(k for k, v in (s.get("flags") or {}).items() if v), s.get("id_notes") or ""
        return [], ""

    @app.get("/api/runs/<run_id>/species_bank")
    def get_species_bank(run_id):
        run_dir = run_dir_for(run_id)
        folder = bank_folder()
        bank = load_bank(run_dir, folder)
        if bank is None:
            return jsonify(available=False)
        if folder == "review_set":   # the source stays hidden until the person has decided, so it can't sway them
            decided = bank_decisions(run_dir, folder)
            for item in bank["items"]:
                if item.get("id") not in decided:
                    for key in ("source", "max_confidence", "kind_marked", "species_marked"):
                        item.pop(key, None)
            bank.pop("counts", None)
            bank.pop("pools", None)
        return jsonify(available=True, bank=bank, decisions=bank_decisions(run_dir, folder))

    @app.get("/api/runs/<run_id>/species_bank/files/<name>")
    def species_bank_file(run_id, name):
        run_dir = run_dir_for(run_id)
        path = (run_dir / bank_folder() / "files" / name).resolve()
        if not BANK_FILE_RE.match(name) or run_dir not in path.parents or not path.is_file():
            abort(404, "File not found")
        kind = "video/mp4" if name.endswith(".mp4") else "image/jpeg"
        resp = send_file(path, mimetype=kind, conditional=True, max_age=0)
        resp.headers["Accept-Ranges"] = "bytes"
        return resp

    @app.post("/api/runs/<run_id>/species_bank/decisions")
    def post_species_bank_decision(run_id):
        run_dir = run_dir_for(run_id)
        folder = bank_folder()
        bank = load_bank(run_dir, folder)
        if bank is None:
            abort(404, "This run has no species bank")
        data = json_body()
        item_id = data.get("item_id")
        if not any(isinstance(i, dict) and i.get("id") == item_id for i in bank["items"]):
            raise BadInput("item_id is not in this bank")
        outcome = data.get("outcome")
        if outcome not in (REVIEW_OUTCOMES if folder == "review_set" else BANK_OUTCOMES):
            raise BadInput("outcome is not a known choice")
        stage = data.get("life_stage") or "unknown"
        if stage not in BANK_LIFE_STAGES:
            raise BadInput("life_stage is not a known choice")
        species = clean_str(data.get("species"), "species", 200) or ""
        if outcome == "species" and not species:
            raise BadInput("Choose a species, or pick another outcome")
        named = outcome in BANK_NAMED and species
        flags, note = species_flags(species) if named else ([], "")
        record = {
            "item_id": item_id, "outcome": outcome,
            "species": species if named else "",
            "life_stage": stage if outcome in BANK_NAMED + ("needs_expert",) else "unknown",
            "species_flags": flags, "status_note": note,
            "notes": clean_str(data.get("notes"), "notes", 2000) or "",
            "reviewer": clean_str(data.get("reviewer"), "reviewer", 100, allow_empty=False),
            "at": now_iso(),
        }
        append_jsonl(run_dir / folder / "decisions.jsonl", record)
        return jsonify(record), 201

    @app.post("/api/runs/<run_id>/review_set")
    def start_review_set(run_id):
        """Run the model over the finished video and pick the items for a person to check."""
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        count = json_body().get("count", 36)
        if count not in REVIEW_SET_SIZES:
            raise BadInput("count must be one of: " + ", ".join(map(str, REVIEW_SET_SIZES)))
        if not detector_ready():
            raise BadInput("The fish detector is not installed on this computer, so this step isn't available.")
        if qc_and_means(results, read_jsonl(run_dir / "subsample_reviews.jsonl"))["n_counted"] == 0:
            raise BadInput("Count the points first. Model flags can sway a count.")
        if jobs.busy_with(run_id):
            raise BadInput("This video is already being processed.")
        return jsonify(jobs.add_review_set(run_id, run_dir, count)), 201

    @app.get("/api/runs/<run_id>/review_set.csv")
    def export_review_set_csv(run_id):
        """Everything needed to reuse a checked item as training data. Boxes are in the recording's pixels."""
        run_dir = run_dir_for(run_id)
        bank = load_bank(run_dir, "review_set")
        if bank is None:
            abort(404, "This run has no review set")
        decisions = bank_decisions(run_dir, "review_set")
        header = ["item_id", "source", "subsample_id", "time_s", "x1", "y1", "x2", "y2", "model_score", "model", "kind_marked",
                  "outcome", "training_label", "species", "life_stage", "notes", "reviewer", "decided_at", "frame_file", "crop_file"]
        rows = []
        for item in bank["items"]:
            d = decisions.get(item.get("id")) or {}
            box, img = item.get("bbox") or [None] * 4, item.get("images") or {}
            rows.append([item.get("id"), item.get("source"), item.get("subsample_id"), item.get("time_s"), *box, item.get("max_confidence"),
                         (bank.get("source") or {}).get("model"), item.get("kind_marked"), d.get("outcome"), TRAINING_LABEL.get(d.get("outcome")),
                         d.get("species") or None, d.get("life_stage"), d.get("notes") or None, d.get("reviewer"), d.get("at"), img.get("frame"), img.get("crop")])
        return csv_response(rows, header, f"{run_id}_review_set.csv")

    @app.get("/api/runs/<run_id>/species_bank.csv")
    def export_species_bank_csv(run_id):
        run_dir = run_dir_for(run_id)
        bank = load_bank(run_dir)
        if bank is None:
            abort(404, "This run has no species bank")
        decisions = bank_decisions(run_dir)
        header = ["item_id", "time_s", "point_s", "flags", "outcome", "species", "life_stage",
                  "species_flags", "notes", "reviewer", "decided_at"]
        rows = []
        for item in bank["items"]:
            d = decisions.get(item.get("id")) or {}
            rows.append([item.get("id"), item.get("time_s"), item.get("point_s"),
                         ";".join(item.get("flags") or []) or None,
                         d.get("outcome"), d.get("species") or None, d.get("life_stage"),
                         ";".join(d.get("species_flags") or []) or None, d.get("notes") or None,
                         d.get("reviewer"), d.get("at")])
        return csv_response(rows, header, f"{run_id}_species_bank.csv")

    # ---- feedback ----------------------------------------------------------
    @app.post("/api/feedback")
    def post_feedback():
        """Local feedback from the Feedback button. Appends to runs/feedback.jsonl (untrusted text)."""
        data = json_body()
        if data.get("website"):  # honeypot field: people leave it empty, bots fill it
            return jsonify(ok=True), 201
        message = clean_str(data.get("message"), "message", 2000, allow_empty=False)
        area, kind = data.get("area"), data.get("type")
        if area not in FEEDBACK_AREAS:
            raise BadInput("area must be one of: " + ", ".join(FEEDBACK_AREAS))
        if kind not in FEEDBACK_TYPES:
            raise BadInput("type must be one of: " + ", ".join(FEEDBACK_TYPES))
        ctx = data.get("page_context")
        if ctx is not None and not isinstance(ctx, (dict, str)):
            raise BadInput("page_context must be an object or text")
        if len(json.dumps(ctx, ensure_ascii=False)) > 2000:
            raise BadInput("page_context is too long")
        record = {"id": uuid.uuid4().hex, "created_at": now_iso(),
                  "name": clean_str(data.get("name"), "name", 60) or "", "area": area, "type": kind,
                  "message": message, "page_context": ctx, "source": "flask"}
        append_jsonl(runs_root / "feedback.jsonl", record)
        return jsonify(ok=True, id=record["id"]), 201

    # ---- blind label mode ---------------------------------------------------
    # Local copy of the Worker routes (deploy/src/worker.js). Rows go to one append-only JSON lines file; the
    # latest row for a set, frame and labeller wins. IDENTITY IS A CHOSEN NAME, NOT A LOGIN: this local server
    # has no sign-in, so anyone who can reach it can type any name. No route returns another person's marks.
    @app.get("/label_sets/index.json")
    def label_set_index():
        ids = []
        if label_sets_root.is_dir():
            ids = sorted(d.name for d in label_sets_root.iterdir() if d.is_dir() and LABEL_SET_RE.match(d.name) and (d / "manifest.json").is_file())
        return jsonify(sets=ids)

    def manifest_with_calibration(path):
        """The manifest, with `calibration` taken from calibration.json next to it when that file exists (same rule as tools/build_demo.py)."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            abort(422, "manifest.json could not be read")
        cal_path = path.parent / "calibration.json"
        if isinstance(data, dict) and cal_path.is_file() and not cal_path.is_symlink():
            try:
                cal = json.loads(cal_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                abort(422, "calibration.json could not be read")
            if isinstance(cal, dict) and cal.get("calibration_only") is True:
                data["calibration_only"] = True
            cal = cal.get("calibration") if isinstance(cal, dict) else cal
            known = {f.get("frame_id") for f in data.get("frames") or [] if isinstance(f, dict)}
            if isinstance(cal, list):
                data["calibration"] = list(dict.fromkeys(i for i in cal if isinstance(i, str) and i in known))
        return data

    @app.get("/label_sets/<set_id>/<path:rest>")
    def label_set_file(set_id, rest):
        """Frames, clips and the manifest. send_file answers Range requests, which the clips need."""
        if not LABEL_SET_RE.match(set_id):
            abort(400, "Bad set name")
        parts = rest.split("/")
        ok = (parts == ["manifest.json"]) or (len(parts) == 2 and parts[0] in ("frames", "clips", "diff") and LABEL_FRAME_RE.match(parts[1]))
        if not ok:
            abort(404, "Not found")
        path = (label_sets_root / set_id / rest).resolve()
        if label_sets_root not in path.parents or not path.is_file() or path.is_symlink():
            abort(404, "Not found")
        if parts == ["manifest.json"]:
            return jsonify(manifest_with_calibration(path))
        resp = send_file(path, conditional=True, max_age=0 if parts[0] == "manifest.json" else 3600)
        return resp

    def label_name(value):
        if not isinstance(value, str):
            raise BadInput("name is required")
        name = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", value)).strip()
        if not name:
            raise BadInput("name is required")
        if len(name) > LABEL_NAME_MAX:
            raise BadInput(f"name is too long (max {LABEL_NAME_MAX} characters)")
        for preset in LABEL_PRESET_NAMES:
            if preset.lower() == name.lower():
                return preset
        return name

    def label_ids(set_id, frame_id=None, need_frame=False):
        if not isinstance(set_id, str) or not LABEL_SET_RE.match(set_id):
            raise BadInput("set is missing or not a plain id")
        if need_frame or frame_id is not None:
            if not isinstance(frame_id, str) or not LABEL_FRAME_RE.match(frame_id):
                raise BadInput("frame is missing or not a plain id")

    def label_frames(set_id):
        path = label_sets_root / set_id / "manifest.json"
        if not path.is_file():
            abort(404, "Unknown label set.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            abort(422, "manifest.json could not be read")
        frames = {}
        for f in (data.get("frames") or []) if isinstance(data, dict) else []:
            if isinstance(f, dict) and isinstance(f.get("frame_id"), str) and LABEL_FRAME_RE.match(f["frame_id"]) \
                    and isinstance(f.get("width"), (int, float)) and isinstance(f.get("height"), (int, float)):
                frames[f["frame_id"]] = (f["width"], f["height"])
        return frames

    def label_rows(set_id):
        """Latest row per (frame, labeller). Names compare without case."""
        latest = {}
        for r in read_jsonl(labels_file):
            if r.get("set") == set_id and isinstance(r.get("frame"), str) and isinstance(r.get("name"), str):
                latest[(r["frame"], r["name"].lower())] = r
        return latest

    @app.get("/api/labels/status")
    def labels_status():
        set_id, name = request.args.get("set"), label_name(request.args.get("name"))
        label_ids(set_id)
        frames = label_frames(set_id)
        counts, mine = {}, {}
        for (frame, who), r in label_rows(set_id).items():
            if frame not in frames:
                continue
            if not r.get("skipped"):
                counts[frame] = counts.get(frame, 0) + 1
            if who == name.lower():
                mine[frame] = {"state": "skipped" if r.get("skipped") else "done", "no_animals": bool(r.get("no_animals")),
                               "n_points": len(r.get("points") or []), "seconds": r.get("seconds"), "updated_at": r.get("updated_at")}
        return jsonify(set=set_id, total=len(frames), counts=counts, mine=mine,
                       team={"frames_with_any": len(counts), "frames_with_two": sum(1 for n in counts.values() if n >= 2)})

    @app.get("/api/labels/mine")
    def labels_mine():
        set_id, frame_id, name = request.args.get("set"), request.args.get("frame"), label_name(request.args.get("name"))
        label_ids(set_id, frame_id, need_frame=True)
        frames = label_frames(set_id)
        if frame_id not in frames:
            abort(404, "That frame is not in this label set.")
        r = label_rows(set_id).get((frame_id, name.lower()))
        if not r:
            return jsonify(exists=False)
        return jsonify(exists=True, frame=frame_id, points=r.get("points") or [], views=r.get("views") or [], no_animals=bool(r.get("no_animals")),
                       skipped=bool(r.get("skipped")), seconds=r.get("seconds"), updated_at=r.get("updated_at"))

    @app.post("/api/labels")
    def labels_save():
        if (request.content_length or 0) > LABEL_MAX_BODY:
            return jsonify(error="That save is too large."), 413
        data = json_body()
        label_ids(data.get("set"), data.get("frame"), need_frame=True)
        name = label_name(data.get("name"))
        frames = label_frames(data["set"])
        if data["frame"] not in frames:
            raise BadInput("That frame is not in this label set.")
        width, height = frames[data["frame"]]
        for key in ("skipped", "no_animals"):
            if data.get(key) is not None and not isinstance(data.get(key), bool):
                raise BadInput(f"{key} must be true or false")
        skipped, no_animals = data.get("skipped") is True, data.get("no_animals") is True
        raw = data.get("points")
        raw = [] if raw is None else raw
        if not isinstance(raw, list):
            raise BadInput("points must be a list")
        if len(raw) > LABEL_MAX_POINTS:
            raise BadInput(f"Too many points (max {LABEL_MAX_POINTS})")
        points = []
        for pt in raw:
            if not isinstance(pt, dict):
                raise BadInput("Each point needs x, y and kind")
            x, y = pt.get("x"), pt.get("y")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (x, y)):
                raise BadInput("Point coordinates must be numbers")
            if x < 0 or y < 0 or x > width or y > height:
                raise BadInput(f"A point is outside the image ({width} x {height})")
            if pt.get("kind") not in LABEL_KINDS:
                raise BadInput("kind must be fish, invertebrate, unsure or not_fish")
            out = {"x": round(x, 1), "y": round(y, 1), "kind": pt["kind"]}
            if pt["kind"] == "not_fish":
                # A not-fish mark has a category (or none) and never a species.
                cat = pt.get("category")
                if cat is not None and cat != "":
                    if not isinstance(cat, str) or cat not in LABEL_NOT_FISH_CATEGORIES:
                        raise BadInput("category must be one of: " + ", ".join(LABEL_NOT_FISH_CATEGORIES) + " (or empty)")
                    out["category"] = cat
            elif pt["kind"] == "unsure":
                pass    # an unsure mark carries no species and no category: anything sent is dropped
            elif pt.get("species") is not None:
                if not isinstance(pt["species"], str):
                    raise BadInput("species must be text")
                sp = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", pt["species"])).strip()
                if len(sp) > LABEL_SPECIES_MAX:
                    raise BadInput(f"species is too long (max {LABEL_SPECIES_MAX} characters)")
                if sp:
                    out["species"] = sp
            points.append(out)
        views = data.get("views")
        if views is None:
            views = []
        if not isinstance(views, list) or len(views) > 10 or any(v not in LABEL_VIEWS for v in views):
            raise BadInput("views must be a list made of: " + ", ".join(LABEL_VIEWS))
        views = [v for v in LABEL_VIEWS if v in views]
        if (no_animals or skipped) and points:
            raise BadInput("A skipped frame or a No animals frame cannot have points")
        if no_animals and skipped:
            raise BadInput("A frame cannot be both skipped and No animals")
        seconds = data.get("seconds", 0)
        seconds = 0 if seconds is None else seconds
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            raise BadInput("seconds must be a number, 0 or more")
        record = {"set": data["set"], "frame": data["frame"], "name": name, "points": points, "views": views, "no_animals": no_animals,
                  "seconds": min(round(seconds, 1), LABEL_MAX_SECONDS), "skipped": skipped, "updated_at": now_iso(), "source": "flask"}
        append_jsonl(labels_file, record)
        return jsonify(ok=True, updated_at=record["updated_at"], n_points=len(points))

    # ---- export ------------------------------------------------------------
    def csv_response(rows, header, name):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        for row in rows:
            # Stop spreadsheet programs treating typed text as a formula.
            w.writerow([("'" + c) if isinstance(c, str) and c and c[0] in "=+-@\t\r" else c for c in row])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.get("/api/runs/<run_id>/export_segments.csv")
    def export_segments_csv(run_id):
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        reviews = read_jsonl(run_dir / "reviews.jsonl")
        tags = read_jsonl(run_dir / "grid_tags.jsonl")
        by_seg, n_dec, n_tags = {}, {}, {}
        for r in reviews:
            sid = r.get("segment_id")
            by_seg[sid] = r
            n_dec[sid] = n_dec.get(sid, 0) + 1
        for t in tags:
            n_tags[t.get("segment_id")] = n_tags.get(t.get("segment_id"), 0) + 1
        include_all = request.args.get("all") == "1"
        rec_id = (results.get("recording") or {}).get("recording_id") or run_id
        rows = []
        for seg in results["segments"]:
            if not isinstance(seg, dict):
                continue
            sid = seg.get("segment_id")
            rev = by_seg.get(sid)
            if rev is None and not include_all:
                continue
            rev = rev or {}
            flags, counts = seg.get("flags") or {}, seg.get("counts") or {}
            rows.append([
                rec_id, sid, seg.get("start_s"), seg.get("end_s"), seg.get("kind"),
                seg.get("audit_sample"), seg.get("status"), seg.get("motion_score"),
                seg.get("visibility_score"), flags.get("shake"), flags.get("low_visibility"),
                seg.get("review_priority"), counts.get("maxn"), counts.get("mean_count"),
                counts.get("unique_tracks"), rev.get("decision"), rev.get("species"),
                rev.get("species_free_text"), rev.get("count"), rev.get("note"),
                rev.get("reviewer"), rev.get("at"), n_dec.get(sid, 0), n_tags.get(sid, 0),
            ])
        rows = [["" if c is None else c for c in row] for row in rows]
        return csv_response(rows, [c for c, _ in CSV_COLUMNS], f"{run_id}_segments_reviewed.csv")

    SUB_COLUMNS = [
        ("Video ID", "Video ID from results.json. Must match the Coastal Action spreadsheet."),
        ("Subsample", "Subsample point id."),
        ("Time (s)", "Seconds from the start of the recording."),
        ("Counter", "Who counted."),
        ("Pass", "primary, qc_blind (second blind count) or recount."),
        ("Total fish count", "Fish counted in the designated second. A relative index, not abundance."),
        ("Invertebrate count", "Invertebrates counted in the designated second. A relative index."),
        ("Number of species", "Species in this subsample."),
        ("Unknown/Unable to ID due to visibility", "Count that could not be identified because of visibility."),
        ("Visibility category", "Water clarity category for this point."),
        ("Visibility change >= 0.5 m", "yes if visibility changed by 0.5 m or more."),
        ("Visibility direction", "increasing or decreasing, when it changed."),
        ("Characteristics ticked", "Of shape, anatomical features, colour or flashes, swimming behaviour."),
        ("Notes", "Reviewer notes. Movement noted as unidentified is a note, never counted."),
        ("Saved at (UTC)", "When the count was saved."),
        ("QC percent difference", "Primary vs second count difference. Formula is provisional (see percent_difference in server.py)."),
        ("QC recount suggested", "yes if the two counts are over the limit and more than a small gap apart. Advisory."),
    ]
    SPECIES_PREFIX = "Count: "

    @app.get("/api/runs/<run_id>/export.csv")
    def export_subsamples_csv(run_id):
        """One row per saved subsample count, Coastal Action style column names."""
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        revs = read_jsonl(run_dir / "subsample_reviews.jsonl")
        info = qc_and_means(results, revs)
        vid = (results.get("recording") or {}).get("video_id") or (results.get("recording") or {}).get("recording_id") or run_id
        times = {s.get("subsample_id"): s.get("t_s") for s in results.get("subsamples") or [] if isinstance(s, dict)}
        names = sorted({n for r in revs for n in (r.get("species_counts") or {})})
        rows = []
        for r in revs:
            q = info["qc"].get(r.get("subsample_id")) if r.get("pass") != "primary" else None
            sc = r.get("species_counts") or {}
            vc = r.get("visibility_change")
            rows.append([vid, r.get("subsample_id"), times.get(r.get("subsample_id")), r.get("counter"), r.get("pass"),
                         r.get("total_fish_count"), r.get("invertebrate_count"), r.get("total_species"),
                         r.get("unknown_count"), r.get("visibility_category"),
                         "" if vc is None else ("yes" if vc else "no"), r.get("visibility_direction"),
                         ";".join(r.get("characteristics") or []), r.get("notes"), r.get("at"),
                         q["percent_diff"] if q and q["percent_diff"] is not None else "",
                         ("yes" if q["recount_needed"] else "no") if q else ""] + [sc.get(n, "") for n in names])
        rows = [["" if c is None else c for c in row] for row in rows]
        header = [c for c, _ in SUB_COLUMNS] + [SPECIES_PREFIX + n for n in names]
        return csv_response(rows, header, f"{run_id}_subsamples.csv")

    @app.get("/api/runs/<run_id>/export_summary.csv")
    def export_summary_csv(run_id):
        """One row for the video: MeanCount, species list, window, juveniles, QC."""
        run_dir = run_dir_for(run_id)
        results = load_results(run_dir)
        revs = read_jsonl(run_dir / "subsample_reviews.jsonl")
        notes = read_jsonl(run_dir / "recording_notes.jsonl")
        n = notes[-1] if notes else {}
        info = qc_and_means(results, revs)
        rec = results.get("recording") or {}
        proto = results.get("protocol") or {}
        species = set(n.get("species_observed") or [])
        for r in info["latest_primary"].values():
            species.update((r.get("species_counts") or {}).keys())
        vis = "; ".join(f"{v['observer']}: {v['category']}" for v in visibility_rows(run_dir, notes))
        finals = list(info["final_fish"].values())
        sd = math.sqrt(sum((v - sum(finals) / len(finals)) ** 2 for v in finals) / (len(finals) - 1)) if len(finals) > 1 else None
        header = ["Video ID", "Transect", "STAT", "Year", "Season", "Window start (s)", "Window end (s)",
                  "Subsamples counted", "Subsamples planned", "MeanCount (fish per subsample, reviewed)",
                  "MeanCount with QC averages", "Standard deviation", "Standard error",
                  "Species observed", "Number of species", "Juveniles present (1/0)", "Visibility by observer",
                  "QC pairs", "QC recounts suggested", "QC agreement (%) (provisional)", "QC result", "Note"]
        qcs = info["qc"].values()
        row = [rec.get("video_id") or rec.get("recording_id") or run_id, rec.get("transect"), rec.get("stat"),
               rec.get("year"), rec.get("season"),
               n.get("window_start_s", proto.get("window_start_s")), n.get("window_end_s", proto.get("window_end_s")),
               info["n_counted"], info["n_subsamples"], info["mean_count_reviewed"], info["mean_count_final"],
               None if sd is None else round(sd, 3), None if sd is None else round(sd / math.sqrt(len(finals)), 3),
               "; ".join(sorted(species)), len(species), n.get("juveniles"), vis,
               len(info["qc"]), sum(1 for q in qcs if q["recount_needed"]), info["qc_agreement"], info["qc_check"]["status"],
               "Counts are a relative index, not abundance."]
        return csv_response([["" if c is None else c for c in row]], header, f"{run_id}_video_summary.csv")

    @app.get("/api/runs/<run_id>/export_columns.csv")
    def export_columns(run_id):
        run_dir_for(run_id)
        return csv_response(SUB_COLUMNS + [("Video summary: MeanCount", "Mean of Total fish count over latest primary counts. A relative index, not abundance.")] + CSV_COLUMNS, ["column", "meaning"], f"{run_id}_column_dictionary.csv")

    return app


def main(argv=None):
    p = argparse.ArgumentParser(description="ClipSift review app (local only)")
    p.add_argument("--runs", default="runs", help="folder holding run folders")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--species", default=None, help="species_list.json (default ../species/)")
    p.add_argument("--aliases", default=None, help="local alias file (default app/local_aliases.jsonl)")
    p.add_argument("--label-sets", default=None, help="folder of label sets (default label_sets/)")
    p.add_argument("--labels", default=None, help="file the label page saves to (default app/local_labels.jsonl)")
    p.add_argument("--videos", default=None, help="folder of videos to process (default videos/)")
    p.add_argument("--open", action="store_true", help="open the app in the web browser")
    args = p.parse_args(argv)
    app = create_app(args.runs, args.species, args.aliases, args.label_sets, args.labels, args.videos)
    print(f"ClipSift: http://127.0.0.1:{args.port}  (runs folder: {app.config['RUNS_ROOT']})")
    if args.open:
        import webbrowser
        threading.Timer(1.0, webbrowser.open, [f"http://127.0.0.1:{args.port}"]).start()
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
