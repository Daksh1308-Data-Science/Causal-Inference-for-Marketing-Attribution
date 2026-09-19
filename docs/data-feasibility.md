# Data Feasibility Assessment — Brazilian E-Commerce (Olist)

Per `Plan.md` §3: *"Do NOT fabricate treatment variables and pretend they are real."*

## 1. Verdict

> **Olist alone cannot support causal marketing attribution.** It contains no marketing treatment/exposure information (no campaigns, ad impressions, clicks, touchpoints, or spend). Therefore we build a **clearly-labeled simulated marketing layer** on top of the real Olist customer/order data, and the pipeline is validated against the simulation's known ground truth. Simulated variables are always prefixed `sim_`.

## 2. What Olist provides (real observations)

| Table | Key fields | Use in this project |
|---|---|---|
| customers | customer_id, customer_unique_id, zip, city, state | identity, geography |
| orders | order_id, customer_id, status, purchase/approved/delivered timestamps | outcome window, time features |
| order_items | order_id, product_id, seller_id, price, freight, shipping_limit | revenue, AOV |
| order_payments | order_id, payment_type, installments, value | payment mix, value checks |
| order_reviews | order_id, review_score, comments, timestamps | engagement/intent proxies |
| products | product_id, category, dimensions, weight | category affinity |
| sellers | seller_id, city, state | — |
| product_category_name_translation | category EN mapping | readability |
| geolocation | zip → lat/lon | regional controls |

Scale (verify at load, Day 1): ~100k orders, ~96k unique customers, 2017-08 → 2018-08, ~74 categories, 11 states (SP dominant). **Repurchase rate is low (~6%)** → RFM features are sparse; the campaign design must include an explicit "new customer" segment where recency is undefined.

## 3. What Olist lacks (why causal claims need simulation)

- ✗ ad exposures / impressions / clicks / touchpoints
- ✗ campaign assignments or control groups
- ✗ channel spend / budget data
- ✗ device / session-level web behavior
- ✗ acquisition channel
- ✗ any natural experiment (policy cutoff, budget shock) for a defensible quasi-experiment

Any paper-written "causal effect of channel X" using Olist raw data alone would therefore be invalid. **We will not do that.**

## 4. Simulated marketing layer design (`simulation/simulate_marketing.py`)

Purpose: give the pipeline a *known-ground-truth* treatment effect world with realistic confounding, so every estimator can be honestly benchmarked.

- **Customer backbone:** real Olist customers with real RFM/category/seasonality features (from the analytical table).
- **Confounders:** recency, frequency, monetary, tenure, category affinity, state, seasonality. All from real data.
- **Unobserved confounder `U`:** latent buying intent, simulated, that affects BOTH assignment and conversion → residual bias exists even under perfect adjustment. This powers the sensitivity analysis.
- **Targeting rule (confounding by design):** assignment probability per channel = logistic(score(RFM, category, seasonality) + U). Exposed customers have structurally higher baseline intent.
- **Ground-truth effects (embedded, per segment):**

| Channel | Known true effect | Narrative |
|---|---|---|
| Email | strong for lapsed high-value | reactivation works |
| Search | strong for new/active | captures demand |
| Display | ≈ 0 | apparent effect is pure confounding |
| Social | negative for high-frequency segment | "sleeping dogs" |

- **Outcome:** purchase within 14 days of campaign date; revenue follow-on.
- **Outputs:** rows per customer × campaign with `sim_*` exposure flags, a `sim_ground_truth` effect column (or lookup table), and outcome. Every column named `sim_*` is simulated.

**This is a synthetic-exercise layer for methodology validation — NOT a claim about real Olist marketing.**

## 5. How this maps onto real advertising data

If real ad-platform logs were available, the same pipeline consumes:

| Simulation element | Real-world counterpart |
|---|---|
| `sim_exposed_*` flags | ad-server impression/person-level exposure logs |
| `sim_targeting` | campaign audience targeting rules (lookalikes, RFM tiers) |
| `sim_ground_truth` | holdout experiments (A/B / geos / budget-split tests) |
| outcome window | conversion window from platform conversion pixels |
| channel cost | actual per-impression/CPC/CPM spend |

## 6. Analytical dataset (target schema, built Day 2)

`customer_id · first_order_date · tenure_days · order_count · total_revenue · avg_order_value · recency_days(rel. campaign) · category_affinity_top · avg_discount_share · state · review_score_avg · review_count · campaign_month · sim_exposed_{email,social,search,display} · converted_14d · revenue_14d`

## 7. Validation hooks

- Ground-truth recovery: bias/MSE of naive vs adjusted vs DR estimators against embedded true effects.
- Placebo treatment/outcome tests (Day 18).
- Sensitivity: how strong must a confounder be to erase each estimated effect.