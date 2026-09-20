"""Figure helpers — every figure lands in results/figures (Day 3).

matplotlib + seaborn for EDA; the causal DAG uses plotly/networkx and lives
in src/causal/dag_plot.py (Day 5). All helpers follow the same contract:

    fig = some_plot(df)      # build
    save_fig(fig, "name.png")  # write to results/figures

matplotlib is forced to the non-interactive Agg backend only OUTSIDE a
notebook kernel (inside ipykernel, the `%matplotlib inline` backend must
win or figures never render in the notebook).
"""
from __future__ import annotations

import sys

import matplotlib

if "ipykernel" not in sys.modules:  # keep notebook inline backend alive
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from src.config import load_config, project_path

sns.set_theme(style="whitegrid", palette="deep")


def figures_dir():
    cfg = load_config()
    return project_path(cfg["paths"]["results"], cfg["results"]["figures"])


def tables_dir():
    cfg = load_config()
    return project_path(cfg["paths"]["results"], cfg["results"]["tables"])


def save_fig(fig, name: str, close: bool = False) -> None:
    """Write a matplotlib figure to results/figures/<name> (creates dirs).

    ``close`` defaults to False so notebook inline output still renders
    (Agg-saved PNGs are written regardless). Scripts/tests may pass
    close=True to avoid figure leaks.
    """
    out = figures_dir()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / name, dpi=150, bbox_inches="tight")
    if close:
        plt.close(fig)


def plot_missingness(missing: pd.DataFrame) -> "plt.Figure":
    """Horizontal bar of % missing per column (columns with 0 are hidden)."""
    data = missing[missing["n_missing"] > 0].sort_values("pct_missing")
    fig, ax = plt.subplots(figsize=(7, max(2.2, 0.5 * len(data) + 1)))
    ax.barh(data["column"], data["pct_missing"], color="#c44e52")
    ax.set_xlabel("% missing")
    ax.set_title("Missingness by column (analytical cohort, N=94,983)")
    for i, v in enumerate(data["pct_missing"]):
        ax.text(v + 0.02, i, f"{v:g}%", va="center", fontsize=8)
    fig.tight_layout()
    return fig


def plot_outlier_box(df: pd.DataFrame, cols: tuple[str, ...], log: bool = False) -> "plt.Figure":
    """Log-or-linear boxplot of the revenue columns with IQR outlier counts."""
    fig, axes = plt.subplots(1, len(cols), figsize=(6.2 * len(cols), 4.2), sharey=False)
    if len(cols) == 1:
        axes = [axes]
    for ax, col in zip(axes, cols):
        s = df[col].dropna()
        if log and (s > 0).all():
            scale = "log"
            s = s
        else:
            scale = "linear"
        ax.boxplot(s, showfliers=True, vert=True, patch_artist=True)
        # IQR outlier count annotation
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        n_out = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
        ax.set_title(f"{col}\n(n={len(s):,}, IQR outliers: {n_out:,})")
        ax.set_yscale(scale)
        ax.set_xticks([])
    fig.suptitle("Revenue outliers (IQR fence k=1.5) — observed Olist data")
    fig.tight_layout()
    return fig


def plot_hist(df: pd.DataFrame, col: str, log_x: bool = False, title: str | None = None) -> "plt.Figure":
    """Histogram + KDE for one numeric column."""
    s = df[col].dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.histplot(s, kde=True, ax=ax, color="#4c72b0")
    if log_x and (s > 0).all():
        ax.set_xscale("log")
        ax.set_xlabel(f"{col} (log scale)")
    else:
        ax.set_xlabel(col)
    ax.set_title(title or f"Distribution of {col} (observed, n={len(s):,})")
    fig.tight_layout()
    return fig


def plot_top_categories(df: pd.DataFrame, top_n: int = 15) -> "plt.Figure":
    """Horizontal bar of the most common top category affinities."""
    top = df["category_affinity_top"].dropna().value_counts().head(top_n)
    fig, ax = plt.subplots(figsize=(8, max(3, 0.42 * len(top))))
    ax.barh(top.index[::-1], top.values[::-1], color="#55a868")
    ax.set_xlabel("customers")
    ax.set_title(f"Top {len(top)} category affinities (observed; {len(df) - len(df.dropna(subset=['category_affinity_top'])):,} missing)")
    fig.tight_layout()
    return fig


def plot_state_bar(df: pd.DataFrame, top_n: int = 10) -> "plt.Figure":
    """Vertical bar of customer counts by state."""
    vc = df["state"].value_counts().head(top_n)
    fig, ax = plt.subplots(figsize=(7, 4))
    vc.plot(kind="bar", ax=ax, color="#8172b2")
    ax.set_ylabel("customers")
    ax.set_title(f"Customers by state — top {len(vc)} (observed)")
    fig.tight_layout()
    return fig


def plot_retention_heatmap(retention: pd.DataFrame) -> "plt.Figure":
    """Cohort retention heatmap (rows=cohort, cols=months since first order)."""
    data = retention.set_index("cohort_month")
    data = data[data.columns[: min(13, len(data.columns))]]
    fig, ax = plt.subplots(figsize=(11, max(4, 0.5 * len(data) + 1)))
    sns.heatmap(data, annot=True, fmt="g", cmap="YlGnBu", cbar_kws={"label": "% of cohort"}, ax=ax)
    ax.set_title("Cohort retention (%) — months since first order (observed)")
    fig.tight_layout()
    return fig


def plot_monthly_activity(summary: pd.DataFrame) -> "plt.Figure":
    """Two-panel monthly activity: orders + revenue (observed)."""
    s = summary.set_index("month")
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    axes[0].bar(s.index, s["n_orders"], color="#4c72b0")
    axes[0].set_ylabel("orders")
    axes[0].set_title("Monthly purchased orders (observed Olist data)")
    axes[1].plot(s.index, s["revenue"], marker="o", color="#55a868")
    axes[1].set_ylabel("revenue (R$)")
    axes[1].set_title("Monthly revenue (observed Olist data)")
    for ax in axes:
        ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def plot_rfm_segments(seg: pd.DataFrame) -> "plt.Figure":
    """Horizontal bar of RFM segment sizes."""
    s = seg.set_index("rfm_segment")["n_customers"].sort_values()
    fig, ax = plt.subplots(figsize=(7, max(3, 0.45 * len(s))))
    ax.barh(s.index, s.values, color="#4c72b0")
    ax.set_xlabel("customers")
    ax.set_title("RFM segments (observed; frequency bands due to ~94% one-time buyers)")
    for i, v in enumerate(s.values):
        ax.text(v + 400, i, f"{v:,}", va="center", fontsize=8)
    fig.tight_layout()
    return fig


def plot_channel_exposure(exposure: pd.DataFrame, title: str = "Simulated exposure rate by channel (sim preview)") -> "plt.Figure":
    """Bar of exposed % per channel for the SIMULATED preview."""
    s = exposure.set_index("channel")["pct_exposed"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.bar(s.index, s.values, color="#4c72b0")
    ax.set_ylabel("% exposed")
    ax.set_ylim(0, max(60, s.max() * 1.25))
    ax.set_title(title)
    for i, v in enumerate(s.values):
        ax.text(i, v + 0.8, f"{v:g}%", ha="center", fontsize=9)
    fig.tight_layout()
    return fig


def plot_naive_conversion(naive: pd.DataFrame) -> "plt.Figure":
    """Grouped bar: conversion among exposed vs unexposed (SIMULATED, descriptive)."""
    fig, ax = plt.subplots(figsize=(7.5, 4))
    width = 0.38
    x = range(len(naive))
    ax.bar([i - width / 2 for i in x], naive["conv_exposed_pct"], width, label="exposed", color="#55a868")
    ax.bar([i + width / 2 for i in x], naive["conv_unexposed_pct"], width, label="unexposed", color="#c44e52")
    ax.set_xticks(list(x))
    ax.set_xticklabels(naive["channel"])
    ax.set_ylabel("conversion % in 14-day window")
    ax.set_title("Simulated conversion by exposure — descriptive ONLY, confounded (not causal)")
    ax.legend()
    fig.tight_layout()
    return fig