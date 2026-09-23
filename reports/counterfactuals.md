# Day 17 — Counterfactual Budget Scenarios

> **Labels:** every number below is a **model-based counterfactual estimate (simulation-only)** — it uses the DGP's per-treated true effects (oracle) and is unachievable on observed data (AGENTS.md §2/§3). Not a prediction of the real world. Every row of `results/counterfactuals/scenarios.csv` carries the machine-readable label `counterfactual (simulated ground truth), model-based`.

## Method

- Fixed total budget = the as-run campaign spend, computed from the Day-16 cost assumptions x observed treated counts (**R$ 77,215**). Four allocations re-split that same budget.
- `as_run` = as executed (shares ∝ cost × treated); `naive` = last-touch attribution (shares ∝ naive revenue ATE × treated); `causal` = Day-12 DR causal ROI (shares ∝ causal ROI); `ctf_guided` = DGP-informed (shares ∝ counterfactual ROI, positive channels only).
- Per channel: spend = share x budget; implied treated = spend / cost; incremental revenue = treated x counterfactual per-treated revenue effect; net = revenue - spend. Deterministic arithmetic on Day-16 numbers — no new sampling uncertainty.
- **Extrapolation limit (positivity):** when implied treated exceeds the observed n_treated for a channel, the linear model is asserted beyond the observed range; those cells are capped at the cohort size and flagged with ⚠ (blueprint §9 extrapolation-limits note).
- **Uncertainty:** scenario totals also carry an estimated-scale 95% CI propagated exactly through the linear transform from the Day-12 DR revenue ATE CIs (treated counts are fixed per scenario, so net = Σ treated × (inc − cost) is a non-negative linear combination). The CI brackets the `sim_u`-inflated estimated net, NOT the counterfactual point — the gap between them is the Days 8–16 bias, quantified at the scenario level.

## Scenario tables (net value, R$)

| Scenario | Channel | Share | Spend | Treated (implied→capped) | Inc. revenue | Net | ⚠ |
|---|---|---|---|---|---|---|---|
| as_run | email | 4% | R$ 2,838 | 28,380 | R$ 68,511 | R$ 65,673 |  |
| as_run | social | 26% | R$ 19,766 | 24,707 | R$ -38,896 | R$ -58,661 |  |
| as_run | search | 62% | R$ 47,517 | 31,678 | R$ 95,684 | R$ 48,167 |  |
| as_run | display | 9% | R$ 7,094 | 35,470 | R$ 0 | R$ -7,094 |  |
| **as_run total** | — | 100% | R$ 77,215 | — | R$ 125,299 | **R$ 48,084** | |

| naive | email | 23% | R$ 18,069 | 180,685→94,983 | R$ 229,294 | R$ 211,226 |  ⚠ |
| naive | social | 21% | R$ 16,056 | 20,070 | R$ -31,596 | R$ -47,653 |  |
| naive | search | 28% | R$ 21,602 | 14,401 | R$ 43,499 | R$ 21,897 |  |
| naive | display | 28% | R$ 21,488 | 107,439→94,983 | R$ 0 | R$ -21,488 |  ⚠ |
| **naive total** | — | 100% | R$ 77,215 | — | R$ 241,197 | **R$ 163,983** | |

| causal | email | 61% | R$ 47,153 | 471,528→94,983 | R$ 229,294 | R$ 182,141 |  ⚠ |
| causal | social | 7% | R$ 5,222 | 6,527 | R$ -10,275 | R$ -15,497 |  |
| causal | search | 4% | R$ 3,038 | 2,025 | R$ 6,117 | R$ 3,080 |  |
| causal | display | 28% | R$ 21,802 | 109,012→94,983 | R$ 0 | R$ -21,802 |  ⚠ |
| **causal total** | — | 100% | R$ 77,215 | — | R$ 225,137 | **R$ 147,922** | |

| ctf_guided | email | 96% | R$ 73,974 | 739,742→94,983 | R$ 229,294 | R$ 155,320 |  ⚠ |
| ctf_guided | social | 0% | R$ 0 | 0 | R$ 0 | R$ 0 |  |
| ctf_guided | search | 4% | R$ 3,240 | 2,160 | R$ 6,525 | R$ 3,285 |  |
| ctf_guided | display | 0% | R$ 0 | 0 | R$ 0 | R$ 0 |  |
| **ctf_guided total** | — | 100% | R$ 77,215 | — | R$ 235,819 | **R$ 158,605** | |

## Scenario ranking (from the counterfactual)

| Rank | Scenario | Net (R$) | CI est. (Day-12 DR, R$) | ROI on budget | ⚠ channels |
|---|---|---|---|---|---|
| 1 | naive | R$ 163,983 | [R$ 3,423,440, R$ 3,983,678] | 212% | 2 |
| 2 | ctf_guided | R$ 158,605 | [R$ 1,547,687, R$ 1,804,104] | 205% | 1 |
| 3 | causal | R$ 147,922 | [R$ 3,043,601, R$ 3,536,248] | 192% | 2 |
| 4 | as_run | R$ 48,084 | [R$ 1,811,451, R$ 2,113,950] | 62% | 0 |

## Key finding

- **Any re-split beats the as-run scatter:** the worst reallocation nets R$ 147,922 against as_run's R$ 48,084 on the same R$ 77,215 budget — the observed campaign bleeds value because observed data made every channel look profitable (Days 8–16).
- **Ranking caveat (reported, not gated):** `naive` tops the counterfactual net at R$ 163,983, but part of that ordering is an extrapolation artifact — email saturates once spend hits R$ 9,498 (whole cohort treated), after which further email budget is pure waste, so wider spreads 'win' by spending less on the saturated channel. They still burn R$ 69,140 of the naive spread on social/display alone (true effects negative/zero). Not an endorsement of any confounded rule.
- **Scenario-level bias in money terms:** the estimated-scale 95% CI on the as_run total is R$ 1,811,451–2,113,950 while its counterfactual net is R$ 48,084 (≈ 2.7% of the CI lower bound) — observed-data estimates overstate achievable scenario value by ≈10–38x across scenarios, the `sim_u` inflation from Days 8–16 at the portfolio level.
- **Robust reads:** the budget-constrained optimum is R$ 288,438 (fund email to saturation, then search; never touch social/display) — no rule-based scenario reaches it, because both observed-data rules (naive, causal) keep funding channels whose counterfactual net is negative: every estimate is `sim_u`-inflated (Days 8–16). Day 18 bounds that confounder.

## Validation hooks — gates

| Gate | Scope | Value | Threshold | Pass |
|---|---|---|---|---|
| scenarios_complete | all scenarios | 20.0000 | 20.0000 | ✅ |
| as_run_reproduces_day16 | as_run vs Day-16 | 0.0000 | 0.0100 | ✅ |
| reallocations_beat_as_run | reallocation scenarios | 99837.7800 | 0.0000 | ✅ |
| email_saturation_documented | email cells | 3.0000 | 1.0000 | ✅ |
| bounded_by_optimum | all scenarios | 124455.4000 | 0.0000 | ✅ |
| extrapolation_flagged | all scenario x channel cells | 0.0000 | 0.0000 | ✅ |
| labels_correct | all rows | 1.0000 | 1.0000 | ✅ |
| uncertainty_reported | scenario totals (estimated scale) | 1.0000 | 1.0000 | ✅ |

## Limitations

- Counterfactual and inherently linear: no saturation, carryover, frequency caps, or cost curves; costs are flat assumptions (ADR-006).
- Extrapolation beyond observed treated ranges is capped, not solved — the flags mark where the model is asserted, not where it is true.
- All values inherit the DGP oracle (sim_u); they define the achievable truth on THIS simulation only. Day 18 quantifies how strong the unobserved confounder must be otherwise.
