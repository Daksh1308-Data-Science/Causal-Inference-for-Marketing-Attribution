# Day 15 — CATE Segmentation & Targeting Guidance

> **Labels:** band statistics are **estimated (simulated)**; `oracle_*` columns and the guidance sign structure are **counterfactual (simulated ground truth)** — they use `sim_u` and are unachievable on observed data (AGENTS.md §2/§3).

## Identification (before evaluation)

- **Causal question:** per channel, is the incremental effect positive / negative / zero for the audience, and how much of the true (counterfactual) effect does ranking by the Day-13 CATE actually concentrate?
- **Segments = quintile bands of the ensemble CATE** (mean of T/S/X, Day 13) per channel × outcome; same identification as Day 13 (exchangeability given X; **sim_u unobserved**). Counterfactual oracle = true per-unit effect from the known DGP.
- **Why band means, not per-customer ranks:** Day 13 showed individual CATE ranks agree only 0.32–0.77 Spearman *across learners*; Day 15 adds the harsher check — ensemble CATE vs the *true* effect — and finds ρ ≈ +0.01…+0.06 (essentially noise). Targeting guidance is therefore per-*channel*, never per-customer.

## Target-segment table — 14-day conversion

| Channel | Band | Share | n | τ̂ ± CI (est) | Oracle mean (counterfactual) | Oracle negative share | Conv rate |
|---|---|---|---|---|---|---|---|
| email | bottom | 20.0% | 18,997 | +0.1156 [+0.1156, +0.1157] | +0.0174 | 0% | 21.7% |
| email | mid-low | 20.0% | 18,996 | +0.1210 [+0.1210, +0.1211] | +0.0172 | 0% | 20.8% |
| email | mid | 20.0% | 18,997 | +0.1240 [+0.1240, +0.1240] | +0.0173 | 0% | 20.5% |
| email | mid-high | 20.0% | 18,996 | +0.1275 [+0.1275, +0.1275] | +0.0176 | 0% | 21.2% |
| email | top | 20.0% | 18,997 | +0.1407 [+0.1405, +0.1409] | +0.0187 | 0% | 24.1% |
| email | all | 100.0% | 94,983 | +0.1258 [+0.1257, +0.1258] | +0.0176 | 0% | 21.7% |

| social | bottom | 20.0% | 18,997 | +0.0990 [+0.0989, +0.0991] | -0.0117 | 100% | 22.6% |
| social | mid-low | 20.0% | 18,996 | +0.1036 [+0.1035, +0.1036] | -0.0114 | 100% | 22.0% |
| social | mid | 20.0% | 18,997 | +0.1055 [+0.1055, +0.1055] | -0.0113 | 100% | 20.9% |
| social | mid-high | 20.0% | 18,996 | +0.1074 [+0.1074, +0.1074] | -0.0111 | 100% | 20.0% |
| social | top | 20.0% | 18,997 | +0.1170 [+0.1168, +0.1171] | -0.0120 | 100% | 22.9% |
| social | all | 100.0% | 94,983 | +0.1065 [+0.1064, +0.1065] | -0.0115 | 100% | 21.7% |

| search | bottom | 20.0% | 18,997 | +0.1087 [+0.1085, +0.1088] | +0.0215 | 0% | 19.5% |
| search | mid-low | 20.0% | 18,997 | +0.1192 [+0.1192, +0.1193] | +0.0214 | 0% | 20.9% |
| search | mid | 20.0% | 18,996 | +0.1253 [+0.1253, +0.1254] | +0.0218 | 0% | 21.3% |
| search | mid-high | 20.0% | 18,996 | +0.1317 [+0.1317, +0.1318] | +0.0223 | 0% | 21.8% |
| search | top | 20.0% | 18,997 | +0.1464 [+0.1461, +0.1466] | +0.0232 | 0% | 24.7% |
| search | all | 100.0% | 94,983 | +0.1263 [+0.1262, +0.1264] | +0.0220 | 0% | 21.7% |

| display | bottom | 20.0% | 18,997 | +0.0992 [+0.0991, +0.0993] | +0.0000 | 0% | 21.7% |
| display | mid-low | 20.0% | 18,996 | +0.1065 [+0.1064, +0.1065] | +0.0000 | 0% | 21.4% |
| display | mid | 20.0% | 18,997 | +0.1110 [+0.1110, +0.1110] | +0.0000 | 0% | 21.4% |
| display | mid-high | 20.0% | 18,996 | +0.1156 [+0.1156, +0.1157] | +0.0000 | 0% | 21.3% |
| display | top | 20.0% | 18,997 | +0.1272 [+0.1270, +0.1273] | +0.0000 | 0% | 22.5% |
| display | all | 100.0% | 94,983 | +0.1119 [+0.1118, +0.1120] | +0.0000 | 0% | 21.7% |

## Target-segment table — 14-day revenue (R$)

| Channel | Band | Share | n | τ̂ ± CI (est) | Oracle mean (counterfactual) | Oracle negative share | Conv rate |
|---|---|---|---|---|---|---|---|
| email | bottom | 20.0% | 18,997 | +14.30 [+14.29, +14.32] | +2.43 | 0% | R$ 31.08 |
| email | mid-low | 20.0% | 18,996 | +15.69 [+15.69, +15.70] | +2.41 | 0% | R$ 29.66 |
| email | mid | 20.0% | 18,997 | +16.51 [+16.51, +16.51] | +2.38 | 0% | R$ 28.35 |
| email | mid-high | 20.0% | 18,996 | +17.35 [+17.34, +17.35] | +2.37 | 0% | R$ 26.85 |
| email | top | 20.0% | 18,997 | +20.92 [+20.86, +20.99] | +2.48 | 0% | R$ 32.08 |
| email | all | 100.0% | 94,983 | +16.96 [+16.94, +16.98] | +2.41 | 0% | R$ 29.61 |

| social | bottom | 20.0% | 18,997 | +13.84 [+13.83, +13.85] | -1.59 | 100% | R$ 33.40 |
| social | mid-low | 20.0% | 18,996 | +15.10 [+15.10, +15.10] | -1.57 | 100% | R$ 29.49 |
| social | mid | 20.0% | 18,997 | +15.75 [+15.75, +15.75] | -1.53 | 100% | R$ 26.84 |
| social | mid-high | 20.0% | 18,996 | +16.54 [+16.54, +16.55] | -1.59 | 100% | R$ 29.10 |
| social | top | 20.0% | 18,997 | +19.19 [+19.14, +19.24] | -1.59 | 100% | R$ 29.19 |
| social | all | 100.0% | 94,983 | +16.09 [+16.07, +16.10] | -1.57 | 100% | R$ 29.61 |

| search | bottom | 20.0% | 18,997 | +15.15 [+15.13, +15.17] | +2.99 | 0% | R$ 29.28 |
| search | mid-low | 20.0% | 18,996 | +16.85 [+16.85, +16.86] | +2.98 | 0% | R$ 28.64 |
| search | mid | 20.0% | 18,997 | +17.62 [+17.62, +17.62] | +3.02 | 0% | R$ 29.64 |
| search | mid-high | 20.0% | 18,996 | +18.36 [+18.36, +18.36] | +3.02 | 0% | R$ 28.40 |
| search | top | 20.0% | 18,997 | +20.56 [+20.51, +20.61] | +3.09 | 0% | R$ 32.06 |
| search | all | 100.0% | 94,983 | +17.71 [+17.69, +17.73] | +3.02 | 0% | R$ 29.61 |

| display | bottom | 20.0% | 18,997 | +13.56 [+13.55, +13.58] | +0.00 | 0% | R$ 29.93 |
| display | mid-low | 20.0% | 18,996 | +15.00 [+15.00, +15.01] | +0.00 | 0% | R$ 28.01 |
| display | mid | 20.0% | 18,997 | +15.68 [+15.68, +15.68] | +0.00 | 0% | R$ 28.19 |
| display | mid-high | 20.0% | 18,996 | +16.41 [+16.41, +16.41] | +0.00 | 0% | R$ 29.30 |
| display | top | 20.0% | 18,997 | +18.63 [+18.60, +18.66] | +0.00 | 0% | R$ 32.59 |
| display | all | 100.0% | 94,983 | +15.86 [+15.84, +15.87] | +0.00 | 0% | R$ 29.61 |

## Targeting guidance — per channel (from the counterfactual sign structure)

| Channel | Est. CATE (conv, 95% CI) | Oracle mean | ρ(τ̂, oracle) | Top−bottom gap (pp) | True sign | Recommendation |
|---|---|---|---|---|---|---|
| email | +0.1258 [+0.1257, +0.1258] | +0.0176 | +0.053 | +0.13 | + | Run — counterfactual effect is positive for the whole audience; per-X micro-targeting adds little (band gradient +0.13 pp, ρ +0.05). Allocate broadly on channel size and monitor the channel-level ATE. |
| social | +0.1065 [+0.1064, +0.1065] | -0.0115 | -0.010 | -0.03 | − | Skip / avoid — counterfactual effect is negative for ~100% of the audience (mean -0.0115); the estimated positive CATE is shared `sim_u` bias, not causal signal. Reallocate budget to the positive channels. |
| search | +0.1263 [+0.1262, +0.1264] | +0.0220 | +0.061 | +0.17 | + | Run — counterfactual effect is positive for the whole audience; per-X micro-targeting adds little (band gradient +0.17 pp, ρ +0.06). Allocate broadly on channel size and monitor the channel-level ATE. |
| display | +0.1119 [+0.1118, +0.1120] | +0.0000 | n/a (constant oracle) | +0.00 | 0 | No budget — counterfactual effect is exactly 0 everywhere (embedded coefficient 0.00); any positive estimate is shared `sim_u` bias. Demonstrated by display's ~0 oracle vs a positive estimate. |

## Key finding — the estimated sign structure is wrong; the counterfactual one explains the pattern

Every channel's estimated CATE is **positive in every band** (email 0.126, search 0.126, social 0.107, display 0.112 mean conversion CATE; 0% negative units) — including social, whose true effect is negative, and display, whose true effect is exactly 0. This is the shared `sim_u` bias carried by every estimator since Day 8; a real analyst looking only at observed data would wrongly conclude *all* channels help. The **counterfactual** sign structure matches the DGP exactly: email/search positive for every unit, social negative for every unit, display exactly zero. **The segments explain the pattern only when the oracle (sim_u) is used; the observed-data ranking cannot recover even the sign.**

- **Rank gradient (measured, not assumed):** ρ(ensemble CATE, true effect) ≈ +0.05/+0.06 conversion for email/search, ≈0 for display, slightly negative for social. The top band's true effect beats the bottom's by only +0.13/+0.17 pp (email/search) — real but tiny; social's gradient is flat-to-inverted (harm-avoidance is unreachable on observed X).
- **Why so weak:** the effect is constant in log-odds and ~90% `sim_u`-driven, so the probability-scale ΔP is a narrow bump that observed X (which predicts sim_u only weakly) can barely track. Day 18 quantifies how strong the unobserved confounder must be to explain the ATE itself.

## Validation hooks

- Gate **estimated_signal_all_positive**: every channel's min band estimated CATE > 0.05 (bias demonstration — min observed 0.099).
- Gate **gt_channels_positive_oracle**: email/search band oracle means all > 0.005 (positive effect throughout).
- Gate **social_negative_oracle**: social band oracle means all < -0.005 (negative effect throughout).
- Gate **display_zero_oracle**: |display band oracle means| ≤ 1e-6 (effect exactly 0).
- Gate **rank_gradient_positive_gt**: email/search top−bottom oracle gap > 0.0001 (real, tiny gradient).

### Gate results

| Gate | Scope | Value | Threshold | Pass |
|---|---|---|---|---|
| gt_channels_positive_oracle | email/search (conversion) | 0.0172 | 0.0050 | ✅ |
| social_negative_oracle | social (conversion) | -0.0111 | -0.0050 | ✅ |
| display_zero_oracle | display (conversion) | 0.0000 | 0.0000 | ✅ |
| estimated_signal_all_positive | all channels (conversion) | 0.0990 | 0.0500 | ✅ |
| rank_gradient_positive_gt | email/search (conversion) | 0.0013 | 0.0001 | ✅ |
| uncertainty_reported | all band rows | 1.0000 | 1.0000 | ✅ |

## Limitations

- Band means are estimates on observed X (sim_u unobserved); their *ordering* within a channel is a weak (but real) signal only for email/search.
- Rate-based 'conv rate' is observed/simulated, not incremental; incremental effects are the τ̂/oracle columns.
- Counterfactual oracle numbers use `sim_u`; they define the achievable sign structure on this DGP but are never reachable from observed data.
