# Day 12 — ATE/ATT Synthesis

> **Label:** all results are **estimated (simulated)** numbers (`sim_*`), never observed Olist facts (AGENTS.md §2). Every row reports point / SE / 95% CI / N / estimator / assumptions.

## Why one master table

- Days 8-11 produced one ATE family per channel (naive, OLS, IPW, DR). Day 7 produced a matched sample from which the **ATT** is read directly. Day 12 adds an independent **DoWhy backdoor** estimate (DoWhy 0.8 `identify_effect` + `estimate_effect`), so the final table lets any two estimators be compared in one place.
- ATE vs ATT: the ATE answers "expose anyone"; the ATT answers "effect on the exposed", i.e. the incremental impact of the current targeting policy. They coincide under constant treatment effects.

## Master estimate table

| Channel | Outcome | Estimator | Point | SE | 95% CI | N | Assumptions |
|---|---|---|---|---|---|---|---|
| email | 14-day conversion | Naive (Day 8) | 0.1252 pp | 0.0031 | [0.1191, 0.1313] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| email | 14-day conversion | OLS (Day 9) | 0.1274 pp | 0.0032 | [0.1211, 0.1337] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| email | 14-day conversion | IPW (Day 10) | 0.1287 pp | 0.0033 | [0.1218, 0.1350] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| email | 14-day conversion | DR / AIPW (Day 11) | 0.1287 pp | 0.0033 | [0.1222, 0.1352] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| email | 14-day conversion | ATT matched (Day 7) | 0.1291 pp | 0.0036 | [0.1222, 0.1361] | 28,118 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| email | 14-day conversion | DoWhy backdoor (Day 12) | 0.1274 pp | 0.0032 | [0.1211, 0.1337] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |
| email | 14-day revenue (R$) | Naive (Day 8) | 16.7713 R$ | 0.6237 | [15.5488, 17.9938] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| email | 14-day revenue (R$) | OLS (Day 9) | 17.1112 R$ | 0.6423 | [15.8522, 18.3702] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| email | 14-day revenue (R$) | IPW (Day 10) | 17.3646 R$ | 0.6808 | [15.9986, 18.6625] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| email | 14-day revenue (R$) | DR / AIPW (Day 11) | 17.3647 R$ | 0.6743 | [16.0430, 18.6864] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| email | 14-day revenue (R$) | ATT matched (Day 7) | 17.4801 R$ | 0.7001 | [16.1080, 18.8522] | 28,118 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| email | 14-day revenue (R$) | DoWhy backdoor (Day 12) | 17.1112 R$ | 0.6423 | [15.8522, 18.3702] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |
| social | 14-day conversion | Naive (Day 8) | 0.1127 pp | 0.0033 | [0.1063, 0.1191] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| social | 14-day conversion | OLS (Day 9) | 0.1061 pp | 0.0034 | [0.0996, 0.1127] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| social | 14-day conversion | IPW (Day 10) | 0.1061 pp | 0.0034 | [0.0990, 0.1122] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| social | 14-day conversion | DR / AIPW (Day 11) | 0.1061 pp | 0.0034 | [0.0994, 0.1127] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| social | 14-day conversion | ATT matched (Day 7) | 0.1086 pp | 0.0039 | [0.1010, 0.1162] | 24,382 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| social | 14-day conversion | DoWhy backdoor (Day 12) | 0.1061 pp | 0.0034 | [0.0996, 0.1127] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |
| social | 14-day revenue (R$) | Naive (Day 8) | 17.1192 R$ | 0.6765 | [15.7932, 18.4451] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| social | 14-day revenue (R$) | OLS (Day 9) | 16.1198 R$ | 0.6943 | [14.7591, 17.4805] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| social | 14-day revenue (R$) | IPW (Day 10) | 16.1041 R$ | 0.7376 | [14.6249, 17.5314] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| social | 14-day revenue (R$) | DR / AIPW (Day 11) | 16.0945 R$ | 0.6970 | [14.7285, 17.4606] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| social | 14-day revenue (R$) | ATT matched (Day 7) | 16.4982 R$ | 0.7902 | [14.9494, 18.0469] | 24,382 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| social | 14-day revenue (R$) | DoWhy backdoor (Day 12) | 16.1198 R$ | 0.6943 | [14.7591, 17.4805] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |
| search | 14-day conversion | Naive (Day 8) | 0.1277 pp | 0.0030 | [0.1218, 0.1335] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| search | 14-day conversion | OLS (Day 9) | 0.1283 pp | 0.0030 | [0.1223, 0.1343] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| search | 14-day conversion | IPW (Day 10) | 0.1288 pp | 0.0030 | [0.1231, 0.1349] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| search | 14-day conversion | DR / AIPW (Day 11) | 0.1286 pp | 0.0031 | [0.1226, 0.1347] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| search | 14-day conversion | ATT matched (Day 7) | 0.1268 pp | 0.0034 | [0.1202, 0.1334] | 31,349 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| search | 14-day conversion | DoWhy backdoor (Day 12) | 0.1283 pp | 0.0030 | [0.1223, 0.1343] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |
| search | 14-day revenue (R$) | Naive (Day 8) | 17.9635 R$ | 0.6031 | [16.7815, 19.1455] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| search | 14-day revenue (R$) | OLS (Day 9) | 18.1239 R$ | 0.6149 | [16.9187, 19.3291] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| search | 14-day revenue (R$) | IPW (Day 10) | 18.2047 R$ | 0.6259 | [16.9147, 19.3264] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| search | 14-day revenue (R$) | DR / AIPW (Day 11) | 18.1850 R$ | 0.6305 | [16.9492, 19.4209] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| search | 14-day revenue (R$) | ATT matched (Day 7) | 17.5785 R$ | 0.6733 | [16.2588, 18.8982] | 31,349 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| search | 14-day revenue (R$) | DoWhy backdoor (Day 12) | 18.1239 R$ | 0.6149 | [16.9187, 19.3291] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |
| display | 14-day conversion | Naive (Day 8) | 0.1117 pp | 0.0029 | [0.1061, 0.1173] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| display | 14-day conversion | OLS (Day 9) | 0.1122 pp | 0.0029 | [0.1066, 0.1179] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| display | 14-day conversion | IPW (Day 10) | 0.1125 pp | 0.0029 | [0.1064, 0.1177] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| display | 14-day conversion | DR / AIPW (Day 11) | 0.1124 pp | 0.0029 | [0.1068, 0.1181] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| display | 14-day conversion | ATT matched (Day 7) | 0.1136 pp | 0.0031 | [0.1074, 0.1197] | 35,285 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| display | 14-day conversion | DoWhy backdoor (Day 12) | 0.1122 pp | 0.0029 | [0.1066, 0.1179] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |
| display | 14-day revenue (R$) | Naive (Day 8) | 15.9584 R$ | 0.5760 | [14.8295, 17.0873] | 94,983 | No adjustment; diff-in-means = effect + targeting/sim_u selection |
| display | 14-day revenue (R$) | OLS (Day 9) | 16.1188 R$ | 0.5808 | [14.9804, 17.2572] | 94,983 | Linear, HC3 SE; adjustment on observed set only; sim_u unadjusted |
| display | 14-day revenue (R$) | IPW (Day 10) | 16.1685 R$ | 0.5760 | [14.9196, 17.1267] | 94,983 | PS correct + positivity; overlap/sim_u limits (weights capped at cfg cap) |
| display | 14-day revenue (R$) | DR / AIPW (Day 11) | 16.1655 R$ | 0.5875 | [15.0141, 17.3170] | 94,983 | PS or outcome model correct; PS clipped per Day-10 cap; sim_u unadjusted |
| display | 14-day revenue (R$) | ATT matched (Day 7) | 16.3137 R$ | 0.6415 | [15.0563, 17.5711] | 35,285 | 1:1 NN caliper match on observed PS; ATT parameter; sim_u unadjusted |
| display | 14-day revenue (R$) | DoWhy backdoor (Day 12) | 16.1188 R$ | 0.5808 | [14.9804, 17.2572] | 94,983 | DoWhy identify + backdoor.linear_regression; SE identical to OLS (same model) |

## Estimator convergence story (validation hook)

- **Expected result, verified:** all estimators converge to the naive gap per channel (e.g. email conversion naive +0.1252, OLS +0.1274, IPW +0.1287, DR +0.1287). The simulated design makes this both the *expected* and the *honest* outcome: `sim_u` (latent intent, U->assignment 0.8, U->outcome 1.0) dominates the DGP, so conditioning on the observed confounders has little additional signal to absorb once the targeting rule is accounted for.
- **Convergence is not correctness:** agreement across estimators here means the residual bias comes from an UNOBSERVED structure common to every estimator, not that the models agree on the truth. Display (sim GT 0.00) is the cleanest illustration: every estimator lands near +0.11 to +0.13 while the simulated ground truth is 0 — pure `sim_u` selection.

Convergence table (conversion: absolute tol; revenue: relative tol):

| Channel | Outcome | Min | Max | Range | Criterion | Tolerance | Status |
|---|---|---|---|---|---|---|---|
| email | 14-day conversion | 0.1252 | 0.1287 | 0.0034 | absolute | 0.0200 | OK |
| email | 14-day revenue (R$) | 16.7713 | 17.3647 | 0.5934 | relative | 1.7153 | OK |
| social | 14-day conversion | 0.1061 | 0.1127 | 0.0067 | absolute | 0.0200 | OK |
| social | 14-day revenue (R$) | 16.0945 | 17.1192 | 1.0246 | relative | 1.6359 | OK |
| search | 14-day conversion | 0.1277 | 0.1288 | 0.0011 | absolute | 0.0200 | OK |
| search | 14-day revenue (R$) | 17.9635 | 18.2047 | 0.2412 | relative | 1.8119 | OK |
| display | 14-day conversion | 0.1117 | 0.1125 | 0.0008 | absolute | 0.0200 | OK |
| display | 14-day revenue (R$) | 15.9584 | 16.1685 | 0.2101 | relative | 1.6103 | OK |

## DoWhy backdoor cross-check

- DoWhy 0.8 (Day 5 DAG stack, classic API) identifies the same backdoor set mechanically and estimates it with `backdoor.linear_regression` — an independent implementation of the Day-9 OLS model. Values must coincide (same model), which validates the DoWhy pipeline end-to-end on this data.

- email/14-day conversion: DoWhy 0.1274 vs OLS 0.1274 (Δ=5.30e-15) — simulated GT +0.120 log-odds.
- email/14-day revenue (R$): DoWhy 17.1112 vs OLS 17.1112 (Δ=7.07e-13) — simulated GT +0.120 log-odds.
- social/14-day conversion: DoWhy 0.1061 vs OLS 0.1061 (Δ=6.01e-15) — simulated GT -0.080 log-odds.
- social/14-day revenue (R$): DoWhy 16.1198 vs OLS 16.1198 (Δ=9.13e-13) — simulated GT -0.080 log-odds.
- search/14-day conversion: DoWhy 0.1283 vs OLS 0.1283 (Δ=1.03e-15) — simulated GT +0.150 log-odds.
- search/14-day revenue (R$): DoWhy 18.1239 vs OLS 18.1239 (Δ=1.35e-13) — simulated GT +0.150 log-odds.
- display/14-day conversion: DoWhy 0.1122 vs OLS 0.1122 (Δ=2.78e-17) — simulated GT +0.000 log-odds.
- display/14-day revenue (R$): DoWhy 16.1188 vs OLS 16.1188 (Δ=0.00e+00) — simulated GT +0.000 log-odds.
- **compat note:** DoWhy 0.8 needed two idempotent shims for the modern stack (see module docstring): `nx.algorithms.d_separated` aliased to `is_d_separator`, and `model.params[0]` exposed as an ndarray for pandas>=2. Both are applied inside `src/causal/synthesis.py` and exercised by tests.

## Limitations

- Every estimator conditions on the OBSERVED set; `sim_u`-driven selection remains, so ATE/ATT are all biased toward the naive gap. Sensitivity analysis (E-value / bias formulas) is Day 18.
- ATT on the matched sample reuses 1:1 NN with caliper (Day 7); the matched-pair SE is two-sample (not accounting for the re-use of controls).
- DoWhy cross-check shares the OLS misspecification surface (linearity, binary outcome as LPM) and its SE/CI are reported from the same OLS fit.
- Email weak overlap (71 units PS≈1.0) is handled via weight/PS truncation in IPW/DR only; matched and DoWhy rows inherit the design caveat.
