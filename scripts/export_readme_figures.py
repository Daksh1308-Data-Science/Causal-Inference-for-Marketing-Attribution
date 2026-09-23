"""Export static PNG snapshots of the key results for the README gallery.

Day-21 follow-up: GitHub cannot render the interactive plotly ``.html`` figures
inside Markdown, so this script renders the same numbers (read only from
precomputed ``results/*.csv`` — never recomputing models) as deterministic
matplotlib PNGs under ``results/figures/readme_*.png``.

Single sources of truth:
- DAG structure: ``src.causal.dag.build_dag_graph`` (shared with the plotly DAG).
- All numbers: the committed result tables (master_estimates, roi_summary,
  scenario_summary, evalue, uplift/qini_curves, sensitivity/bias_formula).

Deterministic: fixed ```seed: 42``-style layout seed and DPI; matplotlib has no
other randomness. Run with the project venv:

    .venv\\Scripts\\python -X utf8 scripts/export_readme_figures.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo-root bootstrap (scripts are run as files, not modules)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib

matplotlib.use("Agg")  # headless-only

import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.causal.dag import build_dag_graph  # noqa: E402
from src.config import load_config, project_path  # noqa: E402

DPI = 150  # raster export resolution (cosmetic, not a pipeline tunable)
PALETTE = {
    "estimated": "#3498db",
    "counterfactual": "#e74c3c",
    "ci": "#5dade2",
    "truth": "#e67e22",
}

CHANNELS = ["email", "social", "search", "display"]
ESTIMATORS = ["naive", "ols", "ipw", "dr", "att_matched", "dowhy_backdoor"]
ESTIMATOR_LABELS = ["Naive", "OLS", "IPW", "DR", "ATT", "DoWhy"]


def _figures_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    out = project_path("results", "figures")
    out.mkdir(parents=True, exist_ok=True)
    return out


def _read(section: str, name: str, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    return pd.read_csv(project_path("results", section) / f"{name}.csv")


# ---------------------------------------------------------------------------
# 1. DAG (email) — networkx + matplotlib, same graph as the interactive HTML
# ---------------------------------------------------------------------------


def export_dag_email(out_dir: Path, cfg: dict) -> Path:
    """Render the email causal DAG as a static PNG (sim_u confounder visible)."""
    G = build_dag_graph("email", cfg)
    pos = nx.spring_layout(G, k=2.5, iterations=200, seed=42)
    # Cosmetic nudges mirroring src/causal/dag.py's plotly renderer
    pos["Treatment"] = np.array([0.0, 0.0])
    pos["Outcome"] = np.array([2.0, 0.0])
    pos["Revenue"] = np.array([3.5, 0.0])
    pos["U"] = np.array([0.0, 2.0])
    confounders = [n for n, d in G.nodes(data=True) if d.get("role") == "confounder"]
    for i, c in enumerate(confounders):
        pos[c] = np.array([-2.0, 0.5 + i * 0.5])
    pos["Click"] = np.array([1.0, -1.5])
    pos["CoExposure"] = np.array([1.0, 1.5])

    role_colors = {
        "treatment": "#e74c3c",
        "outcome": "#2ecc71",
        "outcome_secondary": "#27ae60",
        "confounder": "#3498db",
        "unobserved_confounder": "#e67e22",
        "mediator": "#f39c12",
        "collider": "#9b59b6",
    }

    fig, ax = plt.subplots(figsize=(10, 7), dpi=DPI)
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        ax.annotate(
            "", xy=(x1, y1), xytext=(x0, y0),
            arrowprops=dict(arrowstyle="->", color="#888", lw=1.4,
                            shrinkA=14, shrinkB=14),
        )
    for node, (x, y) in pos.items():
        data = G.nodes[node]
        color = role_colors.get(data.get("role", "other"), "#95a5a6")
        ax.scatter(x, y, s=1800, color=color, edgecolors="white", linewidths=2, zorder=3)
        ax.text(x, y + 0.12, data.get("label", node), ha="center", va="center",
                fontsize=8, zorder=4, fontweight="bold")

    ax.set_title("Causal DAG — email\n"
                 "sim_u (unobserved intent) confounds exposure and outcome",
                 fontsize=12)
    ax.set_xlim(-3.2, 4.5)
    ax.set_ylim(-2.4, 2.9)
    ax.axis("off")
    fig.tight_layout()
    path = out_dir / "readme_dag_email.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 2. Estimator convergence vs counterfactual truth (revenue ATE)
# ---------------------------------------------------------------------------


def export_convergence_revenue(out_dir: Path, cfg: dict) -> Path:
    """Six observed-data estimators per channel vs the oracle truth (R$)."""
    master = _read("tables", "master_estimates", cfg)
    truth = _read("sensitivity", "bias_formula", cfg)[["channel", "truth"]]
    master = master[master["outcome"] == "sim_revenue_14d"].merge(
        truth, on="channel", how="left"
    )

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=DPI, sharey=True)
    for ax, channel in zip(axes.ravel(), CHANNELS):
        rows = master[master["channel"] == channel]
        if rows.empty:
            ax.set_visible(False)
            continue
        rows = rows.set_index("estimator").loc[ESTIMATORS]
        ax.axhline(rows["truth"].iloc[0], color=PALETTE["truth"], ls="--", lw=1.6,
                   label="oracle truth (simulated)")
        yerr = np.array([
            rows["point"].to_numpy() - rows["ci_lower"].to_numpy(),
            rows["ci_upper"].to_numpy() - rows["point"].to_numpy(),
        ])
        colors = [PALETTE["estimated"]] * len(rows)
        ax.bar(range(len(rows)), rows["point"], yerr=yerr, capsize=4,
               color=colors, alpha=0.85, error_kw=dict(elinewidth=1.2, ecolor=PALETTE["ci"]))
        ax.set_xticks(range(len(rows)))
        ax.set_xticklabels(ESTIMATOR_LABELS, fontsize=8, rotation=20)
        ax.set_title(f"{channel}  (truth = R$ {rows['truth'].iloc[0]:,.1f})",
                     fontsize=10)
        ax.axhline(0, color="black", lw=0.6)
        ax.tick_params(axis="y", labelsize=8)
    fig.suptitle("Six confounded estimators agree — all miss the oracle truth\n"
                 "14-day revenue ATE (R$ per treated, 95% CI)", fontsize=12)
    axes[0, 0].legend(loc="upper left", fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    path = out_dir / "readme_convergence_revenue.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 3. Causal ROI vs counterfactual ROI (symlog, CI whiskers)
# ---------------------------------------------------------------------------


def export_roi(out_dir: Path, cfg: dict) -> Path:
    """Estimated causal ROI (95% CI) vs counterfactual truth ROI per channel."""
    roi = _read("roi", "roi_summary", cfg)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=DPI)
    x = np.arange(len(roi))
    causal = roi["causal_roi"].to_numpy()
    ctf = roi["ctf_roi"].to_numpy()
    yerr = np.array([
        causal - roi["causal_roi_ci_low"].to_numpy(),
        roi["causal_roi_ci_high"].to_numpy() - causal,
    ])
    ax.bar(x - 0.19, causal, width=0.38, yerr=yerr, capsize=4,
           color=PALETTE["estimated"], alpha=0.85,
           error_kw=dict(elinewidth=1.2, ecolor=PALETTE["ci"]),
           label="causal ROI (estimated, 95% CI)")
    ax.bar(x + 0.19, ctf, width=0.38, color=PALETTE["counterfactual"], alpha=0.9,
           label="counterfactual ROI (simulated truth)")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_yscale("symlog", linthresh=100)
    ax.set_xticks(x)
    ax.set_xticklabels(roi["channel"], fontsize=10)
    ax.set_ylabel("ROI (R$ per R$ 1 invested, % — symlog scale)")
    ax.set_title("Estimated causal ROI flatters every channel\n"
                 "vs the counterfactual truth: email/search profit, social/display destroy value",
                 fontsize=11)
    ax.legend(fontsize=9, loc="upper left")
    for i, v in enumerate(ctf):
        ax.annotate(f"{v:+,.0f}%", (x[i] + 0.19, v), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=8, color=PALETTE["counterfactual"])
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = out_dir / "readme_roi.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 4. Budget scenarios (net after spend; estimated-scale CI as annotation)
# ---------------------------------------------------------------------------


def export_scenarios(out_dir: Path, cfg: dict) -> Path:
    """Scenario nets on the fixed R$ 77,215 budget; estimated-scale CI annotated."""
    sc = _read("counterfactuals", "scenario_summary", cfg)
    order = ["as_run", "naive", "causal", "ctf_guided"]
    sc = sc.set_index("scenario").loc[order].reset_index()
    optimum = 288438.0  # budget-constrained optimum (counterfactual, from Day 17)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=DPI)
    x = np.arange(len(sc))
    colors = [PALETTE["estimated"] if s != "as_run" else "#95a5a6" for s in sc["scenario"]]
    bars = ax.bar(x, sc["net"], color=colors, alpha=0.9, width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(sc["scenario"], fontsize=10)
    ax.set_ylabel("Net after spend (R$)")
    ax.set_title("Fixed R$ 77,215 budget — any reallocation beats as-run\n"
                 "and approaches the R$ 288,438 counterfactual optimum",
                 fontsize=11)
    ax.axhline(0, color="black", lw=0.8)
    for i, (net, lo, hi, scenario) in enumerate(
        zip(sc["net"], sc["net_est_ci_low"], sc["net_est_ci_high"], sc["scenario"])
    ):
        bar = bars[i]
        ax.annotate(f"R$ {net:,.0f}", (x[i], net), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=9, fontweight="bold")
        if scenario != "as_run":
            ax.annotate(f"est. 95% CI [{lo/1e6:,.2f}–{hi/1e6:,.2f}M]",
                        (x[i], net), textcoords="offset points", xytext=(0, -18),
                        ha="center", fontsize=7, color="#555")
        else:
            ax.annotate("(drift + systemic scatter)", (x[i], net),
                        textcoords="offset points", xytext=(0, -18), ha="center",
                        fontsize=7, color="#555")
    ax.axhline(optimum, color=PALETTE["truth"], ls="--", lw=1.6,
               label=f"optimum R$ {optimum:,.0f} (unreachable by observed rules)")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = out_dir / "readme_scenarios.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 5. E-value fragility
# ---------------------------------------------------------------------------


def export_evalue(out_dir: Path, cfg: dict) -> Path:
    """E-value per channel: how strong must the unmeasured confounder be?"""
    ev = _read("sensitivity", "evalue", cfg)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=DPI)
    x = np.arange(len(ev))
    ax.bar(x, ev["evalue_point"], width=0.55, color=PALETTE["estimated"], alpha=0.85,
           label="E-value (point estimate)")
    ax.scatter(x, ev["evalue_ci_lower"], color=PALETTE["counterfactual"], zorder=5,
               s=40, label="E-value (CI lower bound)")
    ax.axhline(1.7, color=PALETTE["truth"], ls="--", lw=1.6,
               label="RR ≈ 1.7 explains the whole observed lift")
    ax.set_xticks(x)
    ax.set_xticklabels(ev["channel"], fontsize=10)
    ax.set_ylabel("E-value (risk ratio scale)")
    ax.set_ylim(0, max(ev["evalue_point"].max(), 2.0) * 1.15)
    ax.set_title("Fragility: a moderate unmeasured confounder (RR ≈ 1.7) fully\n"
                 "explains away every observed channel effect", fontsize=11)
    for i, (p, lo) in enumerate(zip(ev["evalue_point"], ev["evalue_ci_lower"])):
        ax.annotate(f"{p:.2f}", (x[i], p), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=9, fontweight="bold")
        ax.annotate(f"CI {lo:.2f}", (x[i], lo), textcoords="offset points",
                    xytext=(0, -14), ha="center", fontsize=7, color="#555")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = out_dir / "readme_evalue.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 6. Qini — observed ranking fails to recover true incremental lift
# ---------------------------------------------------------------------------


def export_qini_email(out_dir: Path, cfg: dict) -> Path:
    """Qini curves for email conversion: estimated uplift ranks vs oracle."""
    q = _read("uplift", "qini_curves", cfg)
    q = q[(q["channel"] == "email") & (q["outcome"] == "sim_converted_14d")]

    fig, ax = plt.subplots(figsize=(8.5, 5.5), dpi=DPI)
    for strategy, style, color, label in [
        ("uplift", "--", PALETTE["estimated"], "uplift τ̂ (estimated, from observed X)"),
        ("oracle", "-", PALETTE["counterfactual"], "oracle true lift (simulated truth)"),
    ]:
        subset = q[q["strategy"] == strategy].sort_values("x_population_share")
        if subset.empty:
            continue
        ax.plot(subset["x_population_share"] * 100, subset["y_cum_incremental"],
                style, color=color, lw=2, label=label)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Population share targeted (%)")
    ax.set_ylabel("Cumulative incremental conversions (pp)")
    ax.set_title("Email Qini — observed X ranks the confounded signal,\n"
                 "not the true incremental lift", fontsize=11)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = out_dir / "readme_qini_email.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------


def export_all(cfg: dict | None = None) -> dict[str, Path]:
    """Export every README gallery figure and return name -> path."""
    cfg = cfg or load_config()
    out_dir = _figures_dir(cfg)
    return {
        "readme_dag_email.png": export_dag_email(out_dir, cfg),
        "readme_convergence_revenue.png": export_convergence_revenue(out_dir, cfg),
        "readme_roi.png": export_roi(out_dir, cfg),
        "readme_scenarios.png": export_scenarios(out_dir, cfg),
        "readme_evalue.png": export_evalue(out_dir, cfg),
        "readme_qini_email.png": export_qini_email(out_dir, cfg),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="only print output paths")
    args = parser.parse_args()

    paths = export_all()
    for name, path in paths.items():
        print(f"{name}: {path} ({path.stat().st_size / 1e3:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())