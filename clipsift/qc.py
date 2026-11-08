"""Quality control: compare blind counts of the same frame and say what to do next.

The protocol asks for 6 to 12 random frames per video, counted blind by a second person. The two
counts are averaged, should differ by less than 6%, and a frame outside that is recounted, preferably
by someone else. Below 95% agreement the video is re-annotated.

ASSUMPTIONS, all waiting on Coastal Action. The PDF leaves out the percent difference formula and does
not define agreement. Percent difference is |a - b| / mean(a, b) * 100. Agreement is 100 minus the mean
percent difference. Fish and invertebrates are checked separately, because the protocol says "all count
estimates".

The numbers are always shown, but they never hold anyone up. On frames with few animals a one-fish gap is
already far over 6%, so a frame is only flagged when it is over the limit AND differs by more than small_gap.
A recount is a suggestion. The team decides whether to do one.
"""
from __future__ import annotations

from itertools import combinations

SMALL_GAP = 1   # a difference of this many animals or fewer is never flagged. Setting: protocol.qc_small_gap


def percent_difference(a, b):
    """Percent difference between two counts of one frame. 0 when both are 0, None if one is missing."""
    if a is None or b is None:
        return None
    m = (a + b) / 2.0
    return 0.0 if m == 0 else abs(a - b) / m * 100.0


def qc_flags(pct_diff: float, pc: dict) -> dict:
    """recount: difference above qc_max_percent_diff. reannotate_warning: agreement below qc_agreement."""
    return {"recount": pct_diff > pc["qc_max_percent_diff"],
            "reannotate_warning": (100.0 - pct_diff) < pc["qc_agreement"]}


def _fish(row) -> int:
    return row.get("total_fish_count") or 0


def _inv(row) -> int:
    return row.get("invertebrate_count") or 0


def compare_rows(a: dict, b: dict) -> dict:
    fish, inv = percent_difference(_fish(a), _fish(b)), percent_difference(_inv(a), _inv(b))
    return {"fish_diff": fish, "inv_diff": inv, "percent_diff": max(fish, inv)}


def assess_point(rows: list, limit: float, small_gap: int = SMALL_GAP) -> dict:
    """rows: every count of one frame, first count first. The closest pair decides, so a recount that
    agrees with either earlier count settles the frame. Its two counts are averaged, as the protocol says."""
    best = None
    for i, j in combinations(range(len(rows)), 2):
        c = compare_rows(rows[i], rows[j])
        if best is None or c["percent_diff"] <= best[0]["percent_diff"]:
            best = (c, rows[i], rows[j])
    c, a, b = best
    gap = max(abs(_fish(a) - _fish(b)), abs(_inv(a) - _inv(b)))
    over = c["percent_diff"] > limit
    every = [{"counter": r.get("counter"), "fish": _fish(r), "inv": _inv(r)} for r in rows]
    return {**c, "gap": gap, "small_gap": over and gap <= small_gap, "counts": every,
            "has_animals": any(x["fish"] or x["inv"] for x in every),
            "all_average_fish": sum(x["fish"] for x in every) / len(every), "first_counter": a.get("counter"), "second_counter": b.get("counter"),
            "first_fish": _fish(a), "second_fish": _fish(b), "first_inv": _inv(a), "second_inv": _inv(b),
            "first_total": _fish(a) + _inv(a), "second_total": _fish(b) + _inv(b),
            "average_fish": (_fish(a) + _fish(b)) / 2, "average_inv": (_inv(a) + _inv(b)) / 2,
            "n_counts": len(rows), "counters": [r.get("counter") for r in rows],
            "recount_needed": over and gap > small_gap}


def verdict(sample: list, primary_ids, points: dict, limit: float, target: float) -> dict:
    """What the app suggests. status: no_sample, counting, waiting_second, review or pass. review never blocks anything."""
    done = [sid for sid in sample if sid in points]
    diffs = [points[sid]["percent_diff"] for sid in done]
    agreement = round(max(0.0, 100 - sum(diffs) / len(diffs)), 1) if diffs else None
    recount = [sid for sid in done if points[sid]["recount_needed"]]
    # Two empty counts score 100%, so a mostly empty sample can hide the one frame that matters.
    animal = [points[sid]["percent_diff"] for sid in done if points[sid].get("has_animals")]
    animal_agreement = round(max(0.0, 100 - sum(animal) / len(animal)), 1) if animal else None
    out = {"sample": list(sample), "n_sample": len(sample), "n_done": len(done), "recount": recount,
           "n_within": len(done) - len(recount), "agreement": agreement, "limit": limit, "target": target,
           "n_animal_frames": len(animal), "animal_agreement": animal_agreement}
    if not sample:
        status = "no_sample"
    elif any(sid not in primary_ids for sid in sample):
        status = "counting"
    elif len(done) < len(sample):
        status = "waiting_second"
    elif recount:
        status = "review"
    else:
        status = "pass"
    return {**out, "status": status}


def interrater(videos: list, limit: float) -> dict:
    """Agreement between each pair of people, across every video. videos: a list of lists of count rows."""
    pairs, people = {}, {}
    for rows in videos:
        by_point = {}
        for r in rows:
            who = r.get("counter")
            if who:
                by_point.setdefault(r.get("subsample_id"), {})[who] = r   # the latest row per person
                people.setdefault(who, {"name": who, "frames": 0})
        for counts in by_point.values():
            for who in counts:
                people[who]["frames"] += 1
            for a, b in combinations(sorted(counts), 2):
                row = pairs.setdefault((a, b), {"a": a, "b": b, "frames": 0, "within": 0, "diff_sum": 0.0, "signed_sum": 0})
                c = compare_rows(counts[a], counts[b])
                row["frames"] += 1
                row["within"] += c["percent_diff"] <= limit
                row["diff_sum"] += c["percent_diff"]
                row["signed_sum"] += _fish(counts[a]) - _fish(counts[b])
    out = []
    for row in pairs.values():
        n = row["frames"]
        out.append({"a": row["a"], "b": row["b"], "frames": n, "within": row["within"],
                    "mean_percent_diff": round(row["diff_sum"] / n, 1),
                    "mean_fish_gap": round(row["signed_sum"] / n, 2)})   # above 0: a counts more fish than b
    return {"pairs": sorted(out, key=lambda r: (-r["frames"], r["a"], r["b"])),
            "people": sorted(people.values(), key=lambda r: r["name"]), "limit": limit}
