# Day 18 — Sensitivity: how strong must the unobserved confounder be?

> **Labels (AGENTS.md §2):** *estimated* = Day-12 causal DR revenue ATE on observed (simulated marketing) data; *simulated ground truth* = DGP oracle per-treated effect; *simulated measured* = the confounder `sim_u` read directly out of the DGP (the real U of this simulation); *simulated placebo* = falsification tests. None of this is an observed Olist fact.

## The question

- Every Day-8–17 observed-data estimator reports a positive revenue ATE per channel (≈ R$ 16.09–18.19), yet the sim truth is email/search profitable and social/display worthless or negative. Day 18 asks: **how strong would an unmeasured confounder have to be to produce that entire set of estimates by itself — and how strong is the actual `sim_u` built into this DGP?**

## Method (stated before the numbers)

- **E-value (VanderWeele & Ding 2017).** d = ATE / SD(revenue) = ATE / 81.76; RR* = exp(0.91·d); E-value = RR* + √(RR*·(RR*−1)). An unmeasured confounder associated with **both** exposure and outcome at risk ratio ≥ E-value (per the RR/mean-difference approximation) would fully explain away the estimate. Reported for the point *and* for the CI lower bound (explain away the whole CI).
- **Linear bias formula.** observed = truth + bias, with bias = δ_U·γ_U: δ_U = standardized difference of U between treated/untreated, γ_U = per-SD effect of U on revenue. From it, the **required δ** to (i) zero the estimate and (ii) reach the truth is δ_required = (point − target)/γ_U with γ_U = 20.54 R$/SD
- **Measured U (simulation-only).** `sim_u` is known in the DGP, so δ_U and γ_U are measured directly instead of guessed — this is the honest yardstick for the bounds above.
- **Falsification (placebo) tests.** (1) outcome `sim_u`: the treatment cannot causally change `sim_u` (it is pre-treatment), so any estimated effect on it is pure selection; (2) channel display: its true per-treated effect is 0, so any estimated effect on it is pure bias. Both tests are expected to FAIL hugely — that failure is the evidence, not a bug.

## E-value table (explain-away strength)

| Channel | ATE (R$) | 95% CI | E-value (point) | E-value (CI lower) | n |
|---|---|---|---|---|---|
| email | R$ 17.36 | R$ 16.04–18.69 | 1.72 | 1.68 | 94,983 |
| social | R$ 16.09 | R$ 14.73–17.46 | 1.68 | 1.64 | 94,983 |
| search | R$ 18.19 | R$ 16.95–19.42 | 1.75 | 1.71 | 94,983 |
| display | R$ 16.17 | R$ 15.01–17.32 | 1.68 | 1.65 | 94,983 |

- E-values cluster around **1.70–1.75** — a confounder with per-~SD RR ≈ 1.71 on BOTH the treatment and the outcome explains the estimates away entirely. By epidemiology convention that is **modest robustness**: the observed positive effects are not robust to even a moderate unmeasured confounder.

## Bias formula: required vs actual confounder strength

| Channel | Bias (obs − truth) | γ_U (R$/SD) | δ_U required→truth | δ_U actual (measured) | ratio actual/required | bias explained |
|---|---|---|---|---|---|---|
| email | R$ 14.95 | 20.5 | 0.73 | 0.69 | 95% | 95% |
| social | R$ 17.67 | 20.5 | 0.86 | 0.70 | 82% | 82% |
| search | R$ 15.16 | 20.5 | 0.74 | 0.71 | 97% | 97% |
| display | R$ 16.17 | 20.5 | 0.79 | 0.74 | 94% | 94% |

- The **actual** confounder (measured `sim_u`) shows δ_U ≈ 0.69–0.74 SD between treated and untreated — essentially as strong as the ≈ 0.86 the formula needs to pull every estimate down to the truth. The linear bias formula δ_U·γ_U alone reproduces **82–97% of the observed bias** per channel (the residual is nonlinearity in the conversion/revenue DGP).
- Read together with the E-value: the conservative worst-case bound (E-value ≈ 1.75, symmetric on both axes) is far above the actual outcome-side strength (γ_U/SD ≈ 0.25 SD), yet the measured confounder still explains nearly all of the bias — the E-value is a worst-case guarantee for a *binary, unmeasured* U; the measured continuous U is its real-life counterpart here and the exact linear formula is much tighter.

## Falsification (placebo) tests

| Test | Estimate | Scale | |t| | p | Falsified? |
|---|---|---|---|---|---|
| placebo outcome sim_u | channel email | 0.6613 | mean difference in sim_u | |97.6| | 0 | ⚠ yes (bias visible) |
| placebo outcome sim_u | channel social | 0.6727 | mean difference in sim_u | |94.9| | 0 | ⚠ yes (bias visible) |
| placebo outcome sim_u | channel search | 0.6787 | mean difference in sim_u | |103.8| | 0 | ⚠ yes (bias visible) |
| placebo outcome sim_u | channel display | 0.6986 | mean difference in sim_u | |110.3| | 0 | ⚠ yes (bias visible) |
| placebo channel display (true effect 0) | 16.1655 | R$ per treated (DR) | |27.5| | 1.1e-166 | ⚠ yes (bias visible) |

- The placebo outcome `sim_u` (a variable the treatment **cannot** affect) shows a ~0.7-SD, enormously significant 'effect' of every channel — pure selection through `sim_u`. The placebo channel *display* (true effect 0) shows a positive R$ 16 estimate with |t| ≈ 110. Both placebos fail loudly: observed-data estimation on this DGP detects effects that are not there.

## Cross-estimator stress (alt adjustment sets/estimators)

Day 9–12 already showed naive ≈ OLS ≈ IPW ≈ DR ≈ ATT ≈ backdoor on every channel (convergence gates, `results/tables/master_estimates.csv`); the cross-estimator range is tiny relative to the bias quantified above — so the positive estimates are **stable**, which is exactly why Day 18's confounder bounds, not another estimator, are the honest stress test.

## Key finding

- **A moderate unmeasured confounder fully explains the observed channel effects** (point E-value ≈ 1.71, CI-lower E-value ≈ 1.67): on observed (simulated) data alone, the marketing channel 'effects' should not be treated as causal.
- **The actual confounder is real and nearly sufficient:** measured δ_U ≈ 0.71 vs required-to-truth ≈ 0.78; the bias formula covers 82–97% of every observed bias, and its residual matches DGP nonlinearity — i.e. the observed-data story **(email/search look ~7× too good; social/display look profitable at all) is explained by `sim_u`, and Days 16–17 already priced that in (ROI overstatement ≈7.5×/11×; scenario overstatement ≈10–38×).**
- Day 19 turns this bound into the dashboard's honest headline: 'the observed lift is bias-compatible; the causal bounds are wide; the counterfactual read is email-first, search second, stop display/social'.

## Validation hooks — gates

| Gate | Scope | Value | Threshold | Pass |
|---|---|---|---|---|
| evalue_reported | all channels | 1 | 1 | ✅ |
| evalue_fragility_documented | point E-values | 1.75 | 3 | ✅ |
| bias_formula_explains_most | all channels | 0.816 | 0.7 | ✅ |
| actual_u_is_real_confounder | all channels | 0.692 | 0.5 | ✅ |
| placebo_tests_falsified | placebo outcome + placebo channel | 27.5 | 1.96 | ✅ |
| uncertainty_reported | all channels | 1 | 1 | ✅ |
| labels_correct | all output rows | 1 | 1 | ✅ |

## Limitations

- The E-value RR approximation (exp(0.91·d)) is a standard continuous-outcome bridge, an approximation, not exact for this revenue distribution; the bias-formula numbers are the exact linear decomposition and should be read as primary.
- The measured confounder and the truth come from the DGP — they exist ONLY in this simulation and prove its internal consistency; they are not a claim about real Olist marketing.
- The bias formula assumes linearity in U on the revenue scale; the residual gap (≤ 18% on social) is where nonlinearity hides.
- No unobserved-confounding bound can certify the absence of OTHER confounders on top of `sim_u`; the E-value quantifies fragility, it does not remove it.
