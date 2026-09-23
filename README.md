# Causal Inference for Marketing Attribution

**Measuring what actually causes conversion — not just what correlates with it.**

A portfolio-grade causal analysis of four marketing channels (email, social, search, display) on conversion and revenue, built on the real Brazilian E-Commerce (Olist) dataset with a clearly-labelled simulated marketing layer. It walks the chain:

**Correlation → Causal Effect → Incremental Revenue → Marketing ROI → Budget Allocation**

> ⚠️ **Honest framing (AGENTS.md §8).** Olist contains **no** marketing treatment data, so the marketing layer is a **simulation** (`sim_*` variables, designed in `docs/data-feasibility.md` §4). Every observed-data estimate on this build is **confounder-compatible and fragile** (E-values 1.68–1.75) — the observed 14-day lift is **NOT established causal**. Simulated ground truth (the DGP oracle) is labelled as such and is **not** an observed result. Read the [limitations](#16-honest-framing--what-this-analysis-does-not-claim) before quoting any number.

---

## 1. The problem: attribution is correlation in disguise

Multi-touch attribution tools claim to tell you "which channel caused the sale." They usually report something weaker: *last-touch share*, *look-back window revenue*, or a diff-in-means between customers who were exposed and those who were not. All of those are **correlational**.

The gap is **confounding**: customers who open your emails, click your ads, or show up in your display audience are *not* a random sample of your customer base. They differ in intent, recency, lifetime value, and dozens of other dimensions — and those same dimensions drive whether they buy. A naive "exposed shoppers spend R$ X more" number mixes the channel's true effect with the *selection* of who gets exposed.

This project does the full job: it states the causal question and assumptions up front, estimates treatment effects with methods that adjust for observed confounding (OLS, IPW, doubly-robust AIPW, matching, DoWhy backdoor), quantifies how fragile those estimates are to an *unmeasured* confounder (E-value, bias formula, placebo tests), translates effects into incremental revenue and ROI, and finally into budget-allocation scenarios — while labelling every result as **observed, estimated, simulated, or counterfactual**.

## 2. TL;DR — what we found

On this simulated marketing layer over real Olist customers (94,983-person cohort):

1. **Every observed-data estimator says every channel is positive.** Naive → OLS → IPW → DR → ATT → DoWhy all converge to ≈ +0.11–0.13 pp conversion and ≈ R$ 16–18 incremental revenue per treated customer, for **all four channels** — including display, whose true effect is $0$, and social, whose true effect is *negative*.
2. **That convergence is the confounder, not the truth.** A latent intent variable `sim_u` drives both exposure and purchase. Adjusting for every *observed* covariate changes little; the shared unobserved `sim_u` bias is what makes every estimator agree (Days 8–12).
3. **The counterfactual truth is completely different.** Measured from the simulation's own data-generating process (label: *simulated ground truth / DGP oracle*): email genuinely converts (+0.12 log-odds), search is modestly positive (+0.15), display does nothing (0.00), and social is negative (−0.08).
4. **Money shows the damage.** Even the *causal* ROI looks excellent everywhere (email 17,265%, display 7,983%, social 1,912%, search 1,112%) — because the causal estimate inherits the confounder. The counterfactual ROI says email 2,314% and search 101% are the only winners; **social (−297%) and display (−100%) destroy value**.
5. **Anyone's budget rule can beat the as-run campaign.** On the fixed R$ 77,215 budget, every reallocation scenario nets R$ 148k–164k vs. R$ 48k as run. But no *observed-data* rule reaches the R$ 288,438 budget-constrained optimum — they keep funding social/display because every estimate is inflated.
6. **A modest unmeasured confounder explains everything.** E-values 1.68–1.75: an unmeasured confounder with RR ≈ 1.71 on both axes fully explains the observed effects. The *actual* `sim_u` (δ ≈ 0.69–0.74 SD) reproduces 82–97% of every observed bias, and both placebo tests fail loudly (|t| 27.5–110).

**Bottom line (honest):** on observed data alone you would fund display and social and over-fund search. The confounder-aware read: **email first, search second, stop social and display** — but that read is a *model-based counterfactual priority*, not an observed-data conclusion.

## 3. Project goals & scope

**Primary goal.** Produce a stage-gated, reproducible, portfolio-grade causal-attribution analysis that a CMO can act on **and** a senior data scientist can stress-test.

**Scope.**
- Real data: Brazilian E-Commerce (Olist), ~96k customers / ~100k orders, 2016–2018, via MySQL 8.0.
- Simulated treatment layer: email / social / search / display exposures with known ground truth (documented design + `sim_` prefix).
- Outcomes: 14-day conversion (0/1) and 14-day revenue (R$).
- Methods: potential outcomes framework, DAG-based identification, OLS / IPW / DR / matching / DoWhy backdoor, CATE meta-learners, uplift modeling, E-value sensitivity, budget simulation.
- Product: 7-page Streamlit dashboard over precomputed `results/`, 368-test suite, full report set.

**Out of scope (explicitly).** No claim that the simulation's ground truth transfers to the real world; no spend data (channel costs are documented config *assumptions*, ADR-006); no holdout/live experiment (this is an observational analysis with a simulation).

## 4. Dataset

| Layer | Source | Label |
|---|---|---|
| Customer/order core | Brazilian E-Commerce Olist (Kaggle mirror), loaded into MySQL 8 `olist` DB | **observed** |
| Customer analytics (RFM, cohorts, recency, tenure, category affinity) | SQL views over the Olist core (`sql/analytics/`) | **observed** |
| Channel exposures, `sim_u` intent confounder, outcomes | `simulation/simulate_marketing.py` (design: `docs/data-feasibility.md` §4) | **simulated** (`sim_*`) |

Cohort: **94,983 customers** (98,199 purchased orders, deduplicated, with ≥ 1 order and complete core fields). All analytics (RFM, cohorts, retention) are SQL views — see `sql/schema.sql` and `sql/analytics/customer_analytical.sql`.

> ⚠️ **Olist has no marketing data.** The marketing layer is a clearly-labelled simulation: exposures, the confounder `sim_u`, and channel effects are generated, with a documented data-generating process. **Nothing simulated is ever presented as an observed Olist fact.** Every simulated variable carries the `sim_` prefix; results from the DGP oracle are labelled *simulated ground truth*.

## 5. The causal framework

- **Potential outcomes.** For each customer $i$ and channel $c$, define $Y_i(1)$ = outcome if exposed, $Y_i(0)$ = outcome if not. The causal effect is $Y_i(1) - Y_i(0)$; we estimate the ATE (expose anyone) and ATT (effect on the exposed — the current targeting policy).
- **Directed acyclic graph (DAG).** Per-channel DAGs state the assumed structure *before* fitting (Day 5): observed covariates (recency, tenure, total revenue, order count, review score) → exposure AND outcome; latent **`sim_u` → exposure AND outcome** (the built-in confounder); exposure → conversion → revenue.
- **Identification.** The causal estimand is identified by the backdoor adjustment set (the observed covariates) **given the assumptions** — but `sim_u` is *unobserved* to the estimators, so identification only holds under no-unobserved-confounding, which this DGP deliberately violates. We state this and then *measure* the violation (Days 12, 18).
- **Assumptions (stated, tested, and honestly reported):**
  - *Exchangeability (no unobserved confounding)* — **violated by design** (`sim_u`); the degree of violation is quantified (bias formula: 82–97% of observed bias explained by `sim_u`).
  - *Positivity/overlap* — checked per channel (Day 6): overlap plots + SMD before matching; IPW weights capped (Cole–Hernán truncation, cap 10).
  - *Consistency* — exposure is well-defined per channel (simulation guarantees the counterfactual is coherent).
  - *SUTVA/no interference* — treated as plausible per-channel (no spillover designed into the simulation).

## 6. The simulated marketing layer (design summary)

Full design: `docs/data-feasibility.md` §4. Highlights:

- Latent intent `sim_u ~ N(0, 1)`; assignment coefficients per channel (e.g. email: recency −0.4, total revenue +0.5, order count +0.3, review score +0.1) plus `sim_u` coefficient 0.8 and an intercept — exposure depends on observed covariates **and** the latent confounder.
- Outcome: baseline 14-day purchase intent (log-odds −1.6) + `sim_u` coefficient 1.0 + channel effect + noise; revenue is log-normal (mean 4.6, σ 0.8).
- **Embedded ground truth:** email +0.12 log-odds, search +0.15, display 0.00, social −0.08.
- The DGP oracle (read from the simulator, not from any estimator) is the *simulated ground truth* used for validation — a yardstick that a real observational study never has.

## 7. Pipeline architecture

```
data/raw (Olist CSVs)  →  sql/ (schema.sql, load.sql, analytics views, MySQL 8)
        │                                  │
        └──────────►  data/processed  ◄────┘
                              │
              simulation/simulate_marketing.py  (sim_* treatment layer + sim_u)
                              │
                   data/simulated (features)
                              │
        src/data  src/features  src/causal  src/uplift  src/evaluation  src/visualization
                              │
                 results/ (CSV tables, figures, gates)   ← dashboard reads ONLY results/
                              │
        reports/*.md  ·  dashboard/ (Streamlit, 7 pages)  ·  tests/ (pytest)
```

Design blueprint: `docs/blueprint.md`. Every module is config-driven (tunables in `configs/config.yaml`), seeded (fixed `seed: 42`), and type-hinted with docstrings.

## 8. Repository layout

| Path | Purpose |
|---|---|
| `configs/config.yaml` | All tunables: paths, seeds, outcome window, IPW cap, convergence tolerances, ROI costs, sensitivity gates, simulation DGP |
| `sql/` | MySQL 8 schema, load scripts, analytics views |
| `simulation/` | Simulated marketing layer (`sim_*`) with documented DGP |
| `src/data`, `src/features` | Data loaders, feature construction |
| `src/causal/` | naive, regression (OLS), propensity, ipw, matching, doubly_robust, cate, uplift, segments, roi, counterfactuals, sensitivity, synthesis, dag |
| `src/dashboard/` | Pure page builders (headless-testable) |
| `src/evaluation/`, `src/visualization/` | Gates, plots |
| `dashboard/` | Streamlit app + pages (thin glue over builders) |
| `results/` | Precomputed tables, figures, gate records |
| `reports/` | Per-day markdown reports + portfolio docs |
| `tests/` | 368-test pytest suite |
| `docs/` | blueprint, roadmap, status, decisions (ADRs), data-feasibility, learning-plan |

## 9. Key results — the chain, stage by stage

| Day | Stage | Headline (honestly labelled) |
|---|---|---|
| 3–7 | Data + balance | 94,983-cohort; propensity overlap OK; |SMD| < 0.1 after matching; PS correct + positivity |
| 8 | Naive | Diff-in-means: **observed** lift positive for all 4 channels (selection-dominated) |
| 9–11 | OLS / IPW / DR | Adjusted estimates barely move: **shared `sim_u` bias** (unobserved confounder dominates) |
| 12 | Master ATE + DoWhy | 48-row master table; DoWhy reproduces OLS to ~1e-13; convergence story verified |
| 13–15 | CATE + uplift + segments | Every estimated CATE positive in every band (bias, not signal); counterfactual shows email/search +, social −, display 0; "persuadable email" segment |
| 16 | ROI | Causal ROI positive everywhere (confounded); counterfactual: email 2,314%, search 101%, social −297%, display −100% |
| 17 | Budget scenarios | Any re-split beats as-run (R$ 148k–164k vs 48k); optimum R$ 288,438 unreachable by observed rules |
| 18 | Sensitivity | E-values 1.68–1.75 → fragile; `sim_u` explains 82–97% of bias; placebos fail loudly |
| 19–20 | Product | 7-page dashboard + deliverables-manifest tests (368/368) |

## 10. Finding 1 — estimator convergence is a confounder, not confirmation

Naive ≈ OLS ≈ IPW ≈ DR ≈ ATT ≈ DoWhy on every channel × outcome (Day 12 convergence gates). Example (email, 14-day revenue, R$ per treated): naive 16.77 [15.55, 17.99], OLS 17.11 [15.85, 18.37], IPW 17.36 [16.00, 18.66], DR 17.36 [16.04, 18.69], ATT 17.48 [16.11, 18.85].

Textbook instinct: "if six estimators agree, the effect is real." Wrong here — they agree because they all adjust for the *same observed set* and all leave the **same `sim_u` unadjusted**. The placebo checks prove it: the treatment cannot affect `sim_u` (pre-treatment), yet every channel "shows" a ~0.7-SD effect on it (|t| 95–110); and display (true effect 0) shows R$ 16.17 with |t| = 27.5. Convergence across confounded estimators is not causal identification — an explicit lesson of this project.

**Master table:** `results/tables/master_estimates.csv` (point / SE / 95% CI / N / estimator / assumptions / label) — every row CI'd, never a bare point.

## 11. Finding 2 — incremental revenue and ROI (the money term)

ROI = (incremental revenue per treated − cost per treated) / cost per treated, with per-channel costs as **config assumptions** (ADR-006; R$ per treated over the 14-day window: email 0.10, search 1.50, display 0.20, social 0.80).

| Channel | Observed ROI | Causal ROI (95% CI) | Counterfactual ROI | Causal ÷ truth |
|---|---|---|---|---|
| email | 16,671% | 17,265% [15,943, 18,586] | 2,314% | 7.5× |
| search | 1,098% | 1,112% [1,030, 1,195] | 101% | 11.0× |
| display | 7,879% | 7,983% [7,407, 8,558] | −100% | — |
| social | 2,040% | 1,912% [1,741, 2,083] | −297% | — |

- Every observed/causal ROI is positive because every estimate inherits the `sim_u` bias.
- Counterfactually (DGP oracle): email is excellent, search modestly positive, **social and display destroy value** (negative/zero true effect).
- Overstatement is quantifiable: **~7.5× email, ~11× search**; sign-flipped for social/display.
- Causal ROI report: `reports/roi.md`; table: `results/roi/roi_{summary,long}.csv` (CI columns included).

## 12. Finding 3 — budget allocation via counterfactual scenarios

Fixed budget = the as-run spend (**R$ 77,215**). Four allocations re-split the same budget (as_run / naive / causal / ctf_guided); per-channel treated capped at the cohort (94,983) with extrapolation flags; scenario totals carry an estimated-scale 95% CI (the honest gap between estimated and truth is the Days 8–16 bias in money terms).

| Scenario | Net (R$) | Estimated-scale 95% CI (DR) | vs as_run |
|---|---|---|---|
| naive | 163,983 | [3,423,440, 3,983,678] | +241% |
| ctf_guided | 158,605 | [1,547,687, 1,804,104] | +230% |
| causal | 147,922 | [3,043,601, 3,536,248] | +208% |
| as_run | 48,084 | [1,811,451, 2,113,950] | — |
| *optimum* | *288,438* | — | *+500%* |

Read: **any re-split beats the as-run scatter**, but no observed-data rule reaches the optimum (fund email to saturation ≈ R$ 9,498 spend, then search; never social/display) — because every estimate is inflated and keeps funding loss-making channels. The naive ranking "wins" partly via an extrapolation/saturation artifact, reported not gated. Full tables: `results/counterfactuals/`; report: `reports/counterfactuals.md`.

## 13. Finding 4 — sensitivity: how strong must the unmeasured confounder be?

Day 18 (report: `reports/sensitivity.md`; tables: `results/sensitivity/`), two tools plus falsification:

- **E-value (VanderWeele & Ding 2017, continuous-outcome approximation).** Point E-values 1.68–1.75 per channel (CI-lower 1.64–1.71). Interpretation: an unmeasured confounder associated with **both** exposure and outcome at RR ≈ 1.71 on each axis would fully explain away the observed estimates. **That is fragile.**
- **Linear bias formula.** bias = δ_U·γ_U with the confounder *measured directly from the simulation* (γ_U = R$ 20.5/SD revenue; δ_U actual 0.69–0.74 SD). The formula alone reproduces **82–97% of the observed bias** (email 95% / search 97% / display 94% / social 82%; residual = DGP nonlinearity).
- **Placebo tests.** Placebo outcome `sim_u`: |t| 95–110 across channels. Placebo channel display (true effect 0): R$ 16.17, |t| 27.5. Both fail loudly — the estimator detects effects that are not there.

Together: the observed positive lift is **not robustly causal**; a moderate unmeasured confounder of the kind this simulation actually contains explains essentially all of it.

## 14. Heterogeneity — CATE, uplift, and segments (know *who* responds)

- **CATE meta-learners (T/X/S, Day 13):** all 8 channel × outcome cells pass learner-agreement gates, but individual-level rank agreement is weak (Spearman 0.32–0.77) — observed-X heterogeneity signal is tiny because `sim_u` dominates. Reported, not hidden.
- **Uplift (Day 14):** Qini evaluation *against the counterfactual true lift*; observed-data scores rank the confounded signal (propensity "wins"), while the oracle upper bound shows a real but small rank gradient. The **"persuadable email"** segment is where the counterfactual concentration recommendation comes from.
- **Segments (Day 15):** 5 CATE bands per channel × outcome + Run/Skip/No-budget guidance. Every *estimated* CATE is positive in every band (the shared-bias demonstration); the counterfactual oracle shows email/search +, social −, display 0 — the observed data cannot recover even the sign.

Segmentation guidance is **per-channel**, model-based, and counterfactual-informed — never "this individual customer causes revenue."

## 15. Causal-identification notebook (per channel)

For every channel the identification strategy was written **before** fitting (AGENTS.md §3; audit rows in `results/tables/confounder_audit.csv` and `reports/confounder_audit.md`): causal question, treatment, outcome, required assumptions, why assignment is confounded, sufficient adjustment set, positivity/overlap evidence, SUTVA/consistency plausibility, remaining-unobserved-confounding sources. No claim is made that an assumption holds merely because a library ran.

## 16. Honest framing — what this analysis does NOT claim

1. **The observed 14-day lift is NOT established causal.** It is confounder-compatible and fragile (E-values 1.68–1.75).
2. **Simulated results are not Olist facts.** Every `sim_*` variable and every DGP-oracle number is labelled `simulated` / `simulated ground truth` / `placebo`.
3. **Correlation ≠ causation.** No report, figure, dashboard page, or README says a channel "causes" an outcome based on observed data. Correlation-vs-causation is enforced by tests (`tests/test_artifacts.py` scans every label and report).
4. **Costs are assumptions** (ADR-006), not observed spend.
5. **All effects carry uncertainty** — point + SE + 95% CI, never a bare point estimate (enforced by gates).

The honest dashboard headline, on every page: *"the observed 14-day lift is confounder-compatible and fragile (E-values 1.68–1.75 email) — NOT established causal. Email-first / search-second is a model-based counterfactual priority, not an observed-data conclusion."*

## 17. Dashboard

7-page Streamlit app (`dashboard/`, run `streamlit run dashboard/app.py`) over precomputed `results/` **only** — pages never recompute models:

1. Executive summary (honest KPI cards) · 2. DAGs · 3. Attribution (naive vs causal vs counterfactual, CI bars) · 4. Uplift segments · 5. Budget simulator · 6. Sensitivity (E-value, bias formula, placebos) · 7. Diagnostics (master table, CI columns).

All logic lives in pure builders (`src/dashboard/builders.py`); the app/pages are thin glue. Every page renders the single-source honest framing token; every effect carries a CI. Headless-tested with Streamlit AppTest. ADR-027.

## 18. Reproducibility

- **Config-driven:** every tunable (paths, DSN, seeds, channel costs, outcome window, gate thresholds) in `configs/config.yaml`. No hardcoded magic values in code.
- **Pinned env:** `requirements.txt` (ranges) + `requirements.lock.txt` (exact pins); Python 3.14; local MySQL 8.0 (`MySQL80` service), credentials in `.env` (gitignored; `olist_app` user, never root in code).
- **Fixed seed `42`** for every simulation/model/bootstrap → identical renders and results.
- **Results-only dashboard:** the app reads precomputed CSVs, so a fresh run reproduces the same `results/` → same dashboard.
- **Test gate:** `pytest` from repo root — 368 tests, all green (env gate, data schema, ground-truth recovery on a small synthetic DGP, per-day gates, dashboard renders, deliverables manifest).

## 19. Testing & quality gates

- 20 test modules; coverage: environment gate, data schema/cohort, data-quality audit, per-method correctness (naive, OLS, IPW, DR, matching, DoWhy), ground-truth recovery (synthetic τ = 1.0 DR double-robustness), CATE/uplift/segments gates, ROI, counterfactuals, sensitivity, dashboard (headless AppTest + honest tokens), **deliverables manifest** (every artifact present, gate records green, honest vocabulary everywhere).
- Daily validation hooks (gates) recorded in `results/*/gates.csv` and summarized in `docs/roadmap.md`.
- Stage gates: Week 1 (Days 1–7) → validated; Week 2 (Days 8–14) → validated; Week 3 (Days 15–21) → final Gate 3 after Day 21.

## 20. Tech stack

Python 3.14 · Pandas · NumPy · **MySQL 8.0** (Workbench; window functions/CTEs, no Docker) · DoWhy 0.8 (classic API) · EconML · CausalML · statsmodels · scikit-learn · LightGBM · XGBoost · SHAP · NetworkX + Plotly (DAG rendering; no pygraphviz) · Matplotlib/Seaborn · Streamlit (AppTest for headless tests) · pytest.

## 21. Decision records

Every material decision is an ADR in `docs/decisions.md` (ADR-001 … ADR-028): MySQL over Docker, simulated-layer design, channel list, IPW truncation, DR estimator, DoWhy backdoor cross-check, CATE learners, uplift evaluation, segments, ROI cost assumptions, counterfactual scenarios, E-value/bias-formula sensitivity, pure-builder dashboard, deliverables-manifest gate.

## 22. Quickstart

```bash
# 1. environment
python -m venv .venv && .venv\Scripts\activate        # Windows
pip install -r requirements.lock.txt

# 2. database (MySQL 8 running)
#    create olist DB + olist_app user; copy .env.example -> .env; fill credentials

# 3. data + pipeline (Day-by-day; see docs/roadmap.md for order)
python -X utf8 sql/load.sql                            # (via mysql client; schema.sql first)
python -X utf8 simulation/simulate_marketing.py        # sim_* treatment layer

# 4. tests
pytest                                                 # 368 tests, from repo root

# 5. dashboard
streamlit run dashboard/app.py                         # reads results/ only
```

A full pipeline reproduction guide lives in `docs/roadmap.md` (per-day entry points) with results re-generable into `results/` and `reports/`.

## 23. Reports index

Per-day technical reports in `reports/`: `confounder_audit`, `naive_estimates`, `ols_estimates`, `ipw_estimates`, `dr_estimates`, `treatment_effects` (master), `cate_effects`, `uplift_modeling`, `cate_segmentation`, `roi`, `counterfactuals`, `sensitivity`. Portfolio docs: `reports/executive_summary.md`, `reports/pitches.md`, `reports/interview_qa.md`.

## 24. References & methods

- Rubin causal model; Imbens & Rubin 2015; Hernán & Robins 2020.
- IPW with stabilized weights + Cole–Hernán truncation (2008).
- Doubly robust / AIPW: Robins, Rotnitzky, Zhao 1994; O'Connell & Ferguson semiparametric notes.
- CATE meta-learners: Künzel et al. 2019 (T/X/S-learners), Wager & Athey 2018 (GRF).
- E-value: VanderWeele & Ding 2017; continuous-outcome approximation via standardized mean difference.
- Linear bias formula: VanderWeele & Arah 2011.
- Qini/uplift evaluation: Radcliffe 2007-2012; truthful attribution comparison.
- Dashboard: Streamlit; DoWhy 0.8 classic API.

## 25. Status, roadmap, and final word

Live progress: `docs/status.md` · execution map: `docs/roadmap.md` · master spec: `Plan.md` · agent rules: `AGENTS.md`.

**Final word.** The single most important result of this project is not "email is great." It is that **six confounded estimators agreeing is not identification**, that a *modest* unmeasured confounder can manufacture a positive ROI everywhere, and that honest attribution must therefore report fragility (E-values), validate with placebos, and separate observed/causal/counterfactual labels. When the data (here: the DGP oracle) says social and display destroy value while the observed data says the opposite — the honest answer is "we cannot know from observed data alone, and here is how strong the confounder would have to be." That is the answer a CMO can act on and a data scientist can defend.