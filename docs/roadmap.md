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
| 5 | DAG | DoWhy `CausalModel`; backdoor paths; adjustment set; render (networkx + plotly) | `reports/dag` + graphic | Adjustment set matches audit | `Day 5: causal DAG` | ✅ |
| 6 | Propensity | Logit PS per channel; overlap; PS distributions | `notebooks/02_propensity` | Overlap plot; no near-0/1 | `Day 6: propensity scores` | ✅ |
| 7 | Matching | PSM nearest-neighbor; SMD before/after; love plot; assumptions checklist | Balance report | SMD < 0.1 | `Day 7: PSM + balance` | ✅ |

**🏁 Gate 1 — STOP after Day 7 and get human validation before Week 2.**

## Week 2 — Treatment Effect Estimation (Days 8–14)

| Day | Focus | Tasks (Python / SQL) | Deliverable | Validation | Commit | Status |
|-----|-------|----------------------|-------------|------------|--------|:------:|
| 8 | Naive estimates | Diff-in-means per channel + "why not causal" write-up | Results: naive table | Direction documented | `Day 8: naive estimates` | ✅ |
| 9 | Regression adjustment | OLS treatment coeff, CIs, spec, limitations | Results: OLS table | CIs sane vs naive | `Day 9: regression adjustment` | ✅ |
| 10 | IPW | Stabilized weights, ESS, extreme-weight handling | Results: IPW table | ESS reported; weights bounded | `Day 10: inverse probability weighting` | ✅ |
| 11 | Doubly robust | AIPW (causalml / manual); double-robustness explanation | Results: DR table | Consistent vs OLS/IPW | `Day 11: doubly robust` | ✅ |
| 12 | ATE/ATT | Master estimate table (point/CI/SE/N/estimator/assumptions); DoWhy backdoor cross-check | `reports/treatment_effects` | Estimator convergence story | `Day 12: ATE/ATT synthesis` | ✅ |
| 13 | CATE | T/S/X-learners (causalml); compare | `notebooks/03_cate` | Learner agreement map | `Day 13: heterogeneous effects` | ✅ |
| 14 | Uplift | Persuadables / sure things / lost causes / sleeping dogs; Qini curves; uplift vs propensity | `results/uplift` | Qini above chance; segments interpretable | `Day 14: uplift modeling` | ✅ |

**🏁 Gate 2 — STOP after Day 14 and get human validation before Week 3.**

## Week 3 — Business + Robustness + Product (Days 15–21)

| Day | Focus | Tasks (Python / SQL) | Deliverable | Validation | Commit | Status |
|-----|-------|----------------------|-------------|------------|--------|:------:|
| 15 | CATE segments | Segment deep-dive: high/zero/negative effects → targeting guidance | Target-segment table | Segments explain pattern | `Day 15: CATE segmentation` | ✅ |
| 16 | ROI | Cost assumptions in config; observational vs causal ROI table | `reports/roi` | ROI complete per channel | `Day 16: incremental ROI` | ✅ |
| 17 | Counterfactuals | Scenarios A–D simulator + bootstrap uncertainty + extrapolation limits | `results/counterfactuals` | Uncertainty reported; limits stated | `Day 17: counterfactual simulator` | ⬜ |
| 18 | Sensitivity | E-value, bias formula, placebo tests, alt adjustment sets/estimators; "how strong must U be?" | `reports/sensitivity` | Each claim stress-tested | `Day 18: sensitivity analysis` | ⬜ |
| 19 | Dashboard | 7-page Streamlit wired to `results/` | `dashboard/` app | All pages render | `Day 19: Streamlit dashboard` | ⬜ |
| 20 | Tests + polish | pytest suite (env gate, schema, ground-truth recovery, dashboard data); config; docs | Green test suite | `pytest` passes | `Day 20: tests + hardening` | ⬜ |
| 21 | Docs + portfolio | 25-section README, exec summary, 30s/2min/5min pitch, interview Q&A | `reports/` + README | Install→results reproducible | `Day 21: README + v1.0` | ⬜ |

**🏁 Gate 3 — final validation → tag `v1.0`.**

---

## Progress summary (updated after every day)

- **Completed:** Day 0, Day 1, Day 2, Day 3, Day 4, Day 5, Day 6, Day 7, Day 8, Day 9, Day 10, Day 11, Day 12, Day 13, Day 14, Day 15, Day 16
- **In progress:** Day 17 (counterfactual simulator)
- **Next up:** Day 17 — counterfactual budget scenarios from the ROI story
- **Blockers:** none

> ✅ Day 2 validation hook green: 50/50 tests pass (25 env gate + 25 data schema/cohort/RFM), cohort = 94,983, no dupes, RFM plausible. See `docs/status.md`.

> ✅ Day 3 validation hook green: distributions sane — 94,983-cohort from 98,199 purchased orders (raw ~96k customers / ~100k orders); 18 new EDA tests; full suite 71/71. See `docs/status.md`.

> ✅ Day 4 validation hook green: 23 audit rows, 14 tests pass; per-channel identification strategy + adjustment sets locked; full suite 86/86. See `docs/status.md`.

> ✅ Day 5 validation hook green: 4 per-channel DAGs rendered (HTML), 9 tests pass; adjustment sets match audit; full suite 95/95. See `docs/status.md`.

> ✅ Day 6 validation hook green: 4 channels PS estimated, 13 tests pass; overlap plots + SMD before matching; ESS reported; full suite 108/108. See `docs/status.md`.

> ✅ Day 7 validation hook green: 4 channels matched, 11 tests pass; all covariates |SMD| < 0.1 after matching; match rates 98.7–99.5%; full suite 119/119. See `docs/status.md`.

> ✅ Day 8 validation hook green: naive diff-in-means for 4 channels × 2 outcomes, 12 tests pass; direction documented (all positive, selection-dominated); display/social show confounding signature (naive gap large while simulated ground truth 0/−0.08); full suite 131/131. See `docs/status.md`.

> ✅ Day 9 validation hook green: OLS per channel × outcome (HC3 robust SE, 95% CI), 11 tests pass; CIs sane vs naive (SE ratio 0.5–2.0); honest finding — observed-confounder adjustment barely moves the gap because latent `sim_u` dominates confounding (by design); full suite 142/142. See `docs/status.md`.

> ✅ Day 10 validation hook green: stabilized IPW per channel × outcome, 12 tests pass; ESS reported (raw + after Cole–Hernán truncation, weights bounded at cap 10); email ESS recovered 2.4 → 86,328; bootstrap CI; IPW ≈ OLS ≈ naive (sim_u dominates); full suite 154/154. See `docs/status.md`.

> ✅ Day 11 validation hook green: manual AIPW per channel × outcome, 9 tests pass; DR ≈ IPW ≈ OLS ≈ naive exactly (sim_u unadjusted); double-robustness property verified on synthetic DGP (τ=1.0 recovered under outcome-model misspecification); SEs tighter than naive; email weak-overlap explosion fixed via Day-10-consistent PS clip; full suite 163/163. See `docs/status.md`.

> ✅ Day 12 validation hook green: master ATE/ATT table (48 rows: point/SE/95% CI/N/estimator/assumptions), 12 tests pass; DoWhy backdoor cross-check reproduces OLS to ~1e-13; estimator convergence story verified (all 8 cells within tolerances; convergence = shared unobserved `sim_u` bias, evidenced by display +0.112 pp vs simulated GT 0.00); full suite 175/175. See `docs/status.md`.

> ✅ Day 13 validation hook green: T/S/X meta-learners per channel × outcome, 11 tests pass; learner agreement map — all 8 cells OK (mean CATE within Day-12 OLS ATE tolerance; max pairwise decile spread ≤ 25% of effect size); honest limitation surfaced: individual-level rank agreement only 0.32–0.77 Spearman (observed-X heterogeneity signal is tiny — `sim_u` dominates); full suite 186/186. See `docs/status.md`.

> ✅ Day 14 validation hook green: uplift modeling — 14 tests pass; Qini curves + 4 interpretable segments per channel; all 4 gates green (true-lift above chance: mean 1.12% ≥ 0.5%; display true-lift 0.0 ≤ 0.5%; oracle = max-strategy upper bound 26.7–27.9% vs ~0–3% for every observed-X model — the observed Qini metric is `sim_u`-confounded, propensity 27.4% "wins" and the oracle sits below chance); full suite 200/200. See `docs/status.md`.

> ✅ Day 15 validation hook green: CATE segmentation — 13 tests pass; target-segment table (5 bands + `all` per channel × outcome) + per-channel Run/Skip/No-budget guidance; all 6 gates green, incl. the honest pattern: every estimated CATE is positive in every band (shared `sim_u` bias — observed data cannot recover even the sign), while the counterfactual oracle shows email/search +, social −, display 0; rank gradient real but tiny (top−bottom oracle +0.13/+0.17 pp, ρ 0.05–0.06); full suite 213/213. Gate 2 approved by the human. See `docs/status.md`.

> ✅ Day 16 validation hook green: incremental ROI — 12 tests pass; ROI per channel from cost assumptions (ADR-006 config), three methods (observational / causal DR / counterfactual oracle) + cohort net values; all 6 gates green, incl. the money terms of the sim_u story: even causal ROI is positive for every channel (1,112%–17,265%) while the counterfactual truth is social −299% and display −100%, with causal÷truth overstatement ~7.5x email / ~11x search; full suite 225/225. See `docs/status.md`.