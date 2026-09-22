"""Incremental ROI — Day 16 (blueprint §9).

Converts the Day-12 revenue ATE estimates into marketing ROI per channel:
``ROI = (incremental revenue per treated − cost per treated) / cost per
treated`` (blueprint §9, exact formula). Channel costs are **config
assumptions** (ADR-006: Olist has no spend data) — per-treated-customer R$
over the 14-day outcome window, order-of-magnitude Brazilian e-commerce.

Three methods per channel, ALL reported with labels:
- **observational** — Day-8 naive diff-in-means revenue ATE: the classic
  last-touch/attribution-style ROI (everything the treated earned vs the
  untreated). Includes every spillover of `sim_u` selection.
- **causal** — Day-12 DR (doubly robust) revenue ATE with its 95% CI (the
  project's flagship causal estimate). Propagated to ROI via the monotone
  transform: ROI_lo/hi from ci_lower/ci_upper.
- **counterfactual** — true per-treated revenue effect from the known DGP
  (oracle, simulation-only). Labels the achievable truth on this simulation:
  email/search positive, social negative, display exactly 0.

The honest Day-16 finding, quantified by this module: even the *causal* ROI
overstates every channel (email ~7.5x, search ~11x the counterfactual truth;
display/social look hugely profitable while their true ROI is −1.0x/−3.0x)
because the unobserved confounder `sim_u` dominates the revenue outcome —
the Day-12 convergence story carried into money terms.

Identification / labeling (AGENTS.md §2/§3): observational + causal numbers
inherit the Day-8/Day-9..12 identification (exchangeability given X, sim_u
unobserved); the counterfactual column uses `sim_u` and is unachievable on
observed data. ROI is *per treated customer*; multiply by n_treated for the
campaign-level view (cohort_net columns).

All gates below implement the roadmap hook "ROI complete per channel".
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS
from src.causal.uplift import uplift_frame

ROI_LABELS: dict[str, str] = {
    "observational": "estimated (simulated) - naive diff-in-means revenue ATE",
    "causal": "estimated (simulated) - Day-12 DR revenue ATE",
    "counterfactual": "counterfactual (simulated ground truth) - DGP oracle",
}

REVENUE_OUTCOME = "sim_revenue_14d"


def _master(cfg: dict) -> pd.DataFrame:
    path = project_path(cfg["paths"]["results"], cfg["results"]["tables"]) / "master_estimates.csv"
    return pd.read_csv(path)


def roi_table(cfg: dict | None = None, master: pd.DataFrame | None = None,
              frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Long ROI table: 4 channels x 3 methods (observational / causal / counterfactual).

    Columns: channel, method, cost_per_treated, n_treated, inc_rev point + CI
    (R$ per treated, 14-day window), net_per_treated (inc_rev − cost) + CI,
    roi = net/cost + CI, label. Counterfactual rows use the deterministic DGP
    oracle (CI = point; no sampling uncertainty, simulation-only).
    """
    cfg = cfg or load_config()
    master = master if master is not None else _master(cfg)
    frame = frame if frame is not None else uplift_frame(cfg)
    costs = cfg["roi"]["cost_per_treated"]
    causal = cfg["roi"]["causal_estimator"]
    obs = cfg["roi"]["observational_estimator"]

    n_tr = frame[frame["outcome"] == REVENUE_OUTCOME].groupby("channel")["treatment"].sum()
    orc = frame[frame["outcome"] == REVENUE_OUTCOME].groupby("channel")["oracle"].mean()

    rows = []
    for ch in CHANNELS:
        cost = float(costs[ch])
        n = int(n_tr[ch])
        specs = [
            ("observational", obs, float(n_tr[ch]),
             master[(master["channel"] == ch) & (master["outcome"] == REVENUE_OUTCOME)
                    & (master["estimator"] == obs)].iloc[0], 1.0),
            ("causal", causal, float(n_tr[ch]),
             master[(master["channel"] == ch) & (master["outcome"] == REVENUE_OUTCOME)
                    & (master["estimator"] == causal)].iloc[0], 1.0),
            ("counterfactual", None, float(n_tr[ch]), None, 0.0),
        ]
        for method, _, ntr, row, ci_mask in specs:
            if method == "counterfactual":
                inc = float(orc[ch])
                lo = hi = inc
            else:
                inc = float(row["point"])
                lo, hi = float(row["ci_lower"]), float(row["ci_upper"])
            net = inc - cost
            net_lo, net_hi = lo - cost, hi - cost
            roi = net / cost
            rows.append({
                "channel": ch, "method": method, "cost_per_treated": cost,
                "n_treated": n, "inc_rev": inc, "inc_rev_ci_low": lo,
                "inc_rev_ci_high": hi, "net_per_treated": net,
                "net_ci_low": net_lo, "net_ci_high": net_hi,
                "roi": roi, "roi_ci_low": net_lo / cost, "roi_ci_high": net_hi / cost,
                "label": ROI_LABELS[method],
            })
    return pd.DataFrame(rows)


def roi_summary_from(roi_long: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """Wide per-channel view for the CMO: the three ROIs side by side."""
    cfg = cfg or load_config()
    rows = []
    for ch in CHANNELS:
        sub = roi_long[roi_long["channel"] == ch].set_index("method")
        ctf = sub.loc["counterfactual"]
        caus = sub.loc["causal"]
        ratio = caus["roi"] / ctf["roi"] if ctf["roi"] > 0 else np.nan
        rows.append({
            "channel": ch, "cost_per_treated": float(sub.iloc[0]["cost_per_treated"]),
            "n_treated": int(sub.iloc[0]["n_treated"]),
            "obs_roi": float(sub.loc["observational", "roi"]),
            "causal_roi": float(caus["roi"]),
            "causal_roi_ci_low": float(caus["roi_ci_low"]),
            "causal_roi_ci_high": float(caus["roi_ci_high"]),
            "ctf_roi": float(ctf["roi"]),
            "causal_over_ctf": float(ratio),
            "cohort_net_ctf": float(sub.iloc[0]["n_treated"]) * float(ctf["net_per_treated"]),
        })
    return pd.DataFrame(rows)


def roi_gates(cfg: dict | None = None, roi_long: pd.DataFrame | None = None,
              summary: pd.DataFrame | None = None) -> pd.DataFrame:
    """Day-16 validation hooks: "ROI complete per channel".

    1. complete_rows — 12 rows (4 channels x 3 methods); costs > 0; every ROI
       point/CI finite; n_treated > 0.
    2. causal_roi_positive — min causal ROI > ``causal_roi_positive_min``
       (the sim_u-bias demonstration: even causal ROI is positive everywhere).
    3. ctf_email_search_positive — counterfactual ROI > 0 for email/search.
    4. ctf_social_display_negative — counterfactual ROI < 0 for social/display.
    5. overstatement_documented — min causal/ctf ROI ratio (email/search) >
       ``overstatement_min_gt`` (causal ROI exceeds the truth by a documented
       multiple).
    6. uncertainty_reported — causal rows: finite CI with ilow < roi < ihigh;
       counterfactual rows: CI collapses to the point (deterministic DGP).
    """
    cfg = cfg or load_config()
    roi_long = roi_long if roi_long is not None else roi_table(cfg)
    summary = summary if summary is not None else roi_summary_from(roi_long, cfg)
    seg = cfg["roi"]

    rows = [
        {"gate": "complete_rows", "scope": "all channels",
         "value": len(roi_long), "threshold": int(seg["complete_rows_expected"]),
         "passed": bool(len(roi_long) == int(seg["complete_rows_expected"])
                        and (roi_long["cost_per_treated"] > 0).all()
                        and roi_long[["roi", "roi_ci_low", "roi_ci_high"]].notna().all().all()
                        and (roi_long["n_treated"] > 0).all()),
         "detail": "12 rows; positive costs; finite ROI point/CI; positive treated counts"},
        {"gate": "causal_roi_positive", "scope": "all channels",
         "value": round(float(summary["causal_roi"].min()), 4),
         "threshold": float(seg["causal_roi_positive_min"]),
         "passed": bool((summary["causal_roi"] > float(seg["causal_roi_positive_min"])).all()),
         "detail": "min causal ROI > threshold (sim_u bias makes even causal ROI positive everywhere)"},
        {"gate": "ctf_email_search_positive", "scope": "email/search",
         "value": round(float(summary.loc[summary["channel"].isin(("email", "search")), "ctf_roi"].min()), 6),
         "threshold": float(seg["ctf_email_search_min_roi"]),
         "passed": bool((summary.loc[summary["channel"].isin(("email", "search")), "ctf_roi"]
                         > float(seg["ctf_email_search_min_roi"])).all()),
         "detail": "counterfactual ROI positive for email/search (true effect positive)"},
        {"gate": "ctf_social_display_negative", "scope": "social/display",
         "value": round(float(summary.loc[summary["channel"].isin(("social", "display")), "ctf_roi"].max()), 6),
         "threshold": float(seg["ctf_social_display_max_roi"]),
         "passed": bool((summary.loc[summary["channel"].isin(("social", "display")), "ctf_roi"]
                         < float(seg["ctf_social_display_max_roi"])).all()),
         "detail": "counterfactual ROI negative for social (negative effect) and display (zero effect, cost unrecovered)"},
        {"gate": "overstatement_documented", "scope": "email/search",
         "value": round(float(summary.loc[summary["channel"].isin(("email", "search")), "causal_over_ctf"].min()), 3),
         "threshold": float(seg["overstatement_min_gt"]),
         "passed": bool((summary.loc[summary["channel"].isin(("email", "search")), "causal_over_ctf"]
                         > float(seg["overstatement_min_gt"])).all()),
         "detail": "causal ROI / counterfactual ROI > threshold for email/search (documented overstatement)"},
        {"gate": "uncertainty_reported", "scope": "all rows",
         "value": 1.0, "threshold": 1.0,
         "passed": bool(((roi_long["roi_ci_low"] <= roi_long["roi"]) &
                         (roi_long["roi"] <= roi_long["roi_ci_high"]) &
                         roi_long["roi"].notna()).all()),
         "detail": "every row has finite ROI with sane CI bounds (counterfactual CI collapses to the point)"},
    ]
    return pd.DataFrame(rows)


def render_roi_figure(cfg: dict | None = None, roi_long: pd.DataFrame | None = None,
                      out_dir: Path | None = None) -> Path:
    """Faceted bars per channel: observational vs causal vs counterfactual ROI."""
    cfg = cfg or load_config()
    roi_long = roi_long if roi_long is not None else roi_table(cfg)
    out_dir = out_dir or project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    out_dir.mkdir(parents=True, exist_ok=True)
    order = ["observational", "causal", "counterfactual"]
    colors = {"observational": "#8C8C8C", "causal": "#4C72B0", "counterfactual": "#C44E52"}
    fig = make_subplots(rows=2, cols=2, subplot_titles=[ch for ch in CHANNELS])
    for i, ch in enumerate(CHANNELS):
        row, col = i // 2 + 1, i % 2 + 1
        for method in order:
            r = roi_long[(roi_long["channel"] == ch) & (roi_long["method"] == method)].iloc[0]
            fig.add_trace(go.Bar(name=f"{method}", x=[method], y=[r["roi"]],
                                 marker_color=colors[method],
                                 error_y=dict(type="data", symmetric=False,
                                              array=[r["roi_ci_high"] - r["roi"]],
                                              arrayminus=[r["roi"] - r["roi_ci_low"]])),
                          row=row, col=col)
        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="black", row=row, col=col)
        fig.add_hline(y=1, line_width=1, line_dash="dash", line_color="#2CA02C", row=row, col=col)
    fig.update_layout(title=("Day 16 — ROI per R$ 1 invested (14-day window): observational (naive), "
                             "causal (Day-12 DR, 95% CI), counterfactual (DGP truth). "
                             "Solid green = breakeven (ROI 1.0)."),
                      height=780, showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    fig.update_yaxes(title_text="ROI (R$ per R$ invested)")
    path = out_dir / "roi_comparison.html"
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


def write_roi_tables_from(roi_long: pd.DataFrame, summary: pd.DataFrame,
                          gates: pd.DataFrame, cfg: dict | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["roi"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p1, p2, p3 = out_dir / "roi_long.csv", out_dir / "roi_summary.csv", out_dir / "roi_gates.csv"
    roi_long.to_csv(p1, index=False)
    summary.to_csv(p2, index=False)
    gates.to_csv(p3, index=False)
    return {"roi_long": p1, "summary": p2, "gates": p3}


def roi_report(cfg: dict | None = None, roi_long: pd.DataFrame | None = None,
               summary: pd.DataFrame | None = None) -> str:
    cfg = cfg or load_config()
    roi_long = roi_long if roi_long is not None else roi_table(cfg)
    summary = summary if summary is not None else roi_summary_from(roi_long, cfg)

    lines = []
    lines.append("# Day 16 — Incremental ROI\n")
    lines.append("> **Labels:** observational + causal numbers are **estimated (simulated)** "
                 "(see each row's label); the **counterfactual** column is the true per-treated "
                 "revenue effect from the known DGP — simulation-only, unachievable on observed "
                 "data (AGENTS.md §2/§3). Rows carry machine-readable labels: `estimated (simulated) - naive diff-in-means revenue ATE`, `estimated (simulated) - Day-12 DR revenue ATE`, and `counterfactual (simulated ground truth) - DGP oracle`. Channel costs are **config assumptions** (ADR-006; "
                 "Olist has no spend data), per-treated-customer R$ over the 14-day outcome window.\n")
    lines.append("## Definition\n")
    lines.append("- `ROI = (incremental revenue per treated − cost per treated) / cost per treated` "
                 "(blueprint §9). ROI = 0 is breakeven; ROI = 1 means the R$ doubles on spend.\n"
                 "- **observational** — Day-8 naive diff-in-means (last-touch-style attribution). "
                 "**causal** — Day-12 doubly robust (DR) revenue ATE, CI propagated through the "
                 "monotone ROI transform. **counterfactual** — true effect from the DGP (oracle).\n"
                 "- Per-treated units: see n_treated; contrast the treatment share vs 50/50 random "
                 "assignment (Day 3 preview). Ongoing identification: exchangeability given X, "
                 "**sim_u unobserved** — every estimate since Day 8 inherits this.\n")
    lines.append("## ROI per channel (R$ per R$ 1 invested)\n")
    lines.append("| Channel | Cost/treated | Treated | Observational | Causal (95% CI) | Counterfactual | "
                 "Causal ÷ truth | Cohort net truth (R$) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for _, r in summary.iterrows():
        obs = f"{100 * r['obs_roi']:.0f}%"
        caus = f"{100 * r['causal_roi']:.0f}% [{100 * r['causal_roi_ci_low']:.0f}%, {100 * r['causal_roi_ci_high']:.0f}%]"
        ctf = f"{100 * r['ctf_roi']:.0f}%"
        ratio = f"{r['causal_over_ctf']:.1f}x" if pd.notna(r["causal_over_ctf"]) else "—"
        lines.append(f"| {r['channel']} | R$ {r['cost_per_treated']:.2f} | {int(r['n_treated']):,} | "
                     f"{obs} | {caus} | {ctf} | {ratio} | R$ {r['cohort_net_ctf']:,.0f} |")
    lines.append("")
    lines.append("## Key finding — even the *causal* ROI overstates every channel here\n")
    lines.append(
        "On this simulation the Day-12 estimators converge to ≈ +16–18 R$ incremental revenue per "
        "treated for **every** channel (display +16.2, social +16.1) — the shared `sim_u` bias carried "
        "into money terms. Consequently the causal ROI is positive everywhere (email 17,265%, search "
        "1,112%, display 7,983%, social 1,912%) and, surprisingly, barely improves on the naive "
        "attribution ROI — both are confounded. The **counterfactual** column reveals the truth: "
        "email is genuinely excellent (2,314%), search is modestly positive (101%), while **social "
        "(−299%) and display (−100%) destroy value** — any spend there loses money. `Causal ÷ truth` "
        "quantifies the overstatement: **~7.5x email, ~11x search**, sign-flipped for social/display.\n"
    )
    lines.append(
        "- **Breakeven reads:** email/search break even at any cost below their true incremental "
        "revenue (email R$ 2.41, search R$ 3.02 per treated); social/display never do (true effect "
        "negative/zero) — no cost assumption can rescue them.\n"
        "- **Budget implication (pre-Day-17):** on observed data alone you would fund display and "
        "social; the counterfactual says the opposite. Day 17 turns this into explicit counterfactual "
        "scenarios; Day 18 bounds how strong `sim_u` must be to produce these estimates.\n"
    )
    lines.append("## Validation hooks — gates\n")
    lines.append("| Gate | Scope | Value | Threshold | Pass |")
    lines.append("|---|---|---|---|---|")
    gates = roi_gates(cfg, roi_long=roi_long, summary=summary)
    for _, r in gates.iterrows():
        val = f"{r['value']:.4f}" if isinstance(r["value"], float) else str(r["value"])
        thr = f"{r['threshold']:.4f}" if isinstance(r["threshold"], float) else str(r["threshold"])
        lines.append(f"| {r['gate']} | {r['scope']} | {val} | {thr} | {'✅' if r['passed'] else '❌'} |")
    lines.append("")
    lines.append("## Limitations\n")
    lines.append(
        "- Costs are assumptions (ADR-006), flat per treated customer, no marginal-cost curve, no "
        "frequency effects — ROI = f(cost) is a single point, not a curve.\n"
        "- Counterfactual ROI uses `sim_u`; it is the achievable truth on this DGP only.\n"
        "- 14-day window: revenue accruing beyond the window is excluded by construction.\n"
        "- Causal ROI collapses to the confounded Day-12 story: all estimators agree because all "
        "share the same unobserved `sim_u` bias (see Day 12 report).\n"
    )
    return "\n".join(lines)


def write_roi_report(cfg: dict | None = None, roi_long: pd.DataFrame | None = None,
                     summary: pd.DataFrame | None = None) -> Path:
    cfg = cfg or load_config()
    out = project_path(cfg["paths"]["reports"])
    out.mkdir(parents=True, exist_ok=True)
    path = out / "roi.md"
    path.write_text(roi_report(cfg, roi_long=roi_long, summary=summary), encoding="utf-8")
    return path


def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    master = _master(cfg)
    frame = uplift_frame(cfg)
    roi_long = roi_table(cfg, master=master, frame=frame)
    summary = roi_summary_from(roi_long, cfg)
    gates = roi_gates(cfg, roi_long=roi_long, summary=summary)
    tables = write_roi_tables_from(roi_long, summary, gates, cfg)
    fig = render_roi_figure(cfg, roi_long=roi_long)
    report = write_roi_report(cfg, roi_long=roi_long, summary=summary)
    print("\n--- ROI summary ---")
    print(summary.to_string(index=False))
    print("\n--- Gates ---")
    print(gates.to_string(index=False))
    print(f"\nReport -> {report}")
    return {"tables": tables, "figure": fig, "report": report,
            "roi_long": roi_long, "summary": summary, "gates": gates}


if __name__ == "__main__":
    run_all()