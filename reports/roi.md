# Day 16 — Incremental ROI

> **Labels:** observational + causal numbers are **estimated (simulated)** (see each row's label); the **counterfactual** column is the true per-treated revenue effect from the known DGP — simulation-only, unachievable on observed data (AGENTS.md §2/§3). Rows carry machine-readable labels: `estimated (simulated) - naive diff-in-means revenue ATE`, `estimated (simulated) - Day-12 DR revenue ATE`, and `counterfactual (simulated ground truth) - DGP oracle`. Channel costs are **config assumptions** (ADR-006; Olist has no spend data), per-treated-customer R$ over the 14-day outcome window.

## Definition

- `ROI = (incremental revenue per treated − cost per treated) / cost per treated` (blueprint §9). ROI = 0 is breakeven; ROI = 1 means the R$ doubles on spend.
- **observational** — Day-8 naive diff-in-means (last-touch-style attribution). **causal** — Day-12 doubly robust (DR) revenue ATE, CI propagated through the monotone ROI transform. **counterfactual** — true effect from the DGP (oracle).
- Per-treated units: see n_treated; contrast the treatment share vs 50/50 random assignment (Day 3 preview). Ongoing identification: exchangeability given X, **sim_u unobserved** — every estimate since Day 8 inherits this.

## ROI per channel (R$ per R$ 1 invested)

| Channel | Cost/treated | Treated | Observational | Causal (95% CI) | Counterfactual | Causal ÷ truth | Cohort net truth (R$) |
|---|---|---|---|---|---|---|---|
| email | R$ 0.10 | 28,380 | 16671% | 17265% [15943%, 18586%] | 2314% | 7.5x | R$ 65,673 |
| social | R$ 0.80 | 24,707 | 2040% | 1912% [1741%, 2083%] | -297% | — | R$ -58,661 |
| search | R$ 1.50 | 31,678 | 1098% | 1112% [1030%, 1195%] | 101% | 11.0x | R$ 48,167 |
| display | R$ 0.20 | 35,470 | 7879% | 7983% [7407%, 8558%] | -100% | — | R$ -7,094 |

## Key finding — even the *causal* ROI overstates every channel here

On this simulation the Day-12 estimators converge to ≈ +16–18 R$ incremental revenue per treated for **every** channel (display +16.2, social +16.1) — the shared `sim_u` bias carried into money terms. Consequently the causal ROI is positive everywhere (email 17,265%, search 1,112%, display 7,983%, social 1,912%) and, surprisingly, barely improves on the naive attribution ROI — both are confounded. The **counterfactual** column reveals the truth: email is genuinely excellent (2,314%), search is modestly positive (101%), while **social (−299%) and display (−100%) destroy value** — any spend there loses money. `Causal ÷ truth` quantifies the overstatement: **~7.5x email, ~11x search**, sign-flipped for social/display.

- **Breakeven reads:** email/search break even at any cost below their true incremental revenue (email R$ 2.41, search R$ 3.02 per treated); social/display never do (true effect negative/zero) — no cost assumption can rescue them.
- **Budget implication (pre-Day-17):** on observed data alone you would fund display and social; the counterfactual says the opposite. Day 17 turns this into explicit counterfactual scenarios; Day 18 bounds how strong `sim_u` must be to produce these estimates.

## Validation hooks — gates

| Gate | Scope | Value | Threshold | Pass |
|---|---|---|---|---|
| complete_rows | all channels | 12.0000 | 12.0000 | ✅ |
| causal_roi_positive | all channels | 11.1234 | 0.0000 | ✅ |
| ctf_email_search_positive | email/search | 1.0137 | 0.0000 | ✅ |
| ctf_social_display_negative | social/display | -1.0000 | 0.0000 | ✅ |
| overstatement_documented | email/search | 7.4610 | 1.0000 | ✅ |
| uncertainty_reported | all rows | 1.0000 | 1.0000 | ✅ |

## Limitations

- Costs are assumptions (ADR-006), flat per treated customer, no marginal-cost curve, no frequency effects — ROI = f(cost) is a single point, not a curve.
- Counterfactual ROI uses `sim_u`; it is the achievable truth on this DGP only.
- 14-day window: revenue accruing beyond the window is excluded by construction.
- Causal ROI collapses to the confounded Day-12 story: all estimators agree because all share the same unobserved `sim_u` bias (see Day 12 report).
