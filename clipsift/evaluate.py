"""Compare results.json to human labels. Bias, MAE, per-row table, human-vs-human agreement.

Two label styles (detected from the CSV header):
  subsample rows (spreadsheet style): columns for video id, timestamp, total fish count.
      Header names are matched loosely: 'Video ID', 'Timestamp' (seconds, mm:ss or h:mm:ss),
      'Total Fish Count'. A second counter can be given as 'Total Fish Count B' (first is then 'A',
      or the plain column). Compared with auto.fish_count of the nearest subsample.
  segment rows: recording_id, segment_id or start_s/end_s, maxn, count. maxn is compared with
      counts.maxn and count with counts.unique_tracks. Second counters: maxn_a / maxn_b.

Signed bias = mean(model - human). Rows where the model value is null are skipped and counted.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

SMALL_N = 30


def _norm(h):
    return re.sub(r"[^a-z0-9]+", "", h.lower())


def parse_time(v) -> float:
    s = str(v).strip().lower().replace("min", ":").replace("sec", "")
    if ":" in s:
        parts = [float(x) if x else 0.0 for x in s.split(":")]
        t = 0.0
        for x in parts:
            t = t * 60 + x
        return t
    return float(s)


def _stats(pairs) -> dict:
    """pairs: list of (model, human)."""
    n = len(pairs)
    if not n:
        return {"n": 0, "bias": None, "mae": None}
    d = [m - h for m, h in pairs]
    return {"n": n, "bias": sum(d) / n, "mae": sum(abs(x) for x in d) / n}


def human_agreement(pairs) -> dict:
    n = len(pairs)
    if not n:
        return {"n": 0}
    d = [a - b for a, b in pairs]
    return {"n": n, "exact_agreement": sum(1 for x in d if x == 0) / n, "bias_a_minus_b": sum(d) / n,
            "mae": sum(abs(x) for x in d) / n}


def _cols(header):
    return {_norm(h): h for h in header}


def _find(cols, *names):
    for n in names:
        if _norm(n) in cols:
            return cols[_norm(n)]
    return None


def _num(v):
    try:
        return float(v) if str(v).strip() != "" else None
    except ValueError:
        return None


def evaluate(results_paths, labels_csv) -> dict:
    if isinstance(results_paths, (str, Path)):
        results_paths = [results_paths]
    results = [json.loads(Path(p).read_text(encoding="utf-8")) for p in results_paths]
    with open(labels_csv, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        rows, header = list(rd), rd.fieldnames or []
    cols = _cols(header)
    if _find(cols, "total fish count", "total fish count a", "totalfish", "fish_count") and \
            _find(cols, "timestamp", "time", "timestamp_s", "time_s"):
        return _eval_subsamples(results, rows, cols)
    return _eval_segments(results, rows, cols)


def _pick_result(results, vid):
    if vid:
        for r in results:
            if vid in (r["recording"].get("video_id"), r["recording"]["recording_id"]):
                return r
        return None
    return results[0] if len(results) == 1 else None


def _eval_subsamples(results, rows, cols):
    c_vid = _find(cols, "video id", "video_id", "recording_id")
    c_t = _find(cols, "timestamp", "timestamp_s", "time", "time_s")
    c_a = _find(cols, "total fish count a", "total fish count", "total_fish_count", "fish_count")
    c_b = _find(cols, "total fish count b")
    out_rows, pairs, hh, missing, unmatched = [], [], [], 0, 0
    for row in rows:
        res = _pick_result(results, row.get(c_vid) if c_vid else None)
        human = _num(row.get(c_a))
        if res is None or human is None:
            unmatched += 1
            continue
        t = parse_time(row[c_t])
        half = res["protocol"]["interval_s"] / 2
        ss = min(res["subsamples"], key=lambda x: abs(x["t_s"] - t), default=None)
        if ss is None or abs(ss["t_s"] - t) > half:
            unmatched += 1
            continue
        model = ss["auto"]["fish_count"]
        hb = _num(row.get(c_b)) if c_b else None
        if hb is not None:
            hh.append((human, hb))
        if model is None:
            missing += 1
        else:
            pairs.append((model, human))
        out_rows.append({"video_id": row.get(c_vid, ""), "timestamp_s": t, "subsample_id": ss["subsample_id"],
                         "human": human, "human_b": hb, "model": model,
                         "diff": None if model is None else model - human})
    return _report("subsample", pairs, out_rows, missing, unmatched, hh, results)


def _eval_segments(results, rows, cols):
    c_rec = _find(cols, "recording_id", "video id", "video_id")
    c_seg = _find(cols, "segment_id", "segment")
    c_s, c_e = _find(cols, "start_s", "start"), _find(cols, "end_s", "end")
    c_maxn = _find(cols, "maxn", "maxn_a")
    c_maxn_b = _find(cols, "maxn_b")
    c_cnt = _find(cols, "count", "count_a")
    c_cnt_b = _find(cols, "count_b")
    if not c_maxn and not c_cnt:
        raise ValueError("Labels CSV needs maxn/count columns, or Video ID + Timestamp + Total Fish Count.")
    pairs_m, pairs_c, hh, out_rows, missing, unmatched = [], [], [], [], 0, 0
    for row in rows:
        res = _pick_result(results, row.get(c_rec) if c_rec else None)
        if res is None:
            unmatched += 1
            continue
        seg = None
        if c_seg and row.get(c_seg):
            seg = next((s for s in res["segments"] if s["segment_id"] == row[c_seg]), None)
        elif c_s and c_e and row.get(c_s):
            a, b = parse_time(row[c_s]), parse_time(row[c_e])
            seg = max(res["segments"], key=lambda s: min(b, s["end_s"]) - max(a, s["start_s"]), default=None)
            if seg and min(b, seg["end_s"]) - max(a, seg["start_s"]) <= 0:
                seg = None
        if seg is None:
            unmatched += 1
            continue
        r = {"segment_id": seg["segment_id"]}
        for name, col, colb, key, bucket in (("maxn", c_maxn, c_maxn_b, "maxn", pairs_m),
                                             ("count", c_cnt, c_cnt_b, "unique_tracks", pairs_c)):
            h = _num(row.get(col)) if col else None
            if h is None:
                continue
            m = seg["counts"][key]
            hb = _num(row.get(colb)) if colb else None
            if hb is not None:
                hh.append((h, hb))
            if m is None:
                missing += 1
            else:
                bucket.append((m, h))
            r.update({f"human_{name}": h, f"model_{name}": m, f"diff_{name}": None if m is None else m - h})
        out_rows.append(r)
    rep = _report("segment", pairs_m + pairs_c, out_rows, missing, unmatched, hh, results)
    rep["maxn"], rep["count_vs_unique_tracks"] = _stats(pairs_m), _stats(pairs_c)
    return rep


def _report(kind, pairs, rows, missing, unmatched, hh, results):
    rep = {"kind": kind, "model": _stats(pairs), "rows": rows, "n_model_missing": missing,
           "n_unmatched_label_rows": unmatched, "human_vs_human": human_agreement(hh) if hh else None,
           "detector_sources": sorted({d.get("source", "") for r in results for s in r["subsamples"]
                                       for d in s["auto"]["detections"]}),
           "notes": []}
    if len(pairs) < SMALL_N:
        rep["notes"].append(f"Small sample: only {len(pairs)} compared rows (under {SMALL_N}). "
                            "Bias and MAE are very uncertain. Do not read them as accuracy.")
    if "motion_blob" in rep["detector_sources"]:
        rep["notes"].append("Detections came from the motion_blob stand-in, not a model. This is a pipeline check only.")
    if missing:
        rep["notes"].append(f"{missing} rows skipped because the model value was not computed (null).")
    return rep


def format_report(rep: dict) -> str:
    m = rep["model"]
    lines = [f"Evaluation ({rep['kind']} rows)", f"  compared rows: {m['n']}"]
    if m["n"]:
        lines += [f"  signed bias (model - human): {m['bias']:+.3f}", f"  MAE: {m['mae']:.3f}"]
    for k in ("maxn", "count_vs_unique_tracks"):
        if k in rep and rep[k]["n"]:
            lines.append(f"  {k}: n={rep[k]['n']} bias={rep[k]['bias']:+.3f} MAE={rep[k]['mae']:.3f}")
    if rep["human_vs_human"]:
        h = rep["human_vs_human"]
        lines.append(f"  human vs human: n={h['n']} exact agreement={h['exact_agreement']:.0%} "
                     f"bias(a-b)={h['bias_a_minus_b']:+.3f} MAE={h['mae']:.3f}")
    lines.append(f"  unmatched label rows: {rep['n_unmatched_label_rows']}")
    lines += [f"  NOTE: {n}" for n in rep["notes"]]
    return "\n".join(lines)
