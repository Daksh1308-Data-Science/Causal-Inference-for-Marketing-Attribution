# Day 14 — Uplift Modeling

> **Labels:** Qini/segment numbers are **estimated (simulated)**; the oracle curves are **counterfactual (simulated ground truth)** — they use `sim_u` and are unachievable on observed data (AGENTS.md §2/§3).

## Identification (before evaluation)

- **Causal question:** can τ̂(x) rank customers so targeting the top-ranked yields more incremental outcomes than random or response-based targeting?
- **Score = Day-13 meta-learner ensemble** (mean of T/S/X CATE): no new model family, same identification as Day 13 (exchangeability given X; **sim_u unobserved**).
- **Comparison strategies:** propensity p(X) (Day 6) and baseline E[Y|X] (Day 13) — the naive marketer's 'target likely converters'; oracle = true effect (counterfactual).
- **Qini (Radcliffe 2007, manual, cross-checked against causalml.metrics.get_qini):** cumulative incremental responses among treated, sorted by score. `qini_lift` = normalised area between the curve and the chance diagonal (0 = chance, 100 = max).
- **Two evaluations.** (1) *observed* — computed from observed outcomes (all a real-world analyst has). (2) *true* — evaluated against the **counterfactual** per-unit true effects (sim_u-based, simulation-only): the honest ranking-power check. **The observed metric is `sim_u`-confounded**: within-score-bin rate differences inherit the assignment bias, and the strategy *ordering* itself is biased (see Key finding below).

## Qini lift (% of max, 0 = chance)

Two numbers per strategy: **obs** = observed-outcome metric (real-world computable, `sim_u`-confounded); **true** = cumulative |true effect| gain against the counterfactual oracle labels (simulation-only; the honest ranking-power check; 0 = random, oracle ≈ 27% = this DGP's achievable ceiling — the intrinsic relative spread of the effect).

### 14-day conversion

| Channel | θ̂ obs | p obs | E[Y|X] obs | Oracle obs | θ̂ true | p true | E[Y|X] true | Oracle true |
|---|---|---|---|---|---|---|---|---|
| email | +13.1 | +27.4 | +4.7 | -9.8 | +1.4 | -0.3 | +3.0 | +26.8 |
| social | +20.7 | +17.6 | +17.4 | -22.1 | +0.3 | +3.1 | +3.1 | +27.9 |
| search | +18.9 | +18.8 | +4.2 | -8.9 | +1.6 | -0.6 | +3.0 | +26.7 |
| display | +17.1 | +8.9 | +4.2 | +2.5 | +0.0 | +0.0 | +0.0 | +0.0 |

### 14-day revenue (R$)

| Channel | θ̂ obs | p obs | E[Y|X] obs | Oracle obs | θ̂ true | p true | E[Y|X] true | Oracle true |
|---|---|---|---|---|---|---|---|---|
| email | +23.9 | +28.6 | +4.7 | -14.0 | +0.3 | -0.3 | +3.1 | +26.8 |
| social | +22.5 | +17.3 | +16.7 | -11.7 | +0.1 | +3.1 | +3.0 | +27.9 |
| search | +17.9 | +19.4 | +2.8 | -5.6 | +0.7 | -0.6 | +2.9 | +26.7 |
| display | +19.1 | +8.1 | +3.5 | +0.5 | +0.0 | +0.0 | +0.0 | +0.0 |

## Key finding — the *observed* Qini rewards the confounder, not the effect

On the observed (confounded) metric the propensity score 'wins' — e.g. email conversion: propensity **+27%** vs uplift **+13%** — and the oracle (true effect) is **below chance (−10%)**. This is not a bug: p(X) encodes the `sim_u` selection, so targeting high-propensity customers harvests the assignment bias, exactly like the naive ATE did in Days 8–12. The oracle actively *demotes* the high-`sim_u` 'conversion machines' whose observed diffs are inflated (their true incremental effect ≈ 0), so the raw metric punishes it. **An above-chance observed Qini is NOT evidence of a causal uplift model on confounded data.** The *true* metric is the meaningful one.

## Validation hook — Qini above chance (true metric)

- **Gate (config `uplift`):** mean **Uplift-strategy true-lift** over the three channels with a real embedded effect (email/search/social) **>= 0.5%** (targeting power above random), and **display true-lift <= 0.5%** (embedded effect 0.00 — nothing to rank, so every strategy's true-lift is ≈ 0).
- **Sanity (machinery, asserted in tests):** the counterfactual oracle is the max-strategy true lift for every GT≠0 channel, and display's true-lift == 0 for every strategy.

### Gate results

| Gate | Scope | Value | Threshold | Pass |
|---|---|---|---|---|
| qini_above_chance_gt | email/social/search (mean) | 1.12 | 0.50 | ✅ |
| qini_display_no_effect | display | 0.00 | 0.50 | ✅ |
| oracle_is_upper_bound | email/social/search | True | True | ✅ |
| segments_interpretable | all channels (conversion) | 0.11 | 0.05 | ✅ |

## Marketing segments (conversion, 4 quadrants)

| Channel | Segment | Size | Share | Conv rate | Mean τ̂ | Mean baseline |
|---|---|---|---|---|---|---|
| email | Persuadable | 23,771 | 25.0% | 20.2% | +0.1273 | 0.205 |
| email | Sure Thing | 23,720 | 25.0% | 24.4% | +0.1371 | 0.237 |
| email | Sleeping Dog | 22,948 | 24.2% | 22.4% | +0.1192 | 0.222 |
| email | Lost Cause | 24,544 | 25.8% | 19.7% | +0.1195 | 0.203 |

| social | Persuadable | 27,748 | 29.2% | 19.1% | +0.1090 | 0.202 |
| social | Sure Thing | 19,743 | 20.8% | 24.2% | +0.1136 | 0.238 |
| social | Sleeping Dog | 25,209 | 26.5% | 22.9% | +0.1008 | 0.224 |
| social | Lost Cause | 22,283 | 23.5% | 21.2% | +0.1034 | 0.206 |

| search | Persuadable | 12,991 | 13.7% | 20.5% | +0.1313 | 0.205 |
| search | Sure Thing | 34,500 | 36.3% | 23.7% | +0.1386 | 0.231 |
| search | Sleeping Dog | 10,452 | 11.0% | 22.6% | +0.1140 | 0.230 |
| search | Lost Cause | 37,040 | 39.0% | 19.9% | +0.1164 | 0.203 |

| display | Persuadable | 15,693 | 16.5% | 19.4% | +0.1173 | 0.205 |
| display | Sure Thing | 31,798 | 33.5% | 23.0% | +0.1206 | 0.230 |
| display | Sleeping Dog | 14,017 | 14.8% | 24.1% | +0.1062 | 0.228 |
| display | Lost Cause | 33,475 | 35.2% | 20.4% | +0.1034 | 0.204 |

## Reading the map (honest interpretation)

- **Observed vs true — the strategy ranking flips.** On the observed (confounded) metric propensity 'wins' and the oracle is below chance; on the true (counterfactual) metric the oracle is the ceiling (~27%) while every observed-X strategy is ≈ 0–3%. The observed metric measures *confounder capture*; the true metric measures *real ranking power* — only the latter supports causal targeting claims.
- **Uplift-vs-propensity (true metric):** none of the observed-X rankings reach even ~10% of the ceiling: the mean Uplift-strategy lift is ~1% vs a ~27% oracle. The baseline-response ranking (E[Y|X]) actually edges out the CATE ranking (~3% vs ~1%) — the effect heterogeneity is `sim_u`-driven, so the noisier CATE estimates add ranking noise rather than signal. **The recoverable targeting signal on observed X is tiny; Day 18's sensitivity quantifies how strong U must be to explain the ATE itself.**
- **Integer-segment reading:** within a channel, *persuadable* = high-τ̂/low-baseline (the incremental sweet spot), *sure thing* = high-τ̂/high-baseline (treat to keep), *sleeping dog* = low-τ̂/high-baseline (skip), *lost cause* = low-τ̂/low-baseline (skip). Cross-channel, social (embedded −0.08 log-odds) is the channel where 'skip' is most defensible since its τ̂ ranks lowest.

## Limitations

- The *observed* Qini is `sim_u`-confounded — strategy ranking included — so only the *true* (counterfactual) metric supports claims about real ranking power.
- Segments are cut at channel medians of τ̂ and E[Y|X]; they describe relative responsiveness, not a calibrated absolute effect per customer.
- Oracle scores/curves use `sim_u` (counterfactual, simulated ground truth); they set an upper bound on observed-data models, never an achievable benchmark.
