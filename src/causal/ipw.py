"""Inverse Probability Weighting (IPW) — Day 10.

Stabilized (Hajek-normalized) IPW estimator per channel x outcome:
    w = T * P(T=1)/p(x) + (1-T) * P(T=0)/(1-p(x))
    ATE = sum(w*T*Y)/sum(w*T) - sum(w*(1-T)*Y)/sum(w*(1-T))

Extreme-weight handling (Cole & Hernan truncation): stabilized weights are
capped at ``ipw.weight_cap`` (config), and the number of truncated units is
reported. ESS = (sum w)^2 / sum w^2 is reported BEFORE and AFTER truncation.
CI from bootstrap (fixed seed, ``ipw.bootstrap_reps`` resamples).

**Labels (AGENTS.md §2):** results are SIMULATED estimates. The identification
strategy (exchangeability given the Day-4 adjustment set + ``sim_u`` caveat)
and the weak-overlap caveat for email (71 units with PS = 1.0) are stated here,
before estimation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS, adjustment_sets
from src.causal.naive import OUTCOMES, OUTCOME_LABELS, load_analysis_data, naive_estimates_table
from src.causal.propensity import estimate_propensity_scores
from src.causal.regression import ols_estimates_table


def ipw_weights(
    df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
) -> dict:
    """Stabilized IPW weights (raw + truncated) with diagnostics."""
    cfg = cfg or load_config()
    treatment_col = f"sim_exposed_{channel}"
    cap = float(cfg["ipw"]["weight_cap"])

    ps, _, _ = estimate_propensity_scores(df, channel, cfg)
    ps = np.clip(ps, 1e-8, 1 - 1e-8)  # guard against exact 0/1
    t = df[treatment_col].values.astype(float)
    p_treat = t.mean()

    w_stab = t * (p_treat / ps) + (1 - t) * ((1 - p_treat) / (1 - ps))
    w_trunc = np.minimum(w_stab, cap)

    def ess(w: np.ndarray) -> float:
        return float(w.sum() ** 2 / (w ** 2).sum())

    return {
        "channel": channel,
        "ps": ps,
        "w_stab": w_stab,
        "w_trunc": w_trunc,
        "n_truncated": int((w_stab > cap).sum()),
        "max_stab": float(w_stab.max()),
        "max_trunc": float(w_trunc.max()),
        "ess_raw": ess(w_stab),
        "ess_trunc": ess(w_trunc),
        "n": len(df),
    }


def _ipw_ate(df: pd.DataFrame, weights: np.ndarray, outcome: str) -> float:
    """Hajek-normalized stabilized IPW ATE for one outcome.

    ``df`` must contain the internal ``__t__`` treatment-marker column and
    ``weights`` the (truncated) stabilized weights aligned to df's rows.
    """
    y = df[outcome].values.astype(float)
    t = df["__t__"].values.astype(float)
    mu1 = np.sum(weights * t * y) / np.sum(weights * t)
    mu0 = np.sum(weights * (1 - t) * y) / np.sum(weights * (1 - t))
    return float(mu1 - mu0)


def ipw_estimate(
    df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    outcome: Literal["sim_converted_14d", "sim_revenue_14d"],
    cfg: dict | None = None,
) -> dict:
    """IPW ATE with bootstrap SE + CI (fixed seed, config reps)."""
    cfg = cfg or load_config()
    treatment_col = f"sim_exposed_{channel}"
    n_boot = int(cfg["ipw"]["bootstrap_reps"])
    alpha = float(cfg["ipw"]["alpha"])
    rng = np.random.default_rng(int(cfg["seed"]) + CHANNELS.index(channel))

    w = ipw_weights(df, channel, cfg)["w_trunc"]
    work = df[[treatment_col, outcome]].rename(columns={treatment_col: "__t__"}).copy()
    work["__w__"] = w

    ate = _ipw_ate(work, w, outcome)

    boot = np.empty(n_boot)
    n = len(work)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        rep = work.iloc[idx]
        boot[b] = _ipw_ate(rep, rep["__w__"].values, outcome)

    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return {
        "channel": channel,
        "outcome": outcome,
        "outcome_label": OUTCOME_LABELS[outcome],
        "ipw_ate": ate,
        "se": float(boot.std(ddof=1)),
        "ci_lower": float(lo),
        "ci_upper": float(hi),
        "bootstrap_reps": n_boot,
        "weights": w,
    }


def ipw_estimates_table(cfg: dict | None = None) -> pd.DataFrame:
    """IPW ATE table merged with naive + OLS + ground truth + weight diagnostics."""
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)

    rows = []
    weight_diag = {}
    for ch in CHANNELS:
        weight_diag[ch] = ipw_weights(df, ch, cfg)
        for outcome in OUTCOMES:
            est = ipw_estimate(df, ch, outcome, cfg)
            rows.append(est)

    table = pd.DataFrame(rows)

    naive = naive_estimates_table(cfg)[["channel", "outcome", "diff"]]
    table = table.merge(naive, on=["channel", "outcome"], suffixes=("", "_naive"))
    table = table.merge(
        ols_estimates_table(cfg)[["channel", "outcome", "coef", "se"]],
        on=["channel", "outcome"],
        suffixes=("", "_ols"),
    )

    gt = {
        ch: float(cfg["simulation"]["preview"]["channels"][ch]["effect_log_odds"])
        for ch in CHANNELS
    }
    table["ground_truth_log_odds"] = table["channel"].map(gt)

    for ch in CHANNELS:
        d = weight_diag[ch]
        for outcome in OUTCOMES:
            m = (table["channel"] == ch) & (table["outcome"] == outcome)
            table.loc[m, "n_truncated"] = d["n_truncated"]
            table.loc[m, "max_weight"] = d["max_trunc"]
            table.loc[m, "ess_raw"] = d["ess_raw"]
            table.loc[m, "ess_trunc"] = d["ess_trunc"]
            table.loc[m, "n"] = d["n"]
    return table


def render_ipw_plot(
    table: pd.DataFrame,
    outcome: Literal["sim_converted_14d", "sim_revenue_14d"],
    cfg: dict | None = None,
    output_dir: Path | None = None,
) -> tuple[go.Figure, Path]:
    """Bar chart: IPW vs OLS vs naive for one outcome."""
    cfg = cfg or load_config()
    sub = table[table["outcome"] == outcome].sort_values("channel")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sub["channel"], y=sub["ipw_ate"],
        error_y=dict(type="data", symmetric=True,
                     array=(sub["ci_upper"] - sub["ipw_ate"]).values,
                     arrayminus=(sub["ipw_ate"] - sub["ci_lower"]).values,
                     thickness=1.2),
        marker_color="#9b59b6",
        text=[f"{v:.4f}" for v in sub["ipw_ate"]],
        textposition="outside",
        name="IPW (stabilized, capped)",
    ))
    fig.add_trace(go.Bar(x=sub["channel"], y=sub["coef"],
                         marker_color="#2ecc71", name="OLS (Day 9)", opacity=0.6))
    fig.add_trace(go.Bar(x=sub["channel"], y=sub["diff"],
                         marker_color="#e74c3c", name="Naive (Day 8)", opacity=0.4))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_layout(
        title=f"IPW vs OLS vs naive — {OUTCOME_LABELS[outcome]}",
        title_x=0.5,
        xaxis_title="Channel",
        yaxis_title=f"Effect ({OUTCOME_LABELS[outcome]})",
        barmode="group",
        plot_bgcolor="white",
        height=500,
    )
    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "conversion" if outcome == "sim_converted_14d" else "revenue"
    out_path = output_dir / f"ipw_{suffix}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def write_ipw_table(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    table = ipw_estimates_table(cfg)
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["tables"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ipw_estimates.csv"
    table.to_csv(out_path, index=False)
    return out_path


def ipw_report(cfg: dict | None = None) -> str:
    """Day-10 markdown report: identification statement, table, diagnostics, limits."""
    cfg = cfg or load_config()
    table = ipw_estimates_table(cfg)

    lines = []
    lines.append("# Day 10 — Inverse Probability Weighting (IPW)\n")
    lines.append(
        "> **Label:** SIMULATED estimates (`sim_*`), not observed Olist facts "
        "(AGENTS.md §2). Identification: stabilized Hajek IPW with the Day-4 "
        "adjustment set for the propensity model. Exchangeability holds only "
        "given `sim_u`-free conditioning — and `sim_u` is unobserved by design, "
        "so the estimates remain biased toward the naive gap (quantified Day 18).\n"
    )
    lines.append("## Identification statement (before fitting)\n")
    lines.append(
        "- **Causal question (ATE):** what is the incremental 14-day conversion / "
        "revenue effect of exposure per channel, vs no exposure, for all customers?\n"
        "- **Estimator:** Hajek-normalized IPW with stabilized weights, truncated "
        f"at {cfg['ipw']['weight_cap']} (Cole & Hernan).\n"
        "- **Positivity:** overlap verified Day 6; email has 71 units with PS ≈ 1.0 "
        "(weak overlap) → truncation applied and ESS caveated.\n"
        "- **SUTVA / consistency:** satisfied within the sim design (no interference;\n"
        " single binary exposure).\n"
    )
    lines.append("## IPW ATE table (bootstrap 95% CI)\n")
    lines.append("| Channel | Outcome | IPW ATE | SE | 95% CI | Naive | OLS | ESS% | Truncated | Max w |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for _, r in table.iterrows():
        unit = "pp" if r["outcome"] == "sim_converted_14d" else "R$"
        ess_pct = 100 * r["ess_trunc"] / r["n"]
        lines.append(
            f"| {r['channel']} | {r['outcome_label']} | {r['ipw_ate']:.4f} {unit} "
            f"| {r['se']:.4f} | [{r['ci_lower']:.4f}, {r['ci_upper']:.4f}] "
            f"| {r['diff']:.4f} {unit} | {r['coef']:.4f} {unit} "
            f"| {ess_pct:.1f}% | {int(r['n_truncated'])} | {r['max_weight']:.2f} |"
        )
    lines.append("")
    lines.append("## Weight diagnostics\n")
    for ch in CHANNELS:
        row = table[(table["channel"] == ch) & (table["outcome"] == "sim_converted_14d")].iloc[0]
        lines.append(
            f"- **{ch}:** ESS {row['ess_raw']:.1f} → **{row['ess_trunc']:.1f}** after "
            f"truncation ({100*row['ess_trunc']/row['n']:.1f}% of n={int(row['n'])}, "
            f"weight cap {r['max_weight']:.1f}); {int(row['n_truncated'])} units capped."
        )
    lines.append("")
    lines.append("## Limitations\n")
    lines.append(
        "- Weak overlap for email (71 units PS ≈ 1.0) → stabilized weights are "
        "truncated; ATE then slightly biased but variance-reduced.\n"
        "- `sim_u` is unobserved: IPW reweights on the observed set and cannot "
        "remove `sim_u` selection without strong assumptions.\n"
        "- Bootstrap CI assumes resampling captures design variability; it does "
        "NOT cover model/PS misspecification.\n"
        "- Conversion outcome: weights stabilize the mean but the binary outcome "
        "is better handled by DR / outcome-regression hybrids (Day 11).\n"
    )
    return "\n".join(lines)


def write_ipw_report(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["reports"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ipw_estimates.md"
    out_path.write_text(ipw_report(cfg), encoding="utf-8")
    return out_path


def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    table = ipw_estimates_table(cfg)
    write_ipw_table(cfg)
    for outcome in OUTCOMES:
        render_ipw_plot(table, outcome, cfg)
    report = write_ipw_report(cfg)
    return {"table": table, "report_path": report}


if __name__ == "__main__":
    cfg = load_config()
    out = run_all(cfg)
    print(out["table"][
        ["channel", "outcome", "ipw_ate", "se", "ci_lower", "ci_upper",
         "diff", "coef", "ground_truth_log_odds", "n_truncated", "max_weight",
         "ess_raw", "ess_trunc", "n"]
    ].to_string(index=False))
    print(f"\nReport -> {out['report_path']}")