"""Propensity score estimation and diagnostics (Day 6).

Per-channel logistic regression propensity scores using the adjustment sets
from the confounder audit (Day 4) / DAG (Day 5). Diagnostics include:
- Overlap plots (histograms/density of PS by treatment status)
- Common support region
- Covariate balance (SMD before matching)
- Extreme weight detection

Uses statsmodels for interpretable coefficients + sklearn for fast scoring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS, adjustment_sets


def load_analysis_data(cfg: dict | None = None) -> pd.DataFrame:
    """Load the simulated preview dataset with all sim_* columns."""
    cfg = cfg or load_config()
    path = project_path(cfg["paths"]["simulated_data"]) / "sim_preview.parquet"
    return pd.read_parquet(path)


def estimate_propensity_scores(
    df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
) -> tuple[np.ndarray, sm.LogitResult, StandardScaler]:
    """Estimate propensity scores via logistic regression for a channel.

    Returns:
        ps: propensity scores (P(T=1 | X))
        result: fitted statsmodels LogitResult
        scaler: fitted StandardScaler (for reproducibility)
    """
    cfg = cfg or load_config()
    adj = adjustment_sets(cfg)
    confounders = adj[channel]

    treatment_col = f"sim_exposed_{channel}"

    # Prepare features (confounders only) - handle missing values
    X = df[confounders].copy()
    # Impute missing with median (only review_score_avg has missing)
    X = X.fillna(X.median())
    y = df[treatment_col].values

    # Standardize for numerical stability
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled = pd.DataFrame(X_scaled, columns=confounders, index=X.index)

    # Add constant for statsmodels
    X_sm = sm.add_constant(X_scaled, has_constant="add")

    # Fit logistic regression
    model = sm.Logit(y, X_sm)
    result = model.fit(disp=False, maxiter=200, method="bfgs")

    # Predict propensity scores
    ps = result.predict(X_sm)

    return ps, result, scaler


def propensity_score_diagnostics(
    df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
) -> dict:
    """Compute comprehensive propensity score diagnostics.

    Returns dict with:
        - ps: propensity scores
        - treated_ps: PS for treated units
        - control_ps: PS for control units
        - overlap_region: (min_treated, max_control) common support
        - n_treated, n_control: sample sizes
        - ps_summary: stats (mean, std, min, max by group)
        - extreme_ps_count: count of PS < 0.01 or > 0.99
        - ess: effective sample size (for IPW)
        - scaler: fitted scaler
        - result: statsmodels result
    """
    cfg = cfg or load_config()
    treatment_col = f"sim_exposed_{channel}"

    ps, result, scaler = estimate_propensity_scores(df, channel, cfg)

    treated_mask = df[treatment_col] == 1
    treated_ps = ps[treated_mask]
    control_ps = ps[~treated_mask]

    # Common support / overlap region
    min_treated = treated_ps.min()
    max_control = control_ps.max()
    min_control = control_ps.min()
    max_treated = treated_ps.max()

    overlap_min = max(min_treated, min_control)
    overlap_max = min(max_treated, max_control)

    # Effective sample size for IPW
    # ESS = (sum(w))^2 / sum(w^2) where w = T/ps + (1-T)/(1-ps)
    weights = np.where(treated_mask, 1.0 / ps, 1.0 / (1.0 - ps))
    ess = weights.sum() ** 2 / (weights ** 2).sum()

    # Extreme PS
    extreme_low = (ps < 0.01).sum()
    extreme_high = (ps > 0.99).sum()

    return {
        "channel": channel,
        "ps": ps,
        "treated_ps": treated_ps,
        "control_ps": control_ps,
        "overlap_region": (overlap_min, overlap_max),
        "has_overlap": overlap_min < overlap_max,
        "n_treated": int(treated_mask.sum()),
        "n_control": int((~treated_mask).sum()),
        "ps_summary": {
            "treated": {
                "mean": float(treated_ps.mean()),
                "std": float(treated_ps.std()),
                "min": float(treated_ps.min()),
                "max": float(treated_ps.max()),
            },
            "control": {
                "mean": float(control_ps.mean()),
                "std": float(control_ps.std()),
                "min": float(control_ps.min()),
                "max": float(control_ps.max()),
            },
        },
        "extreme_ps_count": int(extreme_low + extreme_high),
        "extreme_low": int(extreme_low),
        "extreme_high": int(extreme_high),
        "ess": float(ess),
        "total_n": len(df),
        "scaler": scaler,
        "result": result,
        "confounders": adjustment_sets(cfg)[channel],
    }


def render_overlap_plot(
    diagnostics: dict,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
    output_dir: Path | None = None,
) -> tuple[go.Figure, Path]:
    """Render overlap diagnostic plot as interactive Plotly HTML."""
    cfg = cfg or load_config()

    fig = go.Figure()

    # Histograms
    fig.add_trace(go.Histogram(
        x=diagnostics["treated_ps"],
        name=f"Exposed (n={diagnostics['n_treated']})",
        opacity=0.6,
        nbinsx=30,
        marker_color="#e74c3c",
        histnorm="probability density",
    ))
    fig.add_trace(go.Histogram(
        x=diagnostics["control_ps"],
        name=f"Unexposed (n={diagnostics['n_control']})",
        opacity=0.6,
        nbinsx=30,
        marker_color="#3498db",
        histnorm="probability density",
    ))

    # Overlap region shading
    overlap_min, overlap_max = diagnostics["overlap_region"]
    if diagnostics["has_overlap"]:
        fig.add_vrect(
            x0=overlap_min, x1=overlap_max,
            fillcolor="green", opacity=0.1,
            layer="below", line_width=0,
            annotation_text="Common Support", annotation_position="top left",
        )

    # Extreme region markers
    fig.add_vrect(x0=0, x1=0.01, fillcolor="red", opacity=0.05, layer="below", line_width=0)
    fig.add_vrect(x0=0.99, x1=1, fillcolor="red", opacity=0.05, layer="below", line_width=0)

    fig.update_layout(
        title=f"Propensity Score Overlap — Channel: {channel}",
        title_x=0.5,
        xaxis_title="Propensity Score (P(Exposed | X))",
        yaxis_title="Density",
        barmode="overlay",
        showlegend=True,
        plot_bgcolor="white",
        height=500,
    )

    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"ps_overlap_{channel}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def render_ps_distribution_plot(
    diagnostics: dict,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
    output_dir: Path | None = None,
) -> tuple[go.Figure, Path]:
    """Render PS distribution by treatment status (box + violin)."""
    cfg = cfg or load_config()

    fig = go.Figure()

    fig.add_trace(go.Violin(
        y=diagnostics["treated_ps"],
        name="Exposed",
        box_visible=True,
        meanline_visible=True,
        line_color="#e74c3c",
        fillcolor="#e74c3c",
        opacity=0.3,
        points="outliers",
    ))
    fig.add_trace(go.Violin(
        y=diagnostics["control_ps"],
        name="Unexposed",
        box_visible=True,
        meanline_visible=True,
        line_color="#3498db",
        fillcolor="#3498db",
        opacity=0.3,
        points="outliers",
    ))

    fig.update_layout(
        title=f"Propensity Score Distribution by Exposure — Channel: {channel}",
        title_x=0.5,
        yaxis_title="Propensity Score",
        showlegend=True,
        plot_bgcolor="white",
        height=500,
    )

    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"ps_distribution_{channel}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def compute_smd_before_matching(
    df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
) -> pd.DataFrame:
    """Compute Standardized Mean Differences (SMD) before matching.

    SMD = (mean_treated - mean_control) / pooled_std
    where pooled_std = sqrt((var_treated + var_control) / 2)

    Returns DataFrame with one row per confounder + SMD.
    """
    cfg = cfg or load_config()
    adj = adjustment_sets(cfg)
    confounders = adj[channel]
    treatment_col = f"sim_exposed_{channel}"

    treated = df[df[treatment_col] == 1]
    control = df[df[treatment_col] == 0]

    # Impute missing with overall median for SMD computation
    medians = df[confounders].median()
    treated = treated[confounders].fillna(medians)
    control = control[confounders].fillna(medians)

    rows = []
    for c in confounders:
        mt, mc = treated[c].mean(), control[c].mean()
        vt, vc = treated[c].var(), control[c].var()
        pooled_std = np.sqrt((vt + vc) / 2)
        smd = (mt - mc) / pooled_std if pooled_std > 0 else 0.0
        rows.append({
            "variable": c,
            "mean_treated": mt,
            "mean_control": mc,
            "var_treated": vt,
            "var_control": vc,
            "pooled_std": pooled_std,
            "smd": smd,
            "abs_smd": abs(smd),
        })
    return pd.DataFrame(rows)


def render_smd_love_plot(
    smd_df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
    output_dir: Path | None = None,
) -> tuple[go.Figure, Path]:
    """Render SMD love plot (before matching - Day 6; after matching - Day 7)."""
    cfg = cfg or load_config()

    fig = go.Figure()

    # Sort by absolute SMD
    smd_df = smd_df.sort_values("abs_smd", ascending=True)

    colors = ["#e74c3c" if abs(x) > 0.1 else "#2ecc71" for x in smd_df["smd"]]

    fig.add_trace(go.Bar(
        y=smd_df["variable"],
        x=smd_df["smd"],
        orientation="h",
        marker_color=colors,
        text=[f"{x:.3f}" for x in smd_df["smd"]],
        textposition="outside",
        name="SMD",
    ))

    # Threshold lines
    fig.add_vline(x=0.1, line_dash="dash", line_color="green", annotation_text="SMD=0.1")
    fig.add_vline(x=-0.1, line_dash="dash", line_color="green")
    fig.add_vline(x=0, line_color="black", line_width=1)

    fig.update_layout(
        title=f"Standardized Mean Differences (Before Matching) — Channel: {channel}",
        title_x=0.5,
        xaxis_title="SMD (treated - control) / pooled SD",
        yaxis_title="Confounder",
        showlegend=False,
        plot_bgcolor="white",
        height=400 + len(smd_df) * 30,
        margin=dict(l=150),
    )

    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"smd_before_{channel}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def run_all_channels(
    cfg: dict | None = None,
) -> dict:
    """Run propensity score estimation + diagnostics for all channels.

    Returns dict keyed by channel with diagnostics.
    """
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)

    results = {}
    for ch in CHANNELS:
        print(f"  Processing channel: {ch}...")
        diag = propensity_score_diagnostics(df, ch, cfg)
        results[ch] = diag

        # Render plots
        render_overlap_plot(diag, ch, cfg)
        render_ps_distribution_plot(diag, ch, cfg)
        smd_df = compute_smd_before_matching(df, ch, cfg)
        render_smd_love_plot(smd_df, ch, cfg)

    return results


def propensity_summary(channel: Literal["email", "social", "search", "display"], cfg: dict | None = None) -> str:
    """Generate a text summary for the report."""
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)
    diag = propensity_score_diagnostics(df, channel, cfg)

    lines = []
    lines.append(f"# Propensity Score Diagnostics — Channel: {channel}")
    lines.append("")
    lines.append(f"**Adjustment set**: {', '.join(f'`{c}`' for c in diag['confounders'])}")
    lines.append("")
    lines.append("## Sample Sizes")
    lines.append(f"- Exposed (T=1): {diag['n_treated']}")
    lines.append(f"- Unexposed (T=0): {diag['n_control']}")
    lines.append(f"- Total: {diag['total_n']}")
    lines.append("")
    lines.append("## Propensity Score Summary")
    for grp in ["treated", "control"]:
        s = diag["ps_summary"][grp]
        lines.append(f"- **{grp.capitalize()}**: mean={s['mean']:.3f}, std={s['std']:.3f}, min={s['min']:.3f}, max={s['max']:.3f}")
    lines.append("")
    lines.append("## Overlap / Common Support")
    overlap_min, overlap_max = diag["overlap_region"]
    lines.append(f"- Common support region: [{overlap_min:.3f}, {overlap_max:.3f}]")
    lines.append(f"- Overlap exists: {'YES' if diag['has_overlap'] else 'NO'}")
    lines.append(f"- Exposed PS range: [{diag['ps_summary']['treated']['min']:.3f}, {diag['ps_summary']['treated']['max']:.3f}]")
    lines.append(f"- Unexposed PS range: [{diag['ps_summary']['control']['min']:.3f}, {diag['ps_summary']['control']['max']:.3f}]")
    lines.append("")
    lines.append("## Positivity / Extreme Weights")
    lines.append(f"- PS < 0.01: {diag['extreme_low']} units")
    lines.append(f"- PS > 0.99: {diag['extreme_high']} units")
    lines.append(f"- Effective Sample Size (IPW): {diag['ess']:.1f} / {diag['total_n']} ({diag['ess']/diag['total_n']*100:.1f}%)")
    lines.append("")
    lines.append("## Logistic Regression Coefficients")
    result = diag["result"]
    lines.append("```")
    lines.append(result.summary().as_text())
    lines.append("```")
    return "\n".join(lines)


if __name__ == "__main__":
    cfg = load_config()
    print("Running propensity score estimation for all channels...")
    results = run_all_channels(cfg)
    print("\nSummaries:")
    for ch in CHANNELS:
        print(propensity_summary(ch, cfg))
        print("---")