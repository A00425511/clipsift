"""Quality control helpers for double counts."""
from __future__ import annotations


def percent_difference(a: float, b: float) -> float:
    """Percent difference between two counts of the same subsample.

    NOTE: the protocol PDF says the difference should be under 6% but the formula
    is missing from the draft. This uses |a - b| / mean(a, b) * 100 as a PLACEHOLDER
    (0 when both are 0). Replace it once Coastal Action confirms their formula.
    """
    m = (a + b) / 2.0
    return 0.0 if m == 0 else abs(a - b) / m * 100.0


def qc_flags(pct_diff: float, pc: dict) -> dict:
    """recount: difference above qc_max_percent_diff. reannotate_warning: agreement below qc_agreement.
    Agreement here is 100 minus percent difference, which is also an assumption."""
    return {"recount": pct_diff > pc["qc_max_percent_diff"],
            "reannotate_warning": (100.0 - pct_diff) < pc["qc_agreement"]}
