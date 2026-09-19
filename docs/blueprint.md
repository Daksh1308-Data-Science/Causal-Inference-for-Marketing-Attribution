# Project Blueprint

Complete design for **Causal Inference for Marketing Attribution**. Source: `Plan.md`. Status: Day 0 (approved).

---

## 1. Business problem

Budget is allocated on observational metrics (CTR, conversion rate, revenue/channel, ROAS). But **exposure ≠ causation**: customers who see an ad may already have higher purchase intent. The project answers:

> "What is the incremental causal impact of each marketing channel on conversion and revenue?"

## 2. Data flow

```
Olist CSVs (9 tables, real observations)
        │  clean + load (Python→MySQL bulk insert)
        ▼
MySQL 8.0  ── SQL views: cohorts, RFM, retention, monthly revenue, conversion windows
        │  extract analytical customer table
        ▼
customer_analytical.parquet
        │  join simulated marketing layer (sim_*, known ground truth, confounding by design)
        ▼
analysis dataset (customer × channel × exposure × outcome in 14-day window)
        │
        ├── causal estimation: naive / OLS / PSM / IPW / DR / DoWhy backdoor
        ├── CATE + uplift: T/S/X-learners, EconML DR-learner, Qini, quadrants
        ├── ROI + counterfactual scenarios → results/*.json + figures
        └── sensitivity + validation: balance, overlap, placebo, E-value, bias formula
                                   │
                                   ▼
                        Streamlit dashboard (7 pages, reads results/)
```

## 3. Repository structure

```
data/            raw/ (Olist CSVs, gitignored) · processed/ · simulated/
notebooks/       01_eda → 07_sensitivity
src/
  data/          load_olist.py · mysql.py · build_analytical.py
  features/      rfm.py · seasonality.py · category.py
  causal/        dag.py · propensity.py · matching.py · ipw.py · doubly_robust.py · estimates.py
  uplift/        learners.py · segments.py · qini.py
  evaluation/    balance.py · positivity.py · placebo.py · sensitivity.py · bootstrap_ci.py
  visualization/ plots.py · dag_plot.py · dashboard_helpers.py
sql/             schema.sql · load.sql · analytics/*.sql · indexes.sql
simulation/      simulate_marketing.py     ← clearly-labeled synthetic layer
dashboard/       app.py + 7 pages
tests/           env gate · schema · ground-truth recovery · dashboard data
configs/         config.yaml               ← paths, DSN, seeds, costs, outcome window
reports/         technical_report.md · executive_summary.md
results/         figures/ · tables/ · artifacts/
docs/            blueprint · roadmap · status · decisions · data-feasibility · learning-plan
```

## 4. Tech stack

- **Data:** Python 3.14, pandas, numpy, MySQL 8.0 (Workbench + Shell), pymysql, SQLAlchemy
- **Causal:** DoWhy 0.8 (classic API), CausalML, EconML; PSM/IPW/AIPW hand-implemented where instructive
- **Stats:** statsmodels, scipy, bootstrap CI
- **Viz:** matplotlib, seaborn, plotly, networkx (DAG; **no pygraphviz**)
- **App:** Streamlit (reads precomputed `results/`)
- **Eng:** modular `src/`, `configs/config.yaml`, pytest, per-day git commits

## 5. Causal framework (per channel)

```
      U (unobserved intent, simulated) ──┬──────────────────────────────┐
                                         ▼                              ▼
   Recency, Frequency, Monetary, Tenure, CategoryAffinity, Seasonality, Geography
        │  (confounders)          ►  Simulated targeting  ►  Exposure A ► Y (conversion, 14d) ► Revenue
        └──────────────────────────────────────────────────────────────┘
        Mediators (do NOT adjust): Click / Session
        Collider (do NOT adjust):  total channels seen
```

- **Treatment:** simulated exposure flag per channel (email, social, search, display), one analysis per channel plus a joint-model caution.
- **Outcome:** purchase in the 14-day post-campaign window; revenue.
- **Confounder audit:** every variable classified as confounder / treatment / outcome / mediator / collider / irrelevant, each with a written justification (Day 4).
- **Unobserved confounder `U`** (latent buying intent) is deliberately left in the simulator so even optimal adjustment leaves residual bias — it drives the sensitivity analysis and ground-truth bias quantification.

## 6. Identification strategy (written before fitting)

Section per channel (report): causal question · treatment · outcome · assumptions (exchangeability, positivity, consistency, no-interference) with evidence and limitations · why assignment is confounded · sufficient adjustment set · overlap evidence · SUTVA caveat for multi-channel effects · remaining unobserved confounding.

**No library output is ever quoted as "assumptions satisfied."**

## 7. Modeling strategy (estimator ladder)

| Estimator | Answers | Validation hook |
|---|---|---|
| Naive diff-in-means | observational baseline | expected biased by design |
| OLS regression adjustment | ATE + CI | vs naive |
| Propensity Score Matching | ATT + balance | SMD before/after, love plot |
| IPW (stabilized weights, ESS) | ATE | weight extremes checked |
| Doubly robust (AIPW) | ATE | consistent if either model right |
| DoWhy backdoor (multi-method) | ATE cross-check | estimator convergence |
| CausalML T/S/X + EconML DR | CATE segments | Qini, uplift quadrants |

Every estimate reports: point estimate, CI, SE, N, estimator, assumptions, interpretation.

## 8. Validation & sensitivity

- Covariate balance · positivity/overlap · placebo treatment · placebo outcome · estimator robustness · bootstrap CIs
- E-value · Rosenbaum-style bounds · unobserved-confounder bias formula (VanderWeele) · alternative adjustment sets
- **Ground-truth recovery:** bias/MSE of each estimator vs the simulator's known effects
- Section: *"How strong would an unmeasured confounder have to be to eliminate the estimated effect?"*

## 9. ROI & counterfactuals

- `Incremental conversions = CATE × N_targeted`
- `Incremental revenue = inc conversions × avg revenue/conversion`
- `Incremental ROI = (inc revenue − cost) / cost`
- Channel costs are **explicit assumptions** in `configs/config.yaml` (Olist has no spend data)
- Observational vs causal ROI table per channel; scenarios A–D labeled **model-based counterfactual estimates** with bootstrap uncertainty and extrapolation-limits notes

## 10. SQL layer (MySQL 8)

`schema.sql` (DDL, `AUTO_INCREMENT`, indexes) · `load.sql` (Python bulk insert) · analytics views: customer cohorts, monthly revenue, retention, conversion windows, RFM, treatment/control populations, revenue by channel · `EXPLAIN ANALYZE` optimization notes in comments · executable both from Python (pymysql) and MySQL Workbench.

## 11. Dashboard (Streamlit, 7 pages)

1. Executive summary · 2. Interactive DAG · 3. Channel attribution (observed vs causal) · 4. Uplift segmentation (persuadables / sure things / lost causes / sleeping dogs) · 5. Counterfactual budget simulator · 6. Sensitivity analysis · 7. Model diagnostics (overlap, balance, CIs, effect distributions).

Reads precomputed `results/` → fast, deterministic, reproducible.