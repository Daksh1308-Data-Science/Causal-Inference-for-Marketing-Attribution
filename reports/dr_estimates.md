# Day 11 — Doubly Robust Estimation (AIPW)

> **Label:** SIMULATED estimates (`sim_*`), not observed Olist facts (AGENTS.md §2).

## Why double robustness

- AIPW blends the Day-6 propensity score with outcome regressions Mu1(X), Mu0(X): each unit contributes `T(Y-Mu1)/p + Mu1` (treated arm) and `(1-T)(Y-Mu0)/(1-p) + Mu0` (control arm).
- **Doubly robust:** the estimate is consistent if *either* the PS model *or* the outcome model is correct. If the PS is right, the augmented term fixes a misspecified outcome regression; if the outcome model is right, the regression-imputation part dominates and a wrong PS is corrected.
- **Efficiency:** AIPW achieves the semiparametric efficiency bound when both models hold — tighter CIs than plain IPW or OLS for the same data.

## AIPW table (influence-function SE, 95% CI)

| Channel | Outcome | DR ATE | SE | 95% CI | IPW | OLS | Naive | Sim GT |
|---|---|---|---|---|---|---|---|---|
| email | 14-day conversion | 0.1287 pp | 0.0033 | [0.1222, 0.1352] | 0.1287 pp | 0.1274 pp | 0.1252 pp | +0.120 |
| email | 14-day revenue (R$) | 17.3647 R$ | 0.6743 | [16.0430, 18.6864] | 17.3646 R$ | 17.1112 R$ | 16.7713 R$ | +0.120 |
| social | 14-day conversion | 0.1061 pp | 0.0034 | [0.0994, 0.1127] | 0.1061 pp | 0.1061 pp | 0.1127 pp | -0.080 |
| social | 14-day revenue (R$) | 16.0945 R$ | 0.6970 | [14.7285, 17.4606] | 16.1041 R$ | 16.1198 R$ | 17.1192 R$ | -0.080 |
| search | 14-day conversion | 0.1286 pp | 0.0031 | [0.1226, 0.1347] | 0.1288 pp | 0.1283 pp | 0.1277 pp | +0.150 |
| search | 14-day revenue (R$) | 18.1850 R$ | 0.6305 | [16.9492, 19.4209] | 18.2047 R$ | 18.1239 R$ | 17.9635 R$ | +0.150 |
| display | 14-day conversion | 0.1124 pp | 0.0029 | [0.1068, 0.1181] | 0.1125 pp | 0.1122 pp | 0.1117 pp | +0.000 |
| display | 14-day revenue (R$) | 16.1655 R$ | 0.5875 | [15.0141, 17.3170] | 16.1685 R$ | 16.1188 R$ | 15.9584 R$ | +0.000 |

## Validation hook: consistent vs OLS/IPW

Criteria match tests/test_doubly_robust.py: conversion checked on absolute scale (|DR-IPW|<0.01, |DR-OLS|<0.02), revenue on relative scale (<10%).

- email/14-day conversion: |DR−IPW|=0.0000 (< 0.0100 abs) |DR−OLS|=0.0013 (< 0.0200 abs) → OK
- email/14-day revenue (R$): |DR−IPW|=0.0001 (< 1.7365 rel) |DR−OLS|=0.2535 (< 1.7111 rel) → OK
- social/14-day conversion: |DR−IPW|=0.0001 (< 0.0100 abs) |DR−OLS|=0.0001 (< 0.0200 abs) → OK
- social/14-day revenue (R$): |DR−IPW|=0.0096 (< 1.6104 rel) |DR−OLS|=0.0253 (< 1.6120 rel) → OK
- search/14-day conversion: |DR−IPW|=0.0001 (< 0.0100 abs) |DR−OLS|=0.0004 (< 0.0200 abs) → OK
- search/14-day revenue (R$): |DR−IPW|=0.0197 (< 1.8205 rel) |DR−OLS|=0.0611 (< 1.8124 rel) → OK
- display/14-day conversion: |DR−IPW|=0.0000 (< 0.0100 abs) |DR−OLS|=0.0002 (< 0.0200 abs) → OK
- display/14-day revenue (R$): |DR−IPW|=0.0030 (< 1.6169 rel) |DR−OLS|=0.0467 (< 1.6119 rel) → OK

## Limitations

- Both models are fit on the OBSERVED confounders only: `sim_u` remains unadjusted, so AIPW cannot outrun the design — it should track OLS/IPW rather than reach the simulated ground truth.
- Outcome regressions are linear/logistic; deeper misspecification is possible (CATE learners, Day 13, use flexible trees instead).
- IF-based SE is asymptotic; n ≈ 95k makes it reliable, but it does not cover PS-outcome-model selection uncertainty.
