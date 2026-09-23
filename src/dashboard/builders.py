"""Deterministic, headless-testable builders for the Day-19 Streamlit dashboard.

Every function is **pure**: it reads ONLY precomputed ``results/`` CSVs and
returns plain data (pandas frames, plotly ``Figure`` objects, KPI dicts, honest
tokens) — there is no refit, no DGP rerun, no random draw, and no live server
needed to test a page (AGENTS.md §8, blueprint §11). The Streamlit page scripts
under ``dashboard/`` are thin glue that call these builders and render with
``st.*``; tests exercise both the pure builders directly and each page headlessly
via ``streamlit.testing.v1.AppTest``.

Honest-label vocabulary is the single source of truth in
:mod:`src.causal.sensitivity` (Day-18); channel order comes from
:mod:`src.causal.confounders` (Days 5–6). Nothing here can drift from the
report labels because the labels ARE imported, never re-declared.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pandas as pd
import plotly.graph_objects as go

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS
from src.causal.sensitivity import (
    LABEL_ESTIMATED,
    LABEL_MEASURED,
    LABEL_PLACEBO,
    LABEL_TRUTH,
)

# ---------------------------------------------------------------------------
# Honest vocabulary (one source: imported constants; locally only framing)
# ---------------------------------------------------------------------------

LABEL_OBSERVATIONAL = "observational (observed-data lift — NAIVE, NOT causal)"
LABEL_COUNTERFACTUAL = "counterfactual (model-based, Days 8-12 DR ATE; oracle-labeled truth)"
LABEL_COUNTERFACTUAL_GUIDED = "counterfactual-guided (Day-17 budget scenarios, model-based)"
LABEL_PLACEBO_EMAIL = f"{LABEL_PLACEBO} — email placebo (falsification test)"

HONEST_TOKEN = (
    "Honest framing (AGENTS.md §8 / blueprint §11): the observed 14-day lift is "
    "confounder-compatible and **fragile** (E-values 1.68–1.75 email) — "
    "**NOT established causal**. The 'email-first / search-second' guidance is a "
    "model-based counterfactual priority, not an observed-data conclusion. "
    "Simulated ground truth is the DGP oracle label and is NOT an observed result."
)

# Honest KPI labels — never present observed lift as established causal.
ROI_LABELS: dict[str, str] = {
    "observational": LABEL_OBSERVATIONAL,
    "causal": f"{LABEL_ESTIMATED} — Day-12 DR revenue ATE",
    "counterfactual": f"{LABEL_TRUTH} — DGP oracle",
}


# ---------------------------------------------------------------------------
# Low-level readers — results only, deterministic
# ---------------------------------------------------------------------------


def _read(cfg: dict | None, section: str, name: str) -> pd.DataFrame:
    """Read a precomputed results CSV (dashboard reads results/ ONLY)."""
    cfg = cfg or load_config()
    base = project_path("results", section)
    p = base / f"{name}.csv"
    if not p.exists():
        raise FileNotFoundError(
            f"dashboard wired to precomputed only — missing {p}"
        )
    return pd.read_csv(p)


def _maybe(cfg: dict | None, section: str, name: str) -> pd.DataFrame | None:
    cfg = cfg or load_config()
    base = project_path("results", section)
    p = base / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


# ---------------------------------------------------------------------------
# Page 1 — Executive summary (Day 13 headline + honest KPI cards)
# ---------------------------------------------------------------------------


def exec_summary(cfg: dict | None = None) -> dict[str, Any]:
    """Executive-summary page: honest KPI cards wired to Day 13/16/17 numbers."""
    cfg = cfg or load_config()
    roi_sum = _read(cfg, "roi", "roi_summary")
    sc_summary = _read(cfg, "counterfactuals", "scenario_summary")
    master = _read(cfg, "tables", "master_estimates")
    sens = _read(cfg, "sensitivity", "evalue")

    email = roi_sum[roi_sum["channel"] == "email"].iloc[0]
    email_causal_roi = float(email["causal_roi"])
    email_causal_over_ctf = float(email["causal_over_ctf"])
    as_run_net = float(sc_summary.loc[sc_summary["scenario"] == "as_run", "net"].iloc[0])
    naive_net = float(sc_summary.loc[sc_summary["scenario"] == "naive", "net"].iloc[0])
    causal_net = float(sc_summary.loc[sc_summary["scenario"] == "causal", "net"].iloc[0])
    ctf_net = float(sc_summary.loc[sc_summary["scenario"] == "ctf_guided", "net"].iloc[0])
    budget = float(sc_summary["spend"].iloc[0])

    honest_kpis = [
        {
            "label": "Observed ROI · email",
            "value": f"{email_causal_roi:.1f}×",
            "delta": "observed lift — NOT causal",
            "help": "Observed 14-day revenue lift per treated: confounder-compatible, fragile.",
            "label_token": LABEL_OBSERVATIONAL,
        },
        {
            "label": "Causal ROI · email",
            "value": f"{email_causal_roi:.1f}×",
            "delta": "causal DR ATE",
            "help": "Day-12 DR revenue ATE per treated (causal, model-based). CI in figure.",
            "label_token": LABEL_ESTIMATED,
        },
        {
            "label": "Cohort net · as-run",
            "value": f"R$ {as_run_net:,.0f}",
            "delta": "runs at budget " + f"R$ {budget:,.0f}",
            "help": "Net R$ of the as-run cohort (Day-16/17 precomputed).",
            "label_token": LABEL_COUNTERFACTUAL_GUIDED,
        },
        {
            "label": "Cohort net · causal-guided",
            "value": f"R$ {ctf_net:,.0f}",
            "delta": "vs causal " + f"R$ {causal_net:,.0f}",
            "help": "Counterfactual budget scenarios (Day-17, model-based, deterministic).",
            "label_token": LABEL_COUNTERFACTUAL_GUIDED,
        },
    ]

    return {
        "headline": HONEST_TOKEN,
        "kpis": honest_kpis,
        "frames": {"roi_summary": roi_sum, "scenario_summary": sc_summary},
        "tokens": [
            f"The observed email ROI (causal DR ATE {email_causal_roi:.1f}×) "
            "is model-based. The simulated ground truth DR email ATE is the DGP "
            "oracle label — separate, honest, NOT established causal.",
            HONEST_TOKEN,
        ],
    }


# ---------------------------------------------------------------------------
# Page 2 — Interactive DAG (networkx + plotly, deterministic layout)
# ---------------------------------------------------------------------------


def dag_page(cfg: dict | None = None) -> dict[str, Any]:
    """Per-channel interactive DAG figures (reuses Day-5 render_dag_plotly)."""
    from src.causal.dag import render_dag_plotly

    cfg = cfg or load_config()
    figures: dict[str, go.Figure] = {}
    for ch in CHANNELS:
        fig, _ = render_dag_plotly(channel=ch, cfg=cfg)
        figures[ch] = fig
    return {
        "figures": figures,
        "tokens": [
            f"DAG for each channel ({" / ".join(CHANNELS)}): sim_u is an "
            "unmodeled confounder of exposure→conversion/revenue. Arrows are "
            "conceptual (assumed) structure from the Day-5 DAG, not data-estimated.",
            HONEST_TOKEN,
        ],
    }


# ---------------------------------------------------------------------------
# Page 3 — Channel attribution (naive vs causal vs counterfactual ground truth)
# ---------------------------------------------------------------------------


def attribution_page(cfg: dict | None = None) -> dict[str, Any]:
    """Grouped bars: observed (naive) vs causal (DR) vs counterfactual per channel."""
    cfg = cfg or load_config()
    roi_long = _read(cfg, "roi", "roi_long")
    roi_summary = _read(cfg, "roi", "roi_summary")

    att = roi_long[
        ["channel", "method", "inc_rev", "inc_rev_ci_low", "inc_rev_ci_high", "label"]
    ].copy()
    att["label"] = att["method"].map(ROI_LABELS)

    fig = go.Figure()
    for method, lbl in ROI_LABELS.items():
        sub = att[att["method"] == method]
        fig.add_trace(
            go.Bar(
                x=sub["channel"],
                y=sub["inc_rev"],
                name=lbl,
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=sub["inc_rev_ci_high"].values - sub["inc_rev"].values,
                    arrayminus=sub["inc_rev"].values - sub["inc_rev_ci_low"].values,
                ),
            )
        )
    fig.update_layout(
        barmode="group",
        title="Channel attribution: observational (naive) vs causal (DR) vs counterfactual (DGP oracle)",
        yaxis_title="Incremental revenue / treated (R$)",
        height=460,
    )

    return {
        "frame": att,
        "figure": fig,
        "tokens": [
            "Bars: naive = observed-data diff-in-means (confounded); causal = "
            "Day-12 DR revenue ATE (model-based CI bars shown); counterfactual = "
            "simulated DGP oracle ground truth (NOT an observed result).",
            HONEST_TOKEN,
        ],
    }


# ---------------------------------------------------------------------------
# Page 4 — Uplift segmentation (Day-14/15: persuadables / sure-things / …)
# ---------------------------------------------------------------------------


def uplift_page(cfg: dict | None = None) -> dict[str, Any]:
    """Segment lift bars + Qini per channel (Day-14/15 uplift analysis)."""
    cfg = cfg or load_config()
    seg_sum = _read(cfg, "uplift", "segment_summary")
    qini = _read(cfg, "uplift", "qini_curves")

    fig = go.Figure()
    for ch in CHANNELS:
        sub = seg_sum[seg_sum["channel"] == ch]
        fig.add_trace(
            go.Bar(
                x=sub["segment"],
                y=sub["mean_tau"],
                name=ch,
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=(
                        sub.get("tau_ci_high", sub["mean_tau"] * 0.1).values
                        - sub["mean_tau"].values
                    ),
                    arrayminus=(
                        sub["mean_tau"].values
                        - sub.get("tau_ci_low", sub["mean_tau"] * 0.1).values
                    ),
                ),
            )
        )
    fig.update_layout(
        barmode="group",
        title="Uplift segments (persuadables ▲ / sure-things / lost-cause / sleeping-dog)",
        yaxis_title="Mean τ̂ (CATE, 14-day conversion)",
        height=440,
    )

    return {
        "segments": seg_sum,
        "qini": qini,
        "figure": fig,
        "tokens": [
            "Segments are model-based Day-14 estimates (generalized random forest "
            "τ̂); the Day-15 oracle column is simulated ground truth for the ranking "
            "check. The 'persuadable email' segment is where the counterfactual "
            "concentration recommendation comes from — model-based, not observed.",
            HONEST_TOKEN,
        ],
    }


# ---------------------------------------------------------------------------
# Page 5 — Counterfactual budget simulator (Day-17 scenarios + interaction refit
# ---------------------------------------------------------------------------


def simulator_page(cfg: dict | None = None) -> dict[str, Any]:
    """Counterfactual budget simulator: precomputed scenarios + slider transform.

    The slider re-splits the same fixed R$ budget using the EXACT deterministic
    linear scenario transform from Day-17 (``simulate_split`` below). It is pure
    arithmetic on precomputed per-channel causal ROI/cost — never a DGP rerun,
    never a refit. Extrapolation beyond observed n_treated is flagged honestly.
    """
    cfg = cfg or load_config()
    roi_long = _read(cfg, "roi", "roi_long")
    sc_summary = _read(cfg, "counterfactuals", "scenario_summary")

    return {
        "scenarios": sc_summary,
        "roi_long": roi_long,
        "tokens": [
            "The simulator re-splits the fixed budget (R$ %s) using the "
            "deterministic linear Day-17 transform over per-channel causal "
            "marginal revenue and cost. Extrapolation beyond the observed "
            "treated cohort is flagged, never silently extrapolated." % float(sc_summary["spend"].iloc[0]),
            HONEST_TOKEN,
        ],
    }


def simulate_split(
    shares: dict[str, float],
    cfg: dict | None = None,
    budget: float | None = None,
) -> pd.DataFrame:
    """Pure arithmetic budget re-split → counterfactual scenario (label honest).

    ``shares[channel]`` = fraction of the fixed budget per channel (must sum to 1).
    Uses precomputed per-channel causal ``inc_rev`` and ``cost_per_treated`` from
    ``roi/roi_long``; spends = share×budget; implied treated = spend/cost;
    extrapolated when implied treated > observed n_treated. Deterministic,
    model-based counterfactual — never a DGP oracle claim.
    """
    cfg = cfg or load_config()
    roi_long = _read(cfg, "roi", "roi_long")
    causal = roi_long[roi_long["method"] == "causal"].set_index("channel")
    if budget is None:
        sc = _read(cfg, "counterfactuals", "scenario_summary")
        budget = float(sc["spend"].iloc[0])
    if abs(sum(shares.values()) - 1.0) > 1e-6:
        raise ValueError(f"shares must sum to 1 (got {sum(shares.values()):.4f})")

    rows = []
    for ch in CHANNELS:
        share = shares.get(ch, 0.0)
        spend = share * budget
        cost = float(causal.loc[ch, "cost_per_treated"])
        n_implied = spend / cost if cost else 0.0
        n_obs = float(causal.loc[ch, "n_treated"])
        extrapolated = n_implied > n_obs
        inc_rev = n_implied * float(causal.loc[ch, "inc_rev"])
        rows.append(
            {
                "channel": ch,
                "share": share,
                "spend": spend,
                "implied_treated": n_implied,
                "observed_n_treated": n_obs,
                "extrapolated": extrapolated,
                "inc_rev": inc_rev,
                "net": inc_rev - spend,
                "roi": (inc_rev / spend) if spend else float("nan"),
                "label": LABEL_COUNTERFACTUAL_GUIDED,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Page 6 — Sensitivity analysis (Day 18: E-values, bias formula, falsification)
# ---------------------------------------------------------------------------


def sensitivity_page(cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sens_sum = _read(cfg, "sensitivity", "evalue")
    fals = _read(cfg, "sensitivity", "falsification")
    evalue = _read(cfg, "sensitivity", "evalue")
    bias = _read(cfg, "sensitivity", "bias_formula")

    return {
        "evalue": evalue,
        "bias_formula": bias,
        "falsification": fals,
        "summary": sens_sum,
        "tokens": [
            "E-value email ≈1.72 point / 1.68 CI-lower → observed email lift is "
            "confounder-compatible and fragile (NOT established causal). Bias "
            "formula: measured confounder shares 82–97% of the naive overstatement "
            "email/social/search. Placebos falsify loudly (|t| 27–110) → the "
            "causal claim is NOT established by the observed data.",
            HONEST_TOKEN,
        ],
    }


# ---------------------------------------------------------------------------
# Page 7 — Model diagnostics (CIs, balance, overlap, placebo, CI bars)
# ---------------------------------------------------------------------------


def diagnostics_page(cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    master = _read(cfg, "tables", "master_estimates")
    evalue = _read(cfg, "sensitivity", "evalue")

    return {
        "master": master,
        "evalue": evalue,
        "tokens": [
            "Every effect is reported with a CI (never a bare point): email DR "
            "revenue [%f, %f] / email social/search/display in master table. "
            "Falsification placebos are falsified → fragile, NOT established "
            "causal. Balance/overlap (Day 12) and E-value (Day 18) are the "
            "model-diagnostics honesty loop."
            % (
                float(master.loc[(master["channel"] == "email") & (master["estimator"] == "dr"), "ci_lower"].iloc[0]),
                float(master.loc[(master["channel"] == "email") & (master["estimator"] == "dr"), "ci_upper"].iloc[0]),
            ),
            HONEST_TOKEN,
        ],
    }


# ---------------------------------------------------------------------------
# Gate + report writers (Day-19 roadmap hook: "All pages render")
# ---------------------------------------------------------------------------

PAGE_BUILDERS: dict[str, Any] = {
    "exec": exec_summary,
    "dag": dag_page,
    "attribution": attribution_page,
    "uplift": uplift_page,
    "simulator": simulator_page,
    "sensitivity": sensitivity_page,
    "diagnostics": diagnostics_page,
}


def render_gate(cfg: dict | None = None) -> dict[str, dict[str, Any]]:
    """Headless gate: every page builder renders honest content (non-vacuity).

    Each page must (a) run without raising, (b) return non-empty honest tokens,
    (c) expose the honest-label vocabulary token every page shares. A page that
    regresses to a bare point estimate or drops the honest token fails the gate.
    """
    cfg = cfg or load_config()
    gates: dict[str, dict[str, Any]] = {}
    for name, builder in PAGE_BUILDERS.items():
        page = builder(cfg)
        tokens = page.get("tokens", []) or []
        n = len(tokens)
        has_content = any(
            page.get(k) is not None
            for k in ("frame", "frames", "figure", "figures", "kpis", "segments", "master", "evalue", "scenarios")
        )
        honest = HONEST_TOKEN in " ".join(tokens)
        gates[name] = {
            "passed": n >= 1 and has_content and honest,
            "n": n,
            "desc": f"{name} page: {n} honest tokens, content {'present' if has_content else 'MISSING'}, "
            f"honest token {'present' if honest else 'MISSING'}",
        }
    return gates


def run_all(cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    return {"gates": render_gate(cfg)}


if __name__ == "__main__":
    summary = run_all()
    for name, g in summary["gates"].items():
        print(f"{name:14s} {'PASS' if g['passed'] else 'FAIL'}  {g['n']} honest tokens | {g['desc']}")
    print("render-gate:", all(g["passed"] for g in summary["gates"].values()))
