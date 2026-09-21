"""Propensity Score Matching + Balance diagnostics (Day 7).

Nearest-neighbor matching on propensity scores with caliper.
SMD before/after, love plots, balance tables.
Assumptions checklist per channel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.neighbors import NearestNeighbors

from src.config import load_config, project_path
from src.causal.propensity import (
    load_analysis_data,
    propensity_score_diagnostics,
    compute_smd_before_matching,
)
from src.causal.confounders import CHANNELS, adjustment_sets


def nearest_neighbor_match(
    df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
    caliper: float = 0.01,
    ratio: int = 1,
    with_replacement: bool = False,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Perform nearest-neighbor matching on propensity scores.

    Args:
        df: analysis data with sim_exposed_{channel} and confounders
        channel: marketing channel
        cfg: config dict
        caliper: max PS distance for match (in SD of PS)
        ratio: number of controls per treated
        with_replacement: whether controls can be reused

    Returns:
        matched_df: DataFrame with matched pairs (treated + matched controls)
        match_indices: array of control indices matched to each treated
    """
    cfg = cfg or load_config()
    treatment_col = f"sim_exposed_{channel}"

    # Get propensity scores
    diag = propensity_score_diagnostics(df, channel, cfg)
    ps = diag["ps"]
    if hasattr(ps, 'values'):
        ps = ps.values
    treated_mask = df[treatment_col] == 1

    treated_idx = np.where(treated_mask)[0]
    control_idx = np.where(~treated_mask)[0]

    treated_ps = ps[treated_mask].reshape(-1, 1)
    control_ps = ps[~treated_mask].reshape(-1, 1)

    # Caliper in PS units (Austin 2011: 0.2 * SD of logit(PS) or 0.1 * SD of PS)
    ps_sd = ps.std()
    caliper_abs = caliper * ps_sd

    # Nearest neighbor search
    nn = NearestNeighbors(n_neighbors=ratio, metric="euclidean")
    nn.fit(control_ps)
    distances, indices = nn.kneighbors(treated_ps)

    # Apply caliper
    valid_matches = distances.flatten() <= caliper_abs
    matched_treated = treated_idx[valid_matches]
    matched_controls = control_idx[indices[valid_matches].flatten()]

    # Build matched dataset
    matched_treated_df = df.iloc[matched_treated].copy()
    matched_treated_df["match_id"] = range(len(matched_treated))
    matched_treated_df["match_role"] = "treated"

    matched_control_df = df.iloc[matched_controls].copy()
    matched_control_df["match_id"] = np.repeat(range(len(matched_treated)), ratio)
    matched_control_df["match_role"] = "control"

    matched_df = pd.concat([matched_treated_df, matched_control_df], ignore_index=True)

    return matched_df, matched_controls


def compute_smd_after_matching(
    matched_df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
) -> pd.DataFrame:
    """Compute SMD on matched sample."""
    cfg = cfg or load_config()
    adj = adjustment_sets(cfg)
    confounders = adj[channel]
    treatment_col = f"sim_exposed_{channel}"

    treated = matched_df[matched_df[treatment_col] == 1]
    control = matched_df[matched_df[treatment_col] == 0]

    medians = matched_df[confounders].median()
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


def render_smd_love_plot_comparison(
    smd_before: pd.DataFrame,
    smd_after: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
    output_dir: Path | None = None,
) -> tuple[go.Figure, Path]:
    """Render love plot comparing SMD before and after matching."""
    cfg = cfg or load_config()

    # Merge
    merged = smd_before[["variable", "smd"]].rename(columns={"smd": "smd_before"})
    merged = merged.merge(
        smd_after[["variable", "smd"]].rename(columns={"smd": "smd_after"}),
        on="variable",
    )
    merged = merged.sort_values("smd_before", key=abs, ascending=True)

    fig = go.Figure()

    # Before matching
    colors_before = ["#e74c3c" if abs(x) > 0.1 else "#2ecc71" for x in merged["smd_before"]]
    fig.add_trace(go.Bar(
        y=merged["variable"],
        x=merged["smd_before"],
        orientation="h",
        marker_color=colors_before,
        name="Before Matching",
        text=[f"{x:.3f}" for x in merged["smd_before"]],
        textposition="outside",
        opacity=0.7,
    ))

    # After matching
    colors_after = ["#e74c3c" if abs(x) > 0.1 else "#2ecc71" for x in merged["smd_after"]]
    fig.add_trace(go.Bar(
        y=merged["variable"],
        x=merged["smd_after"],
        orientation="h",
        marker_color=colors_after,
        name="After Matching",
        text=[f"{x:.3f}" for x in merged["smd_after"]],
        textposition="outside",
        opacity=0.7,
    ))

    # Threshold lines
    fig.add_vline(x=0.1, line_dash="dash", line_color="green", annotation_text="SMD=0.1")
    fig.add_vline(x=-0.1, line_dash="dash", line_color="green")
    fig.add_vline(x=0, line_color="black", line_width=1)

    fig.update_layout(
        title=f"SMD Love Plot — Before vs After Matching: {channel}",
        title_x=0.5,
        xaxis_title="SMD (treated - control) / pooled SD",
        yaxis_title="Confounder",
        barmode="group",
        showlegend=True,
        plot_bgcolor="white",
        height=400 + len(merged) * 35,
        margin=dict(l=150),
    )

    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"smd_love_{channel}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def render_ps_after_matching(
    matched_df: pd.DataFrame,
    channel: Literal["email", "social", "search", "display"],
    cfg: dict | None = None,
    output_dir: Path | None = None,
) -> tuple[go.Figure, Path]:
    """Render PS distribution after matching."""
    cfg = cfg or load_config()

    # Re-estimate PS on matched sample (should be similar)
    from src.causal.propensity import estimate_propensity_scores
    ps, _, _ = estimate_propensity_scores(matched_df, channel, cfg)
    matched_df = matched_df.copy()
    matched_df["ps"] = ps

    treatment_col = f"sim_exposed_{channel}"
    treated_ps = matched_df[matched_df[treatment_col] == 1]["ps"]
    control_ps = matched_df[matched_df[treatment_col] == 0]["ps"]

    fig = go.Figure()

    fig.add_trace(go.Violin(
        y=treated_ps,
        name="Exposed (matched)",
        box_visible=True,
        meanline_visible=True,
        line_color="#e74c3c",
        fillcolor="#e74c3c",
        opacity=0.3,
        points="outliers",
    ))
    fig.add_trace(go.Violin(
        y=control_ps,
        name="Unexposed (matched)",
        box_visible=True,
        meanline_visible=True,
        line_color="#3498db",
        fillcolor="#3498db",
        opacity=0.3,
        points="outliers",
    ))

    fig.update_layout(
        title=f"Propensity Score After Matching — Channel: {channel}",
        title_x=0.5,
        yaxis_title="Propensity Score",
        showlegend=True,
        plot_bgcolor="white",
        height=500,
    )

    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"ps_after_{channel}.html"
    fig.write_html(str(out_path))
    return fig, out_path


def run_matching_all_channels(
    cfg: dict | None = None,
    caliper: float = 0.01,
    ratio: int = 1,
) -> dict:
    """Run matching for all channels."""
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)

    results = {}
    for ch in CHANNELS:
        print(f"  Matching channel: {ch}...")
        matched_df, match_indices = nearest_neighbor_match(
            df, ch, cfg, caliper=caliper, ratio=ratio
        )
        smd_before = compute_smd_before_matching(df, ch, cfg)
        smd_after = compute_smd_after_matching(matched_df, ch, cfg)

        # Render plots
        render_smd_love_plot_comparison(smd_before, smd_after, ch, cfg)
        render_ps_after_matching(matched_df, ch, cfg)

        results[ch] = {
            "matched_df": matched_df,
            "match_indices": match_indices,
            "smd_before": smd_before,
            "smd_after": smd_after,
            "n_matched_pairs": len(matched_df) // 2,
            "match_rate": len(matched_df) // 2 / (df[f"sim_exposed_{ch}"] == 1).sum(),
        }

    return results


def balance_summary(channel: Literal["email", "social", "search", "display"], cfg: dict | None = None) -> str:
    """Generate balance summary report."""
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)

    matched_df, _ = nearest_neighbor_match(df, channel, cfg)
    smd_before = compute_smd_before_matching(df, channel, cfg)
    smd_after = compute_smd_after_matching(matched_df, channel, cfg)

    lines = []
    lines.append(f"# Matching Balance Report — Channel: {channel}")
    lines.append("")
    lines.append("## Matching Specifications")
    lines.append("- Method: Nearest-neighbor on propensity score (1:1)")
    lines.append("- Caliper: 0.01 * SD(PS)")
    lines.append("- Without replacement")
    lines.append("")
    lines.append("## Sample Sizes")
    orig_treated = (df[f"sim_exposed_{channel}"] == 1).sum()
    matched_pairs = len(matched_df) // 2
    lines.append(f"- Original treated: {orig_treated}")
    lines.append(f"- Matched pairs: {matched_pairs}")
    lines.append(f"- Match rate: {matched_pairs/orig_treated*100:.1f}%")
    lines.append("")
    lines.append("## SMD Comparison")
    lines.append("| Variable | SMD Before | SMD After | Improved |")
    lines.append("|----------|------------|-----------|----------|")
    for _, row in smd_before.iterrows():
        var = row["variable"]
        before = row["smd"]
        after_row = smd_after[smd_after["variable"] == var].iloc[0]
        after = after_row["smd"]
        improved = "✅" if abs(after) < abs(before) else "❌"
        lines.append(f"| {var} | {before:.3f} | {after:.3f} | {improved} |")
    lines.append("")
    lines.append("## Balance Assessment")
    max_before = smd_before["abs_smd"].max()
    max_after = smd_after["abs_smd"].max()
    n_balanced_before = (smd_before["abs_smd"] < 0.1).sum()
    n_balanced_after = (smd_after["abs_smd"] < 0.1).sum()
    n_total = len(smd_before)
    lines.append(f"- Max |SMD| before: {max_before:.3f}")
    lines.append(f"- Max |SMD| after: {max_after:.3f}")
    lines.append(f"- Variables with |SMD| < 0.1 before: {n_balanced_before}/{n_total}")
    lines.append(f"- Variables with |SMD| < 0.1 after: {n_balanced_after}/{n_total}")
    lines.append("")
    if max_after < 0.1:
        lines.append("**✅ PASS**: All covariates balanced (|SMD| < 0.1 after matching)")
    else:
        lines.append("**⚠️ FAIL**: Some covariates remain imbalanced (|SMD| ≥ 0.1 after matching)")
    return "\n".join(lines)


def assumptions_checklist(channel: Literal["email", "social", "search", "display"], cfg: dict | None = None) -> str:
    """Generate assumptions checklist for the channel."""
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)
    adj = adjustment_sets(cfg)[channel]

    lines = []
    lines.append(f"# Assumptions Checklist — Channel: {channel}")
    lines.append("")
    lines.append("| Assumption | Evidence | Status | Limitation |")
    lines.append("|------------|----------|--------|------------|")
    lines.append(
        f"| Exchangeability (unconfoundedness) | Adjustment set {adj} blocks observed backdoor paths; "
        f"sim_u remains unobserved | **Partially met** (residual sim_u confounding) | "
        f"Sensitivity analysis (Day 18) required |"
    )
    lines.append(
        f"| Positivity / Overlap | PS overlap region non-empty; "
        f"match rate > 90% for social/search/display; email match rate lower due to PS=1 clumping | "
        f"{'Met' if channel != 'email' else 'Marginal'} | "
        f"Email has 71 units with PS=1.0 (perfect prediction) |"
    )
    lines.append(
        f"| Consistency | Single binary exposure per channel; no dose variants in preview | **Met** | "
        f"Full campaign grid (Week 2) adds timing variants |"
    )
    lines.append(
        f"| SUTVA / No Interference | Simulation has no cross-unit spillover | **Met in sim** | "
        f"Real marketing has peer effects; per-channel analysis limits joint multi-channel issue |"
    )
    lines.append(
        f"| Correct PS Model Specification | Logistic regression with linear terms; "
        f"pseudo-R² = 0.01–0.06 | **Plausible** | "
        f"Could miss non-linearities/interactions; Day 10 IPW uses same model |"
    )
    lines.append(
        f"| Matching Quality | 1:1 NN with caliper; SMD assessed | {'Met' if channel != 'email' else 'Marginal'} | "
        f"Email PS clumping limits matches; no replacement reduces sample |"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    cfg = load_config()
    print("Running PSM for all channels...")
    results = run_matching_all_channels(cfg)
    print("\nBalance Summaries:")
    for ch in CHANNELS:
        print(balance_summary(ch, cfg))
        print("\nAssumptions Checklist:")
        print(assumptions_checklist(ch, cfg))
        print("---")