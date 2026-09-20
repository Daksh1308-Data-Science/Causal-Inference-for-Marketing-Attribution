"""RFM segmentation for the analytical cohort (Day 3).

Implements a *score-band* RFM (R/F/M each 1-5) tuned to this dataset's
documented reality: ~94% of Olist customers are one-time buyers
(docs/data-feasibility.md §2), so frequency CANNOT be quantile-binned
(identity would dominate). We therefore use:

* R (recency):  quantile bands of `recency_days` (5 = most recent)
* F (frequency): explicit bands 1 / 2 / 3-4 / 5-9 / 10+ orders
                  (quantiles would collapse: P(F=1) ~= 0.94)
* M (monetary):  quantile bands of `total_revenue` (5 = highest spend)

Segment labels follow a documented mapping (champions / loyal / new /
at-risk / lost). This is a *descriptive* segmentation of observed data —
it feeds the confounder audit (Day 4) and confounds the simulated
marketing layer (Days 5+), where targeting will rekey off these tiers.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FREQUENCY_BANDS = pd.CategoricalDtype(
    categories=["1", "2", "3-4", "5-9", "10+"], ordered=True
)

# segment label -> (condition on R, F, M scores)  [first match wins]
_SEGMENT_RULES = [
    ("champions", lambda r, f, m: r >= 4 and f >= 4),
    ("loyal", lambda r, f, m: r >= 3 and f >= 3),
    ("big_spender", lambda r, f, m: m >= 5 and r >= 3),
    ("new_customer", lambda r, f, m: r >= 4 and f <= 2),
    ("potential", lambda r, f, m: r >= 3 and f == 3),
    ("at_risk", lambda r, f, m: r == 3 and f >= 2),
    ("one_time_lapsed", lambda r, f, m: f == 1 and r <= 2),
    ("lapsed", lambda r, f, m: True),  # catch-all
]


def _quantile_score(s: pd.Series, ascending: bool = True) -> pd.Series:
    """Map a series to 1-5 scores by quantile bands.

    With ``ascending=True`` the biggest values get 5; with ``False`` the
    smallest (e.g. smallest recency = most recent) get 5. Ties at a quantile
    boundary are handled by rank-based ties (average), then np.ceil.
    """
    if ascending:
        pct = s.rank(pct=True)
    else:
        # invert so the smallest original value gets the largest pct
        pct = (s.max() - s).rank(pct=True)
    return np.ceil(pct * 5).astype(int).clip(1, 5)


def add_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """Append R/F/M scores, composite `rfm_score`, and `rfm_segment`.

    Expects columns: recency_days, order_count, total_revenue.
    Returns a copy with the new columns; input frame is untouched.
    """
    out = df.copy()

    r = _quantile_score(out["recency_days"], ascending=False)  # recent -> 5
    f = pd.cut(
        out["order_count"], bins=[0, 1, 2, 4, 9, np.inf], labels=["1", "2", "3-4", "5-9", "10+"],
    ).astype("str")
    f_score = f.map({"1": 1, "2": 2, "3-4": 3, "5-9": 4, "10+": 5})
    m = _quantile_score(out["total_revenue"], ascending=True)  # biggest spend -> 5

    out["rfm_R"] = r
    out["rfm_F"] = f_score
    out["rfm_M"] = m

    segments = []
    for rr, ff, mm in zip(r, f_score, m):
        for label, cond in _SEGMENT_RULES:
            if cond(rr, ff, mm):
                segments.append(label)
                break
    out["rfm_segment"] = segments
    out["rfm_score"] = 100 * r + 10 * f_score + m
    return out


def segment_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Size + mean metrics per RFM segment (observed descriptive facts)."""
    g = (
        df.groupby("rfm_segment", observed=True)
        .agg(
            n_customers=("customer_id", "size"),
            total_revenue=("total_revenue", "sum"),
            avg_revenue=("total_revenue", "mean"),
            avg_order_count=("order_count", "mean"),
            avg_recency_days=("recency_days", "mean"),
        )
        .sort_values("n_customers", ascending=False)
        .reset_index()
    )
    g["share_pct"] = (100 * g["n_customers"] / len(df)).round(2)
    for col in ("total_revenue", "avg_revenue", "avg_order_count", "avg_recency_days"):
        g[col] = g[col].round(2)
    return g