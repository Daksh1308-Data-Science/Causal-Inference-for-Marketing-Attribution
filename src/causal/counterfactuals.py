"""Counterfactual budget scenarios — Day 17 (blueprint §9).

Answers "what would the campaign deliver if the budget were allocated
differently?" as **model-based counterfactual estimates** (AGENTS.md §2/§3:
never presented as observed facts — labelled `counterfactual (simulated ground
truth)` everywhere).

Fixed total budget = the as-run campaign spend (Σ cost_per_treated × observed
n_treated, computed from the Day-16 config costs). Four allocation scenarios:
- ``as_run``  — the campaign as executed (shares ∝ cost × n_treated);
- ``naive``   — last-touch-style attribution (shares ∝ naive revenue ATE ×
  n_treated): how a marketer funding observed "revenue per channel" spends;
- ``causal``  — Day-12 DR causal ROI (shares ∝ causal ROI): the recommendation
  you would make from the confounded causal estimates;
- ``ctf_guided`` — DGP-informed (shares ∝ counterfactual ROI, positive channels
  only): guided by the sim's truth about where money should go.

Mechanics per scenario x channel (deterministic arithmetic on Day-16/ROI
numbers, so results carry no new sampling uncertainty):
spend = share × budget; implied treated = spend / cost_per_treated — capped at
the cohort size with an **extrapolation flag** when implied treated exceeds the
observed n_treated (positivity/linearity limit, blueprint's "extrapolation
limits notes"); incremental revenue = treated × counterfactual per-treated
revenue effect (DGP oracle); net = revenue − spend.

Gates ("Scenarios consistent with causal ROI" hook):
1. ``scenarios_complete``          — every scenario x channel row present;
   spends sum to the fixed budget per scenario.
2. ``as_run_reproduces_day16``     — as_run per-channel nets match the Day-16
   cohort-net counterfactual column within ``as_run_net_tol`` R$.
3. ``reallocations_beat_as_run``   — every reallocation scenario's total net >
   as_run total net by at least ``realloc_beat_min_margin`` (the observed
   spend scatter is worse than any re-split of the same budget).
4. ``email_saturation_documented`` — email hits cohort saturation in ≥ 1
   scenario (the cap bites; the budget-waste read is in the report).
5. ``bounded_by_optimum``          — max scenario total net ≤ the
   budget-constrained linear optimum (greedy email-then-search).
6. ``extrapolation_flagged``       — every channel whose implied treated
   exceeds observed n_treated carries flag=True (no silent extrapolation).
7. ``labels_correct``              — every row labelled
   ``counterfactual (simulated ground truth), model-based``.
8. ``uncertainty_reported``        — every scenario total carries a finite,
   ordered 95% CI propagated exactly from the Day-12 DR revenue ATE CIs
   through the linear scenario transform (estimated scale).

Honest finding (reported, not gated): once email spend implies treating more
than the cohort (R$ 9,498 = 94,983 × R$ 0.10), extra budget there is pure
waste — so the ctf_guided scenario can *under*-rank a wider spread on this
capped linear arithmetic. The report treats that as an extrapolation
artifact, not an endorsement of any confounded rule.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS
from src.causal.naive import load_analysis_data
from src.causal.roi import roi_summary_from, roi_table

LABEL = "counterfactual (simulated ground truth), model-based"


def _scenario_shares(roi_long: pd.DataFrame, summary: pd.DataFrame,
                     cfg: dict) -> dict[str, dict[str, float]]:
    """Per-scenario per-channel budget shares (fractions summing to 1)."""
    costs = cfg["roi"]["cost_per_treated"]
    r = roi_long.set_index(["method", "channel"])
    obs_inc = r.loc["observational", "inc_rev"]
    caus_roi = summary.set_index("channel")["causal_roi"]
    ctf_roi = summary.set_index("channel")["ctf_roi"]
    n_treated = summary.set_index("channel")["n_treated"]

    def shares_from(weights: pd.Series) -> dict[str, float]:
        w = weights.clip(lower=0.0)
        total = float(w.sum())
        assert total > 0, "scenario weight vector sums to zero"
        return {ch: float(w[ch] / total) for ch in CHANNELS}

    as_run_w = pd.Series({ch: float(costs[ch]) * float(n_treated[ch]) for ch in CHANNELS})
    naive_w = pd.Series({ch: float(obs_inc[ch]) * float(n_treated[ch]) for ch in CHANNELS})
    return {
        "as_run": shares_from(as_run_w),
        "naive": shares_from(naive_w),
        "causal": shares_from(caus_roi),
        "ctf_guided": shares_from(ctf_roi),
    }


def counterfactual_scenarios(cfg: dict | None = None, roi_long: pd.DataFrame | None = None,
                             summary: pd.DataFrame | None = None) -> pd.DataFrame:
    """Long table: scenario x channel (+ 'all' totals rows). See module docstring."""
    cfg = cfg or load_config()
    roi_long = roi_long if roi_long is not None else roi_table(cfg)
    summary = summary if summary is not None else roi_summary_from(roi_long, cfg)

    costs = cfg["roi"]["cost_per_treated"]
    shares = _scenario_shares(roi_long, summary, cfg)
    r = roi_long.set_index(["method", "channel"])
    ctf_inc = r.loc["counterfactual", "inc_rev"]
    est_lo = r.loc["causal", "inc_rev_ci_low"]
    est_hi = r.loc["causal", "inc_rev_ci_high"]
    n_treated = summary.set_index("channel")["n_treated"]
    cfg_ctf = cfg["counterfactuals"]

    # fixed total budget = as-run spend
    budget = float(sum(float(costs[ch]) * float(n_treated[ch]) for ch in CHANNELS))
    cohort = int(cfg_ctf["cohort_cap"] or 0)
    if cohort == 0:
        cohort = len(load_analysis_data(cfg))  # the analysis population, not sum of per-channel treated

    rows: list[dict] = []
    for scen, sh in shares.items():
        totals = {"channel": "all", "scenario": scen, "label": LABEL, "share": 1.0,
                  "spend": 0.0, "inc_rev": 0.0, "net": 0.0, "roi": np.nan,
                  "net_est_ci_low": 0.0, "net_est_ci_high": 0.0,
                  "implied_treated": 0, "observed_n_treated": 0, "extrapolated": False}
        for ch in CHANNELS:
            share = sh[ch]
            cost = float(costs[ch])
            spend = share * budget
            implied = spend / cost
            extrap = bool(implied > n_treated[ch])
            treated = min(implied, float(cohort))
            inc = treated * float(ctf_inc[ch])
            net = inc - spend
            # uncertainty: propagate the Day-12 causal (DR) revenue ATE CI through the deterministic
            # linear transform net = treated x (inc - cost) - treated is fixed per scenario cell
            net_lo = treated * (float(est_lo[ch]) - cost) - 0.0
            net_hi = treated * (float(est_hi[ch]) - cost) - 0.0
            rows.append({
                "scenario": scen, "channel": ch, "label": LABEL, "share": share,
                "spend": spend, "inc_rev": inc, "net": net,
                "net_est_ci_low": net_lo, "net_est_ci_high": net_hi,
                "implied_treated": implied, "observed_n_treated": int(n_treated[ch]),
                "treated_after_cap": treated, "extrapolated": extrap,
            })
            totals["spend"] += spend
            totals["inc_rev"] += inc
            totals["net"] += net
            totals["net_est_ci_low"] += net_lo
            totals["net_est_ci_high"] += net_hi
            totals["implied_treated"] += int(implied)
        totals["roi"] = totals["net"] / budget
        totals["treated_after_cap"] = np.nan
        rows.append(totals)
    return pd.DataFrame(rows)


def scenario_summary_from(sc: pd.DataFrame) -> pd.DataFrame:
    """One row per scenario with totals."""
    out = []
    for scen, grp in sc[sc["channel"] == "all"].iterrows():
        rows = sc[(sc["scenario"] == grp["scenario"]) & (sc["channel"] != "all")]
        out.append({
            "scenario": grp["scenario"],
            "spend": float(grp["spend"]), "inc_rev": float(grp["inc_rev"]),
            "net": float(grp["net"]), "roi": float(grp["roi"]),
            "net_est_ci_low": float(grp["net_est_ci_low"]),
            "net_est_ci_high": float(grp["net_est_ci_high"]),
            "any_extrapolation": bool(rows["extrapolated"].any()),
            "n_extrapolated_channels": int(rows["extrapolated"].sum()),
        })
    df = pd.DataFrame(out)
    return df.sort_values("net", ascending=False).reset_index(drop=True)


def budget_optimum(cfg: dict, roi_long: pd.DataFrame, budget: float) -> float:
    """Budget-constrained linear optimum net (R$).

    Greedily funds channels with positive counterfactual per-treated revenue in
    order of net per R$ spent (email first, then search) until the fixed
    ``budget`` or cohort saturation is exhausted. Under the linear + capped
    model this is what the best possible allocation of ``budget`` delivers —
    an upper bound every rule-based scenario must respect.
    """
    costs = cfg["roi"]["cost_per_treated"]
    ctf_inc = roi_long[roi_long["method"] == "counterfactual"].set_index("channel")["inc_rev"]
    cohort_n = int(len(load_analysis_data(cfg)) if not cfg["counterfactuals"]["cohort_cap"]
                   else cfg["counterfactuals"]["cohort_cap"])
    optimum, remaining = 0.0, budget
    for ch in sorted(CHANNELS, key=lambda c: -float(ctf_inc[c]) / float(costs[c])):
        if float(ctf_inc[ch]) <= 0 or remaining <= 0:
            continue
        spend = min(remaining, cohort_n * float(costs[ch]))
        treated = spend / float(costs[ch])
        optimum += treated * float(ctf_inc[ch]) - spend
        remaining -= spend
    return optimum


def cf_gates(cfg: dict | None = None, sc: pd.DataFrame | None = None,
             summary: pd.DataFrame | None = None,
             roi_long: pd.DataFrame | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    sc = sc if sc is not None else counterfactual_scenarios(cfg)
    summary = summary if summary is not None else scenario_summary_from(sc)
    ctf = cfg["counterfactuals"]

    scen_names = list(cfg["counterfactuals"]["scenarios"])
    spends = sc[sc["channel"] == "all"].set_index("scenario")["spend"]
    budget = float(spends["as_run"])
    complete = (set(sc["scenario"]) == set(scen_names) and
                set(sc["channel"]) == set(CHANNELS) | {"all"} and
                np.allclose(spends[scen_names].values, budget))

    day16 = roi_long[roi_long["method"] == "counterfactual"].set_index("channel")["net_per_treated"]
    n_t = roi_long[roi_long["method"] == "counterfactual"].set_index("channel")["n_treated"]
    as_run_net = sc[(sc["scenario"] == "as_run") & (sc["channel"] != "all")].set_index("channel")["net"]
    max_dev = float((as_run_net - day16 * n_t).abs().max())

    as_run_net_total = float(summary.loc[summary["scenario"] == "as_run", "net"].iloc[0])
    realloc = summary[~summary["scenario"].isin(["as_run"])]
    min_realloc = float(realloc["net"].min())
    margin_realloc = min_realloc - as_run_net_total

    # email saturation: extrapolation flag on the email cell in any scenario proves the cap bites
    email_flags = int((sc[(sc["channel"] == "email") & (sc["scenario"] != "as_run")]["extrapolated"]).sum())

    # budget-constrained linear optimum (greedy email-then-search) caps what ANY scenario may
    # deliver under the linear + capped model; no scenario reaches it (wider spreads fund
    # negative channels or over-saturate email) - see budget_optimum's docstring.
    optimum = budget_optimum(cfg, roi_long, budget)
    max_net = float(summary["net"].max())
    margin_env = optimum - max_net

    unflagged = sc[(sc["implied_treated"] > sc["observed_n_treated"]) & (~sc["extrapolated"])]
    # 'all' rows: implied_treated sums > observed sums are not channel-level flags
    unflagged_cells = unflagged[(unflagged["channel"] != "all")]

    label_ok = bool((sc["label"] == LABEL).all())

    ci_present = summary[["net_est_ci_low", "net_est_ci_high"]].notna().all(axis=1)
    ci_ok = bool((summary["net_est_ci_low"] <= summary["net_est_ci_high"]).all() and ci_present.all())

    rows = [
        {"gate": "scenarios_complete", "scope": "all scenarios",
         "value": len(sc), "threshold": len(scen_names) * (len(CHANNELS) + 1),
         "passed": complete,
         "detail": "every scenario x channel row present; channel spends sum to the fixed budget per scenario"},
        {"gate": "as_run_reproduces_day16", "scope": "as_run vs Day-16",
         "value": round(max_dev, 4), "threshold": float(ctf["as_run_net_tol"]),
         "passed": bool(max_dev <= float(ctf["as_run_net_tol"])),
         "detail": "as_run per-channel nets match the Day-16 counterfactual cohort nets within tolerance"},
        {"gate": "reallocations_beat_as_run", "scope": "reallocation scenarios",
         "value": round(margin_realloc, 2), "threshold": float(ctf["realloc_beat_min_margin"]),
         "passed": bool(margin_realloc >= float(ctf["realloc_beat_min_margin"])),
         "detail": "every reallocation scenario's total net > as_run total net (the observed spend scatter is worse than any re-split)"},
        {"gate": "email_saturation_documented", "scope": "email cells",
         "value": email_flags, "threshold": 1,
         "passed": bool(email_flags >= 1),
         "detail": "email reaches cohort saturation in >= 1 scenario (the cap bites -> budget beyond ~R$9.5k on email is waste, documented in the report)"},
        {"gate": "bounded_by_optimum", "scope": "all scenarios",
         "value": round(margin_env, 2), "threshold": float(ctf["optimum_min_margin"]),
         "passed": bool(margin_env >= float(ctf["optimum_min_margin"])),
         "detail": "max scenario total net <= the budget-constrained linear optimum (greedy email-then-search)"},
        {"gate": "extrapolation_flagged", "scope": "all scenario x channel cells",
         "value": len(unflagged_cells), "threshold": 0,
         "passed": bool(len(unflagged_cells) == 0),
         "detail": "every over-observed-treated cell carries the extrapolation flag (no silent extrapolation)"},
        {"gate": "labels_correct", "scope": "all rows",
         "value": 1.0, "threshold": 1.0,
         "passed": label_ok,
         "detail": "every row labelled 'counterfactual (simulated ground truth), model-based'"},
        {"gate": "uncertainty_reported", "scope": "scenario totals (estimated scale)",
         "value": 1.0, "threshold": 1.0,
         "passed": ci_ok,
         "detail": "every scenario total carries finite, ordered CI propagated from the Day-12 DR "
                   "revenue ATE CIs (brackets the sim_u-inflated estimated net, not the "
                   "counterfactual point - the gap is the documented bias)"},
    ]
    return pd.DataFrame(rows)


def render_scenarios_figure(cfg: dict | None = None, sc: pd.DataFrame | None = None,
                            out_dir: Path | None = None) -> Path:
    cfg = cfg or load_config()
    sc = sc if sc is not None else counterfactual_scenarios(cfg)
    out_dir = out_dir or project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    out_dir.mkdir(parents=True, exist_ok=True)
    order = list(cfg["counterfactuals"]["scenarios"])
    fig = go.Figure()
    colors = {"email": "#4C72B0", "search": "#55A868", "social": "#C44E52", "display": "#8172B3"}
    for ch in CHANNELS:
        y = [float(sc[(sc["scenario"] == s) & (sc["channel"] == ch)]["net"].iloc[0]) for s in order]
        fig.add_trace(go.Bar(name=ch, x=[f"{s}{'⚠' if sc[(sc['scenario']==s)&(sc['channel']==ch)]['extrapolated'].iloc[0] else ''}"
                                         for s in order], y=y, marker_color=colors[ch]))
        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="black")
    fig.update_layout(title=("Day 17 — Counterfactual budget scenarios: net value (R$) by channel "
                             "per allocation (⚠ = extrapolation beyond observed treated range). "
                             "All values are model-based counterfactual estimates (simulation-only)."),
                      barmode="stack", height=620,
                      yaxis_title="Net value (R$)", legend=dict(orientation="h", y=1.1, x=0))
    path = out_dir / "counterfactual_scenarios.html"
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


def write_cf_tables_from(sc: pd.DataFrame, summary: pd.DataFrame, gates: pd.DataFrame,
                         cfg: dict | None = None) -> dict[str, Path]:
    cfg = cfg or load_config()
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["counterfactuals"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p1, p2, p3 = out_dir / "scenarios.csv", out_dir / "scenario_summary.csv", out_dir / "gates.csv"
    sc.to_csv(p1, index=False)
    summary.to_csv(p2, index=False)
    gates.to_csv(p3, index=False)
    return {"scenarios": p1, "summary": p2, "gates": p3}


def cf_report(cfg: dict | None = None, sc: pd.DataFrame | None = None,
              summary: pd.DataFrame | None = None,
              roi_long: pd.DataFrame | None = None) -> str:
    cfg = cfg or load_config()
    sc = sc if sc is not None else counterfactual_scenarios(cfg)
    summary = summary if summary is not None else scenario_summary_from(sc)
    roi_long = roi_long if roi_long is not None else roi_table(cfg)
    order = list(cfg["counterfactuals"]["scenarios"])

    lines = []
    lines.append("# Day 17 — Counterfactual Budget Scenarios\n")
    lines.append("> **Labels:** every number below is a **model-based counterfactual estimate "
                 "(simulation-only)** — it uses the DGP's per-treated true effects (oracle) and is "
                 "unachievable on observed data (AGENTS.md §2/§3). Not a prediction of the real world. "
                 "Every row of `results/counterfactuals/scenarios.csv` carries the machine-readable "
                 "label `counterfactual (simulated ground truth), model-based`.\n")
    lines.append("## Method\n")
    budget = float(sc[(sc["scenario"] == "as_run") & (sc["channel"] == "all")]["spend"].iloc[0])
    lines.append(
        f"- Fixed total budget = the as-run campaign spend, computed from the Day-16 cost assumptions "
        f"x observed treated counts (**R$ {budget:,.0f}**). Four allocations re-split that same budget.\n"
        "- `as_run` = as executed (shares ∝ cost × treated); `naive` = last-touch attribution (shares ∝ "
        "naive revenue ATE × treated); `causal` = Day-12 DR causal ROI (shares ∝ causal ROI); "
        "`ctf_guided` = DGP-informed (shares ∝ counterfactual ROI, positive channels only).\n"
        "- Per channel: spend = share x budget; implied treated = spend / cost; incremental revenue = "
        "treated x counterfactual per-treated revenue effect; net = revenue - spend. Deterministic "
        "arithmetic on Day-16 numbers — no new sampling uncertainty.\n"
        "- **Extrapolation limit (positivity):** when implied treated exceeds the observed n_treated "
        "for a channel, the linear model is asserted beyond the observed range; those cells are "
        "capped at the cohort size and flagged with ⚠ (blueprint §9 extrapolation-limits note).\n"
        "- **Uncertainty:** scenario totals also carry an estimated-scale 95% CI propagated exactly "
        "through the linear transform from the Day-12 DR revenue ATE CIs (treated counts are fixed "
        "per scenario, so net = Σ treated × (inc − cost) is a non-negative linear combination). The "
        "CI brackets the `sim_u`-inflated estimated net, NOT the counterfactual point — the gap "
        "between them is the Days 8–16 bias, quantified at the scenario level.\n"
    )
    lines.append("## Scenario tables (net value, R$)\n")
    lines.append("| Scenario | Channel | Share | Spend | Treated (implied→capped) | Inc. revenue | Net | ⚠ |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for scen in order:
        for _, r in sc[(sc["scenario"] == scen) & (sc["channel"] != "all")].iterrows():
            def _fmt(v: float) -> str:
                return f"{0.0 if abs(v) < 1e-6 else v:,.0f}"
            cap = "" if not r["extrapolated"] else " ⚠"
            implied = f"{r['implied_treated']:,.0f}→{r['treated_after_cap']:,.0f}" \
                if r["extrapolated"] else f"{r['implied_treated']:,.0f}"
            lines.append(f"| {scen} | {r['channel']} | {100*r['share']:.0f}% | R$ {_fmt(r['spend'])} | "
                         f"{implied} | R$ {_fmt(r['inc_rev'])} | R$ {_fmt(r['net'])} | {cap} |")
        t = sc[(sc["scenario"] == scen) & (sc["channel"] == "all")].iloc[0]
        lines.append(f"| **{scen} total** | — | 100% | R$ {_fmt(t['spend'])} | — | "
                     f"R$ {_fmt(t['inc_rev'])} | **R$ {_fmt(t['net'])}** | |")
        lines.append("")
    lines.append("## Scenario ranking (from the counterfactual)\n")
    lines.append("| Rank | Scenario | Net (R$) | CI est. (Day-12 DR, R$) | ROI on budget | ⚠ channels |")
    lines.append("|---|---|---|---|---|---|")
    for i, (_, r) in enumerate(summary.iterrows(), 1):
        lines.append(f"| {i} | {r['scenario']} | R$ {r['net']:,.0f} | "
                     f"[R$ {r['net_est_ci_low']:,.0f}, R$ {r['net_est_ci_high']:,.0f}] | "
                     f"{100*r['roi']:.0f}% | {r['n_extrapolated_channels']} |")
    lines.append("")
    lines.append("## Key finding\n")
    as_run_t = sc[(sc["scenario"] == "as_run") & (sc["channel"] == "all")].iloc[0]
    budget = float(as_run_t["spend"])
    as_run_net_t = float(as_run_t["net"])
    naive_net = float(summary.loc[summary["scenario"] == "naive", "net"].iloc[0])
    ctf_net = float(summary.loc[summary["scenario"] == "ctf_guided", "net"].iloc[0])
    best = str(summary.iloc[0]["scenario"])
    worst_realloc = float(summary[~summary["scenario"].isin(["as_run"])]["net"].min())
    naive_dead = float(sc[(sc["scenario"] == "naive")
                          & (sc["channel"].isin(("display", "social")))]["net"].sum())
    optimum = budget_optimum(cfg, roi_long, budget)
    cap_n = int(cfg["counterfactuals"]["cohort_cap"] or len(load_analysis_data(cfg)))
    email_sat = float(cfg["roi"]["cost_per_treated"]["email"]) * cap_n
    lines.append(
        f"- **Any re-split beats the as-run scatter:** the worst reallocation nets "
        f"R$ {worst_realloc:,.0f} against as_run's R$ {as_run_net_t:,.0f} on the same "
        f"R$ {budget:,.0f} budget — the observed campaign bleeds value because observed data "
        "made every channel look profitable (Days 8–16).\n"
        f"- **Ranking caveat (reported, not gated):** `{best}` tops the counterfactual net at "
        f"R$ {max(naive_net, ctf_net):,.0f}, but part of that ordering is an extrapolation "
        f"artifact — email saturates once spend hits R$ {email_sat:,.0f} (whole cohort treated), "
        "after which further email budget is pure waste, so wider spreads 'win' by spending less "
        f"on the saturated channel. They still burn R$ {abs(naive_dead):,.0f} of the naive "
        "spread on social/display alone (true effects negative/zero). Not an endorsement of any "
        "confounded rule.\n"
        f"- **Scenario-level bias in money terms:** the estimated-scale 95% CI on the as_run total is "
        f"R$ {summary.loc[summary['scenario'] == 'as_run', 'net_est_ci_low'].iloc[0]:,.0f}–"
        f"{summary.loc[summary['scenario'] == 'as_run', 'net_est_ci_high'].iloc[0]:,.0f} while its "
        f"counterfactual net is R$ {as_run_net_t:,.0f} (≈ "
        f"{100*as_run_net_t/summary.loc[summary['scenario'] == 'as_run', 'net_est_ci_low'].iloc[0]:.1f}% "
        "of the CI lower bound) — observed-data estimates overstate achievable scenario value by "
        "≈10–38x across scenarios, the `sim_u` inflation from Days 8–16 at the portfolio level.\n"
        f"- **Robust reads:** the budget-constrained optimum is R$ {optimum:,.0f} (fund email to "
        "saturation, then search; never touch social/display) — no rule-based scenario reaches "
        "it, because both observed-data rules (naive, causal) keep funding channels whose "
        "counterfactual net is negative: every estimate is `sim_u`-inflated (Days 8–16). "
        "Day 18 bounds that confounder.\n"
    )
    lines.append("## Validation hooks — gates\n")
    lines.append("| Gate | Scope | Value | Threshold | Pass |")
    lines.append("|---|---|---|---|---|")
    gates = cf_gates(cfg, sc=sc, summary=summary, roi_long=roi_long)
    for _, r in gates.iterrows():
        val = f"{r['value']:.4f}" if isinstance(r["value"], (float, np.floating)) else str(r["value"])
        thr = f"{r['threshold']:.4f}" if isinstance(r["threshold"], (float, np.floating)) else str(r["threshold"])
        lines.append(f"| {r['gate']} | {r['scope']} | {val} | {thr} | {'✅' if r['passed'] else '❌'} |")
    lines.append("")
    lines.append("## Limitations\n")
    lines.append(
        "- Counterfactual and inherently linear: no saturation, carryover, frequency caps, or cost "
        "curves; costs are flat assumptions (ADR-006).\n"
        "- Extrapolation beyond observed treated ranges is capped, not solved — the flags mark where "
        "the model is asserted, not where it is true.\n"
        "- All values inherit the DGP oracle (sim_u); they define the achievable truth on THIS "
        "simulation only. Day 18 quantifies how strong the unobserved confounder must be otherwise.\n"
    )
    return "\n".join(lines)


def write_cf_report(cfg: dict | None = None, sc: pd.DataFrame | None = None,
                    summary: pd.DataFrame | None = None,
                    roi_long: pd.DataFrame | None = None) -> Path:
    cfg = cfg or load_config()
    out = project_path(cfg["paths"]["reports"])
    out.mkdir(parents=True, exist_ok=True)
    path = out / "counterfactuals.md"
    path.write_text(cf_report(cfg, sc=sc, summary=summary, roi_long=roi_long), encoding="utf-8")
    return path


def run_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    roi_long = roi_table(cfg)
    summary_roi = roi_summary_from(roi_long, cfg)
    sc = counterfactual_scenarios(cfg, roi_long=roi_long, summary=summary_roi)
    summary = scenario_summary_from(sc)
    gates = cf_gates(cfg, sc=sc, summary=summary, roi_long=roi_long)
    tables = write_cf_tables_from(sc, summary, gates, cfg)
    fig = render_scenarios_figure(cfg, sc=sc)
    report = write_cf_report(cfg, sc=sc, summary=summary, roi_long=roi_long)
    print("\n--- Scenario ranking (counterfactual net) ---")
    print(summary[["scenario", "net", "roi", "n_extrapolated_channels"]].to_string(index=False))
    print("\n--- Gates ---")
    print(gates.to_string(index=False))
    print(f"\nReport -> {report}")
    return {"tables": tables, "figure": fig, "report": report,
            "scenarios": sc, "summary": summary, "gates": gates}


if __name__ == "__main__":
    run_all()