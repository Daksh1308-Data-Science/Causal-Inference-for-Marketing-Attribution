# Day 8 — Naive Estimates (why they are not causal)

> **Label:** all treatment/outcome columns are SIMULATED preview data (`sim_*`). Naive differences are **observed (simulated)** comparisons, NOT causal effects (AGENTS.md §2). Causal claims start at Day 9.

## Difference-in-means (exposed − unexposed)

| Channel | Outcome | Diff | SE | 95% CI | Exposed n | Unexposed n |
|---|---|---|---|---|---|---|
| email | 14-day conversion | 0.1252 pp | 0.0031 | [0.1191, 0.1313] | 28380 | 66603 |
| email | 14-day revenue (R$) | 16.7713 R$ | 0.6237 | [15.5488, 17.9938] | 28380 | 66603 |
| social | 14-day conversion | 0.1127 pp | 0.0033 | [0.1063, 0.1191] | 24707 | 70276 |
| social | 14-day revenue (R$) | 17.1192 R$ | 0.6765 | [15.7932, 18.4451] | 24707 | 70276 |
| search | 14-day conversion | 0.1277 pp | 0.0030 | [0.1218, 0.1335] | 31678 | 63305 |
| search | 14-day revenue (R$) | 17.9635 R$ | 0.6031 | [16.7815, 19.1455] | 31678 | 63305 |
| display | 14-day conversion | 0.1117 pp | 0.0029 | [0.1061, 0.1173] | 35470 | 59513 |
| display | 14-day revenue (R$) | 15.9584 R$ | 0.5760 | [14.8295, 17.0873] | 35470 | 59513 |

## Why these are NOT causal estimates

### Channel: email

- **Simulated ground-truth effect (log-odds, config): +0.12** — this is a SIMULATED target, not an observed fact (AGENTS.md §2).
- **Why the naive difference ≠ this effect:** exposure is targeted on recency_days (-0.40), total_revenue (+0.50), order_count (+0.30), review_score_avg (+0.10) plus the latent intent `sim_u` (unobserved). Every one of those features also raises baseline purchase intent, so exposed customers would have converted more even without marketing.
- The naive difference = causal effect + selection bias. It cannot separate the two without adjustment (Days 9–12).
- Design narrative from config: *reactivation works*.


### Channel: social

- **Simulated ground-truth effect (log-odds, config): -0.08** — this is a SIMULATED target, not an observed fact (AGENTS.md §2).
- **Why the naive difference ≠ this effect:** exposure is targeted on order_count (+0.50), total_revenue (+0.30), tenure_days (+0.20) plus the latent intent `sim_u` (unobserved). Every one of those features also raises baseline purchase intent, so exposed customers would have converted more even without marketing.
- The naive difference = causal effect + selection bias. It cannot separate the two without adjustment (Days 9–12).
- Design narrative from config: *sleeping dogs*.


### Channel: search

- **Simulated ground-truth effect (log-odds, config): +0.15** — this is a SIMULATED target, not an observed fact (AGENTS.md §2).
- **Why the naive difference ≠ this effect:** exposure is targeted on tenure_days (-0.30), order_count (+0.40), total_revenue (+0.30) plus the latent intent `sim_u` (unobserved). Every one of those features also raises baseline purchase intent, so exposed customers would have converted more even without marketing.
- The naive difference = causal effect + selection bias. It cannot separate the two without adjustment (Days 9–12).
- Design narrative from config: *captures demand*.


### Channel: display

- **Simulated ground-truth effect (log-odds, config): +0.00** — this is a SIMULATED target, not an observed fact (AGENTS.md §2).
- **Why the naive difference ≠ this effect:** exposure is targeted on recency_days (-0.20), total_revenue (+0.20) plus the latent intent `sim_u` (unobserved). Every one of those features also raises baseline purchase intent, so exposed customers would have converted more even without marketing.
- The naive difference = causal effect + selection bias. It cannot separate the two without adjustment (Days 9–12).
- Design narrative from config: *apparent effect is pure confounding*.


## Validation hook: direction documented

- All four channels show a **positive naive gap** for both outcomes (treated convert/spend more in raw comparison).
- The naive gap is dominated by **selection**: display's simulated ground truth is 0.00, yet its naive conversion gap is large — the signature of confounding, not marketing.
