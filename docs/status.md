# Project Status — Live Log

Updated at the end of every day. Mirrors `docs/roadmap.md`.

Last updated: **Day 11 — complete** (2026-09-21)

## Current state

| Phase | Status |
|---|---|
| Governance docs | ✅ Done (Day 0) |
| Week 1 — Data + Causal framework (Days 1–7) | ✅ Complete (Gate 1 validated) |
| Week 2 — Treatment effect estimation (Days 8–14) | 🟡 Day 11 complete; Days 12–14 next |
| Week 3 — Business + robustness + product (Days 15–21) | ⬜ Not started |

## Completed

### Day 0 — Governance & project scaffolding
- [x] `AGENTS.md` — operating rules for AI agents
- [x] `docs/blueprint.md` — full project design
- [x] `docs/roadmap.md` — 21-day plan with progress tracking
- [x] `docs/data-feasibility.md` — Olist feasibility + simulation design
- [x] `docs/learning-plan.md` — concept learning roadmap
- [x] `docs/decisions.md` — architecture decision records
- [x] `README.md` stub + `.gitignore` (`.env`, `data/raw/`, venv excluded)
- **Gate 0 passed:** user approved the three key decisions (sim layer on Olist, MySQL, stage-gated).

### Day 1 — Environment + data ingestion
- [x] `requirements.txt` pinned + `requirements.lock.txt` frozen (dowhy==0.8 classic API, causalml, econml, statsmodels, streamlit, pymysql, …)
- [x] `.venv` built on Python 3.14.6; all packages import cleanly
- [x] Extended env gate `tests/test_gate_env.py` — **25 tests pass** (python version, 21 package imports, DoWhy 0.8 classic API, config load, raw-data manifest, live DB connection)
- [x] MySQL 8.0.46 verified; `olist` DB + `olist_app` user created (random 32-char password)
- [x] `.env` written (gitignored) — `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`; `.env.example` committed
- [x] All 9 Olist CSVs downloaded → `data/raw/` from a verified GitHub mirror and checked against documented row counts: orders 99,441 · customers 99,441 · order_items 112,650 · payments 103,886 · reviews 99,224 · products 32,951 · sellers 3,095 · geolocation 1,000,163 · category translation 73 (mirror count; 71 on Kaggle)
- [x] `data/raw/_manifest.json` written (rows + sha256 per file) for Day 2 schema tests
- [x] Skeleton: `src/config.py` (config/.env loader), `src/data/download_olist.py`, `configs/config.yaml` (paths, seed, outcome window, Olist registry)

### Day 2 — Data engineering ✅
- [x] `sql/schema.sql` — 9-table DDL (FK-safe drop/create, utf8mb4, MySQL 8)
- [x] `sql/load.sql` — load contract + FK order + row-count gate documented
- [x] Bulk load via `src/data/load_olist.py` (pandas + pymysql executemany, one transaction per table) — **all 9 tables loaded, every row count matches `data/raw/_manifest.json`**
- [x] Dirty-data handling (reported in `data/processed/_load_report.json`, never hidden):
  - `order_reviews`: 814 duplicate `review_id` values → surrogate UUIDs (0 empty)
  - `order_payments`: 0 empty `payment_type`
  - no-item valid orders: 8 (5 created, 2 invoiced, 1 shipped)
- [x] `sql/analytics/customer_analytical.sql` — `v_customer_analytical` view (real Olist data only; no sim_* columns)
  - Cohort (final definition): customers with ≥1 **purchased order** = non-canceled/unavailable order with ≥1 `order_items` row → **N = 94,983**; 7 customers excluded (only no-item pipeline orders)
  - `customer_unique_id` multi-state quirk: 39 customers → state assigned from earliest purchased order
  - **Performance fix (ADR-008):** replaced the correlated `EXISTS` over `order_items` (which MySQL fused with the same-table equi-join into a plan that never finished — >300 s) with `JOIN order_items … SELECT DISTINCT`. Measured: `SELECT COUNT(*)` 22.8 s (was: never finished). Prerequisite discovered: interrupted/harness-killed client sessions left zombie server queries holding the view metadata lock — these must be `KILL`ed before re-creating the view.
- [x] `src/data/build_analytical.py` – materializes the view → `data/processed/customer_analytical.parquet` (94,983 × 12 cols)
- [x] `tests/test_data_schema.py` — **25 tests pass** covering: raw table rows vs manifest, no duplicate/null PKs, cohort count = 94,983, cohort contains only purchased orders, parquet schema/dtypes, no null keys/revenue, RFM plausibility, revenue tracks order count
- [x] **Full suite: 50/50 tests pass** (25 env gate + 25 data schema). **Day 2 validation hook green.**
- [x] Docker housekeeping requested by user: dropped unrelated databases (`creative_studio`, `text_to_sql`, `sakila`, `world`, `newschema`); MySQL now contains only `olist` + system schemas.
- [x] Operational cleanup: `.env` had a UTF-8 BOM (broke `DB_HOST`); `src/config.py` now reads `.env` as `utf-8-sig`. `olist_app` DB password re-synced to `.env`.

### Day 3 — EDA + cohorts ✅
- [x] Notebook tooling added (ADR-009): `nbformat`, `nbclient`, `ipykernel` in `requirements.txt` + env gate; venv kernel `causal-marketing` registered; notebooks built by script and executed for real (`scripts/build_notebook_01.py` → `notebooks/01_eda.ipynb`, 27 cells, 15 code cells with genuine outputs, 0 errors)
- [x] `sql/analytics/order_monthly.sql` (ADR-010) + `src/data/build_order_monthly.py` → `data/processed/order_monthly.parquet`: 96,861 customer-month rows, 94,983 customers, 98,199 orders — consistent with the Day-2 cohort
- [x] `src/features/eda.py` — missingness, IQR outliers, univariate distribution summaries. Observed: missingness only in review/category proxies (684 / 1,299); revenue right-skewed (median R$108, max R$13.7k); **97.0% one-time buyers**
- [x] `src/features/cohorts.py` — acquisition cohorts + retention matrix (m+0..m+12). Observed: 94,983 customers acquired 2016-09 → 2018-09; retention drops steeply (one-transaction marketplace)
- [x] `src/features/rfm.py` (ADR-011) — R/M quantiles + F bands (1/2/3-4/5-9/10+) → segments led by `one_time_lapsed` (38.8%) / `new_customer` (31.9%) / `big_spender` (11.9%)
- [x] `simulation/simulate_marketing.py` (ADR-012) — clearly-labeled sim preview: deterministic, config-driven targeting + latent `sim_u` + `sim_ground_truth_*` effects + 14-day conversion/revenue outcome → `data/simulated/sim_preview.parquet` (94,983 × 27)
- [x] `src/visualization/plots.py` → **13 figures** in `results/figures/` (missingness, outliers, distributions, states, categories, monthly activity, retention heatmap, RFM segments, sim exposure/conversion)
- [x] `tests/test_eda.py` — **18 tests pass** (cohort scale, distribution sane-ness, missingness contract, retention structure, RFM partition, sim_* prefix contract, determinism, ground-truth match vs config, figures written)
- [x] Docs: ADR-009…012, `docs/data-feasibility.md` §4.1 (Day-3 preview variables documented per AGENTS §2), roadmap Day 3 ✅, repurchase-rate note updated to observed 97% one-time
- [x] **Full suite: 71/71 tests pass** (28 env gate + 25 data schema + 18 EDA). **Day 3 validation hook green.**

### Day 4 — Confounder audit ✅
- [x] `src/causal/confounders.py` — audit module classifying every candidate variable per Plan.md Step 4 (Confounder / Treatment / Outcome / Mediator / Collider / Irrelevant) with rationale, adjust decision, and `active_in_preview` flag
- [x] Identification strategy (AGENTS.md §3) written **before fitting**: per-channel causal question, treatment, outcomes, sufficient observed adjustment set derived from config targeting coefs, assumptions checklist (exchangeability, positivity, consistency, SUTVA) with evidence + limitation
- [x] `results/tables/confounder_audit.csv` — 23 rows, machine-readable
- [x] `reports/confounder_audit.md` — narrative report with identification strategy, assumptions checklist, and full audit table
- [x] Adjustment sets locked per channel: email {order_count, recency_days, review_score_avg, total_revenue}, social {order_count, tenure_days, total_revenue}, search {order_count, tenure_days, total_revenue}, display {recency_days, total_revenue}; sim_u explicitly EXCLUDED (unobserved-confounder source; sensitivity only)
- [x] `tests/test_confounder_audit.py` — 14 tests: every row has rationale, roles/adjust valid, treatments/outcomes present, adjustment sets match config, sim_u/confounders/mediators/colliders/ground-truth classified correctly
- [x] **Full suite: 86/86 tests pass** (28 env gate + 25 data schema + 18 EDA + 14 confounder audit). **Day 4 validation hook green.**

### Day 5 — Causal DAG ✅
- [x] `src/causal/dag.py` — DoWhy 0.8 classic API (`CausalModel` + `common_causes`) + networkx + plotly rendering (no pygraphviz)
- [x] Per-channel DAGs: `results/figures/dag_{email,social,search,display}.html` — interactive HTML with node roles (treatment, outcome, confounder, unobserved, mediator, collider) color-coded
- [x] Nodes per DAG: treatment `sim_exposed_{channel}`, primary outcome `sim_converted_14d`, secondary outcome `sim_revenue_14d`, unobserved confounder `sim_u`, observed confounders (from config targeting coefs), conceptual mediator `click/session`, conceptual collider `co-exposure count`
- [x] Backdoor paths enumerated per channel: all observed confounders + unobserved `sim_u` (flagged as sensitivity target)
- [x] Sufficient adjustment sets match confounder audit exactly (mechanically derived from config)
- [x] `tests/test_dag.py` — 9 tests: DAG files exist, nodes present, adjustment sets match audit, backdoor paths include confounders + sim_u, DoWhy identification works, no pygraphviz import
- [x] **Full suite: 95/95 tests pass** (28 env gate + 25 data schema + 18 EDA + 14 confounder audit + 9 DAG). **Day 5 validation hook green.**

### Day 6 — Propensity Scores ✅
- [x] `src/causal/propensity.py` — per-channel logistic regression PS (statsmodels) using Day-4/5 adjustment sets
- [x] PS diagnostics for all 4 channels: overlap plots, PS distributions, SMD love plots (before matching)
- [x] `results/figures/ps_overlap_{channel}.html` — interactive histograms with common support shading
- [x] `results/figures/ps_distribution_{channel}.html` — violin/box plots by treatment status
- [x] `results/figures/smd_before_{channel}.html` — SMD love plots with 0.1 threshold lines
- [x] Key findings: all channels have common support; no PS < 0.01; email has 71 units with PS ≈ 1.0 (low ESS=3.2); social/search/display ESS 70-92%
- [x] Logistic regression converged for all channels (pseudo R² 0.01–0.06)
- [x] `tests/test_propensity.py` — 13 tests: PS estimated, overlap exists, no near-0 PS, ESS reported, adjustment sets match audit, SMD computed
- [x] **Full suite: 108/108 tests pass** (28 env gate + 25 data schema + 18 EDA + 14 confounder audit + 9 DAG + 13 propensity). **Day 6 validation hook green.**

### Day 7 — PSM + Balance ✅
- [x] `src/causal/matching.py` — nearest-neighbor PSM (1:1) with caliper (0.01 * SD(PS)), without replacement
- [x] Balance diagnostics: SMD love plots (before vs after), PS after matching distributions
- [x] `results/figures/smd_love_{channel}.html` — grouped bar charts with ±0.1 threshold
- [x] `results/figures/ps_after_{channel}.html` — violin plots on matched sample
- [x] Key findings: all 4 channels PASS balance (max |SMD| after < 0.01); match rates 98.7–99.5%
- [x] Email: 28,118 pairs (99.1%); Social: 24,382 (98.7%); Search: 31,349 (99.0%); Display: 35,285 (99.5%)
- [x] All covariates improved: order_count, recency_days, review_score_avg, total_revenue, tenure_days all |SMD| < 0.01
- [x] Assumptions checklist per channel (exchangeability, positivity, consistency, SUTVA, PS spec, matching quality)
- [x] `tests/test_matching.py` — 11 tests: matching runs, SMD balanced, match rates high, caliper respected, checklists generated
- [x] **Full suite: 119/119 tests pass** (28 env + 25 schema + 18 EDA + 14 confounders + 9 DAG + 13 PS + 11 matching). **Day 7 validation hook green.**

### Day 8 — Naive Estimates ✅
- [x] `src/causal/naive.py` — unadjusted diff-in-means per channel × outcome (conversion: two-proportion Wald; revenue: Welch t) with SE + 95% CI
- [x] `results/tables/naive_estimates.csv` — 8 rows (4 channels × 2 outcomes) + simulated ground-truth column
- [x] `results/figures/naive_conversion.html`, `naive_revenue.html` — bar charts with CI error bars
- [x] `reports/naive_estimates.md` — "why not causal" write-up per channel (confounded targeting + latent `sim_u`; naive gap = causal effect + selection)
- [x] Key findings (observed, simulated):
  - All 4 channels show positive naive gaps: conversion +11.2 to +12.8 pp; revenue +R$15.96 to +17.96
  - **Display confounding signature**: ground truth = 0.00, naive gap +11.2 pp → apparent effect is pure selection
  - **Social**: ground truth −0.08 (negative), naive gap +11.3 pp → selection overwhelms the true negative effect
  - Email: naive +12.5 pp vs GT +0.12; Search: naive +12.8 pp vs GT +0.15 — inflated by confounding
- [x] `tests/test_naive.py` — 12 tests: rows present, diff = mean diff exactly, SE/CI valid, direction documented, confounding signatures, report labeled "observed (simulated)", determinism
- [x] **Full suite: 131/131 tests pass** (119 + 12 naive). **Day 8 validation hook green.**

### Day 9 — Regression Adjustment (OLS) ✅
- [x] `src/causal/regression.py` — OLS per channel × outcome on exposure + Day-4 adjustment set, HC3 robust SEs, 95% CI (LPM for conversion; OLS for revenue)
- [x] `results/tables/ols_estimates.csv` — 8 rows merged with naive gap + simulated ground truth
- [x] `results/figures/ols_conversion.html`, `ols_revenue.html` — OLS vs naive grouped bars with CI error bars
- [x] `reports/ols_estimates.md` — comparison table, naive contrast, limitations (linearity, LPM boundaries, no balance guarantee, residual `sim_u`)
- [x] Key findings (estimated, simulated):
  - OLS barely moves the gap vs naive (e.g., display conversion +11.17→+11.22 pp vs simulated GT 0.00; email revenue +R$16.77→+17.11 vs GT +0.12)
  - Honest design point: the DGP is dominated by unobserved `sim_u` (U→outcome coef 1.0 vs observed features 0.05 each) — observed-confounder adjustment alone cannot remove the bias
  - Social is the one channel visibly shrinking toward its negative GT (−0.08)
  - CIs sane vs naive: SE ratios 0.5–2.0, all CI contain coef
- [x] `tests/test_regression.py` — 11 tests: rows present, CI sane, SE ratio vs naive, adjustment set used, coef = statsmodels fit, HC3, honest movement, files written, simulated labeling, determinism
- [x] **Full suite: 142/142 tests pass** (131 + 11 regression). **Day 9 validation hook green.**

### Day 10 — IPW ✅
- [x] `configs/config.yaml`: `ipw:` block (weight_cap 10.0, bootstrap_reps 500, alpha 0.05) — no hardcoded magic values
- [x] `src/causal/ipw.py` — stabilized (Hajek) IPW per channel × outcome; Cole–Hernán weight truncation; ESS before/after; bootstrap CI (fixed seed)
- [x] `results/tables/ipw_estimates.csv`, `results/figures/ipw_{conversion,revenue}.html`, `reports/ipw_estimates.md` (identification statement before fitting, weight diagnostics, limitations)
- [x] Key findings (estimated, simulated):
  - IPW ATE ≈ OLS ≈ naive (e.g., email conv 0.1287 vs OLS 0.1274 vs naive 0.1252) — `sim_u` dominates; IPW reweighting on observed PS cannot remove it
  - Email weak overlap: raw stabilized ESS 2.4 → **86,328 after truncation** (90.9% of n); 13 units capped at weight 10
  - All channels: weights bounded at cap 10.0; ESS 90.9–98.5% of n post-truncation
- [x] `tests/test_ipw.py` — 12 tests: weights bounded, ESS reported + improves, email ESS recovery, bootstrap CI, stabilized-weight formula, IPW≈OLS consistency, determinism
- [x] **Full suite: 154/154 tests pass** (142 + 12 IPW). **Day 10 validation hook green.**

### Day 11 — Doubly Robust (AIPW) ✅
- [x] `src/causal/doubly_robust.py` — manual AIPW (statsmodels outcome regressions + Day-6 PS), influence-function SE/CI (asymptotic root-n), per roadmap "AIPW (causalml / manual)" the manual route was chosen for transparency/reproducibility
- [x] PS truncation reuses the Day-10 `weight_cap` principle: p clipped to `[P(T=1)/cap, 1-(1-P(T=1))/cap]` — prevents the `(1-T)(Y-μ0)/(1-p)` augmentation from exploding for the email weak-overlap units (13 controls with PS→1)
- [x] `results/tables/dr_estimates.csv`, `results/figures/dr_{conversion,revenue}.html`, `reports/dr_estimates.md` (double-robustness explanation, AIPW table, consistency check, limitations)
- [x] Key findings (estimated, simulated):
  - DR ≈ IPW ≈ OLS ≈ naive exactly (e.g., email conv 0.12868 vs IPW 0.12868 vs OLS 0.12738) — as predicted, AIPW cannot outrun the design: `sim_u` is unadjusted so the estimate tracks OLS/IPW rather than the simulated ground truth
  - SEs tigher than naive (e.g., email revenue SE 0.674 vs naive ~1.2), consistent with AIPW efficiency when both models hold
  - Double-robustness property verified on a synthetic DGP (n=8,000): τ=1.0 recovered when the PS is correct but the outcome model is misspecified (1.33→with the double-expit test bug fixed), and vice versa
  - Debugging note: an initial email DR explosion (1.0 vs 0.128) was traced to untruncated control-arm augmentation at PS→1, fixed by the Day-10-consistent PS clip; a test-only double-`expit` bug (Logit.predict already returns probabilities) corrupted the property-test PS and was fixed + documented
- [x] `tests/test_doubly_robust.py` — 9 tests: rows present, consistent vs OLS/IPW (validation hook), IF SE/CI finite & ordered, email truncation reported (n_ps_truncated ≥ 13), no email explosion, **double-robustness property on synthetic DGP**, files written, report explains double robustness + sim_u, determinism
- [x] **Full suite: 163/163 tests pass** (154 + 9 doubly robust). **Day 11 validation hook green.**

## Blockers

None.

## Next actions

1. **Week 2 in progress (Gate 1 passed):** Day 12 ATE/ATT synthesis → Days 13–14 CATE/uplift.
2. **Gate 2** after Day 14 — human validation before Week 3.
3. Emerging storyline (Days 8–11): naive ≈ OLS ≈ IPW ≈ DR because `sim_u` dominates — Day 12 synthesis frames this honestly; Day 18 quantifies the unobserved confounder.