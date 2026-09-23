# Pitches — Causal Inference for Marketing Attribution

Three practiced pitches for the same project. Every word is defensible against the reports in `reports/` and the gates in `results/`. The honest-framing sentence is non-negotiable in every version — it is what separates this portfolio from a correlation rehash.

---

## The 30-second pitch (elevator)

"Attribution tools answer the wrong question. They tell you which channel got the click, not which channel *caused* the sale — and customers who click aren't random: they were already more likely to buy. I built a causal analysis of email, social, search, and display on 95,000 real Olist customers with a clearly-labelled simulated marketing layer, and the result is the caution every marketer needs: six estimators agreed every channel looks positive — display looks like a 7,900% ROI while its true effect is zero, and social looks great while it destroys value. Why? A modest hidden confounder — risk ratio about 1.7 — explains the entire observed lift. Observed lift is not causal lift, and on this data the difference flips the budget: email first, search second, stop social and display. Every number is labelled, every effect carries a confidence interval, and the whole thing is a reproducible 368-test pipeline with a dashboard."

## The 2-minute pitch (interview / portfolio review)

**Hook.** Marketing measurement has a conflation problem. Multi-touch attribution, ROAS dashboards, and A/B-lite comparisons all report something that *looks* like causation. Almost none of it is.

**The build.** Over one summer-project arc I took the real Brazilian E-Commerce (Olist) dataset — 94,983 customers, ~98k orders, loaded into MySQL 8 — and answered a question no Olist dataset can natively answer: *which marketing channel causes conversion and revenue?* Since Olist has no marketing data, I designed a simulated treatment layer (documented in `docs/data-feasibility.md`) with **known ground truth** — email genuinely +0.12, search +0.15, display 0.00, social −0.08 — plus a built-in latent confounder `sim_u` that drives both exposure and purchase. Every simulated variable carries the `sim_` prefix and nothing simulated is ever presented as observed fact.

**The method.** Identification strategy written *before* any fit: DAG, backdoor adjustment set, explicit assumptions (exchangeability, positivity, consistency, SUTVA) with evidence and limitations. Then five estimators — naive, OLS, IPW with stabilized weights, doubly-robust AIPW, and PS matching — plus a DoWhy backdoor cross-check, each reported with point, SE, and 95% CI. Then the part that separates causal from defensive work: **sensitivity**. E-values (1.68–1.75 — a risk-ratio-1.7 confounder explains everything), a linear bias formula that reproduces **82–97% of the observed bias** from the actual measured `sim_u`, and placebo tests that fail loudly (|t| 95–110 on a fake email channel).

**The result.** All five estimators converged — and converged *wrong*. Every channel looked positive, including a channel with true effect zero. Translating to money: causal ROI looked like 1,912% for social (truth: −297%) and 7,983% for display (truth: −100%). Budget scenarios on a fixed R$ 77,215 showed any re-split beats the as-run R$ 48k, but the optimum is unreachable by observed data — every observed rule keeps funding the loss-makers. The honest, defensible recommendation is a **model-based counterfactual priority: email first, search second, stop social and display.**

**The product.** A 7-page Streamlit dashboard that reads precomputed `results/` only, every page carrying the same honest-framing line; a 368-test suite including a deliverables manifest that audits every label for honest vocabulary and every gate as a recorded pass; a 25-section README; per-day technical reports. Deterministic: fixed seed, config-driven tunables, pinned requirements.

**Close.** For a CMO the deliverable is one sentence with teeth: *demand fragility reporting — the channel that looks like your best ROI may be your worst, and a modest hidden confounder can make it look that way.*

## The 5-minute pitch (technical deep dive)

Structure for a senior data-science audience. Table stakes first, then the three findings that matter, then the honest limits.

**1. Data & design (90s).** Real Olist core in MySQL 8 (schema + analytics views in `sql/`); simulated marketing layer from `simulation/simulate_marketing.py` with DGP parameters in `configs/config.yaml` (seed 42). Exposure: `logistic(score(RFM/category/seasonality) + 0.8·sim_u)`; outcome: 14-day conversion and log-normal revenue with `sim_u` coefficient 1.0; per-channel true log-odds email +0.12, search +0.15, display 0.00, social −0.08. The oracle (read from the DGP) is the *simulated ground truth* used to grade every estimator — a yardstick a real study never has.

**2. Identification & estimation (90s).** Per-channel DAGs with latent `sim_u`; backdoor adjustment on observed covariates; assumptions stated pre-fit. Estimator family: naive diff-in-means (Day 8), OLS with HC3 (Day 9), stabilized IPW with Cole–Hernán cap of 10 (Day 10), DR/AIPW (Day 11), 1:1 caliper matching read as ATT (Day 7), DoWhy 0.8 backdoor cross-check (Day 12). Convergence gates: all within 0.02 pp (conversion) / 10% relative (revenue). Result: convergence is real — and misleading, because all estimators share the unobserved `sim_u` term. Positivity evidence: overlap + SMD before/after matching.

**3. Three findings worth defending (120s).**
- *Placebo-validated confounder:* effect_sd on `sim_u` 0.69–0.74 (t 94.9–110.3); a true-zero channel "measuring" R$ 16.17 (t 27.5) — the estimator suite detects effects that are absent.
- *E-value fragility:* point E-values 1.68 (social/display), 1.72 (email), 1.75 (search); CI-lower 1.64–1.71. A confounder at RR ≈ 1.71 on both axes wipes the whole story.
- *Money consequence:* ROI table in `reports/roi.md` — causal ROI positive everywhere but 7.5× (email) and 11× (search) above counterfactual truth, sign-inverted for social/display. Scenario engine: deterministic re-split of R$ 77,215 with extrapolation caps and estimated-scale CIs (the gap between estimated CI and truth-net is the bias, quantified in money).

**4. Limits, stated (60s).** (a) Simulation, not real campaigns — ground truth is built-in, so the oracle comparison is a *validation of the pipeline*, not of the world. (b) Costs are assumptions (ADR-006). (c) No interference assumed; consistency holds by construction. (d) CATE heterogeneity is weak on observed X because `sim_u` dominates (reported in learner-agreement maps). (e) The recommendation is a counterfactual priority, not a causal conclusion from observed data.

**5. Reproducibility (30s).** Config-driven tunables, fixed seeds, pinned `requirements.lock.txt`, 368 tests from repo root, results-only dashboard, deliverables manifest gate. `pytest` green; every gate recorded in `results/*/gates.csv`; README quickstart reproduces install → results.

**Close.** The portfolio's thesis, defensible in one line: *when six confounded estimators agree, you have learned how strong the confounder is — not that the effect is real; report the E-value, run the placebo, label every number.*