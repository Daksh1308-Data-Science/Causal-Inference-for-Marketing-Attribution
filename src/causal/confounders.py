"""Confounder audit & identification strategy (Day 4).

Classifies every candidate variable in the analysis as:

    Confounder / Treatment / Outcome / Mediator / Collider / Irrelevant

per Plan.md Step 4, each row with a causal justification (`rationale`), an
`adjust` decision (include in the covariate model? never?), and a note on
whether the variable is ACTIVE in the Day-3 preview simulation DGP or only
INTENDED for the full Week-2 simulation.

The identification strategy (AGENTS.md §3 — written BEFORE fitting) is
rendered per channel alongside the audit so Days 6-12 estimators inherit
the adjustment set mechanically, not by ad-hoc choice.

Deliverables written by `build_reports()`:
  * results/tables/confounder_audit.csv   — machine-readable audit
  * reports/confounder_audit.md           — narrative + full reasoning
"""
from __future__ import annotations

import pandas as pd

from src.config import load_config, project_path

CHANNELS = ("email", "social", "search", "display")

# role vocabulary (Plan.md Step 4)
ROLE_CONFOUNDER = "Confounder"
ROLE_TREATMENT = "Treatment"
ROLE_OUTCOME = "Outcome"
ROLE_MEDIATOR = "Mediator"
ROLE_COLLIDER = "Collider"
ROLE_IRRELEVANT = "Irrelevant"

# adjust vocabulary
ADJUST_YES = "yes"      # put in the covariate/adjustment model
ADJUST_NO = "no"        # do NOT adjust (mediator / collider / mechanism output)
ADJUST_NEVER = "never"  # must never enter a model (treatment/outcome/benchmark/unobservable)


def _active_confounders(cfg: dict) -> dict[str, list[str]]:
    """Observed confounders ACTIVE in the preview DGP, per channel.

    The preview targeting rule assigns a channel's exposure via a logistic
    score on exactly the features in `assignment_coefs` (plus sim_u).
    Because the outcome also depends on those features, each coef feature is
    a common cause of assignment and outcome -> confounder for that channel.

    This is the mechanical definition the DAG (Day 5) and estimators
    (Days 6-12) will reuse.
    """
    return {
        ch: list(cfg["simulation"]["preview"]["channels"][ch]["assignment_coefs"].keys())
        for ch in CHANNELS
    }


def adjustment_sets(cfg: dict | None = None) -> dict[str, list[str]]:
    """Sufficient observed adjustment set per channel (preview DGP).

    = active confounders. sim_u is intentionally EXCLUDED (it is the
    unobserved-confounder source; sensitivity analysis owns it, AGENTS §3).
    """
    cfg = cfg or load_config()
    return {ch: sorted(c) for ch, c in _active_confounders(cfg).items()}


# --- audit rows ---------------------------------------------------------------

def audit_rows(cfg: dict | None = None) -> list[dict]:
    """One dict per candidate variable. See module docstring for semantics."""
    cfg = cfg or load_config()
    active = _active_confounders(cfg)

    # variable -> channels whose targeting rule weights it (for readable notes)
    active_channels = {v: [] for ch in CHANNELS for v in active[ch]}
    for ch in CHANNELS:
        for v in active[ch]:
            active_channels.setdefault(v, []).append(ch)

    rows: list[dict] = []
    for ch in CHANNELS:
        rows.append(
            {
                "variable": f"sim_exposed_{ch}",
                "source": "simulated",
                "role": ROLE_TREATMENT,
                "adjust": ADJUST_NEVER,
                "channels": ch,
                "active_in_preview": True,
                "rationale": (
                    f"Exposure flag for channel '{ch}' drawn from the logistic targeting "
                    f"rule. It is the TREATMENT of the causal question — model predicts "
                    f"the effect OF this flag, never adjusts for it."
                ),
                "note": "Estimate its effect on conversion/revenue (ATE/ATT/CATE).",
            }
        )

    rows += [
        {
            "variable": "sim_converted_14d",
            "source": "simulated",
            "role": ROLE_OUTCOME,
            "adjust": ADJUST_NEVER,
            "channels": "all",
            "active_in_preview": True,
            "rationale": (
                "Primary outcome: 0/1 purchase within the 14-day outcome window. "
                "It is an effect, not a cause — never a covariate."
            ),
            "note": "Primary estimand target.",
        },
        {
            "variable": "sim_revenue_14d",
            "source": "simulated",
            "role": ROLE_OUTCOME,
            "adjust": ADJUST_NEVER,
            "channels": "all",
            "active_in_preview": True,
            "rationale": (
                "Secondary outcome: follow-on revenue (0 if not converted). "
                "Post-treatment, strongly tied to conversion — modeled as an outcome, "
                "never adjusted."
            ),
            "note": "Secondary estimand target (revenue-online).",
        },
        {
            "variable": "recency_days",
            "source": "observed",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "email, display",
            "active_in_preview": True,
            "rationale": (
                "Days since the customer's last purchase. Drives targeting "
                "(reactivation of lapsed buyers) AND purchase propensity, so it is a "
                "common cause of assignment and outcome -> confounder."
            ),
            "note": f"Active in preview channels: {', '.join(active_channels['recency_days'])}.",
        },
        {
            "variable": "order_count",
            "source": "observed",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "email, search, social",
            "active_in_preview": True,
            "rationale": (
                "Purchase frequency. Higher-frequency customers are more likely "
                "targeted (email, search, social weight it) and more likely to convert -> confounder."
            ),
            "note": "Active in email, search, social targeting; NOT in display.",
        },
        {
            "variable": "total_revenue",
            "source": "observed",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "all",
            "active_in_preview": True,
            "rationale": (
                "Monetary value. High-value customers are preferentially exposed and "
                "have higher baseline intent/revenue -> confounder."
            ),
            "note": "Active in every channel's targeting rule.",
        },
        {
            "variable": "tenure_days",
            "source": "observed",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "search, social",
            "active_in_preview": True,
            "rationale": (
                "Customer age. Search targets new/active customers, social targets "
                "incumbent high-frequency ones; tenure also correlates with intent -> "
                "confounder for those channels."
            ),
            "note": f"Targeted on in preview channels: {', '.join(active_channels['tenure_days'])}.",
        },
        {
            "variable": "review_score_avg",
            "source": "observed",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "email",
            "active_in_preview": True,
            "rationale": (
                "Satisfaction/engagement proxy. Email's targeting rule weights it and "
                "it enters baseline intent -> common cause for the email analysis. "
                "For other channels it is an outcome-only predictor (harmless to include)."
            ),
            "note": "Active in email targeting only.",
        },
        {
            "variable": "avg_order_value",
            "source": "derived",
            "role": ROLE_IRRELEVANT,
            "adjust": ADJUST_NO,
            "channels": "all",
            "active_in_preview": True,
            "rationale": (
                "Total revenue / order count — a deterministic transformation of two "
                "already-included confounders. It has no independent assignment edge in "
                "the preview DGP, so it adds no confounding control; including it only "
                "risks collinearity."
            ),
            "note": "Optional precision covariate at most; excluded to avoid collinearity.",
        },
        {
            "variable": "review_count",
            "source": "observed",
            "role": ROLE_IRRELEVANT,
            "adjust": ADJUST_NO,
            "channels": "all",
            "active_in_preview": False,
            "rationale": (
                "Not used by the preview targeting rule nor the outcome equation; "
                "carries no confounding signal in the current DGP."
            ),
            "note": "May gain a role in the full simulation (engagement proxy).",
        },
        {
            "variable": "category_affinity_top",
            "source": "observed",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "all",
            "active_in_preview": False,
            "rationale": (
                "Product-category affinity is an INTENDED confounder per the simulation "
                "design (category drives both targeting and demand). It is NOT yet wired "
                "into the Day-3 preview DGP; the full Week-2 simulation activates it."
            ),
            "note": "INACTIVE in preview -> balance check on it is a placebo until Week 2.",
        },
        {
            "variable": "state",
            "source": "observed",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "all",
            "active_in_preview": False,
            "rationale": (
                "Geography is an INTENDED confounder (regional demand + regional "
                "targeting). Not active in the preview DGP; activated in the full simulation."
            ),
            "note": "INACTIVE in preview -> balance check on it is a placebo until Week 2.",
        },
        {
            "variable": "sim_u",
            "source": "simulated",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_NEVER,
            "channels": "all",
            "active_in_preview": True,
            "rationale": (
                "Latent purchase intent, the DELIBERATELY unobserved confounder. It "
                "drives both assignment and outcome (confounding by design), so even "
                "perfect adjustment on observed features leaves residual bias. It is "
                "never a covariate: sensitivity analysis (Day 18) and ground-truth "
                "benchmarking use it."
            ),
            "note": "Unobservable in the real world — this is the point of the sensitivity layer.",
        },
        {
            "variable": "sim_p_<channel>",
            "source": "simulated",
            "role": ROLE_IRRELEVANT,
            "adjust": ADJUST_NO,
            "channels": "all",
            "active_in_preview": True,
            "rationale": (
                "Targeting probability = the assignment MECHANISM output (function of "
                "observed features AND sim_u). Knowing it is a design aid; as a covariate "
                "it is neither a confounder nor a mediator — it IS the assignment rule. "
                "Use it for overlap diagnostics and (its estimate) for IPW/Matching "
                "(Days 6-7, 10), never as a regression regressor."
            ),
            "note": "Propensity score source for Days 6/7/10.",
        },
        {
            "variable": "sim_ground_truth_<channel>",
            "source": "simulated",
            "role": ROLE_IRRELEVANT,
            "adjust": ADJUST_NEVER,
            "channels": "all",
            "active_in_preview": True,
            "rationale": (
                "The embedded TRUE effect (log-odds). It is the answer key for "
                "ground-truth recovery (Days 8-12) — must never leak into any estimator."
            ),
            "note": "Evaluation-only column.",
        },
        {
            "variable": "click / session (conceptual)",
            "source": "structural",
            "role": ROLE_MEDIATOR,
            "adjust": ADJUST_NO,
            "channels": "all",
            "active_in_preview": False,
            "rationale": (
                "In real digital marketing, exposure -> click/session -> conversion is a "
                "mediator chain. Conditioning on the mediator blocks the very path we "
                "want to estimate. Absent from the Olist/preview data, but the DAG keeps "
                "the node to forbid accidental adjustment."
            ),
            "note": "NEVER adjust (blueprint §5).",
        },
        {
            "variable": "co-exposure / channels-seen count (conceptual)",
            "source": "structural",
            "role": ROLE_COLLIDER,
            "adjust": ADJUST_NO,
            "channels": "all",
            "active_in_preview": False,
            "rationale": (
                "A customer's total observed channels is a collider when exposures share "
                "common causes (conditioning on it induces selection bias). Joint "
                "multi-channel models must therefore be handled with care; per-channel "
                "analyses sidestep it."
            ),
            "note": "NEVER adjust (blueprint §5).",
        },
        {
            "variable": "first_order_date / last_order_date",
            "source": "observed",
            "role": ROLE_IRRELEVANT,
            "adjust": ADJUST_NO,
            "channels": "all",
            "active_in_preview": False,
            "rationale": (
                "Raw timestamps are not modeled directly; they are transformed into "
                "tenure_days / recency_days (the confounders) and cohort membership. "
                "The derived forms carry the causal signal."
            ),
            "note": "Feature-engineering inputs.",
        },
        {
            "variable": "customer_id",
            "source": "observed",
            "role": ROLE_IRRELEVANT,
            "adjust": ADJUST_NO,
            "channels": "all",
            "active_in_preview": True,
            "rationale": "Identifier/primary key. No causal role; unit of analysis only.",
            "note": "Row key.",
        },
        {
            "variable": "campaign timing / seasonality (conceptual)",
            "source": "structural",
            "role": ROLE_CONFOUNDER,
            "adjust": ADJUST_YES,
            "channels": "all",
            "active_in_preview": False,
            "rationale": (
                "Seasonal demand co-moves with campaign scheduling in the real world "
                "(an intended confounder). The preview is a single campaign snapshot, so "
                "timing is constant; the full campaign-date grid (Week 2) must include it."
            ),
            "note": "Constant in preview; introduce with the campaign grid.",
        },
    ]
    return rows


def build_audit_table(cfg: dict | None = None) -> pd.DataFrame:
    """Audit as a tidy DataFrame (one row per variable)."""
    cols = ["variable", "source", "role", "adjust", "channels", "active_in_preview", "rationale", "note"]
    return pd.DataFrame(audit_rows(cfg), columns=cols)


# --- reports ------------------------------------------------------------------

def build_reports() -> tuple[pd.DataFrame, str]:
    """Write the CSV audit + markdown report; returns (table, md_path)."""
    cfg = load_config()
    table = build_audit_table(cfg)

    tab_out = project_path(cfg["paths"]["results"], cfg["results"]["tables"])
    tab_out.mkdir(parents=True, exist_ok=True)
    csv_path = tab_out / "confounder_audit.csv"
    table.to_csv(csv_path, index=False)

    md = render_markdown(table, cfg)
    rep_out = project_path(cfg["paths"]["reports"])
    rep_out.mkdir(parents=True, exist_ok=True)
    md_path = rep_out / "confounder_audit.md"
    md_path.write_text(md, encoding="utf-8")
    return table, str(md_path)


def render_markdown(table: pd.DataFrame, cfg: dict | None = None) -> str:
    """Render the narrative report (identification strategy + audit table)."""
    cfg = cfg or load_config()
    adjust_sets = adjustment_sets(cfg)

    lines: list[str] = []
    lines.append("# Confounder Audit & Identification Strategy (Day 4)")
    lines.append("")
    lines.append("Causal Inference for Marketing Attribution — written **before fitting** (AGENTS.md §3).")
    lines.append("")
    lines.append("## 1. Identification strategy (per channel)")
    lines.append("")
    for ch in CHANNELS:
        eff = cfg["simulation"]["preview"]["channels"][ch]["effect_log_odds"]
        narr = cfg["simulation"]["preview"]["channels"][ch]["narrative"]
        adj = ", ".join(f"`{v}`" for v in adjust_sets[ch])
        lines.append(f"### Channel: `{ch}`  (embedded true effect log-odds = {eff:+} — {narr})")
        lines.append("")
        lines.append(
            f"* **Causal question:** what is the average causal effect of exposure to "
            f"`sim_exposed_{ch}` on 14-day conversion and follow-on revenue for the "
            f"94,983-customer Olist cohort?"
        )
        lines.append(f"* **Treatment:** `sim_exposed_{ch}` (0/1).")
        lines.append("* **Outcomes:** `sim_converted_14d` (primary), `sim_revenue_14d` (secondary).")
        lines.append(
            f"* **Sufficient observed adjustment set:** {adj} "
            f"(common causes of assignment and outcome in the preview DGP)."
        )
        lines.append(
            "* **Why assignment is confounded:** the targeting rule scores customers on "
            "those features (plus latent `sim_u`), so exposed customers already differ in "
            "baseline intent — naive exposure-vs-control comparisons are biased."
        )
        lines.append("")
    lines.append("## 2. Assumptions checklist (evidence & limitation)")
    lines.append("")
    lines.append("| Assumption | Evidence | Status | Limitation |")
    lines.append("|------------|----------|--------|------------|")
    lines.append(
        "| Exchangeability given the adjustment set | Targeting rule is a deterministic "
        "function of the observed features + `sim_u`; conditioning on the observed set "
        "closes all observed backdoor paths | **Violated by design** (residual `sim_u` "
        "confounding) | Sensitivity analysis (Day 18) quantifies how strong U must be to "
        "explain results |"
    )
    lines.append(
        "| Positivity / overlap | Exposure rates 26-37% per channel (Day-3 preview); "
        "propensity score must avoid extremes | To verify (Day 6 overlap diagnostics) | "
        "Customers deterministic in targeting (impossible scores) would break it |"
    )
    lines.append(
        "| Consistency | Exposure flag is well-defined (single campaign snapshot, no "
        "dose variants) | Plausible in preview | Full campaign grid (Week 2) adds timing "
        "variants -> re-check |"
    )
    lines.append(
        "| SUTVA / no interference | One customer's exposure does not affect another's "
        "outcome in the simulation (no peer effects wired) | Plausible in the sim | Real "
        "word-of-mouth spillover would violate; per-channel analysis limits the joint "
        "multi-channel issue |"
    )
    lines.append("")
    lines.append("## 3. Confounder audit table")
    lines.append("")
    lines.append("Every candidate variable classified per Plan.md Step 4 with rationale. ")
    lines.append("`active_in_preview` marks whether the variable plays a causal role in the ")
    lines.append("Day-3 preview DGP (false = intended for the full Week-2 simulation; ")
    lines.append("balance checks on it are placebos until then).")
    lines.append("")
    lines.append(table.to_markdown(index=False))
    lines.append("")
    lines.append("## 4. Adjustment sets (machine-readable)")
    lines.append("")
    lines.append("```")
    for ch, s in adjust_sets.items():
        lines.append(f"{ch}: {s}")
    lines.append("sim_u: EXCLUDED by design (unobserved-confounder source; sensitivity only)")
    lines.append("```")
    return "\n".join(lines)


if __name__ == "__main__":
    table, path = build_reports()
    print(f"wrote {len(table)} audit rows -> results/tables/confounder_audit.csv")
    print(f"wrote report -> {path}")
    print("\nadjustment sets:", adjustment_sets())