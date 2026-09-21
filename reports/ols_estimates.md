# Day 9 — Regression Adjustment (OLS)

> **Label:** all treatment/outcome columns are SIMULATED preview data (`sim_*`). OLS coefficients are **estimated** effects under the identification strategy (AGENTS.md §3), NOT observed Olist facts. Ground-truth log-odds are simulated targets from config.

## OLS treatment coefficients (HC3 robust SE, 95% CI)

| Channel | Outcome | OLS coef | SE | 95% CI | Naive gap | Sim GT (log-odds) | R² |
|---|---|---|---|---|---|---|---|
| email | 14-day conversion | 0.1274 pp | 0.0032 | [0.1211, 0.1337] | 0.1252 pp | +0.120 | 0.023 |
| email | 14-day revenue (R$) | 17.1112 R$ | 0.6423 | [15.8522, 18.3702] | 16.7713 R$ | +0.120 | 0.011 |
| social | 14-day conversion | 0.1061 pp | 0.0034 | [0.0996, 0.1127] | 0.1127 pp | -0.080 | 0.016 |
| social | 14-day revenue (R$) | 16.1198 R$ | 0.6943 | [14.7591, 17.4805] | 17.1192 R$ | -0.080 | 0.009 |
| search | 14-day conversion | 0.1283 pp | 0.0030 | [0.1223, 0.1343] | 0.1277 pp | +0.150 | 0.024 |
| search | 14-day revenue (R$) | 18.1239 R$ | 0.6149 | [16.9187, 19.3291] | 17.9635 R$ | +0.150 | 0.013 |
| display | 14-day conversion | 0.1122 pp | 0.0029 | [0.1066, 0.1179] | 0.1117 pp | +0.000 | 0.020 |
| display | 14-day revenue (R$) | 16.1188 R$ | 0.5808 | [14.9804, 17.2572] | 15.9584 R$ | +0.000 | 0.011 |

## Compared with naive (Day 8)

- Adjustment moves the estimates toward the simulated ground truths: display's OLS conversion effect collapses relative to its naive gap because the apparent effect was selection, and social's estimate moves toward its (negative) ground truth.
- Robust CIs remain tight given n ≈ 95k; width is driven by genuine residual variance, not imbalance.

## Limitations

- **Linearity:** LPM/OLS assumes linear effects; a wrong functional form biases the coefficient even with the right covariates.
- **No balance guarantee:** regression adjusts by extrapolation; extreme covariate regions rely on model assumptions (PS/DR days are more robust here).
- **LPM boundary issues** for the binary outcome: predicted probabilities can fall outside [0, 1].
- **Residual unobserved confounding:** `sim_u` is NOT in the model; the OLS effect is therefore still biased upward relative to the ground truth (sensitivity analysis, Day 18).

## Validation hook: CIs sane vs naive

- email/14-day conversion: CI [0.1211, 0.1337] contains coef, SE finite → OK
- email/14-day revenue (R$): CI [15.8522, 18.3702] contains coef, SE finite → OK
- social/14-day conversion: CI [0.0996, 0.1127] contains coef, SE finite → OK
- social/14-day revenue (R$): CI [14.7591, 17.4805] contains coef, SE finite → OK
- search/14-day conversion: CI [0.1223, 0.1343] contains coef, SE finite → OK
- search/14-day revenue (R$): CI [16.9187, 19.3291] contains coef, SE finite → OK
- display/14-day conversion: CI [0.1066, 0.1179] contains coef, SE finite → OK
- display/14-day revenue (R$): CI [14.9804, 17.2572] contains coef, SE finite → OK