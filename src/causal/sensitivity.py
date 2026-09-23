"""Sensitivity analysis — Day 18 (blueprint §7.8, roadmap row 18).

Answers "how strong must an unmeasured confounder U be?" for the Day-12 DR
revenue ATEs, then measures the ACTUAL simulated confounder (sim_u) directly
and compares (simulation-only, AGENTS.md §2/§3).

Tools (documented before fitting, AGENTS.md §3):
(a) **E-value** (VanderWeele & Ding 2017), continuous-outcome approximation:
    d = ATE / SD(outcome); RR* = exp(0.91 * d); E-value = RR* + sqrt(RR*(RR*-1)).
    Interpretation: an unmeasured confounder associated with BOTH exposure and
    outcome by risk ratio >= E-value (per ~1 SD, in this approximation) would
    fully explain away the estimate. Reported for the point and for the CI
    lower bound ("explain away the entire confidence interval").
(b) **Linear bias formula** (VanderWeele 2015): observed ATE = true effect +
    delta_U * gamma_U, with delta_U = standardized difference of U between
    treated and untreated, and gamma_U = per-SD effect of U on the outcome.
    Required delta to (i) zero the estimate, (ii) bring it down to the sim
    truth are compared with the measured delta.

Because the DGP ships with a real confounder, everything is checkable:
falsification tests (treatment cannot affect sim_u; display's true effect is
0) must show large, significant "effects" — the estimation bias made visible.

Labels (AGENTS.md §2): DR rows are *estimated*; the truth and the measured
confounder / placebo rows are *simulated (DGP)*. Nothing here is an observed
Olist fact.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from src.config import load_config, project_path
from src.causal.confounders import CHANNELS
from src.causal.naive import load_analysis_data
from src.causal.roi import roi_table

LABEL_ESTIMATED = "estimated (causal DR revenue ATE, Days 8-12)"
LABEL_TRUTH = "simulated ground truth (DGP oracle, per-treated)"
LABEL_MEASURED = "simulated (measured DGP confounder sim_u)"
LABEL_PLACEBO = "simulated placebo (falsification test)"

EVALUE_OUTCOME = "sim_revenue_14d"


def d_to_rr(d: float, coef: float = 0.91) -> float:
    """Approx risk ratio from a standardized mean difference ``d``.

    VanderWeele & Ding's continuous-outcome E-value approximation:
    RR* = exp(coef * d) with coef ~ 0.91 (the ~1/0.91 conversion used in the
    E-value literature for standardized mean differences).
    """
    return float(np.exp(coef * d))


def evalue(rr: float) -> float:
    """VanderWeele-Ding E-value for a risk ratio ``rr``."""
    return float(rr + np.sqrt(rr * (rr - 1)))


def _measure(cfg: dict) -> dict:
    """Measure the actual simulated confounder (simulation-only)."""
    d = load_analysis_data(cfg)
    u = d["sim_u"].to_numpy(dtype=float)
    rev = d["sim_revenue_14d"].to_numpy(dtype=float)
    out: dict = {"n": int(len(d)), "revenue_sd": float(rev.std()),
                 "gamma": float(np.cov(u, rev)[0, 1] / u.var())}
    for ch in CHANNELS:
        t = (d[f"sim_exposed_{ch}"] == 1).to_numpy()
        n1 = int(t.sum())
        n0 = int((~t).sum())
        u1, u0 = u[t], u[~t]
        pooled = float(np.sqrt(((u1.var() * (n1 - 1)) + (u0.var() * (n0 - 1))) / (n1 + n0 - 2)))
        out[f"delta_{ch}"] = float((u1.mean() - u0.mean()) / pooled)
    return out


def master_revenue_ate(cfg: dict, master: pd.DataFrame | None = None) -> pd.DataFrame:
    """The Day-12 DR revenue ATE rows per channel (estimated scale)."""
    master = master if master is not None else pd.read_csv(
        project_path(cfg["paths"]["results"], cfg["results"]["tables"], "master_estimates.csv"))
    rows = master[(master["estimator"] == "dr") & (master["outcome"] == EVALUE_OUTCOME)]
    return rows.set_index("channel").loc[list(CHANNELS)].reset_index()


def evalue_table(cfg: dict, master: pd.DataFrame | None = None,
                 measured: dict | None = None) -> pd.DataFrame:
    """Per-channel E-values for the point estimate and the CI lower bound."""
    sens = cfg["sensitivity"]
    measured = measured or _measure(cfg)
    ate = master_revenue_ate(cfg, master)
    rows = []
    for _, r in ate.iterrows():
        d_point = float(r["point"]) / measured["revenue_sd"]
        d_ci = float(r["ci_lower"]) / measured["revenue_sd"]
        rr_point, rr_ci = d_to_rr(d_point, sens["d_to_rr_coef"]), d_to_rr(d_ci, sens["d_to_rr_coef"])
        rows.append({
            "channel": r["channel"], "label": LABEL_ESTIMATED,
            "ate_point": float(r["point"]), "ci_lower": float(r["ci_lower"]),
            "ci_upper": float(r["ci_upper"]), "n": int(r["n"]),
            "d_point": d_point, "d_ci_lower": d_ci,
            "rr_point": rr_point, "rr_ci_lower": rr_ci,
            "evalue_point": evalue(rr_point), "evalue_ci_lower": evalue(rr_ci),
        })
    return pd.DataFrame(rows)


def bias_formula_table(cfg: dict, master: pd.DataFrame | None = None,
                       roi_long: pd.DataFrame | None = None,
                       measured: dict | None = None) -> pd.DataFrame:
    """Bias-formula decomposition + required vs actual confounder strength."""
    measured = measured or _measure(cfg)
    ate = master_revenue_ate(cfg, master)
    roi_long = roi_long if roi_long is not None else roi_table(cfg)
    ctf = roi_long[roi_long["method"] == "counterfactual"].set_index("channel")["inc_rev"]
    gam = measured["gamma"]
    rows = []
    for _, r in ate.iterrows():
        ch = r["channel"]
        point = float(r["point"])
        truth = float(ctf[ch])
        bias = point - truth
        delta = measured[f"delta_{ch}"]
        pred = delta * gam
        share = pred / bias
        req_zero = point / gam
        req_truth = bias / gam
        rows.append({
            "channel": ch, "label": LABEL_ESTIMATED + " / " + LABEL_TRUTH + " / " + LABEL_MEASURED,
            "ate_point": point, "truth": truth, "observed_bias": bias,
            "gamma": gam, "delta_actual": delta, "predicted_bias": pred,
            "share_explained": share,
            "delta_req_zero": req_zero, "delta_req_truth": req_truth,
            "ratio_actual_to_req_zero": delta / req_zero,
            "ratio_actual_to_req_truth": delta / req_truth,
        })
    return pd.DataFrame(rows)


def falsification_table(cfg: dict, master: pd.DataFrame | None = None,
                        measured: dict | None = None) -> pd.DataFrame:
    """Falsification tests: (1) placebo outcome sim_u (treatment cannot affect
    it causally); (2) placebo channel display (true per-treated effect = 0)."""
    measured = measured or _measure(cfg)
    d = load_analysis_data(cfg)
    u = d["sim_u"].to_numpy(dtype=float)
    ate = master_revenue_ate(cfg, master)
    rows = []
    for ch in CHANNELS:
        t = (d[f"sim_exposed_{ch}"] == 1).to_numpy()
        diff = u[t].mean() - u[~t].mean()
        tstat, p = stats.ttest_ind(u[t], u[~t], equal_var=True)
        rows.append({
            "test": f"placebo outcome sim_u | channel {ch}", "label": LABEL_PLACEBO,
            "estimate": diff, "scale": "mean difference in sim_u",
            "effect_sd_units": measured[f"delta_{ch}"], "t_stat": float(tstat),
            "p_value": float(p), "falsified": bool(abs(tstat) >= 1.96),
        })
    disp = ate[ate["channel"] == "display"].iloc[0]
    z = float(disp["point"]) / float(disp["se"])
    p = float(2 * stats.norm.sf(abs(z)))
    rows.append({
        "test": "placebo channel display (true effect 0)", "label": LABEL_PLACEBO,
        "estimate": float(disp["point"]), "scale": "R$ per treated (DR)",
        "effect_sd_units": float(disp["point"]) / measured["revenue_sd"],
        "t_stat": z, "p_value": p, "falsified": bool(abs(z) >= 1.96),
    })
    return pd.DataFrame(rows)


def sensitivity_gates(cfg: dict, ev: pd.DataFrame | None = None,
                      bf: pd.DataFrame | None = None,
                      fals: pd.DataFrame | None = None,
                      measured: dict | None = None) -> pd.DataFrame:
    """Day-18 validation hooks ("Each claim stress-tested")."""
    sens = cfg["sensitivity"]
    measured = measured or _measure(cfg)
    ev = ev if ev is not None else evalue_table(cfg)
    bf = bf if bf is not None else bias_formula_table(cfg, measured=measured)
    fals = fals if fals is not None else falsification_table(cfg, measured=measured)

    ev_ok = bool(np.isfinite(ev[["evalue_point", "evalue_ci_lower"]]).all().all()
                 and (ev["evalue_point"] > 1).all()
                 and (ev["evalue_ci_lower"] <= ev["evalue_point"] + 1e-9).all())
    max_ev = float(ev["evalue_point"].max())
    fragility = bool(1 < max_ev <= float(sens["max_point_evalue"]))
    share_min = float(bf["share_explained"].min())
    formula_ok = bool(share_min >= float(sens["share_explained_min"]))
    delta_min = min(float(measured[f"delta_{ch}"]) for ch in CHANNELS)
    actual_ok = bool(delta_min >= float(sens["actual_u_min_delta"]))
    t_min = float(fals["t_stat"].abs().min())
    placebo_ok = bool(t_min >= float(sens["min_placebo_t"]))
    unc_ok = bool((ev[["ci_lower", "ci_upper"]].notna().all().all()) and ev["n"].gt(0).all())
    expected_bf_label = f"{LABEL_ESTIMATED} / {LABEL_TRUTH} / {LABEL_MEASURED}"
    labels_ok = bool((ev["label"] == LABEL_ESTIMATED).all()
                     and (bf["label"] == expected_bf_label).all()
                     and (fals["label"] == LABEL_PLACEBO).all())

    rows = [
        {"gate": "evalue_reported", "scope": "all channels",
         "value": 1.0, "threshold": 1.0, "passed": ev_ok,
         "detail": "point + CI-lower E-values finite, > 1, and CI EV <= point EV for every channel"},
        {"gate": "evalue_fragility_documented", "scope": "point E-values",
         "value": round(max_ev, 3), "threshold": float(sens["max_point_evalue"]),
         "passed": fragility,
         "detail": "max point E-value in (1, max_point_evalue]: the estimates are NOT robust - a modest unmeasured confounder suffices"},
        {"gate": "bias_formula_explains_most", "scope": "all channels",
         "value": round(share_min, 3), "threshold": float(sens["share_explained_min"]),
         "passed": formula_ok,
         "detail": "linear bias formula delta_U * gamma_U reproduces >= share_explained_min of every observed bias"},
        {"gate": "actual_u_is_real_confounder", "scope": "all channels",
         "value": round(delta_min, 3), "threshold": float(sens["actual_u_min_delta"]),
         "passed": actual_ok,
         "detail": "measured treated/untreated difference in sim_u >= actual_u_min_delta SD units per channel"},
        {"gate": "placebo_tests_falsified", "scope": "placebo outcome + placebo channel",
         "value": round(t_min, 2), "threshold": float(sens["min_placebo_t"]),
         "passed": placebo_ok,
         "detail": "both falsification tests show |t| >= min_placebo_t: bias is detectable, not estimator luck"},
        {"gate": "uncertainty_reported", "scope": "all channels",
         "value": 1.0, "threshold": 1.0, "passed": unc_ok,
         "detail": "DR rows carry SE/CI/n from the Day-12 master table (E-values derived from point AND ci_lower)"},
        {"gate": "labels_correct", "scope": "all output rows",
         "value": 1.0, "threshold": 1.0, "passed": labels_ok,
         "detail": "estimated / simulated truth / simulated measured / simulated placebo labels as required"},
    ]
    return pd.DataFrame(rows)


def sensitivity_report(cfg: dict, ev: pd.DataFrame | None = None,
                       bf: pd.DataFrame | None = None,
                       fals: pd.DataFrame | None = None,
                       gates: pd.DataFrame | None = None,
                       master: pd.DataFrame | None = None,
                       measured: dict | None = None) -> str:
    """Assemble the Day-18 markdown report."""
    measured = measured or _measure(cfg)
    ev = ev if ev is not None else evalue_table(cfg)
    bf = bf if bf is not None else bias_formula_table(cfg, measured=measured)
    fals = fals if fals is not None else falsification_table(cfg, measured=measured)
    gates = gates if gates is not None else sensitivity_gates(cfg, ev, bf, fals, measured)
    ate = master_revenue_ate(cfg, master)
    rev_sd = measured["revenue_sd"]
    gam = measured["gamma"]

    lines: list[str] = []
    lines.append("# Day 18 — Sensitivity: how strong must the unobserved confounder be?\n")
    lines.append("> **Labels (AGENTS.md §2):** *estimated* = Day-12 causal DR revenue ATE on observed (simulated "
                 f"marketing) data; *simulated ground truth* = DGP oracle per-treated effect; *simulated measured* "
                 "= the confounder `sim_u` read directly out of the DGP (the real U of this simulation); "
                 "*simulated placebo* = falsification tests. None of this is an observed Olist fact.\n")
    lines.append("## The question\n")
    lines.append(f"- Every Day-8–17 observed-data estimator reports a positive revenue ATE per channel "
                 f"(≈ R$ {ate['point'].min():,.2f}–{ate['point'].max():,.2f}), yet the sim truth is email/search "
                 "profitable and social/display worthless or negative. Day 18 asks: **how strong would an "
                 "unmeasured confounder have to be to produce that entire set of estimates by itself — and how "
                 "strong is the actual `sim_u` built into this DGP?**\n")
    lines.append("## Method (stated before the numbers)\n")
    lines.append(
        f"- **E-value (VanderWeele & Ding 2017).** d = ATE / SD(revenue) = ATE / {rev_sd:.2f}; "
        f"RR* = exp({cfg['sensitivity']['d_to_rr_coef']}·d); E-value = RR* + √(RR*·(RR*−1)). An unmeasured "
        "confounder associated with **both** exposure and outcome at risk ratio ≥ E-value (per the RR/mean-"
        "difference approximation) would fully explain away the estimate. Reported for the point *and* for the "
        "CI lower bound (explain away the whole CI).\n"
        "- **Linear bias formula.** observed = truth + bias, with bias = δ_U·γ_U: δ_U = standardized difference "
        "of U between treated/untreated, γ_U = per-SD effect of U on revenue. From it, the **required δ** to "
        f"(i) zero the estimate and (ii) reach the truth is δ_required = (point − target)/γ_U with γ_U = {gam:.2f} "
        "R$/SD\n"
        "- **Measured U (simulation-only).** `sim_u` is known in the DGP, so δ_U and γ_U are measured directly "
        "instead of guessed — this is the honest yardstick for the bounds above.\n"
        "- **Falsification (placebo) tests.** (1) outcome `sim_u`: the treatment cannot causally change `sim_u` "
        "(it is pre-treatment), so any estimated effect on it is pure selection; (2) channel display: its true "
        "per-treated effect is 0, so any estimated effect on it is pure bias. Both tests are expected to FAIL "
        "hugely — that failure is the evidence, not a bug.\n")
    lines.append("## E-value table (explain-away strength)\n")
    lines.append("| Channel | ATE (R$) | 95% CI | E-value (point) | E-value (CI lower) | n |")
    lines.append("|---|---|---|---|---|---|")
    for _, r in ev.iterrows():
        lines.append(f"| {r['channel']} | R$ {r['ate_point']:,.2f} | R$ {r['ci_lower']:,.2f}–"
                     f"{r['ci_upper']:,.2f} | {r['evalue_point']:.2f} | {r['evalue_ci_lower']:.2f} | "
                     f"{r['n']:,} |")
    lines.append("")
    lines.append(f"- E-values cluster around **{ev['evalue_point'].median():.2f}–"
                 f"{ev['evalue_point'].max():.2f}** — a confounder with per-~SD RR ≈ "
                 f"{ev['evalue_point'].mean():.2f} on BOTH the treatment and the outcome explains the estimates "
                 "away entirely. By epidemiology convention that is **modest robustness**: the observed positive "
                 "effects are not robust to even a moderate unmeasured confounder.\n")
    lines.append("## Bias formula: required vs actual confounder strength\n")
    lines.append("| Channel | Bias (obs − truth) | γ_U (R$/SD) | δ_U required→truth | δ_U actual (measured) | bias explained |")
    lines.append("|---|---|---|---|---|---|")
    for _, r in bf.iterrows():
        lines.append(f"| {r['channel']} | R$ {r['observed_bias']:,.2f} | {r['gamma']:.1f} | "
                     f"{r['delta_req_truth']:.2f} | {r['delta_actual']:.2f} | "
                     f"{100*r['share_explained']:.0f}% |")
    lines.append("")
    lines.append(f"- The **actual** confounder (measured `sim_u`) shows δ_U ≈ "
                 f"{min(float(measured[f'delta_{c}']) for c in CHANNELS):.2f}–"
                 f"{max(float(measured[f'delta_{c}']) for c in CHANNELS):.2f} SD between treated and untreated "
                 f"— essentially as strong as the ≈ "
                 f"{bf['delta_req_truth'].max():.2f} the formula needs to pull every estimate down to the truth. "
                 "The linear bias formula δ_U·γ_U alone reproduces **"
                 f"{bf['share_explained'].min()*100:.0f}–{bf['share_explained'].max()*100:.0f}% of the observed "
                 "bias** per channel (the residual is nonlinearity in the conversion/revenue DGP).\n"
                 "- Read together with the E-value: the conservative worst-case bound (E-value ≈ "
                 f"{ev['evalue_point'].max():.2f}, symmetric on both axes) is far above the actual outcome-side "
                 f"strength (γ_U/SD ≈ {gam/rev_sd:.2f} SD), yet the measured confounder still explains nearly all "
                 "of the bias — the E-value is a worst-case guarantee for a *binary, unmeasured* U; the measured "
                 "continuous U is its real-life counterpart here and the exact linear formula is much tighter.\n")
    lines.append("## Falsification (placebo) tests\n")
    lines.append("| Test | Estimate | Scale | |t| | p | Falsified? |")
    lines.append("|---|---|---|---|---|---|")
    for _, r in fals.iterrows():
        lines.append(f"| {r['test']} | {r['estimate']:.4f} | {r['scale']} | |{r['t_stat']:.1f}| | "
                     f"{r['p_value']:.2g} | {'⚠ yes (bias visible)' if r['falsified'] else 'no'} |")
    lines.append("")
    lines.append("- The placebo outcome `sim_u` (a variable the treatment **cannot** affect) shows a ~0.7-SD, "
                 "enormously significant 'effect' of every channel (|t| ≈ "
                 f"{fals['t_stat'].abs().max():.0f}) — pure selection through `sim_u`. The placebo "
                 "channel *display* (true effect 0) shows a positive R$ 16 estimate with |t| ≈ "
                 f"{float(fals.loc[fals['test'] == 'placebo channel display (true effect 0)', 't_stat'].iloc[0]):.0f}. "
                 "Both placebos fail loudly: observed-data estimation on this DGP detects effects that are not there.\n")
    lines.append("## Cross-estimator stress (alt adjustment sets/estimators)\n")
    lines.append("Day 9–12 already showed naive ≈ OLS ≈ IPW ≈ DR ≈ ATT ≈ backdoor on every channel (convergence "
                 "gates, `results/tables/master_estimates.csv`); the cross-estimator range is tiny relative to the "
                 "bias quantified above — so the positive estimates are **stable**, which is exactly why Day 18's "
                 "confounder bounds, not another estimator, are the honest stress test.\n")
    lines.append("## Key finding\n")
    lines.append(f"- **A moderate unmeasured confounder fully explains the observed channel effects** "
                 f"(point E-value ≈ {ev['evalue_point'].mean():.2f}, CI-lower E-value ≈ "
                 f"{ev['evalue_ci_lower'].mean():.2f}): on observed (simulated) data alone, the marketing "
                 "channel 'effects' should not be treated as causal.\n"
                 f"- **The actual confounder is real and nearly sufficient:** measured δ_U ≈ "
                 f"{bf['delta_actual'].mean():.2f} vs required-to-truth ≈ {bf['delta_req_truth'].mean():.2f}; "
                 "the bias formula covers "
                 f"{bf['share_explained'].min()*100:.0f}–{bf['share_explained'].max()*100:.0f}% of every "
                 "observed bias, and its residual matches DGP nonlinearity — i.e. the observed-data story "
                 "**(email/search look ~7× too good; social/display look profitable at all) is explained by "
                 "`sim_u`, and Days 16–17 already priced that in (ROI overstatement ≈7.5×/11×; scenario "
                 "overstatement ≈10–38×).**\n"
                 "- Day 19 turns this bound into the dashboard's honest headline: 'the observed lift is "
                 "bias-compatible; the causal bounds are wide; the counterfactual read is email-first, search "
                 "second, stop display/social'.\n")
    lines.append("## Validation hooks — gates\n")
    lines.append("| Gate | Scope | Value | Threshold | Pass |")
    lines.append("|---|---|---|---|---|")
    for _, g in gates.iterrows():
        lines.append(f"| {g['gate']} | {g['scope']} | {g['value']:.3g} | {g['threshold']:.3g} | "
                     f"{'✅' if g['passed'] else '❌'} |")
    lines.append("")
    lines.append("## Limitations\n")
    lines.append("- The E-value RR approximation (exp(0.91·d)) is a standard continuous-outcome bridge, an "
                 "approximation, not exact for this revenue distribution; the bias-formula numbers are the exact "
                 "linear decomposition and should be read as primary.\n"
                 "- The measured confounder and the truth come from the DGP — they exist ONLY in this simulation "
                 "and prove its internal consistency; they are not a claim about real Olist marketing.\n"
                 "- The bias formula assumes linearity in U on the revenue scale; the residual gap (≤ "
                 f"{100-100*bf['share_explained'].min():.0f}% on social) is where nonlinearity hides.\n"
                 "- No unobserved-confounding bound can certify the absence of OTHER confounders on top of "
                 "`sim_u`; the E-value quantifies fragility, it does not remove it.\n")
    return "\n".join(lines)


def write_sensitivity_tables(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame,
                             fals: pd.DataFrame, gates: pd.DataFrame) -> dict:
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["sensitivity"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p = {k: out_dir / f"{k}.csv" for k in ("evalue", "bias_formula", "falsification", "gates")}
    ev.to_csv(p["evalue"], index=False)
    bf.to_csv(p["bias_formula"], index=False)
    fals.to_csv(p["falsification"], index=False)
    gates.to_csv(p["gates"], index=False)
    return p


def sensitivity_figure_evalue(cfg: dict, ev: pd.DataFrame, measured: dict | None = None) -> go.Figure:
    """E-value dot plot per channel with CI-lower E-value whisker."""
    measured = measured or _measure(cfg)
    fig = go.Figure()
    for _, r in ev.iterrows():
        fig.add_trace(go.Bar(name=r["channel"], x=[r["channel"]], y=[r["evalue_point"]],
                             marker_color={"email": "#2c7fb8", "search": "#31a354",
                                           "display": "#de2d26", "social": "#ff7f0e"}[r["channel"]],
                             error_y=dict(type="data", symmetric=False,
                                          array=[r["evalue_point"] - r["evalue_ci_lower"]],
                                          arrayminus=[0.0])))
    fig.add_hline(y=1.0, line_dash="dot", line_color="grey",
                  annotation_text="E-value = 1 (no confounding needed)")
    fig.update_layout(title="Day 18 — E-value per channel (how strong must an unmeasured confounder be?)",
                      yaxis_title="E-value (risk-ratio scale, per ~SD)",
                      xaxis_title="Channel", showlegend=False, template="plotly_white")
    return fig


def sensitivity_figure_bias(cfg: dict, bf: pd.DataFrame) -> go.Figure:
    """Observed vs formula-predicted bias per channel."""
    fig = go.Figure()
    fig.add_trace(go.Bar(name="observed bias (DR − truth)", x=bf["channel"], y=bf["observed_bias"],
                         marker_color="#3182bd"))
    fig.add_trace(go.Bar(name="predicted bias (δ_U × γ_U)", x=bf["channel"], y=bf["predicted_bias"],
                         marker_color="#e6550d"))
    fig.update_layout(title="Day 18 — Bias decomposition: observed vs linear-formula prediction",
                      yaxis_title="Bias in revenue ATE (R$ per treated)",
                      xaxis_title="Channel", barmode="group", template="plotly_white")
    return fig


def main(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    measured = _measure(cfg)
    ev = evalue_table(cfg, measured=measured)
    bf = bias_formula_table(cfg, measured=measured)
    fals = falsification_table(cfg, measured=measured)
    gates = sensitivity_gates(cfg, ev, bf, fals, measured)
    print(bf[["channel", "observed_bias", "delta_actual", "delta_req_truth",
              "share_explained"]].to_string(index=False))
    print("\n--- Gates ---")
    print(gates[["gate", "value", "threshold", "passed"]].to_string(index=False))
    paths = write_sensitivity_tables(cfg, ev, bf, fals, gates)
    for p in paths.values():
        print("Table ->", p)
    fig_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    fig_dir.mkdir(parents=True, exist_ok=True)
    sensitivity_figure_evalue(cfg, ev, measured).write_html(fig_dir / "evalue.html")
    sensitivity_figure_bias(cfg, bf).write_html(fig_dir / "bias_decomposition.html")
    print("Fig ->", fig_dir / "evalue.html", "|", fig_dir / "bias_decomposition.html")
    report = project_path(cfg["paths"]["reports"], "sensitivity.md")
    report.write_text(sensitivity_report(cfg, ev, bf, fals, gates, measured=measured), encoding="utf-8")
    print("Report ->", report)


if __name__ == "__main__":
    main()