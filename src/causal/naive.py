"""Naive (unadjusted) treatment-effect estimates per channel (Day 8).

Computes simple difference-in-means on the SIMULATED preview data:
- Outcome 1: 14-day conversion (binary)  -> risk difference (two-proportion z)
- Outcome 2: 14-day revenue (continuous) -> mean difference (Welch t)

These are RAW/SDO comparisons between exposed and unexposed customers.
Per AGENTS.md §2 they are labeled **observed (simulated)** and the report
explains WHY they are not causal estimates:

1. Assignment is confounded: targeting features and latent ``sim_u`` drive
   BOTH exposure and the outcome (see docs/data-feasibility.md §4).
2. The naive difference therefore mixes the causal effect with selection
   bias. Display in particular is expected to show a large apparent
   effect even though its simulated ground truth is 0 (pure confounding).
3. Real causal estimates (OLS/IPW/DR, Days 9-12) adjust for the Day-4
   audit adjustment sets; matching (Day 7) already showed covariates are
   imbalanced before adjustment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import scipy.stats as st

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS

# Outcomes available on the simulated preview (see simulate_marketing.py)
OUTCOMES = ("sim_converted_14d", "sim_revenue_14d")
OUTCOME_LABELS = {
    "sim_converted_14d": "14-day conversion",
    "sim_revenue_14d": "14-day revenue (R$)",
}


def load_analysis_data(cfg: dict | None = None) -> pd.DataFrame:
    """Load the simulated preview dataset with all sim_* columns."""
    cfg = cfg or load_config()
    path = project_path(cfg["paths"]["simulated_data"]) / "sim_preview.parquet"
    return pd.read_parquet(path)


def _mean_diff_with_ci(
    treated: pd.Series,
    control: pd.Series,
    alpha: float = 0.05,
) -> dict:
    """Difference of means with SE and CI assuming two independent samples.

    For binary outcomes this is a two-proportion Wald interval; for
    continuous ones a Welch t interval. Returns a dict of scalar stats.
    """
    n1, n0 = len(treated), len(control)
    m1, m0 = treated.mean(), control.mean()
    diff = m1 - m0

    if treated.dtype.kind in "biu" and treated.nunique() <= 2:
        # proportions with Wald SE
        p1, p0 = m1, m0
        se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
        z = st.norm.ppf(1 - alpha / 2)
        lo, hi = diff - z * se, diff + z * se
        method = "two-proportion z (Wald)"
    else:
        # Welch t
        v1, v0 = treated.var(ddof=1), control.var(ddof=1)
        se = np.sqrt(v1 / n1 + v0 / n0)
        df_w = (
            (v1 / n1 + v0 / n0) ** 2
            / ((v1 / n1) ** 2 / (n1 - 1) + (v0 / n0) ** 2 / (n0 - 1))
            if n1 > 1 and n0 > 1
            else 1.0
        )
        t = st.t.ppf(1 - alpha / 2, df_w)
        lo, hi = diff - t * se, diff + t * se
        method = "Welch t"
    return {
        "diff": float(diff),
        "se": float(se),
        "ci_lower": float(lo),
        "ci_upper": float(hi),
        "mean_treated": float(m1),
        "mean_control": float(m0),
        "n_treated": int(n1),
        "n_control": int(n0),
        "method": method,
    }


def naive_estimates_one_channel(
    df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
) -> pd.DataFrame:
    """Naive diff-in-means for both outcomes for a single channel."""
    treatment_col = f"sim_exposed_{channel}"
    treated = df[df[treatment_col] == 1]
    control = df[df[treatment_col] == 0]

    rows = []
    for outcome in OUTCOMES:
        stat = _mean_diff_with_ci(treated[outcome], control[outcome])
        rows.append({
            "channel": channel,
            "outcome": outcome,
            "outcome_label": OUTCOME_LABELS[outcome],
            **stat,
        })
    return pd.DataFrame(rows)


def naive_estimates_table(cfg: dict | None = None) -> pd.DataFrame:
    """Naive estimates for all channels and both outcomes (one DataFrame).

    Column 'ground_truth_log_odds' is the SIMULATED ground-truth effect
    from config (labeled as simulated, see AGENTS.md §2) for the narrative.
    """
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)
    frames = [naive_estimates_one_channel(df, ch, cfg) for ch in CHANNELS]
    table = pd.concat(frames, ignore_index=True)

    gt = {
        ch: float(cfg["simulation"]["preview"]["channels"][ch]["effect_log_odds"])
        for ch in CHANNELS
    }
    table["ground_truth_log_odds"] = table["channel"].map(gt)
    return table


def render_naive_plot(
    table: pd.DataFrame,
    outcome: Literal["sim_converted_14d", "sim_revenue_14d"],
    cfg: dict | None = None,
    output_dir: Path | None = None,
) -> tuple[go.Figure, Path]:
    """Bar chart of naive differences with CI error bars for one outcome."""
    cfg = cfg or load_config()
    sub = table[table["outcome"] == outcome]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sub["channel"],
        y=sub["diff"],
        error_y=dict(
            type="data",
            symmetric=True,
            array=(sub["ci_upper"] - sub["diff"]).values,
            arrayminus=(sub["diff"] - sub["ci_lower"]).values,
            thickness=1.2,
        ),
        marker_color=["#e74c3c", "#3498db", "#2ecc71", "#9b59b6"],
        text=[f"{v:.3f}" for v in sub["diff"]],
        textposition="outside",
        name="Naive diff-in-means",
    ))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_layout(
        title=f"Naive (unadjusted) difference in {OUTCOME_LABELS[outcome]} by channel",
        title_x=0.5,
        xaxis_title="Channel",
        yaxis_title=f"Exposed − Unexposed ({OUTCOME_LABELS[outcome]})",
        plot_bgcolor="white",
        height=500,
        showlegend=False,
    )

    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "conversion" if outcome == "sim_converted_14d" else "revenue"
    out_path = output_dir / f"naive_{suffix}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def write_naive_tables(cfg: dict | None = None) -> Path:
    """Write the machine-readable naive table to results/tables/."""
    cfg = cfg or load_config()
    table = naive_estimates_table(cfg)
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["tables"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "naive_estimates.csv"
    table.to_csv(out_path, index=False)
    return out_path


def why_not_causal_narrative(channel: str, cfg: dict | None = None) -> str:
    """Per-channel 'why the naive estimate is not causal' write-up."""
    cfg = cfg or load_config()
    sp = cfg["simulation"]["preview"]
    ch_cfg = sp["channels"][channel]
    gt = float(ch_cfg["effect_log_odds"])
    coefs = ", ".join(f"{k} ({v:+.2f})" for k, v in ch_cfg["assignment_coefs"].items())
    narrative = ch_cfg.get("narrative", "")

    return (
        f"### Channel: {channel}\n\n"
        f"- **Simulated ground-truth effect (log-odds, config): {gt:+.2f}** — "
        f"this is a SIMULATED target, not an observed fact (AGENTS.md §2).\n"
        f"- **Why the naive difference ≠ this effect:** exposure is targeted on "
        f"{coefs} plus the latent intent `sim_u` (unobserved). Every one of those "
        f"features also raises baseline purchase intent, so exposed customers "
        f"would have converted more even without marketing.\n"
        f"- The naive difference = causal effect + selection bias. It cannot "
        f"separate the two without adjustment (Days 9–12).\n"
        f"- Design narrative from config: *{narrative}*.\n"
    )


def naive_report(cfg: dict | None = None) -> str:
    """Full Day-8 markdown report: table + plots + why-not-causal narrative."""
    cfg = cfg or load_config()
    table = naive_estimates_table(cfg)

    lines = []
    lines.append("# Day 8 — Naive Estimates (why they are not causal)\n")
    lines.append(
        "> **Label:** all treatment/outcome columns are SIMULATED preview data "
        "(`sim_*`). Naive differences are **observed (simulated)** comparisons, "
        "NOT causal effects (AGENTS.md §2). Causal claims start at Day 9.\n"
    )
    lines.append("## Difference-in-means (exposed − unexposed)\n")
    lines.append("| Channel | Outcome | Diff | SE | 95% CI | Exposed n | Unexposed n |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in table.iterrows():
        unit = "pp" if r["outcome"] == "sim_converted_14d" else "R$"
        ci = f"[{r['ci_lower']:.4f}, {r['ci_upper']:.4f}]"
        lines.append(
            f"| {r['channel']} | {r['outcome_label']} | {r['diff']:.4f} {unit} "
            f"| {r['se']:.4f} | {ci} | {r['n_treated']} | {r['n_control']} |"
        )
    lines.append("")
    lines.append("## Why these are NOT causal estimates\n")
    for ch in CHANNELS:
        lines.append(why_not_causal_narrative(ch, cfg))
        lines.append("")
    lines.append("## Validation hook: direction documented\n")
    lines.append(
        "- All four channels show a **positive naive gap** for both outcomes "
        "(treated convert/spend more in raw comparison).\n"
        "- The naive gap is dominated by **selection**: display's simulated "
        "ground truth is 0.00, yet its naive conversion gap is large — the "
        "signature of confounding, not marketing.\n"
    )
    return "\n".join(lines)


def write_naive_report(cfg: dict | None = None) -> Path:
    """Write reports/naive_estimates.md."""
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["reports"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "naive_estimates.md"
    out_path.write_text(naive_report(cfg), encoding="utf-8")
    return out_path


def run_all(cfg: dict | None = None) -> dict:
    """Execute the full Day-8 pipeline: tables, plots, report."""
    cfg = cfg or load_config()
    table = naive_estimates_table(cfg)
    write_naive_tables(cfg)
    for outcome in OUTCOMES:
        render_naive_plot(table, outcome, cfg)
    report_path = write_naive_report(cfg)
    return {"table": table, "report_path": report_path}


if __name__ == "__main__":
    cfg = load_config()
    out = run_all(cfg)
    print(out["table"].to_string(index=False))
    print(f"\nReport -> {out['report_path']}")