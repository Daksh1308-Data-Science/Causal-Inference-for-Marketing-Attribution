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