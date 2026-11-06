"""Coastal Action protocol helpers (DRAFT protocol: every number comes from config).

File names: GoPro chapters such as GX010221_T1@1217pm and GX020221_T1@1226pm.
GX01nnnn and GX02nnnn are chapters of video nnnn. Folder layout is
drive > year > season > date > transect > STAT (for example T1 / STAT 1).
"""
from __future__ import annotations

import random
import re
from pathlib import Path

GX_RE = re.compile(r"GX(\d{2})(\d{4})", re.I)
TRANSECT_RE = re.compile(r"(?:^|[_\-\s])(T\d+)(?=[_\-\s@.]|$)", re.I)
STAT_RE = re.compile(r"STAT[\s_\-]*(\d+)", re.I)
TIME_RE = re.compile(r"@(\d{1,2})(\d{2})\s*([ap]m)", re.I)
SEASONS = ("spring", "summer", "fall", "autumn", "winter")


def video_number(path) -> str | None:
    m = GX_RE.search(Path(path).name)
    return m.group(2) if m else None


def group_chapters(paths) -> dict:
    """Group files by GoPro video number; chapters in name order. Files without a GX number
    all go into one group named by the first file's stem."""
    groups: dict = {}
    for p in sorted((Path(x) for x in paths), key=lambda x: x.name):
        key = video_number(p) or "_other"
        groups.setdefault(key, []).append(p)
    return groups


def parse_names(paths) -> dict:
    """Best-effort parse of video_id, transect, stat, year, season. Unknowns are None (editable)."""
    first = Path(paths[0])
    parts = list(first.parts)
    info = {"video_id": None, "transect": None, "stat": None, "year": None, "season": None}
    vn = video_number(first)
    m = TRANSECT_RE.search(first.stem)
    if m:
        info["transect"] = m.group(1).upper()
    for part in reversed(parts):  # the filename counts too, e.g. "T1-STAT2 411.MP4"
        s = STAT_RE.search(part)
        if s and not info["stat"]:
            info["stat"] = f"STAT {s.group(1)}"
        if re.fullmatch(r"T\d+", part, re.I) and not info["transect"]:
            info["transect"] = part.upper()
        if re.fullmatch(r"20\d\d", part) and not info["year"]:
            info["year"] = int(part)
        if part.lower() in SEASONS and not info["season"]:
            info["season"] = part.lower()
    if vn:
        # GUESS: the spreadsheet's Video ID format is not known. Override with --video-id.
        info["video_id"] = f"GX{vn}" + (f"_{info['transect']}" if info["transect"] else "")
    return info


def analysis_window(duration_s: float, pc: dict, start_override=None, end_override=None):
    """Return (start_s, end_s). Default: trim first and last minute, cap at window_length_s.
    Overrides (config or CLI) replace the default start/end; the recorded times are what was used."""
    start = pc["trim_start_s"] if start_override is None else start_override
    end = duration_s - pc["trim_end_s"] if end_override is None else end_override
    if start_override is None and end_override is None:
        end = min(end, start + pc["window_length_s"])
    start, end = max(0.0, float(start)), min(float(duration_s), float(end))
    if end <= start:
        raise ValueError(f"Analysis window is empty ({start:.1f}s to {end:.1f}s) for a {duration_s:.1f}s recording. "
                         "Check protocol trims or pass window overrides.")
    return start, end


def window_warnings(duration_s: float, start: float, end: float, pc: dict) -> list:
    out = []
    removed_extra = (start - pc["trim_start_s"]) + max(0.0, (duration_s - pc["trim_end_s"]) - end)
    if removed_extra > pc["extra_trim_max_s"]:
        out.append(f"Window removes {removed_extra:.0f}s beyond the standard trims "
                   f"(protocol allows up to {pc['extra_trim_max_s']}s).")
    return out


def subsample_times(start: float, end: float, pc: dict) -> list:
    """Systematic points every interval_s from the window start; each must leave room for the count window."""
    times, k = [], 0
    while True:
        t = start + k * pc["interval_s"]
        if t + pc["count_window_s"] > end + 1e-9:
            break
        times.append(round(t, 3))
        k += 1
    return times


def pick_qc(n: int, pc: dict) -> set:
    """Indices for the random QC review sample (share of points, clamped to qc_min..qc_max)."""
    if n == 0:
        return set()
    k = min(n, max(pc["qc_min"], min(pc["qc_max"], round(pc["qc_share"] * n))))
    return set(random.Random(pc["qc_seed"]).sample(range(n), k))
