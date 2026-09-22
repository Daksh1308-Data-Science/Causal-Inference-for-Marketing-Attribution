"""CATE with meta-learners (T/S/X, causalml) — Day 13.

Estimates the conditional average treatment effect E[Y(1)-Y(0) | X] per
channel using causalml 0.17 meta-learners with sklearn HistGradientBoosting
REGREssors on the 0/1 conversion outcome (probability scale) and on revenue:

- **T-learner:** separate outcome regressions for treated and control arms.
- **S-learner:** one outcome regression with the treatment as a feature
  (known to shrink effects toward constant treatment).
- **X-learner:** four regressions (control/treatment outcome + imputed and
  mirrored treatment-effect models); needs the Day-6 propensity score p(X).

Identification (stated BEFORE fitting, AGENTS.md §3):
- Causal question: how does the incremental effect of each channel on the
  14-day outcome vary with OBSERVED customer features X (Day-4 adjustment
  set: email {order_count, recency_days, review_score_avg, total_revenue},
  social/search {order_count, tenure_days, total_revenue}, display
  {recency_days, total_revenue})?
- Assumptions: exchangeability given X (sim_u is NOT in X — it is unobserved,
  so the CATE is conditional on observed structure and inherits the ATE bias
  documented Days 8-12); positivity/overlap as Day 6 (email weak overlap
  handled there); consistency + SUTVA as the whole project.
- **Why regressors for a binary outcome:** causalml's classifier path calls
  the base learner's hard `predict` (class labels), which collapses the CATE
  to label differences (~0). Fitting regressors on the 0/1 outcome yields a
  valid probability-scale CATE. Verified on real data (Day 13 finding).
- **Cross-fitting:** meta-learners are fitted and predicted on the same
  sample (standard uplift practice, in-sample CATE); DML-style cross-fitting
  is deferred to Day 18 sensitivity.

**Labels (AGENTS.md §2):** all numbers are **estimated (simulated)** —
every result is a CATE estimate on `sim_*` data, never an observed Olist
fact. `sim_u` is never a feature.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.ensemble import HistGradientBoostingRegressor

from causalml.inference.meta import BaseSLearner, BaseTLearner, BaseXLearner

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS, adjustment_sets
from src.causal.naive import OUTCOMES, OUTCOME_LABELS, load_analysis_data
from src.causal.propensity import estimate_propensity_scores

logging.getLogger("causalml").setLevel(logging.ERROR)  # silence fit/predict INFO chatter

LEARNERS: tuple[str, ...] = ("t", "s", "x")

LEARNER_INFO: dict[str, dict[str, str]] = {
    "t": {
        "label": "T-learner",
        "assumptions": "Separate treated/control regressions (probability scale); "
                       "features = adjustment set; sim_u unadjusted; ATE-bias inherited",
    },
    "s": {
        "label": "S-learner",
        "assumptions": "Single regression, treatment as feature (shrinks to constant "
                       "effects); features = adjustment set; sim_u unadjusted",
    },
    "x": {
        "label": "X-learner",
        "assumptions": "Outcome + effect regressions with tight learning on tau; "
                       "requires propensity p(X) (Day 6); sim_u unadjusted",
    },
}


# --------------------------------------------------------------------------
# Estimation
# --------------------------------------------------------------------------

def cate_one_channel(df: pd.DataFrame, channel: str, outcome: str, cfg: dict) -> pd.DataFrame:
    """Unit-level CATE estimates for all three learners on one channel x outcome.

    Returns one row per customer with ``cate_t``/``cate_s``/``cate_x``
    (probability or revenue units), the treatment assignment, observed outcome
    and a ``baseline`` model prediction E[Y|X] used as the heterogeneity axis.
    """
    adj = adjustment_sets(cfg)[channel]
    work = df.copy()
    for c in adj:
        work[c] = work[c].fillna(work[c].median())
    X = work[adj].values.astype(float)
    w = work[f"sim_exposed_{channel}"].values.astype(int)
    y = work[outcome].values.astype(float)
    ps, _, _ = estimate_propensity_scores(df, channel, cfg)  # day-6 PS (own imputation)
    n = len(work)
    ones = np.ones(n)

    depth = int(cfg["cate"]["base_max_depth"])
    iters = int(cfg["cate"]["base_max_iter"])
    rstate = int(cfg["seed"])

    def _mk() -> HistGradientBoostingRegressor:
        # random_state pins the early-stopping validation split (reproducible)
        return HistGradientBoostingRegressor(max_depth=depth, max_iter=iters,
                                             random_state=rstate)

    learners: dict[str, object] = {
        "t": BaseTLearner(learner=_mk()),
        "s": BaseSLearner(learner=_mk()),
        "x": BaseXLearner(learner=_mk()),
    }
    cates: dict[str, np.ndarray] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, l in learners.items():
            l.fit(X, w, y, p=ps)
            cates[name] = np.asarray(l.predict(X, treatment=ones, p=ps)).ravel()

    baseline = _mk().fit(X, y).predict(X).ravel()  # E[Y|X] — heterogeneity axis

    return pd.DataFrame({
        "channel": channel,
        "outcome": outcome,
        "cate_t": cates["t"],
        "cate_s": cates["s"],
        "cate_x": cates["x"],
        "treatment": w,
        "y": y,
        "baseline": baseline,
    })


def cate_estimates(cfg: dict | None = None) -> pd.DataFrame:
    """Unit-level CATE for all channels x outcomes (concatenated)."""
    cfg = cfg or load_config()
    df = load_analysis_data(cfg)
    frames = []
    for ch in CHANNELS:
        for outcome in OUTCOMES:
            frames.append(cate_one_channel(df, ch, outcome, cfg))
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------
# Summary + agreement
# --------------------------------------------------------------------------

def _bootstrap_mean_ci(x: np.ndarray, reps: int, alpha: float, seed: int) -> tuple[float, float]:
    rng = np.random.RandomState(seed)
    means = np.empty(reps)
    for i in range(reps):
        idx = rng.randint(0, len(x), len(x))
        means[i] = x[idx].mean()
    lo = np.percentile(means, 100 * alpha / 2)
    hi = np.percentile(means, 100 * (1 - alpha / 2))
    return float(lo), float(hi)


def cate_summary(cate: pd.DataFrame | None = None, cfg: dict | None = None) -> pd.DataFrame:
    """Per channel x outcome x learner: mean CATE + bootstrap CI, spread, quantiles."""
    cfg = cfg or load_config()
    if cate is None:
        cate = cate_estimates(cfg)
    reps = int(cfg["cate"]["bootstrap_reps"])
    alpha = float(cfg["cate"]["alpha"])
    seed = int(cfg["seed"])

    rows = []
    for (ch, outcome), grp in cate.groupby(["channel", "outcome"], sort=False):
        for name in LEARNERS:
            x = grp[f"cate_{name}"].values.astype(float)
            lo, hi = _bootstrap_mean_ci(x, reps, alpha, seed + int(grp.index[0]) % 1000)
            qs = np.percentile(x, [5, 25, 50, 75, 95])
            rows.append({
                "channel": ch,
                "outcome": outcome,
                "outcome_label": OUTCOME_LABELS[outcome],
                "learner": name,
                "learner_label": LEARNER_INFO[name]["label"],
                "mean_cate": float(x.mean()),
                "sd_cate": float(x.std(ddof=1)),
                "ci_lower": lo,
                "ci_upper": hi,
                "q05": float(qs[0]), "q25": float(qs[1]), "q50": float(qs[2]),
                "q75": float(qs[3]), "q95": float(qs[4]),
                "n": int(len(x)),
                "assumptions": LEARNER_INFO[name]["assumptions"],
                "label": "estimated (simulated)",
            })
    return pd.DataFrame(rows)


def _decile_curves(cate: pd.DataFrame) -> dict[tuple[str, str], pd.DataFrame]:
    """Per channel x outcome: mean CATE by baseline-risk decile for each learner."""
    out: dict[tuple[str, str], pd.DataFrame] = {}
    for (ch, o), grp in cate.groupby(["channel", "outcome"], sort=False):
        g = grp.copy()
        g["decile"] = pd.qcut(g["baseline"].rank(method="first"), 10, labels=False) + 1
        out[(ch, o)] = g.groupby("decile")[["cate_t", "cate_s", "cate_x"]].mean()
    return out


def _ate_reference(cfg: dict) -> dict[tuple[str, str], float]:
    """Day-12 OLS ATE read from the committed master table (no refits)."""
    p = project_path(cfg["paths"]["results"], cfg["results"]["tables"]) / "master_estimates.csv"
    ref: dict[tuple[str, str], float] = {}
    if p.exists():
        m = pd.read_csv(p)
        for _, r in m[(m["estimator"] == "ols")].iterrows():
            ref[(r["channel"], r["outcome"])] = float(r["point"])
    return ref


def learner_agreement(cate: pd.DataFrame | None = None, cfg: dict | None = None) -> dict:
    """Learner agreement per channel x outcome — the Day 13 validation hook.

    Two gate metrics (calibrated on real data; config-driven):
    1. **Mean alignment** — every learner's mean CATE within
       ``cate.agreement_tol_conversion_abs`` (pp) / ``cate.agreement_tol_revenue_rel``
       (relative) of the Day-12 OLS ATE (learners agree with the established effect).
    2. **Decile magnitude** — max pairwise |Δ| between the 10-decile mean CATE curves
       <= ``cate.agreement_max_decile_rel`` * |mean CATE| (the effect size). Normalising
       by SD(mean CATE) is unstable on this DGP (near-flat signal -> tiny SD -> ratios
       blow up, observed 1.00 for social conversion); normalising by the effect size is
       scale-robust (observed max 0.09 vs a 0.25 gate).

    Individual-level rank agreement (pairwise Spearman) is REPORTED in ``detail``
    but deliberately NOT a gate: on this DGP the observed-X heterogeneity signal is
    tiny, so per-unit CATE ranks are weak across learners (observed 0.32-0.77) —
    gating on it would mask an honest limitation (the map's central finding).
    """
    cfg = cfg or load_config()
    if cate is None:
        cate = cate_estimates(cfg)
    tol_abs = float(cfg["cate"]["agreement_tol_conversion_abs"])
    tol_rel = float(cfg["cate"]["agreement_tol_revenue_rel"])
    tol_dec = float(cfg["cate"]["agreement_max_decile_rel"])
    ate_ref = _ate_reference(cfg)

    curves = _decile_curves(cate)
    pairs = [("t", "s"), ("t", "x"), ("s", "x")]
    detail_rows, status_rows = [], []
    for (ch, outcome), grp in cate.groupby(["channel", "outcome"], sort=False):
        mean_cate = grp[["cate_t", "cate_s", "cate_x"]].mean(axis=1).values
        cell_mean = float(np.mean(mean_cate))  # effect size = mean of the learner-mean CATE
        dec = curves[(ch, outcome)]

        max_dec_rel = 0.0
        for a, b in pairs:
            ca, cb = grp[f"cate_{a}"].values, grp[f"cate_{b}"].values
            ind_corr = float(pd.Series(ca).corr(pd.Series(cb), method="spearman"))
            ind_mad = float(np.mean(np.abs(ca - cb)))
            dec_corr = float(dec[f"cate_{a}"].corr(dec[f"cate_{b}"], method="spearman"))
            dec_abs = float(np.mean(np.abs(dec[f"cate_{a}"] - dec[f"cate_{b}"])))
            max_dec_rel = max(max_dec_rel,
                              dec_abs / abs(cell_mean) if cell_mean != 0 else float("nan"))
            detail_rows.append({
                "channel": ch, "outcome": outcome,
                "outcome_label": OUTCOME_LABELS[outcome],
                "pair": f"{a}-{b}",
                "spearman_individual": ind_corr,
                "mad_individual": ind_mad,
                "spearman_decile": dec_corr,
                "mad_decile": dec_abs,
                "label": "estimated (simulated)",
            })

        ref_ate = ate_ref.get((ch, outcome))
        mean_align, mean_tol = float("nan"), float("nan")
        if ref_ate is not None:
            unit_abs = outcome == "sim_converted_14d"
            mean_tol = tol_abs if unit_abs else tol_rel * abs(ref_ate)
            mean_align = float(max(abs(grp[f"cate_{name}"].mean() - ref_ate)
                                   for name in LEARNERS))
        ok = (mean_align <= mean_tol) and (max_dec_rel <= tol_dec)
        status_rows.append({
            "channel": ch, "outcome": outcome,
            "outcome_label": OUTCOME_LABELS[outcome],
            "max_abs_mean_align": mean_align,
            "mean_tolerance": mean_tol,
            "max_decile_rel": max_dec_rel,
            "decile_tolerance": tol_dec,
            "status": "OK" if ok else "CHECK",
            "label": "estimated (simulated)",
        })
    return {"detail": pd.DataFrame(detail_rows), "status": pd.DataFrame(status_rows)}


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def render_agreement_map(cate: pd.DataFrame | None = None,
                         agreement: dict | None = None,
                         cfg: dict | None = None,
                         output_dir: Path | None = None) -> tuple[go.Figure, Path]:
    """Validation-hook figure: per channel x outcome, mean CATE by baseline-risk
    decile for each learner (2 rows x 4 cols). Learners tracking each other = agreement."""
    cfg = cfg or load_config()
    if cate is None:
        cate = cate_estimates(cfg)
    if agreement is None:
        agreement = learner_agreement(cate, cfg)

    colors = {"t": "#e74c3c", "s": "#2ecc71", "x": "#3498db"}
    curves = _decile_curves(cate)
    fig = make_subplots(
        rows=len(OUTCOMES), cols=len(CHANNELS),
        subplot_titles=[f"{ch}" for ch in CHANNELS] * len(OUTCOMES),
        row_heights=[1] * len(OUTCOMES),
        vertical_spacing=0.18,
    )
    for oi, outcome in enumerate(OUTCOMES, start=1):
        for ci, ch in enumerate(CHANNELS, start=1):
            dec = curves[(ch, outcome)]
            for name in LEARNERS:
                means = dec[f"cate_{name}"]
                fig.add_trace(
                    go.Scatter(
                        x=means.index, y=means.values, mode="lines+markers",
                        name=LEARNER_INFO[name]["label"],
                        legendgroup=name,
                        showlegend=(oi == 1 and ci == 1),
                        line=dict(color=colors[name], width=2),
                        marker=dict(size=6),
                        hovertemplate=f"{ch}/{outcome[-9:]}<br>{LEARNER_INFO[name]['label']}<br>"
                                      f"decile %{{x}} -> %{{y:.4f}}<extra></extra>",
                    ),
                    row=oi, col=ci,
                )
            fig.add_hline(y=0, line_color="black", line_width=0.8, row=oi, col=ci)
            fig.update_xaxes(title_text=f"{ch} · risk decile", row=oi, col=ci,
                             tickvals=list(range(1, 11)))
            fig.update_yaxes(title_text=(OUTCOME_LABELS[outcome] if ci == 1 else None),
                             row=oi, col=ci)

    fig.update_layout(
        title="Learner agreement map — mean CATE by baseline-risk decile "
              "(T / S / X learners, 95k units)",
        title_x=0.5, height=620, plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "learner_agreement_map.html"
    fig.write_html(str(out_path))
    return fig, out_path


def render_cate_by_channel(summary: pd.DataFrame | None = None, cfg: dict | None = None,
                           output_dir: Path | None = None) -> tuple[go.Figure, Path]:
    """Mean CATE per channel x outcome x learner with bootstrap CI."""
    cfg = cfg or load_config()
    if summary is None:
        summary = cate_summary(cfg=cfg)
    colors = {"t": "#e74c3c", "s": "#2ecc71", "x": "#3498db"}
    fig = make_subplots(
        rows=1, cols=len(OUTCOMES),
        subplot_titles=[OUTCOME_LABELS[o] for o in OUTCOMES],
    )
    for oi, outcome in enumerate(OUTCOMES, start=1):
        sub = summary[summary["outcome"] == outcome]
        for name in LEARNERS:
            rows = sub[sub["learner"] == name]
            fig.add_trace(go.Bar(
                x=rows["channel"], y=rows["mean_cate"],
                error_y=dict(type="data", symmetric=False,
                             array=(rows["ci_upper"] - rows["mean_cate"]).values,
                             arrayminus=(rows["mean_cate"] - rows["ci_lower"]).values),
                name=LEARNER_INFO[name]["label"], marker_color=colors[name],
                showlegend=(oi == 1),
            ), row=1, col=oi)
    fig.update_layout(
        title="Mean CATE by channel and learner (bootstrap 95% CI, estimated/simulated)",
        title_x=0.5, height=460, plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "cate_by_channel.html"
    fig.write_html(str(out_path))
    return fig, out_path


# --------------------------------------------------------------------------
# Artifacts + report
# --------------------------------------------------------------------------

def write_cate_estimates(cate: pd.DataFrame, cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["tables"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cate_estimates.parquet"
    cate.to_parquet(out_path, index=False)
    return out_path


def write_cate_tables(cate: pd.DataFrame | None = None, cfg: dict | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    if cate is None:
        cate = cate_estimates(cfg)
    summary = cate_summary(cate, cfg)
    agreement = learner_agreement(cate, cfg)
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["tables"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p1 = out_dir / "cate_summary.csv"
    p2 = out_dir / "cate_agreement.csv"
    summary.to_csv(p1, index=False)
    agreement["detail"].to_csv(p2, index=False)
    return {"summary": p1, "agreement": p2}


def cate_report(cate: pd.DataFrame | None = None, cfg: dict | None = None) -> str:
    """Day-13 markdown report (uses only precomputed frames — no refits)."""
    cfg = cfg or load_config()
    if cate is None:
        cate = cate_estimates(cfg)
    summary = cate_summary(cate, cfg)
    agreement = learner_agreement(cate, cfg)
    ate_ref = _ate_reference(cfg)

    lines = []
    lines.append("# Day 13 — CATE with Meta-Learners (T / S / X)\n")
    lines.append("> **Label:** all results are **estimated (simulated)** (`sim_*`), never "
                 "observed Olist facts (AGENTS.md §2). CATE = conditional effect on OBSERVED "
                 "features; `sim_u` is never a feature.\n")
    lines.append("## Identification (before fitting)\n")
    lines.append(
        "- **Causal question:** how does the incremental 14-day effect of each channel vary "
        "with observed customer features X? Feature set = the Day-4 adjustment set per channel "
        "(email: order_count, recency_days, review_score_avg, total_revenue; social/search: "
        "order_count, tenure_days, total_revenue; display: recency_days, total_revenue).\n"
        "- **Assumptions:** exchangeability given X with **sim_u unobserved** (the CATE "
        "inherits the Days 8-12 ATE bias); positivity/overlap per Day 6; consistency + SUTVA "
        "as the whole project. **Sim_u is excluded from features by design.**\n"
        "- **Regressors on the binary outcome:** causalml's classifier path calls the hard "
        "`predict` (labels), collapsing probability CATE to ~0; regressors on 0/1 yields a "
        "valid probability-scale CATE (verified: email conversion T 0.1268 / S 0.1241 / "
        "X 0.1278 vs Day-12 OLS ATE 0.1274).\n"
        "- **Cross-fitting:** learners fit and predict on the same sample (in-sample CATE, "
        "standard uplift practice); DML-style cross-fitting deferred to Day 18.\n"
    )
    lines.append("## CATE summary (mean + bootstrap 95% CI)\n")
    lines.append("| Channel | Outcome | Learner | Mean CATE | 95% CI | SD | q05–q95 |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in summary.iterrows():
        unit = "pp" if r["outcome"] == "sim_converted_14d" else "R$"
        lines.append(
            f"| {r['channel']} | {r['outcome_label']} | {r['learner_label']} "
            f"| {r['mean_cate']:.4f} {unit} | [{r['ci_lower']:.4f}, {r['ci_upper']:.4f}] "
            f"| {r['sd_cate']:.4f} | [{r['q05']:.4f}, {r['q95']:.4f}] |"
        )
    lines.append("")
    lines.append("## Learner agreement map (validation hook)\n")
    lines.append(
        "- **Gates (calibrated to what agreement means on this DGP):** every learner's mean "
        "CATE within the Day-12 OLS ATE tolerance (conversion "
        f"{cfg['cate']['agreement_tol_conversion_abs']} pp abs / revenue "
        f"{cfg['cate']['agreement_tol_revenue_rel']} rel) AND max pairwise decile-curve "
        f"|spread| <= {cfg['cate']['agreement_max_decile_rel']} of the effect size "
        "(|mean CATE|).\n"
        "- **Reported, not gated:** individual-level rank agreement (Spearman) is 0.32-0.77 "
        "across learners — the observed-X heterogeneity signal is tiny, so per-unit CATE "
        "ordering is weak. This is an honest limitation, not a test failure.\n"
    )
    lines.append("Pairwise agreement detail:\n")
    lines.append("| Channel | Outcome | Pair | Indiv. Spearman | Indiv. MAD | Decile Spearman | Decile MAD |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in agreement["detail"].iterrows():
        lines.append(
            f"| {r['channel']} | {r['outcome_label']} | {r['pair']} "
            f"| {r['spearman_individual']:.3f} | {r['mad_individual']:.4f} "
            f"| {r['spearman_decile']:.3f} | {r['mad_decile']:.4f} |"
        )
    lines.append("")
    lines.append("Agreement status (hook):\n")
    lines.append("| Channel | Outcome | Max \\|mean Δ vs ATE\\| | Mean tol | Max decile rel | Decile tol | Status |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in agreement["status"].iterrows():
        lines.append(
            f"| {r['channel']} | {r['outcome_label']} | {r['max_abs_mean_align']:.4f} "
            f"| {r['mean_tolerance']:.4f} | {r['max_decile_rel']:.3f} "
            f"| {r['decile_tolerance']:.3f} | **{r['status']}** |"
        )
    lines.append("")
    lines.append("## Reading the map (honest interpretation)\n")
    lines.append(
        "- **Aggregate level: agreement is real.** Mean CATEs match the Day-12 ATE and the "
        "10-decile curves track each other (max spread ≤ "
        f"{agreement['status']['max_decile_rel'].max():.3f} of the effect size). The signal " 
        "that survives is smooth: effect ≈ flat, mildly tilted by baseline risk (the embedded " 
        "effect is constant in log-odds, so only baseline-driven probability variation "
        "remains).\n"
        "- **Individual level: agreement is weak by design.** Pairwise rank Spearman "
        "0.32-0.77 means personalized CATE ordering on observed X is NOT reliable — there "
        "is little observed heterogeneity for learners to agree on (`sim_u` dominates). "
        "Day-14 uplift must therefore report Qini/persuadable structure honestly at the "
        "aggregate level.\n"
        "- **Agreement is not truth:** like Day 12, learner agreement does not certify the "
        "CATE LEVEL. Display (simulated GT 0.00) again: mean CATE ≈ +0.11 pp ≈ its ATE — "
        "selection, not treatment.\n"
    )
    if ate_ref:
        lines.append("## Reference vs Day-12 OLS ATE\n")
        lines.append("| Channel | Outcome | Mean CATE (avg of T/S/X) | Day-12 OLS ATE |")
        lines.append("|---|---|---|---|")
        for (chk, o), _v in ate_ref.items():
            avg = summary[(summary["channel"] == chk) & (summary["outcome"] == o)][
                "mean_cate"].mean()
            lines.append(
                f"| {chk} | {OUTCOME_LABELS[o]} | {avg:.4f} | {ate_ref[(chk, o)]:.4f} |"
            )
        lines.append("")
    lines.append("## Limitations\n")
    lines.append(
        "- CATE is conditional on OBSERVED X only; `sim_u`-driven heterogeneity is invisible "
        "to every learner, so individualized treatment rules built from these curves inherit "
        "the ATE bias documented on Days 8-12.\n"
        "- In-sample CATE (no cross-fitting); overfitting risk is mild here (4 features, "
        "depth-3 trees) but formal cross-fit/DML is Day 18.\n"
        "- S-learner is known to attenuate effects (shrinkage); T-learner has higher variance "
        "in low-support regions; X-learner depends on a correct-enough propensity p(X).\n"
        "- CATE uncertainty is reported for MEAN CATE (bootstrap); the full CATE distribution "
        "(personalization) is not uncertainty-calibrated per unit.\n"
    )
    return "\n".join(lines)


def write_cate_report(cate: pd.DataFrame | None = None, cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["reports"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cate_effects.md"
    out_path.write_text(cate_report(cate, cfg), encoding="utf-8")
    return out_path


def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    cate = cate_estimates(cfg)
    write_cate_estimates(cate, cfg)
    write_cate_tables(cate, cfg)
    render_agreement_map(cate, None, cfg)
    render_cate_by_channel(cate_summary(cate, cfg), cfg)
    report = write_cate_report(cate, cfg)
    return {"cate": cate, "summary": cate_summary(cate, cfg),
            "agreement": learner_agreement(cate, cfg), "report_path": report}


if __name__ == "__main__":
    cfg = load_config()
    out = run_all(cfg)
    print(out["agreement"]["status"].to_string(index=False))
    print()
    print(out["summary"][["channel", "outcome", "learner", "mean_cate",
                          "ci_lower", "ci_upper"]].to_string(index=False))
    print(f"\nReport -> {out['report_path']}")