"""Doubly robust AIPW estimation per channel (Day 11).

Augmented inverse-probability weighting combines the Day-6 propensity model
with outcome regressions Mu1(X), Mu0(X):

    ATE = 1/n sum [ T(Y - Mu1(X))/p(X) + Mu1(X) ]
        - 1/n sum [ (1-T)(Y - Mu0(X))/(1-p(X)) + Mu0(X) ]

The estimator stays consistent if EITHER the propensity model OR the outcome
regressions are correctly specified (double robustness). SE/CI come from the
influence-function variance, the standard root-n asymptotic for AIPW:
    IF_i = T(Y-Mu1)/p + Mu1 - m1bar  -  [ (1-T)(Y-Mu0)/(1-p) + Mu0 - m0bar ]
    SE = sd(IF) / sqrt(n)

Labels (AGENTS.md §2): every number is a SIMULATED estimate. ``sim_u`` is
unobserved, so both models are fit on observed confounders only and the AIPW
estimate remains biased toward the naive gap a priori (quantified Day 12/18).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import statsmodels.api as sm
from scipy import stats

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS, adjustment_sets
from src.causal.naive import OUTCOMES, OUTCOME_LABELS, load_analysis_data, naive_estimates_table
from src.causal.propensity import estimate_propensity_scores
from src.causal.regression import ols_estimates_table


def _outcome_model(df: pd.DataFrame, confounders: list[str], outcome: str,
                   treated: bool, treatment_col: str):
    """Fit outcome regression on the treated/control subset.

    Binary outcome -> statsmodels Logit (probabilities); continuous -> OLS.
    Covariates are median-imputed and standardized (as in the Day-6 PS model)
    for numerical stability; predictions are invariant to this for OLS and
    effectively so for Logit (constant included).
    Returns a callable predicting E[Y | X] on the full feature matrix.
    """
    from sklearn.preprocessing import StandardScaler

    subset = df[df[treatment_col] == int(treated)].copy()
    medians = subset[confounders].median()
    X_raw = subset[confounders].fillna(medians)
    scaler = StandardScaler()
    X = pd.DataFrame(scaler.fit_transform(X_raw), columns=confounders, index=X_raw.index)
    X = sm.add_constant(X, has_constant="add")
    y = subset[outcome].astype(float)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if y.nunique() <= 2:  # binary outcome -> logistic
            res = sm.Logit(y, X).fit(disp=False, maxiter=200, method="newton")
        else:
            res = sm.OLS(y, X).fit()

    def predict(full_df: pd.DataFrame) -> np.ndarray:
        full_raw = full_df[confounders].fillna(medians)
        z = scaler.transform(full_raw)
        design = sm.add_constant(pd.DataFrame(z, columns=confounders, index=full_raw.index),
                                 has_constant="add")
        return np.asarray(res.predict(design))

    return predict


def _aipw_ate(df: pd.DataFrame, ps: np.ndarray, treatment_col: str,
              outcome: str, confounders: list[str], cap: float | None = 10.0) -> dict:
    """AIPW point estimate + influence-function SE/CI on a working frame.

    Propensity scores are truncated by default to the same Cole-Hernan bound
    used by IPW (Day 10): p in [P(T=1)/cap, 1-(1-P(T=1))/cap]. This prevents
    the (1-T)(Y-mu0)/(1-p) augmentation from exploding for units with p -> 1.
    Pass ``cap=None`` to disable truncation (used by the double-robustness
    property test, which exercises the raw estimator).
    """
    t = df[treatment_col].values.astype(float)
    y = df[outcome].values.astype(float)
    p_treat = t.mean()

    if cap is None:
        lo, hi = 1e-8, 1 - 1e-8
    else:
        lo = p_treat / cap
        hi = 1 - (1 - p_treat) / cap
    p = np.clip(ps, lo, hi)
    n_ps_truncated = int(((ps < lo) | (ps > hi)).sum())

    mu1 = _outcome_model(df, confounders, outcome, True, treatment_col)(df)
    mu0 = _outcome_model(df, confounders, outcome, False, treatment_col)(df)
    mu1, mu0 = np.asarray(mu1, float), np.asarray(mu0, float)

    term1 = t * (y - mu1) / p + mu1
    term0 = (1 - t) * (y - mu0) / (1 - p) + mu0
    ate = float(term1.mean() - term0.mean())

    m1bar, m0bar = term1.mean(), term0.mean()
    if_i = term1 - m1bar - (term0 - m0bar)
    se = float(if_i.std(ddof=1) / np.sqrt(len(df)))
    z = stats.norm.ppf(1 - 0.05 / 2)
    return {"ate": ate, "se": se,
            "ci_lower": ate - z * se, "ci_upper": ate + z * se,
            "n": len(df), "n_ps_truncated": n_ps_truncated,
            "ps_clip": (lo, hi)}


def dr_estimate(df: pd.DataFrame,
                channel: Literal["email", "social", "search", "display"],
                outcome: Literal["sim_converted_14d", "sim_revenue_14d"],
                cfg: dict | None = None) -> dict:
    """AIPW estimate for one channel x outcome (uses Day-6 PS model)."""
    cfg = cfg or load_config()
    treatment_col = f"sim_exposed_{channel}"
    confounders = adjustment_sets(cfg)[channel]
    ps, _, _ = estimate_propensity_scores(df, channel, cfg)
    full = _aipw_ate(df, ps, treatment_col, outcome, confounders,
                     cap=float(cfg["ipw"]["weight_cap"]))
    return {
        "channel": channel,
        "outcome": outcome,
        "outcome_label": OUTCOME_LABELS[outcome],
        "dr_ate": full["ate"],
        "se": full["se"],
        "ci_lower": full["ci_lower"],
        "ci_upper": full["ci_upper"],
        "n": full["n"],
        "n_ps_truncated": full["n_ps_truncated"],
        "ps_clip_lo": full["ps_clip"][0],
        "ps_clip_hi": full["ps_clip"][1],
    }


def dr_estimates_table(cfg: dict | None = None) -> pd.DataFrame:
    """AIPW table merged with naive / OLS / IPW / ground truth."""
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)

    rows = []
    for ch in CHANNELS:
        for outcome in OUTCOMES:
            rows.append(dr_estimate(df, ch, outcome, cfg))

    table = pd.DataFrame(rows)

    naive = naive_estimates_table(cfg)[["channel", "outcome", "diff"]]
    table = table.merge(naive, on=["channel", "outcome"], suffixes=("", "_naive"))
    table = table.merge(
        ols_estimates_table(cfg)[["channel", "outcome", "coef"]],
        on=["channel", "outcome"], suffixes=("", "_ols"))
    ipw = __import__("src.causal.ipw", fromlist=["ipw_estimates_table"]).ipw_estimates_table(cfg)
    table = table.merge(ipw[["channel", "outcome", "ipw_ate"]],
                        on=["channel", "outcome"], suffixes=("", "_ipw"))

    gt = {ch: float(cfg["simulation"]["preview"]["channels"][ch]["effect_log_odds"])
          for ch in CHANNELS}
    table["ground_truth_log_odds"] = table["channel"].map(gt)
    return table


def render_dr_plot(table: pd.DataFrame,
                   outcome: Literal["sim_converted_14d", "sim_revenue_14d"],
                   cfg: dict | None = None,
                   output_dir: Path | None = None) -> tuple[go.Figure, Path]:
    """Bar chart: DR vs IPW vs OLS vs naive for one outcome."""
    cfg = cfg or load_config()
    sub = table[table["outcome"] == outcome].sort_values("channel")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sub["channel"], y=sub["dr_ate"],
        error_y=dict(type="data", symmetric=True,
                     array=(sub["ci_upper"] - sub["dr_ate"]).values,
                     arrayminus=(sub["dr_ate"] - sub["ci_lower"]).values,
                     thickness=1.2),
        marker_color="#f39c12",
        text=[f"{v:.4f}" for v in sub["dr_ate"]],
        textposition="outside",
        name="DR / AIPW",
    ))
    fig.add_trace(go.Bar(x=sub["channel"], y=sub["ipw_ate"],
                         marker_color="#9b59b6", name="IPW (Day 10)", opacity=0.6))
    fig.add_trace(go.Bar(x=sub["channel"], y=sub["coef"],
                         marker_color="#2ecc71", name="OLS (Day 9)", opacity=0.5))
    fig.add_trace(go.Bar(x=sub["channel"], y=sub["diff"],
                         marker_color="#e74c3c", name="Naive (Day 8)", opacity=0.35))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_layout(
        title=f"Doubly robust (AIPW) vs IPW/OLS/naive — {OUTCOME_LABELS[outcome]}",
        title_x=0.5, xaxis_title="Channel",
        yaxis_title=f"Effect ({OUTCOME_LABELS[outcome]})",
        barmode="group", plot_bgcolor="white", height=500)
    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "conversion" if outcome == "sim_converted_14d" else "revenue"
    out_path = output_dir / f"dr_{suffix}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def write_dr_table(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    table = dr_estimates_table(cfg)
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["tables"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dr_estimates.csv"
    table.to_csv(out_path, index=False)
    return out_path


def dr_report(cfg: dict | None = None) -> str:
    """Day-11 report: double-robustness explanation + table + consistency vs OLS/IPW."""
    cfg = cfg or load_config()
    table = dr_estimates_table(cfg)

    lines = []
    lines.append("# Day 11 — Doubly Robust Estimation (AIPW)\n")
    lines.append(
        "> **Label:** SIMULATED estimates (`sim_*`), not observed Olist facts "
        "(AGENTS.md §2).\n"
    )
    lines.append("## Why double robustness\n")
    lines.append(
        "- AIPW blends the Day-6 propensity score with outcome regressions "
        "Mu1(X), Mu0(X): each unit contributes `T(Y-Mu1)/p + Mu1` (treated arm) "
        "and `(1-T)(Y-Mu0)/(1-p) + Mu0` (control arm).\n"
        "- **Doubly robust:** the estimate is consistent if *either* the PS model "
        "*or* the outcome model is correct. If the PS is right, the augmented term "
        "fixes a misspecified outcome regression; if the outcome model is right, "
        "the regression-imputation part dominates and a wrong PS is corrected.\n"
        "- **Efficiency:** AIPW achieves the semiparametric efficiency bound when "
        "both models hold — tighter CIs than plain IPW or OLS for the same data.\n"
    )
    lines.append("## AIPW table (influence-function SE, 95% CI)\n")
    lines.append("| Channel | Outcome | DR ATE | SE | 95% CI | IPW | OLS | Naive | Sim GT |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for _, r in table.iterrows():
        unit = "pp" if r["outcome"] == "sim_converted_14d" else "R$"
        lines.append(
            f"| {r['channel']} | {r['outcome_label']} | {r['dr_ate']:.4f} {unit} "
            f"| {r['se']:.4f} | [{r['ci_lower']:.4f}, {r['ci_upper']:.4f}] "
            f"| {r['ipw_ate']:.4f} {unit} | {r['coef']:.4f} {unit} "
            f"| {r['diff']:.4f} {unit} | {r['ground_truth_log_odds']:+.3f} |"
        )
    lines.append("")
    lines.append("## Validation hook: consistent vs OLS/IPW\n")
    lines.append(
        "Criteria match tests/test_doubly_robust.py: conversion checked on absolute "
        "scale (|DR-IPW|<0.01, |DR-OLS|<0.02), revenue on relative scale (<10%).\n"
    )
    for _, r in table.iterrows():
        d_ipw = abs(r["dr_ate"] - r["ipw_ate"])
        d_ols = abs(r["dr_ate"] - r["coef"])
        if r["outcome"] == "sim_revenue_14d":
            tol_ipw, tol_ols = 0.10 * abs(r["ipw_ate"]), 0.10 * abs(r["coef"])
            scale = "rel"
        else:
            tol_ipw, tol_ols = 0.01, 0.02
            scale = "abs"
        ok = (d_ipw < tol_ipw) and (d_ols < tol_ols)
        status = "OK" if ok else "CHECK"
        lines.append(
            f"- {r['channel']}/{r['outcome_label']}: |DR−IPW|={d_ipw:.4f} "
            f"(< {tol_ipw:.4f} {scale}) |DR−OLS|={d_ols:.4f} "
            f"(< {tol_ols:.4f} {scale}) → {status}"
        )
    lines.append("")
    lines.append("## Limitations\n")
    lines.append(
        "- Both models are fit on the OBSERVED confounders only: `sim_u` remains "
        "unadjusted, so AIPW cannot outrun the design — it should track OLS/IPW "
        "rather than reach the simulated ground truth.\n"
        "- Outcome regressions are linear/logistic; deeper misspecification is "
        "possible (CATE learners, Day 13, use flexible trees instead).\n"
        "- IF-based SE is asymptotic; n ≈ 95k makes it reliable, but it does not "
        "cover PS-outcome-model selection uncertainty.\n"
    )
    return "\n".join(lines)


def write_dr_report(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["reports"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dr_estimates.md"
    out_path.write_text(dr_report(cfg), encoding="utf-8")
    return out_path


def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    table = dr_estimates_table(cfg)
    write_dr_table(cfg)
    for outcome in OUTCOMES:
        render_dr_plot(table, outcome, cfg)
    report = write_dr_report(cfg)
    return {"table": table, "report_path": report}


if __name__ == "__main__":
    cfg = load_config()
    out = run_all(cfg)
    print(out["table"][
        ["channel", "outcome", "dr_ate", "se", "ci_lower", "ci_upper",
         "ipw_ate", "coef", "diff", "ground_truth_log_odds"]
    ].to_string(index=False))
    print(f"\nReport -> {out['report_path']}")