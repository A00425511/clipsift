"""One summary of a video's counts, used by the app, its CSVs and the command line export, so they always agree.

MeanCount, every blind comparison and the quality check result all come from here. See qc.py for the rules
and their assumptions.
"""
from __future__ import annotations

from . import protocol as proto
from . import qc as qcm

QC_DEFAULTS = {"qc_max_percent_diff": 6, "qc_agreement": 95, "qc_small_gap": 1, "qc_share": 0.10, "qc_min": 6, "qc_max": 12, "qc_seed": 4321}


def qc_sample_ids(results: dict) -> list:
    """The frames picked for the blind check. Runs made before the pick was recorded get one now."""
    subs = sorted([x for x in results.get("subsamples") or [] if isinstance(x, dict)], key=lambda x: x.get("t_s") or 0)
    marked = [x["subsample_id"] for x in subs if x.get("qc_sample")]
    if marked:
        return marked
    pc = {**QC_DEFAULTS, **(results.get("protocol") or {})}
    picks = proto.pick_qc(len(subs), pc, (results.get("recording") or {}).get("recording_id") or "")
    return [x["subsample_id"] for i, x in enumerate(subs) if i in picks]


def summarise(results: dict, sub_reviews: list) -> dict:
    """Latest first count per point, every blind comparison, the quality check result, and MeanCount."""
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
