# Day 13 — CATE with Meta-Learners (T / S / X)

> **Label:** all results are **estimated (simulated)** (`sim_*`), never observed Olist facts (AGENTS.md §2). CATE = conditional effect on OBSERVED features; `sim_u` is never a feature.

## Identification (before fitting)

- **Causal question:** how does the incremental 14-day effect of each channel vary with observed customer features X? Feature set = the Day-4 adjustment set per channel (email: order_count, recency_days, review_score_avg, total_revenue; social/search: order_count, tenure_days, total_revenue; display: recency_days, total_revenue).
- **Assumptions:** exchangeability given X with **sim_u unobserved** (the CATE inherits the Days 8-12 ATE bias); positivity/overlap per Day 6; consistency + SUTVA as the whole project. **Sim_u is excluded from features by design.**
- **Regressors on the binary outcome:** causalml's classifier path calls the hard `predict` (labels), collapsing probability CATE to ~0; regressors on 0/1 yields a valid probability-scale CATE (verified: email conversion T 0.1268 / S 0.1241 / X 0.1278 vs Day-12 OLS ATE 0.1274).
- **Cross-fitting:** learners fit and predict on the same sample (in-sample CATE, standard uplift practice); DML-style cross-fitting deferred to Day 18.

## CATE summary (mean + bootstrap 95% CI)

| Channel | Outcome | Learner | Mean CATE | 95% CI | SD | q05–q95 |
|---|---|---|---|---|---|---|
| email | 14-day conversion | T-learner | 0.1273 pp | [0.1272, 0.1273] | 0.0139 | [0.1110, 0.1493] |
| email | 14-day conversion | S-learner | 0.1230 pp | [0.1229, 0.1231] | 0.0136 | [0.1062, 0.1471] |
| email | 14-day conversion | X-learner | 0.1271 pp | [0.1270, 0.1271] | 0.0082 | [0.1205, 0.1399] |
| email | 14-day revenue (R$) | T-learner | 17.2720 R$ | [17.2452, 17.2959] | 3.8341 | [13.1292, 22.5322] |
| email | 14-day revenue (R$) | S-learner | 16.3555 R$ | [16.3339, 16.3740] | 3.1348 | [12.8043, 22.6610] |
| email | 14-day revenue (R$) | X-learner | 17.2384 R$ | [17.2191, 17.2606] | 3.2269 | [15.0173, 21.5872] |
| social | 14-day conversion | T-learner | 0.1097 pp | [0.1096, 0.1098] | 0.0126 | [0.0973, 0.1259] |
| social | 14-day conversion | S-learner | 0.1015 pp | [0.1014, 0.1016] | 0.0093 | [0.0926, 0.1165] |
| social | 14-day conversion | X-learner | 0.1082 pp | [0.1082, 0.1083] | 0.0064 | [0.1050, 0.1189] |
| social | 14-day revenue (R$) | T-learner | 16.6195 R$ | [16.6002, 16.6395] | 3.1555 | [12.7924, 21.1147] |
| social | 14-day revenue (R$) | S-learner | 15.2290 R$ | [15.2105, 15.2472] | 2.6351 | [12.9653, 18.6300] |
| social | 14-day revenue (R$) | X-learner | 16.4079 R$ | [16.3937, 16.4228] | 2.2243 | [14.9930, 21.0945] |
| search | 14-day conversion | T-learner | 0.1280 pp | [0.1278, 0.1281] | 0.0251 | [0.0955, 0.1650] |
| search | 14-day conversion | S-learner | 0.1230 pp | [0.1229, 0.1231] | 0.0131 | [0.1075, 0.1422] |
| search | 14-day conversion | X-learner | 0.1278 pp | [0.1277, 0.1279] | 0.0128 | [0.1138, 0.1433] |
| search | 14-day revenue (R$) | T-learner | 17.9808 R$ | [17.9598, 18.0067] | 3.5248 | [13.8748, 21.2170] |
| search | 14-day revenue (R$) | S-learner | 17.1487 R$ | [17.1332, 17.1661] | 2.4928 | [13.6063, 19.8092] |
| search | 14-day revenue (R$) | X-learner | 17.9970 R$ | [17.9842, 18.0136] | 2.3538 | [14.9193, 19.6910] |
| display | 14-day conversion | T-learner | 0.1136 pp | [0.1135, 0.1137] | 0.0178 | [0.0895, 0.1411] |
| display | 14-day conversion | S-learner | 0.1085 pp | [0.1084, 0.1086] | 0.0135 | [0.0927, 0.1286] |
| display | 14-day conversion | X-learner | 0.1136 pp | [0.1135, 0.1136] | 0.0060 | [0.1073, 0.1269] |
| display | 14-day revenue (R$) | T-learner | 16.1756 R$ | [16.1592, 16.1966] | 2.9253 | [12.1599, 20.3066] |
| display | 14-day revenue (R$) | S-learner | 15.2214 R$ | [15.2082, 15.2381] | 2.3176 | [11.8217, 18.4693] |
| display | 14-day revenue (R$) | X-learner | 16.1741 R$ | [16.1657, 16.1850] | 1.4341 | [14.3298, 18.9906] |

## Learner agreement map (validation hook)

- **Gates (calibrated to what agreement means on this DGP):** every learner's mean CATE within the Day-12 OLS ATE tolerance (conversion 0.01 pp abs / revenue 0.1 rel) AND max pairwise decile-curve |spread| <= 0.25 of the effect size (|mean CATE|).
- **Reported, not gated:** individual-level rank agreement (Spearman) is 0.32-0.77 across learners — the observed-X heterogeneity signal is tiny, so per-unit CATE ordering is weak. This is an honest limitation, not a test failure.

Pairwise agreement detail:

| Channel | Outcome | Pair | Indiv. Spearman | Indiv. MAD | Decile Spearman | Decile MAD |
|---|---|---|---|---|---|---|
| email | 14-day conversion | t-s | 0.653 | 0.0083 | 0.903 | 0.0049 |
| email | 14-day conversion | t-x | 0.609 | 0.0063 | 0.964 | 0.0011 |
| email | 14-day conversion | s-x | 0.569 | 0.0087 | 0.842 | 0.0051 |
| email | 14-day revenue (R$) | t-s | 0.711 | 1.8398 | 0.903 | 1.0334 |
| email | 14-day revenue (R$) | t-x | 0.712 | 1.5242 | 0.770 | 0.4710 |
| email | 14-day revenue (R$) | s-x | 0.615 | 1.5877 | 0.612 | 0.8830 |
| social | 14-day conversion | t-s | 0.394 | 0.0101 | 0.539 | 0.0082 |
| social | 14-day conversion | t-x | 0.716 | 0.0062 | 0.855 | 0.0028 |
| social | 14-day conversion | s-x | 0.394 | 0.0078 | 0.406 | 0.0067 |
| social | 14-day revenue (R$) | t-s | 0.647 | 2.1060 | 0.733 | 1.4745 |
| social | 14-day revenue (R$) | t-x | 0.797 | 1.3499 | 0.818 | 0.6938 |
| social | 14-day revenue (R$) | s-x | 0.698 | 1.6303 | 0.745 | 1.1788 |
| search | 14-day conversion | t-s | 0.621 | 0.0135 | 0.964 | 0.0050 |
| search | 14-day conversion | t-x | 0.696 | 0.0120 | 0.964 | 0.0021 |
| search | 14-day conversion | s-x | 0.796 | 0.0076 | 0.927 | 0.0048 |
| search | 14-day revenue (R$) | t-s | 0.688 | 1.5917 | 0.794 | 0.8321 |
| search | 14-day revenue (R$) | t-x | 0.773 | 1.2634 | 0.927 | 0.4672 |
| search | 14-day revenue (R$) | s-x | 0.583 | 1.4379 | 0.770 | 0.9347 |
| display | 14-day conversion | t-s | 0.535 | 0.0118 | 0.636 | 0.0059 |
| display | 14-day conversion | t-x | 0.511 | 0.0109 | 0.576 | 0.0025 |
| display | 14-day conversion | s-x | 0.761 | 0.0088 | 0.952 | 0.0055 |
| display | 14-day revenue (R$) | t-s | 0.641 | 1.7240 | 0.745 | 1.0548 |
| display | 14-day revenue (R$) | t-x | 0.673 | 1.3864 | 0.806 | 0.5115 |
| display | 14-day revenue (R$) | s-x | 0.654 | 1.5092 | 0.842 | 1.0932 |

Agreement status (hook):

| Channel | Outcome | Max \|mean Δ vs ATE\| | Mean tol | Max decile rel | Decile tol | Status |
|---|---|---|---|---|---|---|
| email | 14-day conversion | 0.0044 | 0.0100 | 0.041 | 0.250 | **OK** |
| email | 14-day revenue (R$) | 0.7557 | 1.7111 | 0.061 | 0.250 | **OK** |
| social | 14-day conversion | 0.0047 | 0.0100 | 0.077 | 0.250 | **OK** |
| social | 14-day revenue (R$) | 0.8908 | 1.6120 | 0.092 | 0.250 | **OK** |
| search | 14-day conversion | 0.0053 | 0.0100 | 0.039 | 0.250 | **OK** |
| search | 14-day revenue (R$) | 0.9752 | 1.8124 | 0.053 | 0.250 | **OK** |
| display | 14-day conversion | 0.0038 | 0.0100 | 0.053 | 0.250 | **OK** |
| display | 14-day revenue (R$) | 0.8974 | 1.6119 | 0.069 | 0.250 | **OK** |

## Reading the map (honest interpretation)

- **Aggregate level: agreement is real.** Mean CATEs match the Day-12 ATE and the 10-decile curves track each other (max spread ≤ 0.092 of the effect size). The signal that survives is smooth: effect ≈ flat, mildly tilted by baseline risk (the embedded effect is constant in log-odds, so only baseline-driven probability variation remains).
- **Individual level: agreement is weak by design.** Pairwise rank Spearman 0.32-0.77 means personalized CATE ordering on observed X is NOT reliable — there is little observed heterogeneity for learners to agree on (`sim_u` dominates). Day-14 uplift must therefore report Qini/persuadable structure honestly at the aggregate level.
- **Agreement is not truth:** like Day 12, learner agreement does not certify the CATE LEVEL. Display (simulated GT 0.00) again: mean CATE ≈ +0.11 pp ≈ its ATE — selection, not treatment.

## Reference vs Day-12 OLS ATE

| Channel | Outcome | Mean CATE (avg of T/S/X) | Day-12 OLS ATE |
|---|---|---|---|
| email | 14-day conversion | 0.1258 | 0.1274 |
| email | 14-day revenue (R$) | 16.9553 | 17.1112 |
| social | 14-day conversion | 0.1065 | 0.1061 |
| social | 14-day revenue (R$) | 16.0855 | 16.1198 |
| search | 14-day conversion | 0.1263 | 0.1283 |
| search | 14-day revenue (R$) | 17.7088 | 18.1239 |
| display | 14-day conversion | 0.1119 | 0.1122 |
| display | 14-day revenue (R$) | 15.8571 | 16.1188 |

## Limitations

- CATE is conditional on OBSERVED X only; `sim_u`-driven heterogeneity is invisible to every learner, so individualized treatment rules built from these curves inherit the ATE bias documented on Days 8-12.
- In-sample CATE (no cross-fitting); overfitting risk is mild here (4 features, depth-3 trees) but formal cross-fit/DML is Day 18.
- S-learner is known to attenuate effects (shrinkage); T-learner has higher variance in low-support regions; X-learner depends on a correct-enough propensity p(X).
- CATE uncertainty is reported for MEAN CATE (bootstrap); the full CATE distribution (personalization) is not uncertainty-calibrated per unit.
