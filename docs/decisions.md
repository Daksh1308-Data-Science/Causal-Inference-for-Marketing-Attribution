# Architecture Decision Records (ADRs)

Status: **Accepted** unless noted. When a decision changes, add a new ADR overriding the old one — never rewrite history silently.

---

## ADR-001 — MySQL 8.0 + MySQL Workbench for the SQL layer

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Master prompt specifies PostgreSQL; no local PostgreSQL exists, and Docker Desktop's daemon is not running. MySQL 8.0 is installed and running as service `MySQL80`, with Workbench available.
- **Decision:** Use MySQL 8.0 + MySQL Workbench. Drivers: `pymysql` + `SQLAlchemy`.
- **Consequences:** MySQL 8 supports window functions/CTEs — all analytics (RFM, cohorts, retention, conversion windows) implemented in SQL. Dialect notes: `AUTO_INCREMENT`, backticks. README will document MySQL as the SQL engine.

## ADR-002 — Simulated marketing layer on real Olist data (never fabricate real treatments)

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Olist has no marketing treatment data. The prompt forbids fabricating treatments as real.
- **Decision:** Build the customer backbone from real Olist data; overlay a clearly-labeled simulated marketing layer (`sim_*` variables) with known ground-truth effects, confounding by design, and an unobserved-confounding variable. Pipeline validated by ground-truth recovery.
- **Consequences:** Absolute rule — no simulated variable is ever presented as observed. Feasibility doc (`docs/data-feasibility.md`) explains the real-data mapping.

## ADR-003 — Stage-gated 21-day execution

- **Date:** 2026-09-19 · **Status:** Accepted
- **Decision:** Build Week 1 (Days 1–7) → human validation → Week 2 → validation → Week 3 → validation → `v1.0`. No jumping ahead (prompt §27).

## ADR-004 — Python 3.14 + pinned causal stack: `dowhy==0.8`, causalml, econml, statsmodels

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Python 3.14.6 in use; a prior env gate passed this stack. DoWhy 0.8 uses the classic API.
- **Decision:** Use classic DoWhy 0.8 API (`CausalModel` + `identify_effect` + `estimate_effect`). Do not upgrade DoWhy mid-project without a new env gate.
- **Consequences:** All DoWhy code targets the 0.8 API.

## ADR-005 — DAG rendering without pygraphviz

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** `pygraphviz` has native-build risk on Windows.
- **Decision:** Use `networkx` (layout) + `plotly` (interactive render) for DAGs. DAG construction still via DoWhy's `CausalModel`.

## ADR-006 — Channel costs are config assumptions, not observed data

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Olist has no spend data; ROI needs a cost basis.
- **Decision:** Per-channel costs (CPM/CPC/contact) live in `configs/config.yaml`, explicitly labeled assumptions, documented in ROI reports.

## ADR-007 — Streamlit reads precomputed results

- **Date:** 2026-09-19 · **Status:** Accepted
- **Decision:** The 7-page dashboard loads `results/*.json` + artifacts; only the counterfactual simulator recomputes in memory. Fast, deterministic, reproducible.

## ADR-008 — `v_customer_analytical`: JOIN+DISTINCT instead of correlated EXISTS

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** The first version of `v_customer_analytical` filtered purchased orders with a correlated `EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)`. MySQL 8.0.46 fused that semi-join with the outer equi-joins on the *same* `order_items` table and produced a catastrophic plan (full order_items scan × full customers hash join). `SELECT COUNT(*)` never finished (>300 s timeout; 60 s+ on retest).
- **Decision:** Replace the `EXISTS` filter with `JOIN order_items … SELECT DISTINCT` in the `purchased_orders` CTE. MySQL materializes the purchased-order set once and reuses it across all consumer CTEs (verified via `EXPLAIN ANALYZE`). Folded the customer geography join into the same CTE so consumers stop re-joining `customers`.
- **Measured impact:** `SELECT COUNT(*)` = 22.8 s (was: never finished). Full `SELECT *` ≈ 35–40 s. The remaining cost is the five per-customer aggregation/window passes, which is inherent to a view on this machine.
- **Consequences:** Cohort semantics unchanged (98,199 purchased orders, 94,983 customers). Scalar subqueries for tenure/recency are re-evaluated per output row by MySQL but each costs <50 ms against the materialized CTE. Documented in `sql/analytics/customer_analytical.sql`.

## ADR-009 — Notebooks are built + executed by script, not hand-typed

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** The Day-2 artifacts were plain Python; Days 3+ deliver narrated notebooks (`notebooks/01_eda → 07_sensitivity`). Hand-written notebooks risk stale/invented outputs.
- **Decision:** Every notebook is *constructed* from narrative markdown + code cells in `scripts/build_notebook_01.py` (code cells only call `src/` modules) and *executed* for real with `nbclient` against a registered venv kernel (`causal-marketing`). Committed notebooks therefore contain genuine outputs and are reproducible by re-running the builder. `nbformat`, `nbclient`, `ipykernel` added to `requirements.txt`; env gate extended.
- **Consequences:** Reviewers can trust every number in the committed notebook. `src/visualization/plots.py` forces the Agg backend only *outside* ipykernel so inline figures still render.

## ADR-010 — `v_order_monthly` order-level table for cohorts/retention

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** Day-3 retention/cohort analysis needs order-level monthly activity, but the Day-2 deliverable is a customer-level table.
- **Decision:** New view `sql/analytics/order_monthly.sql` (per customer × purchase-month: order_count, revenue; purchased-order semantics as in ADR-008) materialized by `src/data/build_order_monthly.py` → `data/processed/order_monthly.parquet`. Cohorts/retention computed from it in `src/features/cohorts.py`.
- **Verification:** 96,861 customer-month rows; 94,983 distinct customers; 98,199 orders — consistent with the Day-2 cohort.

## ADR-011 — RFM uses frequency bands, not quantiles

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** Olist is ~97% one-time buyers, so a quantile-binned frequency score collapses (P(F=1)≈0.97).
- **Decision:** `src/features/rfm.py` scores R/M by quantiles but F by explicit bands (1 / 2 / 3-4 / 5-9 / 10+). Composite `rfm_score = 100R + 10F + M`; documented segment mapping. Descriptive only — segmentation feeds the Day-4 confounder audit and Day-5 DAG.

## ADR-012 — Simulation preview ships on Day 3 (single snapshot)

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** The roadmap's Day-3 EDA includes "channel descriptive stats (sim preview)", and Days 6-7 (propensity, matching) already need `sim_*` exposure inputs.
- **Decision:** `simulation/simulate_marketing.py` implements the Day-3 *preview*: a single campaign snapshot (no per-campaign date grid yet) with logistic targeting per channel, latent `sim_u` confounding by design, embedded `sim_ground_truth_*` effects from config, and a 14-day conversion + lognormal revenue outcome. All columns `sim_*`-prefixed; naive conversions reported as *descriptive, not causal*. The full campaign-date grid lands in Week 2 when the analysis dataset is finalized.
- **Consequences:** Day-6/7 estimators can already run against `data/simulated/sim_preview.parquet`; results are clearly labeled as simulation-preview outputs in `notebooks/01_eda` §8.

## ADR-013 — Confounder audit scope: active-in-preview vs intended-full-sim

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** Day-4 requires classifying every variable (confounder/treatment/outcome/mediator/collider/irrelevant) with rationale. The Day-3 preview DGP only activates a subset of the intended confounders (recency_days, order_count, total_revenue, tenure_days, review_score_avg + sim_u). The full Week-2 simulation will add category_affinity_top, state, seasonality, and click/session mediators.
- **Decision:** The audit table classifies variables by their *intended causal role per the simulation design*, with an `active_in_preview` boolean flag. Variables not yet wired in the preview DGP (category, state, seasonality, click/session, co-exposure collider) are marked `active_in_preview=False` and their balance checks serve as placebos until Week 2. The `adjustment_sets()` function derives the *active* observed confounders mechanically from `config.yaml` targeting coefs so Days 5-7 estimators use the exact adjustment set that matches the preview DGP, not the intended one.
- **Consequences:**
  - Honest classification: no variable is claimed to confound the preview when it doesn't.
  - `reports/confounder_audit.md` includes the full identification strategy (AGENTS.md §3) written before fitting, per channel.
  - `adjustment_sets()` is the single source of truth for Day-5 DAG and Day-6/7 estimators.
  - Category/state/seasonality are confounders by design — estimators must include them once the full sim activates them.

## ADR-014 — DAG construction with DoWhy 0.8 + networkx/plotly (no pygraphviz)

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** Day-5 requires per-channel causal DAGs showing nodes, edges, backdoor paths, and adjustment sets. DoWhy 0.8 classic API (`CausalModel` + `identify_effect`) is the mandated causal engine. DAG rendering must avoid `pygraphviz` (native-build risk on Windows per ADR-005).
- **Decision:**
  - `src/causal/dag.py` uses DoWhy's `common_causes` parameter (cleaner than graph string parsing) for identification.
  - Interactive DAGs rendered via `networkx` (spring layout with manual positioning) + `plotly` → `results/figures/dag_{channel}.html`.
  - Nodes: treatment, primary/secondary outcomes, observed confounders (from `adjustment_sets()`), unobserved confounder `sim_u`, conceptual mediator `click/session`, conceptual collider `co-exposure count`.
  - Edges reflect the preview DGP: confounders → treatment + outcome; `sim_u` → treatment + outcome; treatment → outcome → revenue; treatment → mediator → outcome; treatment → collider ← other treatments.
  - Backdoor paths enumerated explicitly; adjustment set = observed confounders per channel; `sim_u` path remains open (by design, sensitivity analysis Day 18).
  - `dag_summary()` generates text report for `reports/` integration.
- **Consequences:**
  - Adjustment sets mechanically match Day-4 audit (`adjustment_sets()` single source of truth).
  - DoWhy identification validates the backdoor criterion; fallback estimand object if graph parsing fails.
  - No pygraphviz dependency — pure Python stack (networkx + pydot for DoWhy, plotly for viz).
  - DAGs are interactive HTML — reviewers can hover for node roles, zoom, pan.
  - Per-channel DAGs align with per-channel identification strategy (AGENTS.md §3).

## ADR-015 — Propensity score estimation with statsmodels + overlap diagnostics

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** Day-6 requires per-channel propensity scores with overlap diagnostics (PS distributions, common support, SMD before matching). The adjustment sets are fixed from Day-4 audit / Day-5 DAG. Must avoid near-0/1 PS for positivity.
- **Decision:**
  - `src/causal/propensity.py` uses `statsmodels.Logit` for interpretable coefficients + convergence reporting.
  - Features standardized via `StandardScaler`; missing `review_score_avg` imputed with median (only 684/94983 missing, email channel only).
  - Diagnostics per channel: PS overlap histogram (common support shaded), PS distribution violin plot, SMD love plot (before matching).
  - ESS computed for IPW weights: `ESS = (sum(w))² / sum(w²)`.
  - Extreme PS flagged (< 0.01 or > 0.99).
  - Outputs: 12 interactive HTML figures (3 per channel) in `results/figures/`.
- **Consequences:**
  - All 4 channels have common support (overlap region non-empty).
  - No PS < 0.01 (positivity satisfied at lower bound).
  - Email channel has 71 units with PS = 1.0 (perfect prediction) → ESS = 3.2 (0.003%) — will need trimming/clipping for IPW (Day 10).
  - Social/search/display ESS 70-92% — acceptable for IPW.
  - SMD before matching shows meaningful imbalance (|SMD| > 0.1 for several confounders), justifying matching (Day 7).
  - Adjustment sets mechanically match Day-4/5 audit.

## ADR-016 — Nearest-neighbor PSM with caliper + balance diagnostics

- **Date:** 2026-09-20 · **Status:** Accepted
- **Context:** Day-7 requires propensity score matching with covariate balance (SMD < 0.1). Must use Day-4/5 adjustment sets and Day-6 PS estimates.
- **Decision:**
  - `src/causal/matching.py` implements 1:1 nearest-neighbor matching on PS with caliper = 0.01 × SD(PS), without replacement.
  - SMD computed before and after matching for all confounders in the adjustment set.
  - Love plots (`smd_love_{channel}.html`) show grouped before/after bars with ±0.1 threshold.
  - PS after matching distributions (`ps_after_{channel}.html`) confirm overlap on matched sample.
  - Assumptions checklist per channel (6 rows: exchangeability, positivity, consistency, SUTVA, PS spec, matching quality).
- **Consequences:**
  - All 4 channels achieve balance: max |SMD| after matching < 0.01 (well below 0.1 threshold).
  - Match rates 98.7–99.5% — minimal treated units lost.
  - Email channel's PS=1.0 clumping (71 units) did not prevent matching; caliper handled it.
  - All covariates improved: order_count, recency_days, tenure_days, total_revenue, review_score_avg.
  - Matching quality "Met" for social/search/display; "Marginal" for email due to PS clumping.
  - Positivity assumption: Met for 3 channels; Marginal for email (perfect prediction subgroup).
  - Exchangeability: Partially met (observed confounders balanced; residual `sim_u` confounding by design).
  - Ready for treatment effect estimation on matched samples (Week 2).

## ADR-017 — Naive diff-in-means baseline (Day 8, Week 2 kickoff)

- **Date:** 2026-09-21 · **Status:** Accepted
- **Context:** Week 2 starts with a naive, unadjusted comparison per channel so the causal estimators (Days 9–12) can be benchmarked against it. The naive gap is expected to be selection-dominated because assignment is confounded by design.
- **Decision:**
  - `src/causal/naive.py` computes diff-in-means (exposed − unexposed) for both simulated outcomes: 14-day conversion (risk difference, two-proportion Wald CI) and 14-day revenue (Welch t CI).
  - Each row carries the SIMULATED ground-truth log-odds from config for the narrative — never presented as observed fact (AGENTS.md §2).
  - Report `reports/naive_estimates.md` includes a per-channel "why not causal" section naming the confounders and `sim_u`.
  - Outputs: `results/tables/naive_estimates.csv`, `results/figures/naive_{conversion,revenue}.html`.
- **Consequences:**
  - All channels show a large positive naive gap (conversion +11.2 to +12.8 pp; revenue +R$15.96–17.96).
  - Display: ground truth 0.00 but naive +11.2 pp → textbook confounding signature, used as the validation story.
  - Social: ground truth −0.08 but naive +11.3 pp → selection bias outweighs a genuinely negative effect ("sleeping dogs" narrative).
  - Establishes the benchmark that adjustment (Days 9–12) must shrink toward the simulated ground truths.
  - Full suite 131/131; Day 8 validation hook ("direction documented") green.

## ADR-018 — OLS regression adjustment with HC3 robust SEs (Day 9)

- **Date:** 2026-09-21 · **Status:** Accepted
- **Context:** Day-9 requires a regression-adjusted treatment coefficient per channel with CIs and explicit limitations. Adjustment set is fixed from Day-4/5. The DGP is dominated by unobserved `sim_u`, so OLS is expected to move little vs the Day-8 naive gap.
- **Decision:**
  - `src/causal/regression.py` fits OLS of outcome on exposure + adjustment set per channel × outcome. Conversion = linear probability model (risk difference); revenue = OLS (R$). Inference with HC3 heteroskedasticity-robust SEs.
  - Outputs: `results/tables/ols_estimates.csv`, `results/figures/ols_{conversion,revenue}.html`, `reports/ols_estimates.md` (limitations section: linearity, LPM boundaries, no balance guarantee, residual `sim_u`).
- **Consequences:**
  - OLS barely moves vs naive (display conversion +11.17→+11.22 pp vs GT 0.00; email revenue +R$16.77→+17.11 vs GT +0.12) — consistent with sim_u dominating (U→outcome coef 1.0 vs observed features 0.05 each in the DGP).
  - Social shrinks most toward its negative GT (conversion 0.1127→0.1061); directionally honest.
  - CI sanity vs naive validated at SE ratio 0.5–2.0; R² low (0.009–0.024), as expected for a noisy binary/lognormal outcome.
  - Confirms the Day-18 sensitivity need: quantify how strong unobserved U must be to explain the remaining gap.
  - Full suite 142/142; Day 9 validation hook ("CIs sane vs naive") green.

## ADR-019 — Stabilized IPW with Cole–Hernán truncation (Day 10)

- **Date:** 2026-09-21 · **Status:** Accepted
- **Context:** Day-10 requires a propensity-weighted ATE with ESS reporting and extreme-weight handling. Day-6 flagged email's weak overlap (71 units PS ≈ 1.0) which renders naive unstabilized IPW near-useless (ESS ≈ 3).
- **Decision:**
  - `src/causal/ipw.py` uses Hajek-normalized STABILIZED weights `w = T·P(T=1)/p + (1−T)·P(T=0)/(1−p)`; truncation at `ipw.weight_cap = 10` (Cole & Hernán) with truncation count reported; ESS = (Σw)²/Σw² computed before and after truncation.
  - CIs from bootstrap (fix `ipw.bootstrap_reps = 500`, seed = config seed + channel index).
  - Tunables in `configs/config.yaml` under `ipw:` (no magic values).
- **Consequences:**
  - Email raw stabilized ESS = 2.4 (worse than unstabilized 3.2, as stabilized weights concentrate) → post-truncation ESS **86,328 (90.9% of n)**; only 13 units capped at 10.
  - All channels: weights bounded at cap; ESS 90.9–98.5% of n after truncation.
  - IPW ATE ≈ OLS ≈ naive (email conv 0.1287 vs 0.1274 vs 0.1252) — reweighting on observed confounders cannot remove `sim_u` selection; consistent with Day-9 finding.
  - Bootstrap CI captures design variability, not PS/model misspecification — stated as a limitation.
  - Full suite 154/154; Day 10 validation hook ("ESS reported; weights bounded") green.

## ADR-020 — Master ATE/ATT table + DoWhy backdoor cross-check (Day 12)

- **Date:** 2026-09-22 · **Status:** Accepted
- **Context:** Days 8-11 produced four ATE families (naive, OLS, IPW, DR) plus a Day-7 matched sample (ATT), each in its own report. Day 12 must present one comparable master table and independently validate the pipeline with the DoWhy machinery introduced on Day 5.
- **Decision:**
  - `src/causal/synthesis.py` builds a single long table: channel × outcome × {naive, OLS, IPW, DR, ATT-matched, DoWhy-backdoor} → point / SE / 95% CI / N / assumptions, every row labeled `estimated (simulated)`.
  - ATT read from Day-7 1:1 NN matched pairs (two-sample SE + normal CI), no re-fit.
  - DoWhy cross-check = `backdoor.linear_regression` on the real data through the classic API (`identify_effect` + `estimate_effect`); SE/CI reused from the Day-9 OLS table because DoWhy's linear-regression estimate is the same OLS by construction (flagged in `assumptions`).
  - Compat shims (idempotent, in-module, no site-packages edits): `nx.algorithms.d_separated` → `is_d_separator` (nx ≥ 2.6 rename) and a pandas-2-safe replacement of dowhy 0.8's `RegressionEstimator._estimate_effect` (`params[0]` → `params.iloc[0]`).
  - Convergence tolerances config-driven: `synthesis.convergence_tol_conversion_abs` (0.02 pp, absolute), `synthesis.convergence_tol_revenue_rel` (0.10, relative) — match the test contract.
- **Consequences:**
  - DoWhy reproduces OLS to ~1e-13 on all 8 cells → pipeline validated end-to-end (identification + estimation) on real data.
  - Convergence story verified: all 8 cells within tolerance; convergence evidences a shared unobserved `sim_u` bias rather than agreement on truth (display converges to +0.112 pp vs simulated GT 0.00).
  - Master table = the single source table downstream (ROI, counterfactuals, dashboard) reads from.
  - Full suite 175/175; Day 12 validation hook ("estimator convergence story") green.

## ADR-021 — CATE meta-learners: regressors on the binary outcome + agreement gate calibration (Day 13)

- **Date:** 2026-09-22 · **Status:** Accepted
- **Context:** Day 13 must estimate heterogeneous effects with T/S/X-learners (causalml) and deliver a "learner agreement map" as its validation hook. Two issues surfaced during implementation.
- **Decision:**
  1. **Regressors on the 0/1 conversion outcome** — causalml 0.17's classifier path calls the base learner's hard `predict` (class labels), collapsing a valid probability-scale CATE to ~0 (verified: email conversion T-learner mean ≈ 0.0006, S-learner exactly 0). All meta-learners therefore fit HistGradientBoosting **regressors** on the binary outcome; for a binary outcome the resulting CATE is a probability difference. `random_state` pinned from config `seed` because HistGB's `early_stopping='auto'` otherwise makes a *random* validation split (email conversion mean CATE moved 0.1269 → 0.1290 between unseeded runs).
  2. **Agreement gate calibrated to the DGP** — the naive idea (gate on pairwise *individual*-level Spearman ≥ 0.7) is wrong here: the observed-X heterogeneity signal is tiny (effect constant in log-odds → near-flat CATE; `sim_u` dominates), so per-unit rank agreement is inherently weak (observed 0.32–0.77). Gating on it would mask an honest limitation. Gate instead on two stable quantities: (a) **mean alignment** — every learner's mean CATE within the Day-12 OLS ATE tolerance (conversion abs 0.01 pp / revenue rel 0.10); (b) **decile-magnitude** — max pairwise decile-curve |Δ| ≤ 25% of the effect size |mean CATE| (observed max 0.092). Normalising the decile spread by SD(mean CATE) was rejected: SD explodes on near-flat signals (observed ratio 1.00 for social conversion → spurious CHECK); the effect size is scale-robust. Individual-level Spearman is reported in the map and the report but is not a gate.
- **Consequences:**
  - All 8 channel × outcome cells pass both gates; mean CATEs agree with the Day-12 ATE (max Δ 0.0053 pp conversion / 5.4% revenue).
  - Determinism: refitting a channel with the pinned seed reproduces the CATE vectors exactly (tested).
  - The map's central honest finding: learners agree at the aggregate level but per-unit CATE ordering on observed X is not reliable — Day 14 uplift must report Qini/persuadable structure at the aggregate level.
  - Full suite 185/185; Day 13 validation hook ("learner agreement map") green.

## ADR-022 — Uplift evaluation: confounded observed Qini vs counterfactual true-lift; gate on pure ranking power (Day 14)

- **Date:** 2026-09-22 · **Status:** Accepted
- **Context:** Day 14 must report Qini curves and "Qini above chance" as its validation hook; the decision is *which* Qini to gate on. causalml's `get_qini(treatment_effect_col=...)` computes `l = cumsum(τ)/i × cumsum_tr` — the treatment-density weighting re-imports `sim_u` assignment selection into the score (propensity true-lift inflated to ~21% vs the uplift model's ~2%). On the real-world (observed) metric the strategy ordering itself is confounded: propensity "wins" (email conversion 27.4% vs uplift 13.1%) and the oracle sits *below* chance (−9.8%) because it demotes the high-`sim_u` conversion machines.
- **Decision:**
  1. **Report two metrics, gate only on the *true* one.** `qini_lift_observed_pct` (manual Radcliffe diff-in-means, cross-checked exactly against causalml `get_qini`) is reported for realism but never gated — it measures *confounder capture*, not causal ranking power. `qini_lift_true_pct` is the gate: a **pure cumulative-gain ranking-power curve on the counterfactual per-unit |true effect|** (sim_u, simulation-only) — `l = cumsum(|true effect|)`, endpoint-normalised with the chance diagonal (a Lorenz-style concentration measure), **no treatment weighting** (assignment coupling deliberately excluded so the metric measures ranking quality only).
  2. **|true effect| labels, not signed.** Sorting by signed effect inverts the ranking for the negative channel (social, all effects < 0): signed-descending = ascending magnitude → spurious oracle true-lift of −27.9%. |·| puts all channels on one axis — "responds most" = |effect| (harm-avoidance for social) — and the oracle strategy itself is scored by |true effect| (targeting value = response magnitude).
  3. **Oracle = the achievable ceiling (~27% on this DGP)** — the effect's intrinsic relative spread — so "above chance" is calibrated to what X-based models can reach on this simulation, not to a naive 90% expectation (which would gate on the confounder instead). Manual implementation keeps a deterministic stable sort (causalml's default quicksort breaks ties arbitrarily; the formula itself is verified identical).
- **Consequences:**
  - Observed: propensity 17.6–28.6% > uplift 13.1–23.9%; oracle −22.1…−8.9% (the observed metric punishes true-effect targeting). True: oracle 26.7–27.9% ceiling; every observed-X model ≈ 0–3%, uplift mean 1.12% (gate ≥ 0.5% passes with headroom); baseline E[Y|X] ~3% even beats the CATE ranking — heterogeneity is `sim_u`-driven, so uplift should target permission only at the aggregate level.
  - Display (embedded effect 0.00) true-lift == 0.0 for every strategy — the honest null.
  - Revenue true-lift == conversion true-lift for outcome-invariant scores (propensity) and monotone labels (oracle); uplift/baseline are per-outcome models so their lifts differ.
  - 4 uplift gates green; full suite 200/200. Day 14 closes Week 2 → **Gate 2 (human validation) required before Week 3.**

## ADR-023 — CATE segmentation: quantified quintile bands + counterfactual sign structure; guidance is per-channel, not per-customer (Day 15)

- **Date:** 2026-09-22 · **Status:** Accepted
- **Context:** Day 15 must deliver the roadmap's "target-segment table" with high/zero/negative-effect segments and targeting guidance ("Segments explain pattern" hook). Two facts block the naive design: (1) the estimated CATE is positive in **every** band of **every** channel (email 0.126 / search 0.126 / social 0.107 / display 0.112 conversion mean; 0% negative units) — the shared `sim_u` bias means a sign-based segment split on observed data is empty; (2) the ensemble-vs-truth rank correlation is ρ ≈ 0.01–0.06 (weaker than the Day-13 learner agreement, which measured mutual consistency, not truth), so per-customer targeting claims are unsupportable.
- **Decision:**
  1. **Segments = quintile bands of the ensemble CATE per cell** (`n_bands` 5: bottom … top + an `all` reference), each row carrying the estimated CATE with analytic SE + 95% normal CI AND the **counterfactual oracle mean** + oracle negative share — so the table always shows what targeting a band would *actually* achieve (simulation-only) next to what the model claims.
  2. **Guidance is per-channel and grounded in the counterfactual sign structure**, not the biased estimates: Run (email/search — positive throughout), Skip/avoid (social — negative for ~100% of the audience), No budget (display — effect exactly 0). The report states plainly that the *estimated* sign structure is wrong everywhere and explains the pattern only via the oracle.
  3. **Gate set split into machinery + empirical:** oracle sign-structure gates (email/search positive throughout, social negative throughout, display zero — DGP-plumbing checks), `estimated_signal_all_positive` (the bias demonstration), `rank_gradient_positive_gt` (email/search top−bottom oracle gap > 0.0001 — real but tiny, calibrated 0.13/0.17 pp), `uncertainty_reported`. Social's flat-to-inverted gradient is reported, deliberately not gated (the honest finding is "harm-avoidance is unreachable on observed X").
- **Consequences:**
  - Target-segment table + guidance land with every number labeled estimated vs counterfactual; a CMO sees "run email/search, skip social, zero-budget display" and a data scientist sees the band table with CIs and oracle columns.
  - Band gradients quantify the known limit: even the top band beats the bottom by only ~0.1–0.2 pp of incremental conversion — micro-targeting on observed X is nearly worthless; budget decisions are channel-level.
  - 6 gates green; full suite 213/213. Sets up Day 16 (ROI at config costs), Day 17 (counterfactual scenarios), Day 18 (sensitivity) on the same honest baseline.

## ADR-024 — Incremental ROI: three labeled methods (observational / causal / counterfactual) + cost assumptions in config (Day 16)

- **Date:** 2026-09-22 · **Status:** Accepted
- **Context:** Day 16 must deliver the roadmap's ROI deliverable (`reports/roi`, "ROI complete per channel"). Two design hazards: (1) Olist has no spend data, so costs are pure assumptions (ADR-006: put them in `configs/config.yaml`); (2) the Day-12 convergence story means ALL estimators are `sim_u`-biased — a "causal ROI" table alone would recommend funding display/social.
- **Decision:**
  1. **Costs = config assumptions, per-treated-customer R$ over the 14-day window** (`roi.cost_per_treated`: email 0.10, search 1.50, display 0.20, social 0.80 — Brazilian e-commerce order-of-magnitude). ROI = `(incremental revenue per treated − cost)/cost` (blueprint §9, exact).
  2. **Three methods per channel, every row labeled** (AGENTS.md §2): *observational* (Day-8 naive ATE — attribution-style), *causal* (Day-12 DR ATE, CI propagated through the monotone ROI transform — no delta method needed), *counterfactual* (true per-treated effect from the DGP oracle, simulation-only, CI collapses to the point). Summary table adds the `causal ÷ truth` overstatement multiple (NaN where the truth is negative — sign-flipped ratios are unquotable) and cohort net value = n_treated × net.
  3. **Gate on completeness + the honest pattern**: `complete_rows` (12 rows, positive costs, finite ROIs), `causal_roi_positive` (the bias demonstration — even causal ROI is positive everywhere), `ctf_email_search_positive` / `ctf_social_display_negative` (counterfactual truth), `overstatement_documented` (email/search ratio > 1), `uncertainty_reported`.
- **Consequences:**
  - Causal ROI: email 17,265%, search 1,112%, display 7,983%, social 1,912% — all wildly positive; naive ROI is similar (both confounded). Counterfactual: email 2,314%, search 101%, **social −299%, display −100%**. Overstatement ~7.5x (email) / ~11x (search); display/social sign-flipped.
  - Breakeven reads: email/search profitable at any cost below their true incremental revenue (R$ 2.41 / R$ 3.02 per treated); social/display can never break even — no cost assumption rescues them.
  - Cohort net value (counterfactual): +R$ 65,673 email, +R$ 48,167 search, −R$ 58,661 social, −R$ 7,094 display.
  - 6 gates green; full suite 225/225. Sets up Day 17 (counterfactual budget scenarios from these numbers) and Day 18 (sensitivity).

## ADR-025 — Counterfactual budget scenarios: fixed as-run budget, extrapolation caps + flags, CI propagated from Day-12 DR, honest gate set (Day 17)

- **Date:** 2026-09-22/23 · **Status:** Accepted
- **Context:** Day 17 must deliver "Scenarios A–D simulator + bootstrap uncertainty + extrapolation limits" (`results/counterfactuals`, hook "Uncertainty reported; limits stated"). Hazards: (1) scenario arithmetic is deterministic-linear on Day-16/ROI numbers, so bootstrap adds ~2h of runtime to reproduce what exact analytic CIs already give; (2) the naive first draft's "truth-wins" expectation was false on the data — an email-saturation artifact lets the naive spread top the counterfactual ranking (AGENTS.md rule 8: report what the data says, gate what is robust).
- **Decision:**
  1. **Fixed total budget = as-run spend** (Σ cost × observed treated = R$ 77,215). Four scenarios re-split it: `as_run` (as executed), `naive` (∝ last-touch revenue attribution), `causal` (∝ Day-12 DR causal ROI), `ctf_guided` (∝ counterfactual ROI, positive channels only). Every row labeled `counterfactual (simulated ground truth), model-based`.
  2. **Extrapolation limits (blueprint §9):** implied treated = spend/cost; cells exceeding the observed n_treated are capped at the cohort (94,983 — the analysis population, NOT the sum of per-channel treated = 120,235) and flagged ⚠. No silent extrapolation (gate).
  3. **Uncertainty reported without bootstrap:** net = Σ treated × (inc − cost) with treated fixed per scenario is a non-negative linear combination, so the 95% CI propagates exactly from the Day-12 DR revenue ATE CIs; the CI brackets the sim_u-inflated estimated scale, not the counterfactual point (the gap IS the documented bias).
  4. **Gates on robust claims only:** scenarios_complete; as_run_reproduces_day16 (cross-day consistency check against Day-16 cohort nets); reallocations_beat_as_run (any re-split beats the observed scatter); email_saturation_documented (the cap bites); bounded_by_optimum (no scenario exceeds the budget-constrained greedy email→search optimum); extrapolation_flagged; labels_correct; uncertainty_reported. The naive-topping-artifact is *reported, not gated*.
- **Consequences:**
  - Ranking (counterfactual net): naive 163,983 > ctf_guided 158,605 > causal 147,922 > as_run 48,084. Any reallocation beats as_run by ≥ R$ 99,838. The naive win is an email-saturation artifact (email saturates at R$ 9,498 spend; wider spreads waste less there) — it still burns R$ 69,140 on social/display. Budget-constrained optimum = R$ 288,438 (email to saturation, then search; never social/display); no observed-data rule reaches it.
  - Bias at portfolio level: counterfactual net = 2.7–10.3% of the estimated-scale CI lower bound → **≈10–38× overstatement** across scenarios.
  - 8 gates green; full suite 240/240. Sets up Day 18 (sensitivity: how strong must `sim_u` be?) and Day 19 (Streamlit dashboard).

## ADR-026 — Sensitivity analysis: E-value + exact linear bias formula with directly measured confounder; placebo tests as evidence (Day 18)

- **Date:** 2026-09-23 · **Status:** Accepted
- **Context:** Day 18 must answer the roadmap "how strong must U be?" ("Each claim stress-tested" hook). The Day-12 estimate convergence made the standard alternatives uninformative: every estimator (naive/OLS/IPW/DR/ATT/backdoor) gives the same positive ATE, so "try another estimator" proves nothing. The right stress test is confounder strength. Design constraints: (1) the E-value literature is binary-outcome flavoured — a continuous outcome needs the documented exp(0.91·d) approximation; (2) this DGP actually contains the confounder (`sim_u`), so unlike a real study we can measure δ and γ directly and check the bounds against reality; (3) a bootstrap would add runtime to reproduce what the exact linear bias formula gives analytically.
- **Decision:**
  1. **Two complementary tools**, both documented before fitting (AGENTS.md §3): (a) VanderWeele–Ding **E-value** via RR* = exp(0.91·d), d = ATE/SD(revenue), reported for the point and for the CI-lower bound ("explain away the whole CI"); (b) **linear bias formula** bias = δ_U·γ_U with γ_U = per-SD effect of `sim_u` on revenue and δ_U = standardized treated/untreated difference in `sim_u`, both measured directly from the DGP (simulation-only). Required δ to zero the estimate and to hit the truth is compared with actual δ.
  2. **Falsification tests as first-class evidence:** placebo outcome `sim_u` (treatment cannot affect it) and placebo channel display (true effect 0) must show large significant "effects" — the estimator bias made detectable. They are reported as expected failures, i.e. as evidence of bias.
  3. **Gate set on robust claims only:** evalue_reported; evalue_fragility_documented (point E-values in (1, max]); bias_formula_explains_most (share ≥ 0.70 per channel); actual_u_is_real_confounder (δ ≥ 0.50 SD); placebo_tests_falsified (|t| ≥ 1.96); uncertainty_reported; labels_correct. The tension between the conservative E-value (≈1.71) and the measured confounder (outcome-side RR ≈ 1.26 yet explaining 82–97% of bias) is reported, not papered over.
- **Consequences:**
  - E-values 1.68–1.75 (point) / 1.64–1.71 (CI-lower): a moderate unmeasured confounder (per-~SD RR ≈ 1.71 on both axes) fully explains the observed channel effects — the observed lift is NOT robustly causal.
  - Bias formula reproduces email 95% / search 97% / display 94% / social 82% of the observed bias; measured δ_U = 0.69–0.74 SD vs required-to-truth 0.73–0.86 — the actual confounder is nearly sufficient by itself (residual = DGP nonlinearity).
  - Placebo tests fail loudly (|t| 27.5–110), closing the loop from Days 8–12.
  - 7 gates green; full suite 254/254. Emphasizes the honest dashboard headline for Day 19: "observed lift is bias-compatible; causal bounds wide; counterfactual read email-first/search-second/stop display+social".

## ADR-027 — Streamlit dashboard: pure builders + honest framing single-source (Day 19)

- **Date:** 2026-09-23 · **Status:** Accepted
- **Context:** The Day-19 dashboard must productize the analysis as a 7-page Streamlit app without ever regressing into "established causal" language (AGENTS.md §8) and without leaking logic into the UI layer. Risky failure modes: (1) pages recompute estimates instead of reading `results/` (drift from the validated pipeline); (2) honest phrasing re-declared per page (drift between pages); (3) layout logic buried in Streamlit scripts that AppTest cannot reach headlessly.
- **Decision:**
  1. **All logic lives in pure builders** (`src/dashboard/builders.py`), one per page (`PAGE_BUILDERS` = exec, dag, attribution, uplift, simulator, sensitivity, diagnostics), each rendering deterministically from `load_config()` and precomputed `results/` CSVs — never recomputing models. `dashboard/app.py` + `dashboard/pages/*.py` are thin glue that bootstrap repo root into `sys.path` and call the builders.
  2. **Honest vocabulary has a single source:** `LABEL_ESTIMATED / LABEL_MEASURED / LABEL_PLACEBO / LABEL_TRUTH` are identity-imported from `src/causal/sensitivity.py` (Day 18) into the builders, never re-declared; every page carries the shared `HONEST_TOKEN` framing — "observed 14-day lift is confounder-compatible and **fragile** (E-values 1.68–1.75 email) — **NOT established causal**; email-first/search-second is a model-based counterfactual priority, not an observed conclusion; simulated ground truth is the DGP oracle label, NOT an observed result."
  3. **Gates enforce non-vacuity:** `render_gate()` asserts per page that content exists, honest tokens are present, and honest framing is carried; missing `results/` raises `FileNotFoundError` (no silent pass). Every effect keeps its CI columns (attribution `inc_rev_ci_low/high`, diagnostics `ci_lower/ci_upper`).
- **Consequences:**
  - Full suite 282/282 (254 + 28 dashboard tests): per-page headless AppTest renders (no exception + `HONEST_TOKEN` verbatim across markdown/title/info/error), builder-contract keys, label identity vs the sensitivity single source, CI presence/ordering, gate pass + gate non-vacuity, determinism, `run_all`.
  - Found and fixed while hardening: the first draft imported phantom labels (`LABEL_DGP / LABEL_PLACEBO_TOKEN / LABEL_NAIVE`) that exist nowhere — a collection-fatal bug; AppTest resolves relative scripts against the caller (tests/), so the suite passes absolute `_ROOT`-anchored paths; the gates read `results/` only, so the non-vacuity test monkeypatches `project_path`, not `cfg["results"]`. Dashboard reads `results/` only — no new `dashboard:` tunables block (blueprint §11 knobs live in `configs/config.yaml` for the pipeline, not the viewer).
  - Sets up Day 20 (tests + hardening) and Day 21 (README + `v1.0`), then **Gate 3 (final human validation)**.