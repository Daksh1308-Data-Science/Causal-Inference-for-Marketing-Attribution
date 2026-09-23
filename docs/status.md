# Project Status — Live Log

Updated at the end of every day. Mirrors `docs/roadmap.md`.

Last updated: **Day 21 — complete · Gate 3 approved · `v1.0` tagged · post-release polish (`6898982`)** (2026-09-23)

## Current state

| Phase | Status |
|---|---|
| Governance docs | ✅ Done (Day 0) |
| Week 1 — Data + Causal framework (Days 1–7) | ✅ Complete (Gate 1 validated) |
| Week 2 — Treatment effect estimation (Days 8–14) | ✅ Complete (Gate 2 validated) |
| Week 3 — Business + robustness + product (Days 15–21) | ✅ Complete (**Gate 3 validated by human on 2026-09-23**) |
| Release | ✅ **`v1.0` tagged and pushed** (annotated tag on `43998e9`) |
| Post-release polish | ✅ `6898982` — README image gallery + `.gitattributes` language stats |

### Post-release polish (`6898982`) — README visuals + GitHub language stats
- [x] **README gallery (7 figures):** GitHub cannot render the plotly `.html` figures inline, so `scripts/export_readme_figures.py` (matplotlib-only, deterministic, reuses `src.causal.dag.build_dag_graph`) exports six `results/figures/readme_*.png` snapshots read from the committed result tables: DAG (email), six-estimator convergence vs oracle truth (R$), causal-vs-counterfactual ROI (symlog, CI whiskers), budget scenario nets, E-values, Qini. Plus the existing `13_sim_naive_conversion.png` in §6. Embedded in README §5/6/10/11/12/13/14 as Figures 1–7 with honest captions ("estimated (simulated)" vs "simulated ground truth").
- [x] **`src/causal/dag.py`:** node/edge construction extracted to `build_dag_graph` (single source of truth) — plotly DAG output byte-identical (verified; only the random plotly div UUID differs, reverted as churn), `test_dag.py` 9/9.
- [x] **Language stats:** `.gitattributes` marks plotly HTML, PNGs, result CSVs/parquet, and notebooks as `linguist-generated` (+ `*.md` documentation). GitHub's bar (previously ~94.5% HTML from 235 MB of committed plotly figures) now computes to ~**95% Python** + SQL/YAML — "mainly Python and other". Figures stay committed (report links + Install→results bundle intact).
- [x] **README §22 quickstart fix:** the invalid `python -X utf8 sql/load.sql` line replaced with the actual loader invocations (`-m src.data.download_olist/load_olist/build_analytical/build_order_monthly`); §18 documents the regeneration command + attribution change.
- [x] **Manifest + suite:** `readme_*.png` added to the deliverables manifest; full suite **374/374 green** (368 + 6 new manifest entries); figure churn reverted.

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

### Day 12 — ATE/ATT Synthesis ✅
- [x] `configs/config.yaml`: `synthesis:` block (dowhy_method `backdoor.linear_regression`, conversion abs tol 0.02 pp, revenue rel tol 0.10) — no hardcoded magic values
- [x] `src/causal/synthesis.py` — **master estimate table**: channel × outcome × estimator (naive, OLS, IPW, DR, ATT-matched, DoWhy backdoor) → point / SE / 95% CI / N / assumptions per row, all labeled `estimated (simulated)`
- [x] ATT from the Day-7 matched sample (1:1 NN, caliper): matched-pair diff-in-means with two-sample SE + normal CI (e.g., email conversion ATT 0.1291, N = 28,118 pairs)
- [x] **DoWhy backdoor cross-check** (Day 5 stack, classic API): `identify_effect` + `backdoor.linear_regression` with the real data — reproduces the Day-9 OLS ATE to ~1e-13 per cell (independent implementation of the same model, validating the full DoWhy pipeline)
- [x] **Compat shims (documented in module docstring):** DoWhy 0.8 calls `nx.algorithms.d_separated` (renamed `is_d_separator` in nx ≥ 2.6) and reads `model.params[0]` positionally (broken on pandas ≥ 2 string-indexed Series) — both fixed idempotently inside `synthesis.py`, no site-packages edits
- [x] `results/tables/master_estimates.csv` (48 rows), `results/figures/estimator_convergence_{conversion,revenue}.html` (all six estimators with 95% CI error bars), `reports/treatment_effects.md`
- [x] **Validation hook — estimator convergence story (green):** naive ≈ OLS ≈ IPW ≈ DR ≈ ATT across all 8 cells within tolerances (max conversion spread 0.0035 pp < 0.02; max revenue spread ~6% < 10%). **Convergence is not correctness:** display (simulated GT 0.00) converges to +0.112—+0.112 pp, so agreement here evidences a common UNOBSERVED bias (`sim_u`) shared by every estimator
- [x] `tests/test_synthesis.py` — 12 tests: master table shape/columns, rows complete (finite SE/CI, ci_lower < point < ci_upper, label, assumptions), estimator labels, DoWhy ≈ OLS (≤1e-6 rel), ATT sane vs OLS + Day-7 pair counts, convergence story all OK + explicit tolerances, DoWhy determinism, files written, plots render, report content
- [x] **Full suite: 175/175 tests pass** (163 + 12 synthesis). **Day 12 validation hook green.**

### Day 13 — CATE with Meta-Learners (T / S / X) ✅
- [x] `configs/config.yaml`: `cate:` block (base_max_depth 3, base_max_iter 100, bootstrap_reps 300, agreement tolerances) — no hardcoded magic values
- [x] `src/causal/cate.py` — **unit-level CATE** per channel × outcome × learner (T/S/X via causalml 0.17 `BaseTLearner`/`BaseSLearner`/`BaseXLearner`) on the Day-4 adjustment sets; `sim_u` never a feature; day-6 propensity p(X) feeds the X-learner; baseline E[Y|X] model provides the heterogeneity axis
- [x] **Day-13 finding — regressors on the binary outcome:** causalml's classifier path calls the base learner's hard `predict` (class labels), which collapses probability CATE to ~0 (verified: email conversion T ≈ 0.0006, S exactly 0). Fitting HistGradientBoosting **regressors** on the 0/1 outcome yields a valid probability-scale CATE (email conversion T 0.1269 / S 0.1241 / X 0.1278 vs Day-12 OLS 0.1274). `random_state` pinned from config seed (HistGB early-stopping split is otherwise random — mean CATEs moved between unseeded runs)
- [x] `results/tables/cate_estimates.parquet` (unit-level, 4×2×94,983 rows), `cate_summary.csv` (24 rows: mean + bootstrap 95% CI / SD / quantiles / assumptions / label), `cate_agreement.csv` (pairwise detail), `results/figures/learner_agreement_map.html` + `cate_by_channel.html`, `reports/cate_effects.md`
- [x] `notebooks/03_cate.ipynb` — built + executed via `scripts/build_notebook_03.py` (reads the committed artifacts, renders the map live; genuine outputs, not fabricated)
- [x] **Validation hook — learner agreement map (green):** two gates per cell, calibrated to what agreement means on this DGP: (1) every learner's mean CATE within the Day-12 OLS ATE tolerance (max observed Δ 0.0053 pp conversion / 5.4% revenue); (2) max pairwise decile-curve spread ≤ 25% of the effect size (observed max 0.092). All 8 cells **OK**
- [x] **Honest limitation surfaced by the map:** individual-level rank agreement (pairwise Spearman) is only 0.32–0.77 — the observed-X heterogeneity signal is tiny (`sim_u` dominates; effect constant in log-odds → near-flat CATE), so per-unit CATE ordering is NOT reliable. Reported in the map, deliberately not gated. Gate-2 calibration note: normalising the decile spread by SD(mean CATE) is unstable on near-flat signals (observed ratio 1.00 for social conversion) → normalise by the effect size instead (calc + rationale in `learner_agreement` docstring)
- [x] `tests/test_cate.py` — 11 tests: unit-level shape + no `sim_u`, summary shape/labels/CI, mean CATE ≈ Day-12 OLS ATE (both tolerances), **agreement hook all-OK + explicit tolerances**, individual agreement reported-not-gated, adjustment-set-only features, determinism (refit same channel identical; summary on loaded frame), artifacts written, report content, notebook deliverable
- [x] **Full suite: 186/186 tests pass** (175 + 11 cate — includes the notebook deliverable check against built `03_cate.ipynb`). **Day 13 validation hook green.**

### Day 14 — Uplift Modeling (Persuadables / Qini) ✅
- [x] `configs/config.yaml`: `uplift:` block — `qini_grid_points` 10, `qini_true_lift_min_gt_pct` 0.5, `qini_true_lift_display_max_pct` 0.5 (calibrated to this DGP's ~27% oracle ceiling — a modest, honest bar), `scatter_sample` 5000, `segment_min_share` 0.05 + `results.uplift` output path
- [x] `src/causal/uplift.py` — per channel × outcome × 4 strategies (**uplift** = Day-13 mean T/S/X CATE; **propensity** p(X) Day 6; **baseline** E[Y|X] Day 13; **oracle** = counterfactual true effect): manual **Radcliffe Qini** `qini_curve`/`qini_lift` (observed mode cross-checked against causalml `get_qini` — formula identical, max diff 0.0 on tie-free scores; mine breaks ties stably), median-quadrant **segments** (persuadable / sure thing / sleeping dog / lost cause), figures, report
- [x] **Two-metric evaluation, both reported:** (1) *observed* Qini — real-world computable, `sim_u`-confounded; (2) *true* Qini — **counterfactual cumulative |true effect| gain** (simulation-only; chance = diagonal, Lorenz-style concentration). The true metric deliberately drops causalml's `×cumsum_tr` treatment weighting (which re-imports `sim_u` assignment selection into the score — propensity true-lift inflated to ~21% vs uplift ~2%) and uses |effect| so the negative channel (social) is evaluated like the positive ones (ranking by response magnitude)
- [x] **Key finding — the observed Qini metric is `sim_u`-confounded:** email conversion observed lift: propensity 27.4% "wins", uplift 13.1%, and the **oracle sits below chance (−9.8%)** because it correctly demotes the high-`sim_u` conversion machines the assignment bias rewards. On the **true** metric the strategy order flips: oracle ≈ 26.7–27.9% (the achievable ceiling — the effect's intrinsic relative spread) while every observed-X model is ≈ 0–3% (uplift email 1.4 / social 0.3 / search 1.6, mean 1.1%). Real heterogeneity is essentially **unreachable on observed X**, and the plain baseline-response ranking (~3%) even beats the CATE ranking (~1%) — `sim_u` drives the effect. Display: 0.0 for every strategy (honest null; embedded effect 0.00)
- [x] `results/uplift/{qini_curves,qini_summary,segment_summary,gates}.csv`, `results/figures/qini_curves_{conversion,revenue}.html` + `uplift_segments_conversion.html`, `reports/uplift_modeling.md`
- [x] **Validation hooks — all 4 gates green:** `qini_above_chance_gt` (mean GT uplift true-lift 1.12% ≥ 0.5%), `qini_display_no_effect` (0.0 ≤ 0.5%), `oracle_is_upper_bound` (oracle true-lift is the max strategy per GT≠0 channel), `segments_interpretable` (every segment share ≥ 0.05, min 0.11; conv-rate/tau orderings structural)
- [x] `tests/test_uplift.py` — 14 tests: frame schema + 1:1 alignment with analysis data, **observed Qini == causalml `get_qini` (tie-free, exact)**, random score ⇒ chance, oracle upper-bound + ceiling sanity, display true-lift == 0, revenue true-lift == conversion for outcome-invariant scores (propensity/oracle), gate logic non-vacuous (zero mean ⇒ gate fails), segment interpretability + cohort sums, determinism, artifacts + report content
- [x] **Full suite: 200/200 tests pass** (186 + 14 uplift). **Day 14 validation hooks green — Week 2 complete → STOP for Gate 2.**

### Day 15 — CATE Segmentation & Targeting Guidance ✅
- [x] `configs/config.yaml`: `segments:` block — `n_bands` 5, gate thresholds calibrated to the measured DGP facts (`gt_positive_min_oracle` 0.005, `social_negative_max_oracle` −0.005, `display_oracle_zero_tol` 1e-6, `est_all_positive_min` 0.05, `rank_gap_min` 0.0001) + `results.target_segments` path
- [x] `src/causal/segments.py` — quintile **bands** of the Day-13 ensemble CATE per channel × outcome (bottom … top + `all` reference row), each with estimated CATE + analytic SE + 95% CI, **counterfactual oracle mean** + oracle negative share, observed conv/rev rate and baseline; **targeting guidance** per channel (Run / Skip / No budget) grounded in the counterfactual sign structure; 2 figures; report
- [x] **Key finding — the estimated sign structure cannot recover the true sign:** every channel's estimated CATE is positive in every band (email 0.126 / search 0.126 / social 0.107 / display 0.112 conversion mean; 0% negative units) — the shared `sim_u` bias. Only the **counterfactual** oracle explains the pattern: email/search positive for every unit, social negative for every unit (100% negative share), display exactly zero. A real analyst using only observed data would wrongly conclude *all* channels help
- [x] **Rank gradient (measured, not assumed):** ρ(ensemble CATE, true effect) ≈ +0.05/+0.06 conversion for email/search, ≈ 0 display, slightly negative social; top-band true effect beats the bottom's by only +0.13/+0.17 pp — real but tiny; guidance is per-*channel*, never per-customer
- [x] `results/target_segments/{target_segments,guidance,gates}.csv`, `results/figures/{target_bands_conversion,cate_distribution_conversion}.html`, `reports/cate_segmentation.md`
- [x] **Validation hooks — all 6 gates green:** gt_channels_positive_oracle, social_negative_oracle, display_zero_oracle, estimated_signal_all_positive (bias demonstration), rank_gradient_positive_gt, uncertainty_reported
- [x] `tests/test_cate_segments.py` — 13 tests: schema/coverage/canonical band order, uncertainty, bias-demo + oracle sign structure vs DGP, rank gradient, gates pass, **gate non-vacuity** (flipped social oracle ⇒ gate fails; negative estimated CATE ⇒ bias-demo gate fails), guidance recommendations/signs, determinism, artifacts + report content
- [x] **Full suite: 213/213 tests pass** (200 + 13 segments). **Day 15 validation hook green — Week 3 in progress.**

### Day 16 — Incremental ROI (Observational vs Causal) ✅
- [x] `configs/config.yaml`: `roi:` block — per-treated-customer **cost assumptions** in R$ over the 14-day window (`email 0.10 / search 1.50 / display 0.20 / social 0.80`; ADR-006: costs are config assumptions, Olist has no spend data) + gate thresholds + `results.roi` path
- [x] `src/causal/roi.py` — `ROI = (incremental revenue per treated − cost) / cost` (blueprint §9), three methods per channel: **observational** (Day-8 naive ATE → attribution-style ROI), **causal** (Day-12 DR ATE, CI propagated through the monotone transform), **counterfactual** (true per-treated effect from the DGP oracle, simulation-only); summary view (obs/causal+CI/ctf ROI, causal÷truth overstatement multiple, cohort net truth = n_treated × net); 1 figure; report
- [x] **Key finding — even the *causal* ROI overstates every channel here:** the Day-12 estimators converge to ≈ +16–18 R$/treated for **every** channel (display +16.2, social +16.1) — `sim_u` bias in money terms. Causal ROI is positive everywhere (email 17,265% / search 1,112% / display 7,983% / social 1,912%) and barely beats the naive attribution ROI. Only the **counterfactual** column reveals the truth: email 2,314% (excellent), search 101% (modest), **social −299% and display −100%** (value-destroying). `Causal ÷ truth`: **~7.5x email, ~11x search**, sign-flipped for social/display — no cost assumption can rescue them (breakeven reads in the report)
- [x] `results/roi/{roi_long,roi_summary,roi_gates}.csv`, `results/figures/roi_comparison.html` (faceted bars, CI error bars, breakeven line at ROI 1), `reports/roi.md`
- [x] **Validation hooks — all 6 gates green:** complete_rows (12 rows), causal_roi_positive (bias demo), ctf_email_search_positive, ctf_social_display_negative, overstatement_documented (7.5/11.0 > 1), uncertainty_reported (CI propagated; counterfactual CI collapses to the point)
- [x] `tests/test_roi.py` — 12 tests: schema/labels/n_treated from frame, cost-from-config, CI propagation + uncertainty, the honest causal-vs-counterfactual pattern, overstatement multiple, cohort net, gates pass, **gate non-vacuity** (display ctf flipped to positive ⇒ gate fails; search causal ROI flipped negative ⇒ gate fails), determinism, artifacts + report content, no literal escapes
- [x] **Full suite: 225/225 tests pass** (213 + 12 roi). **Day 16 validation hook green — Week 3 in progress.**

### Day 17 — Counterfactual budget scenarios ✅
- [x] `configs/config.yaml`: `counterfactuals:` block — scenario list `[as_run, naive, causal, ctf_guided]`, cohort cap (94,983), gate thresholds (`as_run_net_tol`, `realloc_beat_min_margin`, `optimum_min_margin`) + `results.counterfactuals` path
- [x] `src/causal/counterfactuals.py` — **model-based counterfactual estimates** (labeled `counterfactual (simulated ground truth), model-based` on every row): fixed budget = as-run spend (R$ 77,215, from Day-16 costs × treated); four allocations re-split it — as_run (as executed), naive (∝ last-touch revenue attribution), causal (∝ Day-12 DR causal ROI), ctf_guided (∝ counterfactual ROI, positive channels only). Mechanics: spend → implied treated → capped at cohort with ⚠ **extrapolation flag** → incremental revenue at DGP oracle per-treated effect → net. `budget_optimum()` = budget-constrained linear optimum (greedy email-then-search); 1 figure; report
- [x] **Honest finding (reported, not gated):** any reallocation beats the as-run scatter (worst reallocation R$ 147,922 vs R$ 48,084 — naive 163,983 > ctf_guided 158,605 > causal 147,922 > as_run 48,084). But the naive spread tops the ranking only via an **email-saturation artifact**: email saturates at R$ 9,498 spend (whole cohort treated), so wider spreads "win" by wasting less on the saturated channel — they still burn R$ 69,140 on social/display (true effects negative/zero). No rule-based scenario reaches the optimum (R$ 288,438, email→search only) — observed-data rules keep funding negative-counterfactual channels because every estimate is sim_u-inflated. Nothing about the ranking endorses a confounded rule
- [x] **Uncertainty reported (roadmap hook):** scenario totals carry an estimated-scale 95% CI propagated exactly through the linear transform from the Day-12 DR revenue ATE CIs (treated counts fixed per scenario ⇒ monotone linear combination). The CI brackets the sim_u-inflated estimates, NOT the counterfactual point — the gap is the bias at portfolio level: counterfactual net is 2.7–10.3% of the CI lower bound (**≈10–38× overstatement**)
- [x] `results/counterfactuals/{scenarios,scenario_summary,gates}.csv`, `results/figures/counterfactual_scenarios.html` (stacked net by channel per scenario, ⚠ markers), `reports/counterfactuals.md`
- [x] **Validation hooks — all 8 gates green:** scenarios_complete, as_run_reproduces_day16 (cross-day consistency with Day-16 cohort nets, max dev 0.00), reallocations_beat_as_run (+99,838), email_saturation_documented (3 email cells flagged), bounded_by_optimum (margin 124,455), extrapolation_flagged (no silent extrapolation), labels_correct, uncertainty_reported (finite ordered CI on every scenario total)
- [x] `tests/test_counterfactuals.py` — 15 tests: schema/labels, spends sum to budget, as_run↔Day-16 consistency, ranking/purity (as_run last, monotonic), email saturation + zero-spend ctf_guided cells, bounded-by-optimum, CI columns + bias-gap magnitude, gates pass, **gate non-vacuity** (naive inflated past optimum ⇒ bounded_by_optimum fails; email un-flagged ⇒ saturation gate fails; causal deflated below as_run ⇒ realloc gate fails; CI bounds inverted ⇒ uncertainty gate fails), determinism, artifacts + report content, no literal escapes
- [x] **Full suite: 240/240 tests pass** (225 + 15 counterfactuals). **Day 17 validation hook green — Week 3 in progress.**

### Day 18 — Sensitivity: how strong must U be? ✅
- [x] `configs/config.yaml`: `sensitivity:` block — `d_to_rr_coef` (0.91), gate thresholds (`share_explained_min`, `max_point_evalue`, `min_placebo_t`, `actual_u_min_delta`) + `results.sensitivity` path
- [x] `src/causal/sensitivity.py` — the roadmap "Each claim stress-tested" hook on the Day-12 DR revenue ATEs:
  - **E-value (VanderWeele & Ding 2017, continuous-outcome approx):** d = ATE/SD(rev); RR* = exp(0.91·d); E-value = RR* + √(RR*·(RR*−1)); reported for the point AND the CI-lower bound. Every row labeled (estimated / simulated ground truth / simulated measured / simulated placebo)
  - **Linear bias formula:** bias = δ_U·γ_U with δ_U = standardized treated/untreated difference in `sim_u`, γ_U = per-SD effect of `sim_u` on revenue (both measured directly from the DGP, simulation-only); required δ to zero the estimate and to reach the truth compared with the actual δ
  - **Falsification tests:** placebo outcome `sim_u` (treatment cannot affect it) — every channel shows ≈0.7-SD hugely significant "effects" (|t| ≈ 95–110); placebo channel display (true effect 0) shows R$ 16.17 with |t| = 27.5 — both placebos fail loudly, which IS the evidence
  - **Cross-estimator stress:** Days 9–12 convergence (naive≈OLS≈IPW≈DR≈ATT≈backdoor) shown tiny relative to the bias; bounds, not another estimator, are the stress test
- [x] **Results:** E-value 1.68–1.75 per channel (point) / 1.64–1.71 (CI-lower) — **fragile**: a moderate unmeasured confounder (RR ≈ 1.71 on BOTH axes) fully explains the estimates. Bias formula reproduces **82–97%** of every observed bias (email 95% / search 97% / display 94% / social 82% — residual = DGP nonlinearity); measured δ_U = 0.69–0.74 SD vs required-to-truth 0.73–0.86
- [x] `results/sensitivity/{evalue,bias_formula,falsification,gates}.csv`, `results/figures/{evalue,bias_decomposition}.html`, `reports/sensitivity.md`
- [x] **Validation hooks — all 7 gates green:** evalue_reported, evalue_fragility_documented (max 1.75 ≤ 3.0), bias_formula_explains_most (min 0.82 ≥ 0.70), actual_u_is_real_confounder (min δ 0.69 ≥ 0.50), placebo_tests_falsified (|t| min 27.5 ≥ 1.96), uncertainty_reported, labels_correct
- [x] `tests/test_sensitivity.py` — 14 tests: schema/labels, E-value ordering+fragility band+RR-approx identity, bias-formula consistency (share ≡ δ·γ/bias), confounder magnitude, placebo falsification, display-placebo |t| ≡ point/se, gates pass, **gate non-vacuity** (E-value inflated ⇒ fragility gate fails; δ weakened ⇒ actual-U gate fails; δ crushed ⇒ formula gate fails; placebo neutralised ⇒ placebo gate fails), determinism, artifacts + report content, no literal escapes
- [x] **Full suite: 254/254 tests pass** (240 + 14 sensitivity). **Day 18 validation hook green — Week 3 in progress.**

### Day 19 — Streamlit dashboard (honest framing inside the product) ✅
- [x] `configs/config.yaml`: `results.dashboard` path note (dashboard reads `results/` only — no new tunables; builders are wired to precomputed CSVs, never recompute in the app)
- [x] `src/dashboard/builders.py` — pure, headless-testable page builders (all logic; the Streamlit pages are thin glue):
  - **7 pages, one builder each** (`PAGE_BUILDERS`): exec, dag, attribution, uplift, simulator, sensitivity, diagnostics — every one returns `tokens` and renders through `load_config()` from `results/` only
  - **Honest vocabulary single-source:** `LABEL_ESTIMATED / LABEL_MEASURED / LABEL_PLACEBO / LABEL_TRUTH` identity-imported from `src/causal/sensitivity.py` (never re-declared); every page carries the shared `HONEST_TOKEN` framing — observed lift is confounder-compatible and **fragile** (E-values 1.68–1.75), **NOT established causal**; sim_/DGP-oracle markers everywhere
  - CI on every effect (attribution `inc_rev_ci_low/high`, diagnostics `ci_lower/ci_upper`); `render_gate()` checks non-vacuity per page (missing `results/` ⇒ raises)
- [x] `dashboard/app.py` + `dashboard/pages/2_DAG…7_Diagnostics.py` — thin Streamlit glue, each boots repo root into `sys.path` and calls the pure builders
- [x] `tests/test_dashboard.py` — 28 tests: per-page **headless AppTest** (no exception + `HONEST_TOKEN` verbatim on every page across all element types), builder contract keys + honest tokens, **label identity** (builders reuse sensitivity vocabulary, not re-declared), CI columns present and ordered, `render_gate` passes 7/7 + **non-vacuity** (missing results trips the gate), determinism (identical render twice), `run_all`
- [x] **Full suite: 282/282 tests pass** (254 + 28 dashboard). **Day 19 validation hook green — Week 3 in progress.**

### Day 20 — Tests + hardening: deliverables manifest wraps the whole build ✅
- [x] `tests/test_artifacts.py` — **86 tests**: the bundle-level acceptance gate ("Install→results reproducible", AGENTS.md §6 dashboard-data-presence at artifact scale):
  - **Manifest presence** — every roadmapped artifact (`results/tables, figures, roi, counterfactuals, sensitivity, uplift, target_segments` + all 12 `reports/*.md`) exists and is non-empty; section dirs resolve through `configs/config.yaml` `results:` block (no hardcoded paths)
  - **Schema contracts** — `master_estimates` (point/se/ci/n/label), `roi_summary` CI ordering (`causal_roi_ci_low ≤ causal_roi ≤ ci_high`), `evalue` CI columns; `scenario_summary` CIs are on the **estimated (Day-12 DR) scale and sit strictly above the truth-scale net** — the honest sim_u overstatement (10–38×, ADR-025) is visible in the artifact, not hidden
  - **Gate records green** — every artifact `gates.csv` (roi 6 / counterfactuals 8 / sensitivity 7 / uplift 4 / target_segments 6) reports `passed == True` with measured values (deterministic records, not just in-code asserts)
  - **Dashboard data contract** — static scan: every `_read`/`_maybe` CSV the Day-19 builders read exists on disk AND is in the manifest (9/9 pairs)
  - **Honest vocabulary at bundle level** — every `label` column across all result CSVs uses the honest roots (estimated/simulated/placebo/counterfactual/naive/observed/measured) and never "established causal/caused by/…causes"; no channel-`causes` claim in any report (AGENTS.md §8 survives into prose)
- [x] **Full suite: 367/367 tests pass** (282 + 85). **Day 20 validation hook green — Week 3 in progress.**

### Day 21 — Docs + portfolio: README + `v1.0` package ✅
- [x] **25-section `README.md`** — portfolio-grade: problem (attribution = correlation in disguise) → TL;DR (6 findings) → goals/scope → dataset & simulated layer → causal framework & assumptions → pipeline/layout → results chain (Days 3–20) → 4 findings (estimator convergence is a confounder; ROI money term; budget scenarios; E-value sensitivity) → heterogeneity → **honest framing (16: what this does NOT claim)** → dashboard → reproducibility → testing → stack → ADRs → quickstart → reports index → references → status/final word. Every number cross-checked against `results/*.csv` before writing (none fabricated).
- [x] **`reports/executive_summary.md`** — CMO-facing, 3–4 min read: the trap, five-estimator convergence, the sim_u confounder (82–97%), E-value fragility, ROI table (observed/causal/counterfactual), budget story, honest bottom line.
- [x] **`reports/pitches.md`** — 30s / 2min / 5min pitches, each with the non-negotiable honest-framing sentence.
- [x] **`reports/interview_qa.md`** — 10 Q&As (estimator convergence, randomization, unmeasured confounding, positivity, DoWhy, ROI contradiction, budget advice, reproducibility proof, limitations, hire-me) — every answer cites the backing artifact.
- [x] **Hardening:** portfolio docs added to the deliverables manifest; banned-claim regex now permits the honest "NOT established causal" negation (reports can say what the analysis does NOT claim); `reports/*.md` scanned for unnegated causal claims → green.
- [x] **Final reproducibility attestation:** full suite re-run green on the packaged state; figure churn reverted. **Day 21 validation hook green — awaiting Gate 3.**

## Blockers

None.

## Next actions

1. **Complete.** All 21 roadmap days done; **Gate 3 validated by the human on 2026-09-23; release tag `v1.0` created and pushed** (annotated, on commit `43998e9`). Post-release polish (`6898982`): README image gallery + `.gitattributes` language-stats fix — repository now reads as ~95% Python on GitHub. Repository: `https://github.com/Daksh1308-Data-Science/Causal-Inference-for-Marketing-Attribution`.
2. Emerging storyline (Days 8–18): naive ≈ OLS ≈ IPW ≈ DR ≈ ATT ≈ mean-CATE because `sim_u` dominates. Day 16 quantified the money consequence — even causal ROI is positive for every channel (≈1,100%–17,000%) vs the counterfactual truth (email/search profitable; social/display −299%/−100%). Day 17 turned it into budget what-ifs on a fixed R$ 77,215 budget: any reallocation beats the as-run scatter (48→≥148k), email saturates at R$ 9,498, and no observed-data rule reaches the R$ 288,438 budget-constrained optimum. Day 18 closed the loop: an unmeasured confounder with RR ≈ 1.71 on both axes explains the whole spurious effect (E-value), the actual `sim_u` (δ ≈ 0.69–0.74 SD, γ = R$ 20.5/SD) reproduces 82–97% of every observed bias, and both placebos fail loudly. Day 19 productized it: the 7-page dashboard carries the honest framing on every page (single-source `HONEST_TOKEN`), renders headless-clean. Day 20 wrapped the whole build in a deliverables-manifest suite (86 tests: every artifact present + schemas + gate records green + honest labels everywhere), full suite 367/367. Day 21 packaged it: 25-section README, executive summary, pitches, interview Q&A, manifest-verified, full suite re-run green — the build is complete and **stopped at Gate 3 for final human validation**.