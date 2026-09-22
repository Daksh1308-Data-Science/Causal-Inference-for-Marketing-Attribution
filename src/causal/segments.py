"""CATE segmentation / targeting guidance — Day 15.

Deep-dive on the Day-13 meta-learner CATE: cuts each channel x outcome into
quantile **bands** of the ensemble CATE (low -> high responsiveness) and puts
each band's *estimated* CATE next to its *counterfactual* true effect (oracle)
so targeting guidance is grounded in the DGP sign structure, not in the
sim_u-biased point estimates. Delivers the roadmap's "target-segment table".

Bands (config ``segments.n_bands``, default 5): bottom / mid-low / mid /
mid-high / top; plus one ``all`` reference row per cell.

The honest Day-15 story, quantified by this module:
- The **estimated** sign structure is uniformly positive — every channel x
  outcome has 0% negative CATEs (email 0.1258 / search 0.1263 / social 0.1065 /
  display 0.1119 mean conversion CATE, all bands positive). This is the shared
  `sim_u` bias carried by every estimator since Day 8 — NOT causal signal.
- The **counterfactual** sign structure matches the DGP: email/search positive
  for every unit, social negative for every unit, display exactly zero.
- The ensemble-vs-oracle rank gradient is tiny: ρ ≈ +0.05/+0.06 (email/search
  conversion), ≈ 0 (display), slightly NEGATIVE for social. Even the top band's
  oracle mean barely beats the bottom's (email +0.13 pp, search +0.17 pp).
  So per-X micro-targeting is nearly worthless here; guidance is per-channel
  (run / skip / no budget), not per-customer.

Identification (stated BEFORE fitting/evaluation, AGENTS.md §3):
- Causal question: per channel, is the *sign* of the incremental effect
  positive / negative / zero for the audience, and does ranking units by the
  Day-13 CATE concentrate the true (counterfactual) effect?
- Assumptions: Day-13 CATE assumptions carry over (exchangeability given X,
  **sim_u unobserved**); the counterfactual oracle comes from the known DGP and
  uses `sim_u` (simulation-only, unachievable on observed data).
- **Labels:** band statistics are **estimated (simulated)**; ``oracle_*``
  columns are **counterfactual (simulated ground truth)**. Never presented as
  observed Olist facts (AGENTS.md §2).
"""

from __future__ import annotations

import logging
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import spearmanr

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS
from src.causal.naive import OUTCOMES, OUTCOME_LABELS
from src.causal.uplift import uplift_frame

logging.getLogger("causalml").setLevel(logging.ERROR)

BANDS: tuple[str, ...] = ("bottom", "mid-low", "mid", "mid-high", "top")

TRUE_SIGN_LABEL: dict[str, str] = {
    "+": "counterfactual effect positive for the whole audience",
    "\u2212": "counterfactual effect negative for the whole audience",
    "0": "counterfactual effect exactly zero (embedded coefficient 0.00)",
}


def _bands_of(grp: pd.DataFrame, n_bands: int) -> pd.Series:
    """Quintile/band labels of the ensemble CATE within one cell (stable).

    Returns an ordered categorical so groupby iterates in BANDS order.
    """
    tau = grp["uplift"].values
    labels = list(BANDS[:n_bands])
    try:
        band = pd.qcut(tau, n_bands, labels=labels)
    except ValueError:  # degenerate: too few unique CATE values
        band = pd.Categorical([labels[0]] * len(grp), categories=labels, ordered=True)
    return band


def target_segments(cfg: dict | None = None, frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per cell x CATE-band segment table: estimated vs counterfactual truth.

    Each row is one (channel, outcome, band) with:
    - n / share of the cell;
    - ``tau_mean`` + analytic SE + 95% normal CI of the ensemble CATE
      (estimated, labels the row);
    - ``oracle_mean`` / ``oracle_neg_share`` — the **counterfactual** mean true
      effect and the share of units with a negative true effect inside the band
      (what targeting this band would actually achieve, simulation-only);
    - ``mean_y`` (observed outcome mean) and ``mean_baseline`` (Day-13 E[Y|X]).
    A final band-level row ``all`` gives the cell totals.
    """
    cfg = cfg or load_config()
    frame = frame if frame is not None else uplift_frame(cfg)
    n_bands = int(cfg["segments"]["n_bands"])
    rows: list[dict] = []
    for (ch, o), grp in frame.groupby(["channel", "outcome"]):
        band = _bands_of(grp, n_bands)
        for name, sub in grp.assign(band=band).groupby("band", observed=True):
            n = len(sub)
            tm = float(sub["uplift"].mean())
            se = float(sub["uplift"].std(ddof=1) / np.sqrt(n))
            rows.append({
                "channel": ch, "outcome": o, "outcome_label": OUTCOME_LABELS[o],
                "band": str(name), "n": n, "share": n / len(grp),
                "tau_mean": tm, "tau_se": se,
                "tau_ci_low": tm - 1.96 * se, "tau_ci_high": tm + 1.96 * se,
                "oracle_mean": float(sub["oracle"].mean()),
                "oracle_neg_share": float((sub["oracle"] < 0).mean()),
                "mean_y": float(sub["y"].mean()),
                "mean_baseline": float(sub["baseline"].mean()),
                "label": "estimated (simulated)",
                "oracle_label": "counterfactual (simulated ground truth)",
            })
        # reference row: whole cell
        n = len(grp)
        tm = float(grp["uplift"].mean())
        se = float(grp["uplift"].std(ddof=1) / np.sqrt(n))
        rows.append({
            "channel": ch, "outcome": o, "outcome_label": OUTCOME_LABELS[o],
            "band": "all", "n": n, "share": 1.0,
            "tau_mean": tm, "tau_se": se,
            "tau_ci_low": tm - 1.96 * se, "tau_ci_high": tm + 1.96 * se,
            "oracle_mean": float(grp["oracle"].mean()),
            "oracle_neg_share": float((grp["oracle"] < 0).mean()),
            "mean_y": float(grp["y"].mean()),
            "mean_baseline": float(grp["baseline"].mean()),
            "label": "estimated (simulated)",
            "oracle_label": "counterfactual (simulated ground truth)",
        })
    return pd.DataFrame(rows)


def _true_sign(ts: pd.DataFrame, ch: str) -> str:
    """Sign of the counterfactual effect: '+'/'−'/'0' from the band oracle means."""
    orc = ts[(ts["channel"] == ch) & (ts["outcome"] == "sim_converted_14d")
             & (ts["band"] != "all")]["oracle_mean"]
    if np.allclose(orc.values, 0.0, atol=1e-9):
        return "0"
    return "+" if (orc > 0).all() else "\u2212"


def targeting_guidance(cfg: dict | None = None, ts: pd.DataFrame | None = None,
                       frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-channel targeting recommendation grounded in the counterfactual.

    Columns: channel, est mean conversion CATE + CI, counterfactual mean effect,
    Spearman(ensemble CATE, oracle), top-vs-bottom oracle gap (conversion,
    probability points), the true sign structure, recommendation, basis.
    """
    cfg = cfg or load_config()
    ts = ts if ts is not None else target_segments(cfg, frame=frame)
    frame = frame if frame is not None else uplift_frame(cfg)
    rows = []
    for ch in CHANNELS:
        conv = frame[(frame["channel"] == ch) & (frame["outcome"] == "sim_converted_14d")]
        tau, orc = conv["uplift"].values, conv["oracle"].values
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # constant oracle (display) -> rho undefined (NaN)
            rho, _ = spearmanr(tau, orc)
        bands = ts[(ts["channel"] == ch) & (ts["outcome"] == "sim_converted_14d")
                   & (ts["band"] != "all")]
        top = float(bands.loc[bands["band"] == "top", "oracle_mean"].iloc[0])
        bot = float(bands.loc[bands["band"] == "bottom", "oracle_mean"].iloc[0])
        gap = top - bot
        ref = ts[(ts["channel"] == ch) & (ts["outcome"] == "sim_converted_14d")
                 & (ts["band"] == "all")]
        est_mean = float(ref["tau_mean"].iloc[0])
        est_lo = float(ref["tau_ci_low"].iloc[0])
        est_hi = float(ref["tau_ci_high"].iloc[0])
        orc_mean = float(ref["oracle_mean"].iloc[0])
        sign = _true_sign(ts, ch)
        if sign == "+":
            rec = ("Run \u2014 counterfactual effect is positive for the whole audience; "
                   "per-X micro-targeting adds little (band gradient "
                   f"{100 * gap:+.2f} pp, \u03c1 {rho:+.2f}). Allocate broadly on channel "
                   "size and monitor the channel-level ATE.")
            basis = TRUE_SIGN_LABEL["+"]
        elif sign == "\u2212":
            rec = ("Skip / avoid \u2014 counterfactual effect is negative for ~100% of the "
                   "audience (mean "
                   f"{orc_mean:.4f}); the estimated positive CATE is shared `sim_u` bias, "
                   "not causal signal. Reallocate budget to the positive channels.")
            basis = TRUE_SIGN_LABEL["\u2212"]
        else:
            rec = ("No budget \u2014 counterfactual effect is exactly 0 everywhere "
                   "(embedded coefficient 0.00); any positive estimate is shared `sim_u` "
                   "bias. Demonstrated by display's ~0 oracle vs a positive estimate.")
            basis = TRUE_SIGN_LABEL["0"]
        rows.append({
            "channel": ch, "est_mean_cate_conv": est_mean,
            "est_ci_conv": f"[{est_lo:+.4f}, {est_hi:+.4f}]",
            "oracle_mean_conv": orc_mean, "spearman_tau_oracle": round(float(rho), 4),
            "top_bottom_oracle_gap_pp": round(100 * gap, 4),
            "true_sign": sign, "recommendation": rec, "basis": basis,
            "label": "estimated (simulated)",
            "oracle_label": "counterfactual (simulated ground truth)",
        })
    return pd.DataFrame(rows)


def segment_gates(cfg: dict | None = None, ts: pd.DataFrame | None = None) -> pd.DataFrame:
    """Day-15 validation hooks (AGENTS.md §4): pass/fail per gate.

    All gates evaluate the conversion outcome and use the counterfactual oracle
    as ground truth:
    1. ``gt_channels_positive_oracle`` — email/search: every band's oracle mean
       > ``gt_positive_min_oracle`` (true effect positive throughout).
    2. ``social_negative_oracle`` — social: every band's oracle mean
       < ``social_negative_max_oracle`` (true effect negative throughout).
    3. ``display_zero_oracle`` — display: |band oracle mean| <=
       ``display_oracle_zero_tol`` (true effect exactly 0).
    4. ``estimated_signal_all_positive`` — every channel: every band's estimated
       CATE > ``est_all_positive_min`` (the shared-`sim_u`-bias demonstration:
       observed data cannot recover the true sign structure).
    5. ``rank_gradient_positive_gt`` — email/search: top-band oracle mean >
       bottom-band by > ``rank_gap_min`` (a real but tiny rank gradient).
    6. ``uncertainty_reported`` — every band row has a finite positive SE and a
       sane 95% CI.
    """
    cfg = cfg or load_config()
    ts = ts if ts is not None else target_segments(cfg)
    seg = cfg["segments"]
    conv = ts[ts["outcome"] == "sim_converted_14d"]
    bands = conv[conv["band"] != "all"]

    gt_min = float(bands[bands["channel"].isin(("email", "search"))]
                   .groupby("channel")["oracle_mean"].min().min())
    soc_max = float(bands[bands["channel"] == "social"]["oracle_mean"].max())
    disp_max = float(bands[bands["channel"] == "display"]["oracle_mean"].abs().max())
    est_min = float(bands.groupby("channel")["tau_mean"].min().min())

    gap = {}
    for ch in ("email", "search"):
        b = bands[bands["channel"] == ch]
        gap[ch] = float(b.loc[b["band"] == "top", "oracle_mean"].iloc[0]) - \
                  float(b.loc[b["band"] == "bottom", "oracle_mean"].iloc[0])
    gap_min = min(gap.values())

    ci_ok = bool(((bands["tau_se"] > 0) &
                  (bands["tau_ci_low"] < bands["tau_mean"]) &
                  (bands["tau_mean"] < bands["tau_ci_high"])).all())
    ci_frac = float((bands["tau_se"] > 0).mean())

    rows = [
        {"gate": "gt_channels_positive_oracle", "scope": "email/search (conversion)",
         "value": round(gt_min, 6), "threshold": float(seg["gt_positive_min_oracle"]),
         "passed": bool(gt_min > float(seg["gt_positive_min_oracle"])),
         "detail": "min band oracle mean across email/search > threshold (true effect positive throughout)"},
        {"gate": "social_negative_oracle", "scope": "social (conversion)",
         "value": round(soc_max, 6), "threshold": float(seg["social_negative_max_oracle"]),
         "passed": bool(soc_max < float(seg["social_negative_max_oracle"])),
         "detail": "max band oracle mean for social < threshold (true effect negative throughout)"},
        {"gate": "display_zero_oracle", "scope": "display (conversion)",
         "value": round(disp_max, 9), "threshold": float(seg["display_oracle_zero_tol"]),
         "passed": bool(disp_max <= float(seg["display_oracle_zero_tol"])),
         "detail": "max |band oracle mean| for display <= threshold (true effect exactly 0)"},
        {"gate": "estimated_signal_all_positive", "scope": "all channels (conversion)",
         "value": round(est_min, 6), "threshold": float(seg["est_all_positive_min"]),
         "passed": bool(est_min > float(seg["est_all_positive_min"])),
         "detail": "min band ESTIMATED CATE > threshold in every channel: the shared sim_u bias pushes ALL estimates positive"},
        {"gate": "rank_gradient_positive_gt", "scope": "email/search (conversion)",
         "value": round(gap_min, 6), "threshold": float(seg["rank_gap_min"]),
         "passed": bool(gap_min > float(seg["rank_gap_min"])),
         "detail": "min over email/search of (top-band oracle mean - bottom-band) -> real but tiny rank gradient"},
        {"gate": "uncertainty_reported", "scope": "all band rows",
         "value": round(ci_frac, 4), "threshold": 1.0,
         "passed": ci_ok,
         "detail": "every band row has finite positive SE and ci_low < tau_mean < ci_high"},
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Figures (conversion)
# --------------------------------------------------------------------------


def render_target_bands(cfg: dict | None = None, ts: pd.DataFrame | None = None,
                        out_dir: Path | None = None) -> Path:
    """Grouped bars per channel: estimated CATE vs counterfactual oracle per band."""
    cfg = cfg or load_config()
    ts = ts if ts is not None else target_segments(cfg)
    out_dir = out_dir or project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    out_dir.mkdir(parents=True, exist_ok=True)
    conv = ts[(ts["outcome"] == "sim_converted_14d") & (ts["band"] != "all")]
    fig = make_subplots(rows=2, cols=2, subplot_titles=[f"{ch} \u2014 estimated \u03c4\u0302 vs counterfactual oracle" for ch in CHANNELS],
                        shared_yaxes=False)
    for i, ch in enumerate(CHANNELS):
        b = conv[conv["channel"] == ch].sort_values("band", key=lambda s: s.map({x: i for i, x in enumerate(BANDS)}))
        row, col = i // 2 + 1, i % 2 + 1
        fig.add_trace(go.Bar(name="Estimated CATE", x=b["band"], y=100 * b["tau_mean"],
                             marker_color="#4C72B0", error_y=dict(type="data", array=196 * b["tau_se"])),
                      row=row, col=col)
        fig.add_trace(go.Bar(name="Counterfactual oracle", x=b["band"], y=100 * b["oracle_mean"],
                             marker_color="#C44E52"),
                      row=row, col=col)
        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="black", row=row, col=col)
    fig.update_layout(title="Day 15 \u2014 CATE bands: estimated vs true (counterfactual) incremental conversion, by channel",
                      barmode="group", height=760,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    fig.update_yaxes(title_text="Incremental conv. (pp)", row=1, col=1)
    fig.update_yaxes(title_text="Incremental conv. (pp)", row=2, col=1)
    path = out_dir / "target_bands_conversion.html"
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


def render_cate_distribution(cfg: dict | None = None, frame: pd.DataFrame | None = None,
                             out_dir: Path | None = None) -> Path:
    """Histograms of the ensemble CATE per channel with the true-effect mean marked."""
    cfg = cfg or load_config()
    frame = frame if frame is not None else uplift_frame(cfg)
    out_dir = out_dir or project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    out_dir.mkdir(parents=True, exist_ok=True)
    conv = frame[frame["outcome"] == "sim_converted_14d"]
    fig = make_subplots(rows=2, cols=2, subplot_titles=[ch for ch in CHANNELS])
    for i, ch in enumerate(CHANNELS):
        tau = conv.loc[conv["channel"] == ch, "uplift"]
        orc = conv.loc[conv["channel"] == ch, "oracle"]
        row, col = i // 2 + 1, i % 2 + 1
        fig.add_trace(go.Histogram(x=100 * tau.values, nbinsx=40, name=f"{ch} estimated",
                                   marker_color="#4C72B0", opacity=0.85), row=row, col=col)
        fig.add_vline(x=100 * float(orc.mean()), line_width=2, line_dash="dash",
                      line_color="#C44E52", row=row, col=col)
        fig.add_annotation(x=100 * float(orc.mean()), y=1.0, yref="paper", showarrow=False,
                           text=f"oracle mean {100 * float(orc.mean()):+.2f} pp",
                           font=dict(color="#C44E52"), xanchor="left", row=row, col=col)
    fig.update_layout(title="Day 15 \u2014 Ensemble CATE distribution per channel (conversion); dashed = true mean effect (counterfactual)",
                      height=760, showlegend=False)
    fig.update_xaxes(title_text="Estimated conversion CATE (pp)")
    path = out_dir / "cate_distribution_conversion.html"
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# --------------------------------------------------------------------------
# Tables + report
# --------------------------------------------------------------------------


def write_segment_tables_from(ts: pd.DataFrame, guide: pd.DataFrame, gates: pd.DataFrame,
                              cfg: dict | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["target_segments"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p1, p2, p3 = out_dir / "target_segments.csv", out_dir / "guidance.csv", out_dir / "gates.csv"
    ts.to_csv(p1, index=False)
    guide.to_csv(p2, index=False)
    gates.to_csv(p3, index=False)
    return {"target_segments": p1, "guidance": p2, "gates": p3}


def cate_segmentation_report(cfg: dict | None = None, ts: pd.DataFrame | None = None,
                             guide: pd.DataFrame | None = None) -> str:
    cfg = cfg or load_config()
    ts = ts if ts is not None else target_segments(cfg)
    guide = guide if guide is not None else targeting_guidance(cfg, ts=ts)
    seg = cfg["segments"]

    lines = []
    lines.append("# Day 15 \u2014 CATE Segmentation & Targeting Guidance\n")
    lines.append("> **Labels:** band statistics are **estimated (simulated)**; `oracle_*` "
                 "columns and the guidance sign structure are **counterfactual (simulated "
                 "ground truth)** \u2014 they use `sim_u` and are unachievable on observed data "
                 "(AGENTS.md \u00a72/\u00a73).\n")
    lines.append("## Identification (before evaluation)\n")
    lines.append(
        "- **Causal question:** per channel, is the incremental effect positive / negative / "
        "zero for the audience, and how much of the true (counterfactual) effect does ranking "
        "by the Day-13 CATE actually concentrate?\n"
        "- **Segments = quintile bands of the ensemble CATE** (mean of T/S/X, Day 13) per "
        "channel \u00d7 outcome; same identification as Day 13 (exchangeability given X; "
        "**sim_u unobserved**). Counterfactual oracle = true per-unit effect from the known DGP.\n"
        "- **Why band means, not per-customer ranks:** Day 13 showed individual CATE ranks agree "
        "only 0.32\u20130.77 Spearman *across learners*; Day 15 adds the harsher check \u2014 "
        "ensemble CATE vs the *true* effect \u2014 and finds \u03c1 \u2248 +0.01\u2026+0.06 "
        "(essentially noise). Targeting guidance is therefore per-*channel*, never per-customer.\n"
    )
    for o in OUTCOMES:
        lines.append(f"## Target-segment table \u2014 {OUTCOME_LABELS[o]}\n")
        lines.append("| Channel | Band | Share | n | \u03c4\u0302 \u00b1 CI (est) | Oracle mean (counterfactual) | "
                     "Oracle negative share | Conv rate |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for ch in CHANNELS:
            for _, r in ts[(ts["channel"] == ch) & (ts["outcome"] == o)].iterrows():
                lines.append(f"| {ch} | {r['band']} | {100 * r['share']:.1f}% | {int(r['n']):,} | "
                             f"{r['tau_mean']:+.4f} [{r['tau_ci_low']:+.4f}, {r['tau_ci_high']:+.4f}] | "
                             f"{r['oracle_mean']:+.4f} | {100 * r['oracle_neg_share']:.0f}% | "
                             f"{100 * r['mean_y']:.1f}% |" if o == "sim_converted_14d"
                        else f"| {ch} | {r['band']} | {100 * r['share']:.1f}% | {int(r['n']):,} | "
                             f"{r['tau_mean']:+.2f} [{r['tau_ci_low']:+.2f}, {r['tau_ci_high']:+.2f}] | "
                             f"{r['oracle_mean']:+.2f} | {100 * r['oracle_neg_share']:.0f}% | "
                             f"R$ {r['mean_y']:.2f} |")
            lines.append("")
    lines.append("## Targeting guidance \u2014 per channel (from the counterfactual sign structure)\n")
    lines.append("| Channel | Est. CATE (conv, 95% CI) | Oracle mean | \u03c1(\u03c4\u0302, oracle) | "
                 "Top\u2212bottom gap (pp) | True sign | Recommendation |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in guide.iterrows():
        rho = ("n/a (constant oracle)" if pd.isna(r["spearman_tau_oracle"])
               else f"{r['spearman_tau_oracle']:+.3f}")
        lines.append(f"| {r['channel']} | {r['est_mean_cate_conv']:+.4f} {r['est_ci_conv']} | "
                     f"{r['oracle_mean_conv']:+.4f} | {rho} | "
                     f"{r['top_bottom_oracle_gap_pp']:+.2f} | {r['true_sign']} | {r['recommendation']} |")
    lines.append("")
    lines.append("## Key finding \u2014 the estimated sign structure is wrong; the counterfactual one explains the pattern\n")
    lines.append(
        "Every channel's estimated CATE is **positive in every band** (email 0.126, search 0.126, "
        "social 0.107, display 0.112 mean conversion CATE; 0% negative units) \u2014 including "
        "social, whose true effect is negative, and display, whose true effect is exactly 0. "
        "This is the shared `sim_u` bias carried by every estimator since Day 8; a real analyst "
        "looking only at observed data would wrongly conclude *all* channels help. The "
        "**counterfactual** sign structure matches the DGP exactly: email/search positive for "
        "every unit, social negative for every unit, display exactly zero. **The segments "
        "explain the pattern only when the oracle (sim_u) is used; the observed-data ranking "
        "cannot recover even the sign.**\n"
    )
    lines.append(f"- **Rank gradient (measured, not assumed):** \u03c1(ensemble CATE, true effect) "
                 f"\u2248 +0.05/+0.06 conversion for email/search, \u22480 for display, slightly "
                 f"negative for social. The top band's true effect beats the bottom's by only "
                 f"+0.13/+0.17 pp (email/search) \u2014 real but tiny; social's gradient is "
                 f"flat-to-inverted (harm-avoidance is unreachable on observed X).\n"
                 f"- **Why so weak:** the effect is constant in log-odds and ~90% `sim_u`-driven, "
                 f"so the probability-scale \u0394P is a narrow bump that observed X (which "
                 f"predicts sim_u only weakly) can barely track. Day 18 quantifies how strong the "
                 f"unobserved confounder must be to explain the ATE itself.\n"
    )
    lines.append("## Validation hooks\n")
    lines.append(f"- Gate **estimated_signal_all_positive**: every channel's min band estimated CATE "
                 f"> {seg['est_all_positive_min']} (bias demonstration \u2014 min observed 0.099).\n"
                 f"- Gate **gt_channels_positive_oracle**: email/search band oracle means all > "
                 f"{seg['gt_positive_min_oracle']} (positive effect throughout).\n"
                 f"- Gate **social_negative_oracle**: social band oracle means all < "
                 f"{seg['social_negative_max_oracle']} (negative effect throughout).\n"
                 f"- Gate **display_zero_oracle**: |display band oracle means| \u2264 "
                 f"{seg['display_oracle_zero_tol']} (effect exactly 0).\n"
                 f"- Gate **rank_gradient_positive_gt**: email/search top\u2212bottom oracle gap > "
                 f"{seg['rank_gap_min']} (real, tiny gradient).\n"
    )
    gates = segment_gates(cfg, ts=ts)
    lines.append("### Gate results\n")
    lines.append("| Gate | Scope | Value | Threshold | Pass |")
    lines.append("|---|---|---|---|---|")
    for _, r in gates.iterrows():
        val = f"{r['value']:.4f}" if isinstance(r["value"], float) else str(r["value"])
        thr = f"{r['threshold']:.4f}" if isinstance(r["threshold"], float) else str(r["threshold"])
        lines.append(f"| {r['gate']} | {r['scope']} | {val} | {thr} | {'✅' if r['passed'] else '❌'} |")
    lines.append("")
    lines.append("## Limitations\n")
    lines.append(
        "- Band means are estimates on observed X (sim_u unobserved); their *ordering* within a "
        "channel is a weak (but real) signal only for email/search.\n"
        "- Rate-based 'conv rate' is observed/simulated, not incremental; incremental effects "
        "are the \u03c4\u0302/oracle columns.\n"
        "- Counterfactual oracle numbers use `sim_u`; they define the achievable sign structure "
        "on this DGP but are never reachable from observed data.\n"
    )
    return "\n".join(lines)


def write_cate_segmentation_report(cfg: dict | None = None, ts: pd.DataFrame | None = None,
                                   guide: pd.DataFrame | None = None) -> Path:
    cfg = cfg or load_config()
    out = project_path(cfg["paths"]["reports"])
    out.mkdir(parents=True, exist_ok=True)
    path = out / "cate_segmentation.md"
    path.write_text(cate_segmentation_report(cfg, ts=ts, guide=guide), encoding="utf-8")
    return path


def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    frame = uplift_frame(cfg)
    ts = target_segments(cfg, frame=frame)
    guide = targeting_guidance(cfg, ts=ts, frame=frame)
    gates = segment_gates(cfg, ts=ts)
    tables = write_segment_tables_from(ts, guide, gates, cfg)
    figs = {
        "target_bands": render_target_bands(cfg, ts=ts),
        "cate_distribution": render_cate_distribution(cfg, frame=frame),
    }
    report = write_cate_segmentation_report(cfg, ts=ts, guide=guide)
    print("\n--- Targeting guidance ---")
    cols = ["channel", "est_mean_cate_conv", "oracle_mean_conv", "spearman_tau_oracle",
            "top_bottom_oracle_gap_pp", "true_sign"]
    print(guide[cols].to_string(index=False))
    print("\n--- Gates ---")
    print(gates.to_string(index=False))
    print(f"\nReport -> {report}")
    return {"tables": tables, "figures": figs, "report": report,
            "segments": ts, "guidance": guide, "gates": gates}


if __name__ == "__main__":
    run_all()