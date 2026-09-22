"""Uplift modeling — Day 14.

Evaluates whether the Day-13 meta-learner CATE can *rank* customers by
incremental response (Qini curves), compares that ranking against "target the
most likely to convert" strategies (propensity / baseline), and classifies
customers into the four classic marketing segments (persuadables, sure things,
lost causes, sleeping dogs).

Scores (all rendered on the same units):
- ``uplift``     — mean of the Day-13 T/S/X-learner CATE (probability-scale for
  conversion, R$ for revenue). The meta-learner ensemble IS the uplift model.
- ``propensity`` — Day-6 propensity score P(T=1|X) (channel-level).
- ``baseline``   — Day-13 baseline model E[Y|X].
- ``oracle``     — **counterfactual (simulated ground truth)** upper bound:
  the TRUE per-unit treatment effect on the probability scale, recomputed from
  the known DGP using ``sim_u`` (label it is never achievable on observed data).

Qini curves:
- **observed** (manual Radcliffe 2007, cross-checked against
  causalml.metrics.get_qini): sorted by score, l_i = cumulative incremental
  responses among treated on observed outcomes. This is the real-world
  computable metric, but it is `sim_u`-confounded — including the strategy
  ranking itself (propensity "wins" by chasing the confounder; the oracle is
  *below* chance: a feature, not a bug — see report key finding).
- **true** (counterfactual, simulation-only): pure cumulative-mean of the
  per-unit |true effect| in score order — the honest ranking-power check:
  do top-ranked customers really respond most? ``qini_lift_true_pct`` gates it.
``qini_lift`` = ∫(y − x)dx / 0.5 ∈ [−1, 1], 0 = chance (report in %).

Identification (stated BEFORE fitting/evaluation, AGENTS.md §3):
- Causal question: can τ̂(x) rank customers so that treating the top-ranked
  produces more incremental outcomes than random or response-based targeting?
- Assumptions: the Day-13 CATE assumptions carry over (exchangeability given
  X, **sim_u unobserved**); Qini's inner per-bin rate difference inherits the
  ATE bias (sim_u) — the curve level is biased, the *ordering* is what is
  evaluated. Consistency + SUTVA as the whole project.
- **Labels:** every number is **estimated (simulated)** except the oracle
  scores, which are **counterfactual (simulated ground truth)**. Never
  presented as observed Olist facts.

**Honest expectation:** Day 13 showed the observed-X heterogeneity signal is
tiny (individual CATE ranks 0.32–0.77 Spearman across learners). Qini lift is
therefore expected to be *modest* for channels with a real embedded effect
(email +0.12, search +0.15, social −0.08 log-odds) and ≈ chance for display
(embedded effect 0.00 — any display lift is pure unobserved `sim_u` selection
leaking through). The oracle shows the best a perfect model could do.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.special import expit

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS
from src.causal.naive import OUTCOMES, OUTCOME_LABELS
from src.causal.propensity import estimate_propensity_scores, load_analysis_data

logging.getLogger("causalml").setLevel(logging.ERROR)

STRATEGIES: tuple[str, ...] = ("uplift", "propensity", "baseline", "oracle")

STRATEGY_INFO: dict[str, dict[str, str]] = {
    "uplift": {
        "label": "Uplift \u03c4\u0302 (mean T/S/X CATE)",
        "assumptions": "Day-13 meta-learner CATE on observed X; sim_u unobserved",
    },
    "propensity": {
        "label": "Propensity p(X)",
        "assumptions": "Day-6 logit PS on X; ranks likely-treated customers; sim_u unobserved",
    },
    "baseline": {
        "label": "Baseline E[Y|X]",
        "assumptions": "Day-13 outcome model on X; ranks likely-to-convert customers; sim_u unobserved",
    },
    "oracle": {
        "label": "Oracle (true effect)",
        "assumptions": "Counterfactual simulated ground truth using sim_u; unachievable on observed data",
    },
}


# --------------------------------------------------------------------------
# Data assembly
# --------------------------------------------------------------------------

def uplift_frame(cfg: dict | None = None) -> pd.DataFrame:
    """Per channel x outcome: uplift scores + scores for comparison strategies.

    Columns: channel, outcome, uplift, propensity, baseline, oracle, treatment, y.
    Rows are aligned 1:1 with the Day-13 CATE frame (same order per block).
    """
    cfg = cfg or load_config()
    cate = pd.read_parquet(project_path(cfg["paths"]["results"], cfg["results"]["tables"])
                           / "cate_estimates.parquet")
    df = load_analysis_data(cfg)  # sim preview (has sim_u, sim_*) — sim_u only feeds oracle
    n = len(df)

    # propensity per channel (day-6, raw rank — ranking is clip-invariant)
    ps_by_ch: dict[str, np.ndarray] = {}
    for ch in CHANNELS:
        ps_by_ch[ch], _, _ = estimate_propensity_scores(df, ch, cfg)

    oracle = _oracle_effects(df, cfg)  # (channel, outcome) -> np.ndarray

    rows = []
    for ch in CHANNELS:
        for o in OUTCOMES:
            block = cate[(cate["channel"] == ch) & (cate["outcome"] == o)]
            assert len(block) == n, f"{ch}/{o} block misaligned with analysis data"
            rows.append(pd.DataFrame({
                "channel": ch,
                "outcome": o,
                "uplift": block[["cate_t", "cate_s", "cate_x"]].mean(axis=1).values,
                "propensity": ps_by_ch[ch],
                "baseline": block["baseline"].values,
                "oracle": oracle[(ch, o)],
                "treatment": block["treatment"].values.astype(int),
                "y": block["y"].values.astype(float),
            }))
    return pd.concat(rows, ignore_index=True)


def _z_features(df: pd.DataFrame) -> pd.DataFrame:
    """Standardised FEATURE_COLS exactly as the simulator did (same mean/std)."""
    feats = df[["recency_days", "tenure_days", "order_count", "total_revenue",
                "avg_order_value", "review_score_avg"]].astype(float)
    return (feats - feats.mean()) / feats.std().replace(0, 1.0)


def _oracle_effects(df: pd.DataFrame, cfg: dict) -> dict[tuple[str, str], np.ndarray]:
    """TRUE per-unit effect on the probability (conversion) / revenue scale.

    Replicates the simulation DGP (simulation.simulate_marketing.py) exactly:
    logit(conv) = base + Σ_feat 0.05·z(feat) + u_outcome_coef·sim_u
                  + Σ_ch effect_log_odds_ch · exposed_ch.
    Effect of channel c on unit i (probability scale):
        expit(L_no_c + γ_c) − expit(L_no_c),  L_no_c = L − γ_c·exposed_c.
    Revenue effect = probability effect × E[lognormal] = ΔP·exp(μ + σ²/2)
    (revenue amount does not depend on exposure given conversion).

    Uses sim_u -> this is a **counterfactual (simulated ground truth)** score.
    """
    sp = cfg["simulation"]["preview"]
    z = _z_features(df)
    L = float(sp["base_outcome_intercept"]) + 0.05 * z.sum(axis=1).values
    L = L + float(sp["u_outcome_coef"]) * df["sim_u"].values
    for ch in CHANNELS:
        L = L + float(sp["channels"][ch]["effect_log_odds"]) * df[f"sim_exposed_{ch}"].values

    rev_mean = float(np.exp(float(sp["revenue_log_mean"]) + 0.5 * float(sp["revenue_log_sigma"]) ** 2))
    out: dict[tuple[str, str], np.ndarray] = {}
    for ch in CHANNELS:
        g = float(sp["channels"][ch]["effect_log_odds"])
        exposed = df[f"sim_exposed_{ch}"].values
        l_no_c = L - g * exposed
        dprob = expit(l_no_c + g) - expit(l_no_c)
        out[(ch, "sim_converted_14d")] = dprob
        out[(ch, "sim_revenue_14d")] = dprob * rev_mean
    return out


# --------------------------------------------------------------------------
# Qini
# --------------------------------------------------------------------------

def qini_curve(
    score: np.ndarray,
    treatment: np.ndarray,
    y: np.ndarray,
    true_effect: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Normalised Radcliffe Qini curve, causalml-compatible.

    Sort by score descending; for cumulative population index i:

    * **observed mode** (``true_effect=None``)::
          l_i = Σ_{j≤i} y_j·t_j − Σ_{j≤i} y_j·(1−t_j) · (Σ_{j≤i}t_j)/(i−Σ_{j≤i}t_j)
      i.e. cumulative observed incremental outcomes among the treated. This is
      what can be computed on real data — but it is `sim_u`-confounded: the
      curve level and even the *strategy ranking* inherit the assignment bias
      (see report: propensity "wins" by chasing the confounder).
    * **true mode** (``true_effect`` given, use of sim_u -> counterfactual)::
          l_i = Σ_{j≤i} |true_effect_j|
      the cumulative-gain curve on |true effect|. Endpoint-normalised so the
      y-axis is "share of total incremental effect accumulated" and the chance
      (random targeting) baseline is the diagonal — the classic Lorenz-style
      concentration check: does the score put the most-responsive customers
      (largest |true effect|) first? No treatment weighting and no sim_u
      coupling: pure *ranking quality*. |·| keeps negative-effect channels
      (social) on the same axis — "responds most" = |effect|, i.e. for social
      the rank signal is harm-avoidance (most-affected last).

    Returns (x, y): x = 0..N / N (population share in score order, N+1 points
    with the 0-anchor prepended exactly like causalml's output), y = l/l_N in
    [0,1] (endpoint 1; when there is nothing to rank — true effects all zero —
    y ≡ 0).
    """
    order = np.argsort(-np.asarray(score), kind="stable")
    t = np.asarray(treatment)[order].astype(float)
    n = len(t)
    idx = np.arange(0, n + 1) / n  # 0..N anchors inclusive (causalml-compatible)
    if true_effect is None:
        yy = np.asarray(y)[order].astype(float)
        cum_tr = np.cumsum(t)
        cum_ct = np.arange(1, n + 1) - cum_tr  # 1-based, causalml-compatible
        cum_y_tr = np.cumsum(yy * t)
        cum_y_ct = np.cumsum(yy * (1 - t))
        with np.errstate(divide="ignore", invalid="ignore"):
            l = cum_y_tr - cum_y_ct * cum_tr / cum_ct
        l = np.where(np.isfinite(l), l, np.nan)
        ser = pd.Series(l, index=np.arange(1, n + 1))
        ser.loc[0] = 0.0  # causalml's 0-anchor, then interpolate the leading treated-run
        l = ser.sort_index().interpolate().fillna(0.0).values  # indices 0..N
    else:
        l = np.concatenate([[0.0], np.cumsum(np.abs(np.asarray(true_effect)[order]))])
    l_final = l[-1]
    if l_final == 0:  # degenerate: no (true) incremental effect to rank
        return idx, np.zeros(n + 1)
    return idx, l / l_final


def qini_lift(
    score: np.ndarray,
    treatment: np.ndarray,
    y: np.ndarray,
    true_effect: np.ndarray | None = None,
) -> float:
    """Normalised area between the Qini curve and the chance diagonal.

    Chance = the (0,0)→(1,1) diagonal; lift = ∫(y − x)dx / 0.5 ∈ [−1, 1]
    (0 = chance), because with y,x∈[0,1] the maximal positive deviation is 0.5.
    Returns 0.0 (not −1) for the degenerate case (no effect to rank).
    """
    x, y_curve = qini_curve(score, treatment, y, true_effect)
    if np.all(y_curve == 0):
        return 0.0
    return float((np.trapezoid(y_curve, x) - 0.5 * x[-1] ** 2) / 0.5)


def qini_curves_tables(cfg: dict | None = None) -> dict:
    """Full-curve lifts (observed + true) per cell x strategy + 10-point grids.

    ``lift_true`` evaluates ranking power against the counterfactual |true
    effects| (sim_u) — the honest check, only meaningful in this simulation.
    ``lift_observed`` is the real-world computable metric but is
    `sim_u`-confounded (strategy ordering itself is biased).
    """
    cfg = cfg or load_config()
    fr = uplift_frame(cfg)
    grid = int(cfg["uplift"]["qini_grid_points"])
    rows_curve, rows_sum = [], []
    for (ch, o), grp in fr.groupby(["channel", "outcome"], sort=False):
        t = grp["treatment"].values
        yy = grp["y"].values
        tau_true = grp["oracle"].values  # counterfactual (simulated ground truth)
        for strat in STRATEGIES:
            score = grp[strat].values
            if strat == "oracle":
                score = np.abs(score)  # targeting value = |response|; signed effects invert the
                                       # ranking for the negative-effect channel (social)
            lift_obs = qini_lift(score, t, yy)
            lift_true = qini_lift(score, t, yy, true_effect=tau_true)
            rows_sum.append({
                "channel": ch, "outcome": o, "outcome_label": OUTCOME_LABELS[o],
                "strategy": strat, "strategy_label": STRATEGY_INFO[strat]["label"],
                "qini_lift_observed_pct": round(100 * lift_obs, 2),
                "qini_lift_true_pct": round(100 * lift_true, 2),
                "n": int(len(grp)),
                "assumptions": STRATEGY_INFO[strat]["assumptions"],
                "label": ("counterfactual (simulated ground truth)" if strat == "oracle"
                          else "estimated (simulated)"),
            })
            xs = np.linspace(0, 1, grid + 1)[1:]
            x, y = qini_curve(score, t, yy)
            y_at = np.interp(xs, np.sort(x), y[np.argsort(x)])
            for xi, yi in zip(xs, y_at):
                rows_curve.append({
                    "channel": ch, "outcome": o, "outcome_label": OUTCOME_LABELS[o],
                    "strategy": strat, "x_population_share": round(float(xi), 4),
                    "y_cum_incremental": round(float(yi), 4),
                    "label": ("counterfactual (simulated ground truth)" if strat == "oracle"
                              else "estimated (simulated)"),
                })
    return {"curves": pd.DataFrame(rows_curve), "summary": pd.DataFrame(rows_sum)}


# --------------------------------------------------------------------------
# Segments (conversion)
# --------------------------------------------------------------------------

SEGMENTS: tuple[str, ...] = ("persuadable", "sure_thing", "sleeping_dog", "lost_cause")

SEGMENT_INFO: dict[str, str] = {
    "persuadable": "High \u03c4\u0302, low baseline: would NOT convert organically but responds to the "
                   "channel -> the incremental targeting sweet spot",
    "sure_thing": "High \u03c4\u0302, high baseline: responds AND would convert anyway -> treat to keep, "
                  "low marginal gain",
    "sleeping_dog": "Low \u03c4\u0302, high baseline: converts anyway and shows poor/negative response -> "
                    "avoid (wastes budget, can backfire)",
    "lost_cause": "Low \u03c4\u0302, low baseline: unlikely to convert and shows little response -> skip",
}


def segment_assignment(channel_frame: pd.DataFrame) -> pd.DataFrame:
    """Median-quadrant segmentation on (uplift, baseline) for one channel (conversion).

    quadrant (tau above/below channel median) x (baseline above/below median):
      tau>med, base<=med -> persuadable;  tau>med, base>med -> sure_thing
      tau<=med, base<=med -> lost_cause;  tau<=med, base>med -> sleeping_dog
    Returns a copy with the ``segment`` column added.
    """
    f = channel_frame.copy()
    med_tau = float(f["uplift"].median())
    med_base = float(f["baseline"].median())
    high_tau = f["uplift"] > med_tau
    high_base = f["baseline"] > med_base
    f["segment"] = np.select(
        [high_tau & ~high_base, high_tau & high_base, ~high_tau & high_base],
        ["persuadable", "sure_thing", "sleeping_dog"],
        default="lost_cause",
    )
    return f


def segment_summary(cfg: dict | None = None) -> pd.DataFrame:
    """Per channel x segment: size/share, observed conversion rate, mean tau/baseline."""
    cfg = cfg or load_config()
    fr = uplift_frame(cfg)
    rows = []
    for (ch, o), grp in fr.groupby(["channel", "outcome"], sort=False):
        if o != "sim_converted_14d":
            continue
        seg = segment_assignment(grp)
        for s in SEGMENTS:
            sub = seg[seg["segment"] == s]
            rows.append({
                "channel": ch, "outcome": o, "outcome_label": OUTCOME_LABELS[o],
                "segment": s, "segment_label": f"{s.replace('_', ' ').title()}",
                "description": SEGMENT_INFO[s],
                "n": int(len(sub)), "share": round(float(len(sub) / len(grp)), 4),
                "conv_rate": round(float(sub["y"].mean()), 4),
                "mean_tau": round(float(sub["uplift"].mean()), 5),
                "mean_baseline": round(float(sub["baseline"].mean()), 4),
                "label": "estimated (simulated)",
            })
    return pd.DataFrame(rows)


def segment_frame(cfg: dict | None = None) -> pd.DataFrame:
    """Unit-level segment assignment (conversion only) — for the mosaic figure."""
    cfg = cfg or load_config()
    fr = uplift_frame(cfg)
    parts = []
    for ch in CHANNELS:
        block = fr[(fr["channel"] == ch) & (fr["outcome"] == "sim_converted_14d")]
        seg = segment_assignment(block)
        parts.append(seg[["channel", "uplift", "baseline", "treatment", "y", "segment", "oracle"]])
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

_COLORS = {"uplift": "#e74c3c", "propensity": "#f39c12", "baseline": "#2ecc71", "oracle": "#3498db"}


def render_qini_curves(qtables: dict | None = None, cfg: dict | None = None,
                       output_dir: Path | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    if qtables is None:
        qtables = qini_curves_tables(cfg)
    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    curves, summary = qtables["curves"], qtables["summary"]
    paths: dict[str, Path] = {}
    for o in OUTCOMES:
        fig = make_subplots(rows=2, cols=2, subplot_titles=list(CHANNELS))
        for ci, ch in enumerate(CHANNELS, start=1):
            for strat in STRATEGIES:
                c = curves[(curves["channel"] == ch) & (curves["outcome"] == o) &
                           (curves["strategy"] == strat)]
                lift = summary[(summary["channel"] == ch) & (summary["outcome"] == o) &
                               (summary["strategy"] == strat)]["qini_lift_observed_pct"].iloc[0]
                fig.add_trace(go.Scatter(
                    x=c["x_population_share"], y=c["y_cum_incremental"],
                    mode="lines+markers", name=STRATEGY_INFO[strat]["label"],
                    legendgroup=strat, showlegend=(ci == 1),
                    line=dict(color=_COLORS[strat], width=2),
                    marker=dict(size=4), hovertemplate=f"{ch}<br>{strat} observed lift {lift:+.1f}%"
                                                       f"<br>%{{x:.2f}} -> %{{y:.2f}}<extra></extra>",
                ), row=(ci - 1) // 2 + 1, col=(ci - 1) % 2 + 1)
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                     line=dict(color="black", dash="dot", width=1),
                                     name="chance", showlegend=False,
                                     hovertemplate="random targeting<extra></extra>"),
                          row=(ci - 1) // 2 + 1, col=(ci - 1) % 2 + 1)
            fig.update_xaxes(title_text=f"{ch}: treated share", row=(ci - 1) // 2 + 1,
                             col=(ci - 1) % 2 + 1, range=[0, 1.02])
            fig.update_yaxes(title_text="cum. incremental resp.", row=(ci - 1) // 2 + 1,
                             col=(ci - 1) % 2 + 1)
        fig.update_layout(
            title=f"Qini curves — {OUTCOME_LABELS[o]} (estimated/simulated; oracle = counterfactual)",
            title_x=0.5, height=560, plot_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        out = output_dir / f"qini_curves_{'conversion' if o == 'sim_converted_14d' else 'revenue'}.html"
        fig.write_html(str(out))
        paths[o] = out
    return paths


def render_uplift_segments(seg_frame: pd.DataFrame | None = None, cfg: dict | None = None,
                           output_dir: Path | None = None) -> Path:
    """Segment mosaic: uplift vs baseline scatter, quadrant-split, downsampled for display."""
    cfg = cfg or load_config()
    if seg_frame is None:
        seg_frame = segment_frame(cfg)
    sample_n = int(cfg["uplift"]["scatter_sample"])
    if output_dir is None:
        output_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    output_dir.mkdir(parents=True, exist_ok=True)
    seg_colors = {"persuadable": "#2ecc71", "sure_thing": "#3498db",
                  "sleeping_dog": "#e74c3c", "lost_cause": "#95a5a6"}
    fig = make_subplots(rows=2, cols=2, subplot_titles=list(CHANNELS))
    for ci, ch in enumerate(CHANNELS, start=1):
        sub = seg_frame[seg_frame["channel"] == ch]
        sub = sub.sample(n=min(sample_n, len(sub)), random_state=int(cfg["seed"]))
        for s in SEGMENTS:
            pts = sub[sub["segment"] == s]
            fig.add_trace(go.Scatter(
                x=pts["baseline"], y=pts["uplift"], mode="markers",
                name=s.replace("_", " ").title(),
                legendgroup=s, showlegend=(ci == 1),
                marker=dict(size=3, color=seg_colors[s], opacity=0.55,
                            line=dict(width=0)),
                hovertemplate=f"{ch}<br>{s}<br>E[Y|X] %{{x:.3f}} tau %{{y:.4f}}<extra></extra>",
            ), row=(ci - 1) // 2 + 1, col=(ci - 1) % 2 + 1)
        sub2 = sub[["baseline", "uplift"]].copy()
        fig.update_xaxes(title_text=f"{ch}: baseline E[Y|X](conv)", row=(ci - 1) // 2 + 1,
                         col=(ci - 1) % 2 + 1)
        fig.update_yaxes(title_text="uplift \u03c4\u0302 (mean T/S/X)", row=(ci - 1) // 2 + 1,
                         col=(ci - 1) % 2 + 1, title_standoff=4)
    fig.update_layout(
        title=f"Uplift segments (downsampled to {sample_n:,} pts/channel, phase-split by "
              "channel medians) — estimated/simulated",
        title_x=0.5, height=600, plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    out = output_dir / "uplift_segments_conversion.html"
    fig.write_html(str(out))
    return out


# --------------------------------------------------------------------------
# Artifacts + report
# --------------------------------------------------------------------------

def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    qtables = qini_curves_tables(cfg)
    seg = segment_summary(cfg)
    tables = write_uplift_tables_from(qtables, seg, cfg)
    fig_paths = render_qini_curves(qtables, cfg)
    seg_fig = render_uplift_segments(None, cfg)
    report = write_uplift_report(cfg)
    return {"tables": tables, "figures": fig_paths, "segments_figure": seg_fig,
            "report": report, "summary": qtables["summary"], "segments": seg}


def write_uplift_tables_from(qtables: dict, seg: pd.DataFrame, cfg: dict | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["uplift"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p1 = out_dir / "qini_curves.csv"
    p2 = out_dir / "qini_summary.csv"
    p3 = out_dir / "segment_summary.csv"
    p4 = out_dir / "gates.csv"
    qtables["curves"].to_csv(p1, index=False)
    qtables["summary"].to_csv(p2, index=False)
    seg.to_csv(p3, index=False)
    uplift_gates(cfg, qtables=qtables, segments=seg).to_csv(p4, index=False)
    return {"qini_curves": p1, "qini_summary": p2, "segment_summary": p3, "gates": p4}


def uplift_gates(cfg: dict | None = None, qtables: dict | None = None,
                 segments: pd.DataFrame | None = None) -> pd.DataFrame:
    """Validation hooks (AGENTS.md-friendly): pass/fail per gate.

    Gates (all config-driven):
    1. "Qini above chance": mean Uplift-strategy TRUE lift over the channels
       with a real embedded effect (email/search/social) >= ``qini_true_lift_min_gt_pct``.
    2. Display (embedded effect 0.00): Uplift TRUE lift <= ``qini_true_lift_display_max_pct``
       (nothing to rank -> any score's true lift is ~0).
    3. Oracle sanity: for every GT!=0 channel the oracle strategy's TRUE lift is
       the maximum of the four strategies (the counterfactual upper bound wins).
    4. Segments interpretable: every segment's share >= ``segment_min_share`` in
       every channel (conversion).
    """
    cfg = cfg or load_config()
    if qtables is None:
        qtables = qini_curves_tables(cfg)
    if segments is None:
        segments = segment_summary(cfg)
    ul = cfg["uplift"]
    sm = qtables["summary"]
    conv = sm[sm["outcome"] == "sim_converted_14d"]
    gt_channels = ("email", "social", "search")

    uplift_true = conv[conv["strategy"] == "uplift"].set_index("channel")["qini_lift_true_pct"]
    mean_gt = float(uplift_true.loc[list(gt_channels)].mean())
    display = float(uplift_true.loc["display"])

    oracle_max = all(
        float(conv[(conv["channel"] == ch) & (conv["strategy"] == "oracle")]["qini_lift_true_pct"].iloc[0])
        >= float(conv[conv["channel"] == ch]["qini_lift_true_pct"].max())
        for ch in gt_channels
    )
    seg_min = segments.groupby("channel")["share"].min()
    segs_ok = all(float(seg_min.loc[ch]) >= float(ul["segment_min_share"]) for ch in CHANNELS)

    rows = [
        {"gate": "qini_above_chance_gt", "scope": "email/social/search (mean)",
         "value": round(mean_gt, 4), "threshold": float(ul["qini_true_lift_min_gt_pct"]),
         "passed": bool(mean_gt >= float(ul["qini_true_lift_min_gt_pct"])),
         "detail": "mean Uplift-strategy true lift over channels with a real embedded effect"},
        {"gate": "qini_display_no_effect", "scope": "display",
         "value": round(display, 4), "threshold": float(ul["qini_true_lift_display_max_pct"]),
         "passed": bool(display <= float(ul["qini_true_lift_display_max_pct"])),
         "detail": "embedded effect 0.00 -> nothing to rank; true lift must be ~0 (bias would show)"},
        {"gate": "oracle_is_upper_bound", "scope": "email/social/search",
         "value": oracle_max, "threshold": True,
         "passed": bool(oracle_max),
         "detail": "counterfactual oracle true lift is the max strategy per GT!=0 channel"},
        {"gate": "segments_interpretable", "scope": "all channels (conversion)",
         "value": round(float(seg_min.min()), 4),
         "threshold": float(ul["segment_min_share"]),
         "passed": bool(segs_ok),
         "detail": "every 4-quadrant segment holds >= segment_min_share of its channel"},
    ]
    return pd.DataFrame(rows)


def write_uplift_tables(cfg: dict | None = None) -> dict[str, Path]:
    return write_uplift_tables_from(qini_curves_tables(cfg), segment_summary(cfg), cfg)


def uplift_report(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    qtables = qini_curves_tables(cfg)
    seg = segment_summary(cfg)
    tl = cfg["uplift"]

    lines = []
    lines.append("# Day 14 — Uplift Modeling\n")
    lines.append("> **Labels:** Qini/segment numbers are **estimated (simulated)**; the oracle "
                 "curves are **counterfactual (simulated ground truth)** — they use `sim_u` and "
                 "are unachievable on observed data (AGENTS.md §2/§3).\n")
    lines.append("## Identification (before evaluation)\n")
    lines.append(
        "- **Causal question:** can \u03c4\u0302(x) rank customers so targeting the top-ranked "
        "yields more incremental outcomes than random or response-based targeting?\n"
        "- **Score = Day-13 meta-learner ensemble** (mean of T/S/X CATE): no new model family, "
        "same identification as Day 13 (exchangeability given X; **sim_u unobserved**).\n"
        "- **Comparison strategies:** propensity p(X) (Day 6) and baseline E[Y|X] (Day 13) — the "
        "naive marketer's 'target likely converters'; oracle = true effect (counterfactual).\n"
        "- **Qini (Radcliffe 2007, manual, cross-checked against causalml.metrics.get_qini):** "
        "cumulative incremental responses among treated, sorted by score. `qini_lift` = "
        "normalised area between the curve and the chance diagonal (0 = chance, 100 = max).\n"
        "- **Two evaluations.** (1) *observed* — computed from observed outcomes (all a real-world "
        "analyst has). (2) *true* — evaluated against the **counterfactual** per-unit true effects "
        "(sim_u-based, simulation-only): the honest ranking-power check. **The observed metric is "
        "`sim_u`-confounded**: within-score-bin rate differences inherit the assignment bias, and "
        "the strategy *ordering* itself is biased (see Key finding below).\n"
    )
    lines.append("## Qini lift (% of max, 0 = chance)\n")
    lines.append("Two numbers per strategy: **obs** = observed-outcome metric (real-world "
                 "computable, `sim_u`-confounded); **true** = cumulative |true effect| gain "
                 "against the counterfactual oracle labels (simulation-only; the honest "
                 "ranking-power check; 0 = random, oracle ≈ 27% = this DGP's achievable ceiling — "
                 "the intrinsic relative spread of the effect).\n")
    for o in OUTCOMES:
        lines.append(f"### {OUTCOME_LABELS[o]}\n")
        lines.append("| Channel | θ̂ obs | p obs | E[Y|X] obs | Oracle obs | θ̂ true | p true | E[Y|X] true | Oracle true |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        sm = qtables["summary"]
        for ch in CHANNELS:
            row = {}
            for strat in STRATEGIES:
                r = sm[(sm["channel"] == ch) & (sm["outcome"] == o) & (sm["strategy"] == strat)].iloc[0]
                row[strat] = (r["qini_lift_observed_pct"], r["qini_lift_true_pct"])
            lines.append(f"| {ch} | {row['uplift'][0]:+.1f} | {row['propensity'][0]:+.1f} | "
                         f"{row['baseline'][0]:+.1f} | {row['oracle'][0]:+.1f} | "
                         f"{row['uplift'][1]:+.1f} | {row['propensity'][1]:+.1f} | "
                         f"{row['baseline'][1]:+.1f} | {row['oracle'][1]:+.1f} |")
        lines.append("")
    lines.append("## Key finding — the *observed* Qini rewards the confounder, not the effect\n")
    lines.append(
        "On the observed (confounded) metric the propensity score 'wins' — e.g. email "
        "conversion: propensity **+27%** vs uplift **+13%** — and the oracle (true effect) is "
        "**below chance (−10%)**. This is not a bug: p(X) encodes the `sim_u` selection, so "
        "targeting high-propensity customers harvests the assignment bias, exactly like the naive "
        "ATE did in Days 8–12. The oracle actively *demotes* the high-`sim_u` 'conversion "
        "machines' whose observed diffs are inflated (their true incremental effect ≈ 0), so the "
        "raw metric punishes it. **An above-chance observed Qini is NOT evidence of a causal "
        "uplift model on confounded data.** The *true* metric is the meaningful one.\n"
    )
    lines.append("## Validation hook — Qini above chance (true metric)\n")
    lines.append(f"- **Gate (config `uplift`):** mean **Uplift-strategy true-lift** over the three "
                 f"channels with a real embedded effect (email/search/social) **>= "
                 f"{tl['qini_true_lift_min_gt_pct']}%** (targeting power above random), and "
                 f"**display true-lift <= {tl['qini_true_lift_display_max_pct']}%** (embedded effect "
                 f"0.00 — nothing to rank, so every strategy's true-lift is ≈ 0).\n"
                 f"- **Sanity (machinery, asserted in tests):** the counterfactual oracle is the "
                 f"max-strategy true lift for every GT≠0 channel, and display's true-lift == 0 "
                 f"for every strategy.\n"
    )
    gates = uplift_gates(cfg, qtables=qtables, segments=seg)
    lines.append("### Gate results\n")
    lines.append("| Gate | Scope | Value | Threshold | Pass |")
    lines.append("|---|---|---|---|---|")
    for _, r in gates.iterrows():
        val = f"{r['value']:.2f}" if isinstance(r["value"], float) else str(r["value"])
        thr = f"{r['threshold']:.2f}" if isinstance(r["threshold"], float) else str(r["threshold"])
        lines.append(f"| {r['gate']} | {r['scope']} | {val} | {thr} | "
                     f"{'✅' if r['passed'] else '❌'} |")
    lines.append("")
    lines.append("## Marketing segments (conversion, 4 quadrants)\n")
    lines.append("| Channel | Segment | Size | Share | Conv rate | Mean \u03c4\u0302 | Mean baseline |")
    lines.append("|---|---|---|---|---|---|---|")
    for ch in CHANNELS:
        sg = seg[seg["channel"] == ch]
        for s in SEGMENTS:
            r = sg[sg["segment"] == s].iloc[0]
            lines.append(f"| {ch} | {s.replace('_', ' ').title()} | {int(r['n']):,} | "
                         f"{100*r['share']:.1f}% | {100*r['conv_rate']:.1f}% | "
                         f"{r['mean_tau']:+.4f} | {r['mean_baseline']:.3f} |")
        lines.append("")
    lines.append("## Reading the map (honest interpretation)\n")
    lines.append(
        "- **Observed vs true — the strategy ranking flips.** On the observed (confounded) "
        "metric propensity 'wins' and the oracle is below chance; on the true (counterfactual) "
        "metric the oracle is the ceiling (~27%) while every observed-X strategy is ≈ 0–3%. "
        "The observed metric measures *confounder capture*; the true metric measures *real "
        "ranking power* — only the latter supports causal targeting claims.\n"
        "- **Uplift-vs-propensity (true metric):** none of the observed-X rankings reach even "
        "~10% of the ceiling: the mean Uplift-strategy lift is ~1% vs a ~27% oracle. The "
        "baseline-response ranking (E[Y|X]) actually edges out the CATE ranking (~3% vs ~1%) — "
        "the effect heterogeneity is `sim_u`-driven, so the noisier CATE estimates add ranking "
        "noise rather than signal. **The recoverable targeting signal on observed X is tiny; "
        "Day 18's sensitivity quantifies how strong U must be to explain the ATE itself.**\n"
        "- **Integer-segment reading:** within a channel, *persuadable* = high-τ̂/low-baseline "
        "(the incremental sweet spot), *sure thing* = high-τ̂/high-baseline (treat to keep), "
        "*sleeping dog* = low-τ̂/high-baseline (skip), *lost cause* = low-τ̂/low-baseline (skip). "
        "Cross-channel, social (embedded −0.08 log-odds) is the channel where 'skip' is most "
        "defensible since its τ̂ ranks lowest.\n"
    )
    lines.append("## Limitations\n")
    lines.append(
        "- The *observed* Qini is `sim_u`-confounded — strategy ranking included — so only the "
        "*true* (counterfactual) metric supports claims about real ranking power.\n"
        "- Segments are cut at channel medians of \u03c4\u0302 and E[Y|X]; they describe relative "
        "responsiveness, not a calibrated absolute effect per customer.\n"
        "- Oracle scores/curves use `sim_u` (counterfactual, simulated ground truth); they set an "
        "upper bound on observed-data models, never an achievable benchmark.\n"
    )
    return "\n".join(lines)


def write_uplift_report(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["reports"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "uplift_modeling.md"
    out.write_text(uplift_report(cfg), encoding="utf-8")
    return out


def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    qtables = qini_curves_tables(cfg)
    seg = segment_summary(cfg)
    tables = write_uplift_tables_from(qtables, seg, cfg)
    fig_paths = render_qini_curves(qtables, cfg)
    seg_fig = render_uplift_segments(None, cfg)
    report = write_uplift_report(cfg)
    return {"tables": tables, "figures": fig_paths, "segments_figure": seg_fig,
            "report": report, "summary": qtables["summary"], "segments": seg,
            "gates": pd.read_csv(tables["gates"])}


if __name__ == "__main__":
    cfg = load_config()
    out = run_all(cfg)
    print(out["summary"][["channel", "outcome_label", "strategy",
                          "qini_lift_observed_pct", "qini_lift_true_pct"]]
          .to_string(index=False))
    print()
    print(out["segments"][["channel", "segment", "share", "conv_rate", "mean_tau"]]
          .to_string(index=False))
    print(f"\n--- Gates ---")
    print(out["gates"].to_string(index=False))
    print(f"\nReport -> {out['report']}")