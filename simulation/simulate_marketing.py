"""Clearly-labeled simulated marketing layer (Day 3 — PREVIEW scope).

Per `docs/data-feasibility.md` §4 and AGENTS.md §2: Olist contains NO real
marketing treatment data, so we build a *synthetic* exposure layer on top of
the real customer backbone (94,983 real Olist customers with real RFM /
category / tenure features). EVERY column this module emits is prefixed
``sim_`` and is a SIMULATION — never an observed Olist fact.

Preview scope (Day 3):
  * one campaign snapshot (no per-campaign date grid yet — that lands in
    Week 2 when the analysis dataset is finalized)
  * targeting rule per channel: logistic(intercept + coefs * z(features) + u_coef * U)
  * latent intent U ~ N(0, u_std) drives BOTH assignment and conversion =>
    confounding is built in by design (this powers Days 5-7 estimators and
    the Day-18 sensitivity analysis)
  * outcome: purchase within the `outcome_window_days` window after the
    campaign; revenue lognormal when converted
  * embedded ground-truth effects per channel (from data-feasibility §4)

Usage:
    python -m simulation.simulate_marketing
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import expit

from src.config import load_config, project_path

FEATURE_COLS = (
    "recency_days",
    "tenure_days",
    "order_count",
    "total_revenue",
    "avg_order_value",
    "review_score_avg",
)
CHANNELS = ("email", "social", "search", "display")


def load_backbone() -> pd.DataFrame:
    """Real customer backbone (observed Olist facts, no sim_* columns)."""
    cfg = load_config()
    path = project_path(cfg["paths"]["processed_data"]) / "customer_analytical.parquet"
    return pd.read_parquet(path)


def build_sim_preview(backbone: pd.DataFrame | None = None, seed: int | None = None) -> pd.DataFrame:
    """Generate the simulated marketing preview (single campaign snapshot).

    Args:
        backbone: real customer table (default: loaded from processed parquet).
        seed: RNG seed (default: config ``seed``).

    Returns:
        A copy of the backbone plus sim_* columns (see module docstring).
        The returned frame is written to data/simulated/sim_preview.parquet
        by the CLI entry point, NOT here (module stays side-effect-free).
    """
    cfg = load_config()
    sp = cfg["simulation"]["preview"]
    if backbone is None:
        backbone = load_backbone()
    df = backbone.copy()

    rng = np.random.default_rng(seed if seed is not None else int(cfg["seed"]))

    # --- standardized feature matrix (z-scores computed on the real data) ---
    feats = df[list(FEATURE_COLS)].astype(float)
    z = (feats - feats.mean()) / feats.std().replace(0, 1.0)

    # --- latent intent U: affects assignment AND outcome (by design) ---
    sim_u = rng.normal(0.0, float(sp["u_std"]), size=len(df))
    df["sim_u"] = np.round(sim_u, 6)

    # --- per-channel targeting + exposure ---
    for ch in CHANNELS:
        c = sp["channels"][ch]
        score = float(c["assignment_intercept"])
        for feat, w in c["assignment_coefs"].items():
            score += float(w) * z[feat]
        score += float(sp["u_assignment_coef"]) * sim_u
        p_exp = expit(score)
        df[f"sim_p_{ch}"] = np.round(p_exp, 6)
        df[f"sim_exposed_{ch}"] = (rng.random(len(df)) < p_exp).astype(int)

    # --- outcome: purchase within window + follow-on revenue ---
    logit_y = float(sp["base_outcome_intercept"])
    # real features also shape baseline intent (this is WHY adjustment matters:
    # exposed customers are already higher-intent on observable features)
    for feat in FEATURE_COLS:
        logit_y = logit_y + 0.05 * z[feat]
    logit_y = logit_y + float(sp["u_outcome_coef"]) * sim_u
    for ch in CHANNELS:
        ground_truth = float(sp["channels"][ch]["effect_log_odds"])
        df[f"sim_ground_truth_{ch}"] = ground_truth
        logit_y = logit_y + ground_truth * df[f"sim_exposed_{ch}"].values

    p_y = expit(logit_y)
    df["sim_converted_14d"] = (rng.random(len(df)) < p_y).astype(int)

    rev = np.where(
        df["sim_converted_14d"] == 1,
        rng.lognormal(float(sp["revenue_log_mean"]), float(sp["revenue_log_sigma"]), size=len(df)),
        0.0,
    )
    df["sim_revenue_14d"] = np.round(rev, 2)
    return df


def channel_descriptive_stats(sim: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Channel descriptive stats for the SIMULATED preview.

    Everything here is simulated (sim_* columns). The conversion-by-exposure
    table is a *naive descriptive* comparison — it is NOT a causal effect
    (confounding by design). Causal estimates come from Days 5-12.
    """
    tabs: dict[str, pd.DataFrame] = {}

    # exposure rates
    tabs["exposure_rate"] = (
        pd.DataFrame(
            {
                "channel": CHANNELS,
                "pct_exposed": [round(100 * sim[f"sim_exposed_{c}"].mean(), 2) for c in CHANNELS],
                "n_exposed": [int(sim[f"sim_exposed_{c}"].sum()) for c in CHANNELS],
            }
        )
    )

    # correlation of exposures (pairwise channel overlap proxy)
    corr = np.corrcoef([sim[f"sim_exposed_{c}"] for c in CHANNELS])
    tabs["exposure_overlap_corr"] = pd.DataFrame(
        corr, index=list(CHANNELS), columns=list(CHANNELS)
    ).round(3)

    # naive conversion by exposure (descriptive only)
    rows = []
    for c in CHANNELS:
        ex = sim[f"sim_exposed_{c}"] == 1
        rows.append(
            {
                "channel": c,
                "conv_exposed_pct": round(100 * sim.loc[ex, "sim_converted_14d"].mean(), 2),
                "conv_unexposed_pct": round(100 * sim.loc[~ex, "sim_converted_14d"].mean(), 2),
                "conv_diff_pp": round(
                    100 * (sim.loc[ex, "sim_converted_14d"].mean() - sim.loc[~ex, "sim_converted_14d"].mean()),
                    2,
                ),
            }
        )
    tabs["naive_conversion"] = pd.DataFrame(rows)
    return tabs


# --- CLI ---------------------------------------------------------------------

def main() -> int:
    sim = build_sim_preview()
    cfg = load_config()
    out_dir = project_path(cfg["paths"]["simulated_data"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "sim_preview.parquet"
    sim.to_parquet(out, index=False)
    stats = channel_descriptive_stats(sim)
    print(f"wrote {len(sim):,} x {sim.shape[1]} cols -> {out}")
    print("\n[sim preview] exposure rates (% exposed):\n", stats["exposure_rate"].to_string(index=False))
    print("\n[sim preview] naive conversion by exposure (descriptive ONLY, not causal):\n",
          stats["naive_conversion"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())