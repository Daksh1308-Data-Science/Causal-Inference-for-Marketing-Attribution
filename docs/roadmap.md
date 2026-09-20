# 21-Day Roadmap

Execution plan per `Plan.md` §20. Status legend: ⬜ not started · 🟡 in progress · ✅ done · ❌ blocked/failed.

**Stage gates:** Week 1 → human validation → Week 2 → human validation → Week 3 → human validation → `v1.0`.

---

## Week 0 — Governance (done)

- [x] ✅ Day 0 — Governance docs, AGENTS.md, blueprint, roadmap, decisions, feasibility, status.

## Week 1 — Data + Causal Framework (Days 1–7)

| Day | Focus | Tasks (Python / SQL) | Deliverable | Validation | Commit | Status |
|-----|-------|----------------------|-------------|------------|--------|:------:|
| 1 | Env + data | Restore pinned reqs into `.venv`; extended env gate (dowhy0.8 classic API, causalml, econml, streamlit, pymysql); verify MySQL80 + credentials in `.env`; create `olist` DB + `olist_app` user; download Olist CSVs → `data/raw/` | Working env + raw data in MySQL | Imports pass; live DB connection; row counts vs Olist docs | `Day 1: env gate + MySQL ingestion` | ✅ |
| 2 | Data engineering | `schema.sql`, `load.sql`; bulk-load 9 tables; `customer_analytical` view → RFM / tenure / category / state / seasonality; processed parquet | Analytical dataset | Schema tests pass; no dupes; RFM plausible | `Day 2: customer analytical dataset` | ✅ |
| 3 | EDA | Missingness, outliers, distributions, cohorts, retention, RFM segmentation; channel descriptive stats (sim preview) | `notebooks/01_eda` + figures | Distributions sane; ~96k customers / ~100k orders | `Day 3: EDA + cohorts` | ✅ |
| 4 | Confounders | Classify every variable: confounder / treatment / outcome / mediator / collider / irrelevant, with rationale | Confounder audit table | Each row causally justified | `Day 4: confounder audit` | ✅ |
| 5 | DAG | DoWhy `CausalModel`; backdoor paths; adjustment set; render (networkx + plotly) | `reports/dag` + graphic | Adjustment set matches audit | `Day 5: causal DAG` | ⬜ |
| 6 | Propensity | Logit PS per channel; overlap; PS distributions | `notebooks/02_propensity` | Overlap plot; no near-0/1 | `Day 6: propensity scores` | ⬜ |
| 7 | Matching | PSM nearest-neighbor; SMD before/after; love plot; assumptions checklist | Balance report | SMD < 0.1 | `Day 7: PSM + balance` | ⬜ |

**🏁 Gate 1 — STOP after Day 7 and get human validation before Week 2.**

## Week 2 — Treatment Effect Estimation (Days 8–14)

| Day | Focus | Tasks (Python / SQL) | Deliverable | Validation | Commit | Status |
|-----|-------|----------------------|-------------|------------|--------|:------:|
| 8 | Naive estimates | Diff-in-means per channel + "why not causal" write-up | Results: naive table | Direction documented | `Day 8: naive estimates` | ⬜ |
| 9 | Regression adjustment | OLS treatment coeff, CIs, spec, limitations | Results: OLS table | CIs sane vs naive | `Day 9: regression adjustment` | ⬜ |
| 10 | IPW | Stabilized weights, ESS, extreme-weight handling | Results: IPW table | ESS reported; weights bounded | `Day 10: inverse probability weighting` | ⬜ |
| 11 | Doubly robust | AIPW (causalml / manual); double-robustness explanation | Results: DR table | Consistent vs OLS/IPW | `Day 11: doubly robust` | ⬜ |
| 12 | ATE/ATT | Master estimate table (point/CI/SE/N/estimator/assumptions); DoWhy backdoor cross-check | `reports/treatment_effects` | Estimator convergence story | `Day 12: ATE/ATT synthesis` | ⬜ |
| 13 | CATE | T/S/X-learners (causalml); compare | `notebooks/03_cate` | Learner agreement map | `Day 13: heterogeneous effects` | ⬜ |
| 14 | Uplift | Persuadables / sure things / lost causes / sleeping dogs; Qini curves; uplift vs propensity | `results/uplift` | Qini above chance; segments interpretable | `Day 14: uplift modeling` | ⬜ |

**🏁 Gate 2 — STOP after Day 14 and get human validation before Week 3.**

## Week 3 — Business + Robustness + Product (Days 15–21)

| Day | Focus | Tasks (Python / SQL) | Deliverable | Validation | Commit | Status |
|-----|-------|----------------------|-------------|------------|--------|:------:|
| 15 | CATE segments | Segment deep-dive: high/zero/negative effects → targeting guidance | Target-segment table | Segments explain pattern | `Day 15: CATE segmentation` | ⬜ |
| 16 | ROI | Cost assumptions in config; observational vs causal ROI table | `reports/roi` | ROI complete per channel | `Day 16: incremental ROI` | ⬜ |
| 17 | Counterfactuals | Scenarios A–D simulator + bootstrap uncertainty + extrapolation limits | `results/counterfactuals` | Uncertainty reported; limits stated | `Day 17: counterfactual simulator` | ⬜ |
| 18 | Sensitivity | E-value, bias formula, placebo tests, alt adjustment sets/estimators; "how strong must U be?" | `reports/sensitivity` | Each claim stress-tested | `Day 18: sensitivity analysis` | ⬜ |
| 19 | Dashboard | 7-page Streamlit wired to `results/` | `dashboard/` app | All pages render | `Day 19: Streamlit dashboard` | ⬜ |
| 20 | Tests + polish | pytest suite (env gate, schema, ground-truth recovery, dashboard data); config; docs | Green test suite | `pytest` passes | `Day 20: tests + hardening` | ⬜ |
| 21 | Docs + portfolio | 25-section README, exec summary, 30s/2min/5min pitch, interview Q&A | `reports/` + README | Install→results reproducible | `Day 21: README + v1.0` | ⬜ |

**🏁 Gate 3 — final validation → tag `v1.0`.**

---

## Progress summary (updated after every day)

- **Completed:** Day 0, Day 1, Day 2, Day 3, Day 4
- **In progress:** —
- **Next up:** Days 5–7 (DAG → propensity → matching) → **Gate 1** at end of Day 7
- **Blockers:** none

> ✅ Day 2 validation hook green: 50/50 tests pass (25 env gate + 25 data schema/cohort/RFM), cohort = 94,983, no dupes, RFM plausible. See `docs/status.md`.

> ✅ Day 3 validation hook green: distributions sane — 94,983-cohort from 98,199 purchased orders (raw ~96k customers / ~100k orders); 18 new EDA tests; full suite 71/71. See `docs/status.md`.

> ✅ Day 4 validation hook green: 23 audit rows, 14 tests pass; per-channel identification strategy + adjustment sets locked; full suite 86/86. See `docs/status.md`.