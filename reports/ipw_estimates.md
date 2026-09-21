# Day 10 — Inverse Probability Weighting (IPW)

> **Label:** SIMULATED estimates (`sim_*`), not observed Olist facts (AGENTS.md §2). Identification: stabilized Hajek IPW with the Day-4 adjustment set for the propensity model. Exchangeability holds only given `sim_u`-free conditioning — and `sim_u` is unobserved by design, so the estimates remain biased toward the naive gap (quantified Day 18).

## Identification statement (before fitting)

- **Causal question (ATE):** what is the incremental 14-day conversion / revenue effect of exposure per channel, vs no exposure, for all customers?
- **Estimator:** Hajek-normalized IPW with stabilized weights, truncated at 10.0 (Cole & Hernan).
- **Positivity:** overlap verified Day 6; email has 71 units with PS ≈ 1.0 (weak overlap) → truncation applied and ESS caveated.
- **SUTVA / consistency:** satisfied within the sim design (no interference;
 single binary exposure).

## IPW ATE table (bootstrap 95% CI)

| Channel | Outcome | IPW ATE | SE | 95% CI | Naive | OLS | ESS% | Truncated | Max w |
|---|---|---|---|---|---|---|---|---|---|
| email | 14-day conversion | 0.1287 pp | 0.0033 | [0.1218, 0.1350] | 0.1252 pp | 0.1274 pp | 90.9% | 13 | 10.00 |
| email | 14-day revenue (R$) | 17.3646 R$ | 0.6808 | [15.9986, 18.6625] | 16.7713 R$ | 17.1112 R$ | 90.9% | 13 | 10.00 |
| social | 14-day conversion | 0.1061 pp | 0.0034 | [0.0990, 0.1122] | 0.1127 pp | 0.1061 pp | 93.5% | 9 | 10.00 |
| social | 14-day revenue (R$) | 16.1041 R$ | 0.7376 | [14.6249, 17.5314] | 17.1192 R$ | 16.1198 R$ | 93.5% | 9 | 10.00 |
| search | 14-day conversion | 0.1288 pp | 0.0030 | [0.1231, 0.1349] | 0.1277 pp | 0.1283 pp | 94.3% | 4 | 10.00 |
| search | 14-day revenue (R$) | 18.2047 R$ | 0.6259 | [16.9147, 19.3264] | 17.9635 R$ | 18.1239 R$ | 94.3% | 4 | 10.00 |
| display | 14-day conversion | 0.1125 pp | 0.0029 | [0.1064, 0.1177] | 0.1117 pp | 0.1122 pp | 98.5% | 1 | 10.00 |
| display | 14-day revenue (R$) | 16.1685 R$ | 0.5760 | [14.9196, 17.1267] | 15.9584 R$ | 16.1188 R$ | 98.5% | 1 | 10.00 |

## Weight diagnostics

- **email:** ESS 2.4 → **86327.9** after truncation (90.9% of n=94983, weight cap 10.0); 13 units capped.
- **social:** ESS 85733.5 → **88813.1** after truncation (93.5% of n=94983, weight cap 10.0); 9 units capped.
- **search:** ESS 89321.4 → **89547.0** after truncation (94.3% of n=94983, weight cap 10.0); 4 units capped.
- **display:** ESS 93523.7 → **93556.0** after truncation (98.5% of n=94983, weight cap 10.0); 1 units capped.

## Limitations

- Weak overlap for email (71 units PS ≈ 1.0) → stabilized weights are truncated; ATE then slightly biased but variance-reduced.
- `sim_u` is unobserved: IPW reweights on the observed set and cannot remove `sim_u` selection without strong assumptions.
- Bootstrap CI assumes resampling captures design variability; it does NOT cover model/PS misspecification.
- Conversion outcome: weights stabilize the mean but the binary outcome is better handled by DR / outcome-regression hybrids (Day 11).
