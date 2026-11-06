"""CSV export: one row per subsample, a per-video summary, a segments table, and a column dictionary.

Reads results.json plus (if present) subsample_reviews.jsonl, reviews.jsonl, recording_notes.jsonl.
Counts are a relative index of what was seen in the designated windows, not abundance.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .qc import percent_difference, qc_flags


def read_jsonl(path) -> list:
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # a half-written last line should not stop an export
    return out


def mmss(t: float) -> str:
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


SUBSAMPLE_COLS = [
    ("Video ID", "Video ID as in the Coastal Action spreadsheet (guessed from the file name unless set)."),
    ("Subsample ID", "ss_NN, order of the point in the analysis window."),
    ("Timestamp (s)", "Seconds from the start of the recording (chapters joined)."),
    ("Timestamp (mm:ss)", "Same time as minutes and seconds."),
    ("Total Fish Count", "Reviewed count (latest primary or recount pass). Blank if not reviewed. A relative index, not abundance."),
    ("Invertebrate Count", "Reviewed invertebrate count (crabs, shrimp, worms, snails). Blank if not reviewed."),
    ("Total Species", "Number of species the counter recorded."),
    ("Species Counts", "JSON of individuals per species."),
    ("Unknown/Unable to ID due to visibility", "Animals counted but not identifiable."),
    ("Visibility Category", "<0.5 m, 0.5-1.0 m, 1.0-1.5 m or >1.5 m, as recorded by the counter."),
    ("Visibility Change (>=0.5 m)", "Whether visibility changed by 0.5 m or more."),
    ("Notes", "Counter notes."),
    ("Counter", "Who made the reviewed count."),
    ("QC Sample", "True if this point is in the random quality-control sample."),
    ("QC Second Count (fish)", "Blind second counter's fish count, if recorded."),
    ("QC Percent Difference", "Placeholder formula |a-b|/mean(a,b)*100. The protocol PDF does not give its formula."),
    ("QC Recount Needed", "True if percent difference is above the configured limit."),
    ("Auto Fish Count (suggestion)", "Model or stand-in suggestion. Never a final count. Blank means not computed. If the detector is the motion_blob stand-in this is a moving-blob count, not a fish count."),
    ("Auto Invertebrate Count (suggestion)", "Model suggestion, usually blank."),
    ("Auto Detector Source", "Which backend made the suggestion, for example motion_blob or onnx:file."),
    ("Motion Near Point", "Quick pass saw movement within the count window plus tolerance."),
    ("Movement Unidentified", "Number of movement events in the context window. A note only, not counted."),
]


def _latest(reviews, sid, passes):
    rs = [r for r in reviews if r.get("subsample_id") == sid and r.get("pass") in passes]
    return rs[-1] if rs else None


def export_run(run_dir, out_dir=None) -> list:
    run_dir = Path(run_dir)
    res = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    out_dir = Path(out_dir) if out_dir else run_dir / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    rid = res["recording"]["recording_id"]
    vid = res["recording"].get("video_id") or rid
    pc = res["protocol"]
    sreviews = read_jsonl(run_dir / "subsample_reviews.jsonl")
    seg_reviews = read_jsonl(run_dir / "reviews.jsonl")
    notes = read_jsonl(run_dir / "recording_notes.jsonl")

    rows = []
    for ss in res["subsamples"]:
        sid = ss["subsample_id"]
        fin = _latest(sreviews, sid, ("primary", "recount"))
        qcb = _latest(sreviews, sid, ("qc_blind",))
        a = ss["auto"]
        pct = None
        if fin and qcb:
            pct = percent_difference(fin["total_fish_count"], qcb["total_fish_count"])
        src = sorted({d.get("source", "") for d in a.get("detections", [])})
        sc = (fin or {}).get("species_counts") or {}
        rows.append({
            "Video ID": vid, "Subsample ID": sid, "Timestamp (s)": ss["t_s"], "Timestamp (mm:ss)": mmss(ss["t_s"]),
            "Total Fish Count": fin["total_fish_count"] if fin else "",
            "Invertebrate Count": fin.get("invertebrate_count", "") if fin else "",
            "Total Species": fin.get("total_species", len(sc)) if fin else "",
            "Species Counts": json.dumps(sc) if fin else "",
            "Unknown/Unable to ID due to visibility": fin.get("unknown_count", "") if fin else "",
            "Visibility Category": (fin or {}).get("visibility_category") or "",
            "Visibility Change (>=0.5 m)": "" if not fin or fin.get("visibility_change") is None else fin["visibility_change"],
            "Notes": (fin or {}).get("notes", ""), "Counter": (fin or {}).get("counter", ""),
            "QC Sample": ss["qc_sample"],
            "QC Second Count (fish)": qcb["total_fish_count"] if qcb else "",
            "QC Percent Difference": round(pct, 2) if pct is not None else "",
            "QC Recount Needed": qc_flags(pct, pc)["recount"] if pct is not None else "",
            "Auto Fish Count (suggestion)": "" if a["fish_count"] is None else a["fish_count"],
            "Auto Invertebrate Count (suggestion)": "" if a["invertebrate_count"] is None else a["invertebrate_count"],
            "Auto Detector Source": ";".join(src), "Motion Near Point": a["motion_near_point"],
            "Movement Unidentified": a["movement_unidentified"],
        })
    cols = [c for c, _ in SUBSAMPLE_COLS]
    p_sub = out_dir / f"{rid}_subsamples.csv"
    _write_csv(p_sub, cols, rows)

    # per-video summary
    rev = [r["Total Fish Count"] for r in rows if r["Total Fish Count"] != ""]
    auto = [r["Auto Fish Count (suggestion)"] for r in rows if r["Auto Fish Count (suggestion)"] != ""]
    species = set()
    for r in rows:
        if r["Species Counts"]:
            species |= set(json.loads(r["Species Counts"]))
    juv = ""
    for n in notes:
        species |= set([n["species_observed"]] if isinstance(n.get("species_observed"), str) else n.get("species_observed", []))
        if "juveniles_present" in n:
            juv = n["juveniles_present"]
    pcts = [r["QC Percent Difference"] for r in rows if r["QC Percent Difference"] != ""]
    summ = [{
        "Video ID": vid, "Recording": rid, "Transect": res["recording"].get("transect") or "",
        "STAT": res["recording"].get("stat") or "", "Year": res["recording"].get("year") or "",
        "Season": res["recording"].get("season") or "",
        "Window Start (s)": pc["window_start_s"], "Window End (s)": pc["window_end_s"],
        "Subsamples": len(rows), "Subsamples Reviewed": len(rev),
        "MeanCount (reviewed)": round(sum(rev) / len(rev), 3) if rev else "",
        "MeanCount (auto suggestion)": round(sum(auto) / len(auto), 3) if auto else "",
        "Species Observed": "; ".join(sorted(species)), "Juveniles Present": juv,
        "QC Pairs": len(pcts), "QC Mean Percent Difference": round(sum(pcts) / len(pcts), 2) if pcts else "",
    }]
    p_sum = out_dir / f"{rid}_video_summary.csv"
    _write_csv(p_sum, list(summ[0]), summ)

    # segments (supporting pass)
    seg_rows = []
    for s in res["segments"]:
        rs = [r for r in seg_reviews if r.get("segment_id") == s["segment_id"]]
        last = rs[-1] if rs else {}
        c = s["counts"]
        seg_rows.append({
            "recording_id": rid, "segment_id": s["segment_id"], "start_s": s["start_s"], "end_s": s["end_s"],
            "duration_s": round(s["end_s"] - s["start_s"], 3), "kind": s["kind"], "audit_sample": s["audit_sample"],
            "status": s["status"], "motion_score": s["motion_score"], "visibility_score": s["visibility_score"],
            "shake": s["flags"]["shake"], "low_visibility": s["flags"]["low_visibility"],
            "maxn": "" if c["maxn"] is None else c["maxn"], "mean_count": "" if c["mean_count"] is None else c["mean_count"],
            "unique_tracks": "" if c["unique_tracks"] is None else c["unique_tracks"],
            "n_detections": len(s["detections"]),
            "detection_sources": ";".join(sorted({d["source"] for d in s["detections"]})),
            "review_priority": s["review_priority"], "n_reviews": len(rs),
            "review_decision": last.get("decision", ""), "review_species": last.get("species") or "",
            "review_count": "" if last.get("count") is None else last.get("count"),
            "review_note": last.get("note", ""), "reviewer": last.get("reviewer", ""), "reviewed_at": last.get("at", "")})
    p_seg = out_dir / f"{rid}_segments.csv"
    _write_csv(p_seg, list(seg_rows[0]) if seg_rows else ["recording_id"], seg_rows)

    p_doc = out_dir / f"{rid}_columns.md"
    with open(p_doc, "w", encoding="utf-8") as f:
        f.write("# Column dictionary\n\n")
        f.write("IMPORTANT: counts are relative indices of what was visible in the designated count windows. "
                "They are not abundance or density.\n\n")
        f.write("Auto columns are suggestions from software. A person makes the final count. "
                "If the detector is the motion_blob stand-in, auto values are moving-blob counts, not model results.\n\n")
        f.write(f"## {p_sub.name}\n\n")
        for c, d in SUBSAMPLE_COLS:
            f.write(f"- **{c}**: {d}\n")
        f.write(f"\n## {p_sum.name}\n\nOne row per video: MeanCount is the mean of Total Fish Count over reviewed subsamples. "
                "Species Observed comes from reviews and recording_notes.jsonl.\n")
        f.write(f"\n## {p_seg.name}\n\nSupporting motion-scan segments (maxn, mean_count and unique_tracks are "
                "relative indices; blank means not computed). Merged with reviews.jsonl (latest decision per segment).\n")
    return [p_sub, p_sum, p_seg, p_doc]


def _write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
