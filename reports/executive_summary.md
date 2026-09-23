# Executive Summary — Causal Inference for Marketing Attribution

> **Audience:** CMO / VP Marketing / board. **Read time:** 3–4 minutes.
> **One-sentence warning:** every number in this summary that you could *spend money on* is a **model-based counterfactual estimate** built on a clearly-labelled simulation layer over real Olist customer data — NOT a claim about your real campaigns. The one robust lesson transfers to the real world: **observed lift is not causal lift**, and the difference is big enough to invert a budget decision.

---

## The question

Which of four channels — **email, social, search, display** — actually *drives* conversion and revenue, and how should a fixed budget be split across them?

The trap: exposure to a channel is never random. Customers who get your email or see your ad are *already* more engaged and more likely to buy. A naive comparison ("exposed customers spend R$ X more") quietly bills that pre-existing difference to the channel. The only honest question is **incremental**: what would *not* have happened without the channel?

## What we did

1. Built the analysis on **94,983 real Olist customers** (Brazilian E-Commerce, ~98k orders) with a documented, clearly-labelled **simulated marketing layer** (`sim_*`) — Olist has no marketing data, so we generated exposures with *known ground truth* (design in `docs/data-feasibility.md`).
2. Estimated treatment effects five independent ways — naive, OLS, IPW (inverse-probability weighting), doubly-robust AIPW, and matching — plus a DoWhy backdoor cross-check, each with point, SE, and 95% CI.
3. Stress-tested the estimates against an **unmeasured confounder** (E-value / bias formula) and with **placebo tests** (a treatment that cannot work, made to look like it does).
4. Translated effects into **incremental revenue → ROI → budget-allocation scenarios**, labelled throughout as observed / estimated / simulated / counterfactual.

## What we found

**1. Every observed-data method says every channel is great — and that's the problem.**

All five estimators converged to +0.11–0.13 pp conversion and R$ 16–18 incremental revenue per treated customer, *for every channel* — including display (true effect: zero) and social (true effect: negative). Six methods agreeing is normally reassuring. Here it is the tell: they all adjust for the same observed covariates and all miss the same unobserved factor. Adjusting for what we could observe barely moved the numbers.

**2. The hidden factor is real and it does the damage.**

A latent "intent" variable (call it `sim_u` — engagement, intent, or lifecycle stage in the real world) drives both who gets exposed and who buys. Measured directly from the simulation: it explains **82–97% of every observed "effect."** Placebos confirm it — a *fake* email channel "showed" |t| ≈ 98–110 on a variable it cannot affect, and a channel with true effect zero "showed" R$ 16.17 with |t| = 27.5.

**3. How strong would a hidden confounder have to be? Not very.**

E-values of **1.68–1.75**: a confounder associated with both exposure and outcome at risk ratio ≈ **1.71** on each axis would fully explain away the observed results. That is the fragility of the observed lift, in one number.

**4. The truth (simulation's known ground truth) is a different budget.**

| Channel | Naive ROI | "Causal" ROI (95% CI) | True ROI (oracle) | Reality check |
|---|---|---|---|---|
| Email | 16,671% | 17,265% [15,943–18,586] | **2,314%** | Genuinely best — but ~7.5× overstated |
| Search | 1,098% | 1,112% [1,030–1,195] | **101%** | Modestly profitable — ~11× overstated |
| Display | 7,879% | 7,983% [7,407–8,558] | **−100%** | You lose 100% of spend — looks amazing |
| Social | 2,040% | 1,912% [1,741–2,083] | **−297%** | Destroys value — looks great |

Observed and "causal" ROI columns are **estimated (simulated)** and confounded; the oracle column is **simulated ground truth**, i.e. what the simulation was built to contain. The money lesson: a confounder-inflated estimate doesn't just overstate winners — it **funds the channels that are actively destroying value.**

**5. The budget story.**

On the fixed R$ 77,215 as-run budget, every reallocation rule netted **R$ 148k–164k vs. R$ 48k as-run** — but the theoretical optimum (R$ 288k) is unreachable by any observed-data rule, because every rule keeps funding social/display on inflated estimates. The counterfactual-informed rule: **email to saturation (≈ R$ 9.5k spend), then search — stop social, stop display.**

## The honest bottom line

- **Robust, transferable lesson:** observed/attribution-style lift is a fragile, confounder-compatible number. A modest hidden factor (RR ≈ 1.7) can flip a loss-making channel into your "best performer." Always demand fragility reporting (E-value), placebo checks, and unknown unknowns.
- **This build's counterfactual priority** — *email first, search second, stop social/display* — is a **model-based counterfactual result on a simulation**, not an observed-data conclusion and not a claim about any real campaign.
- **What we did NOT do:** claim observed lift is causal; present simulated results as Olist facts; report a single estimate without its CI; force a pre-determined business conclusion.

## Where to go deeper

`README.md` (25 sections) · 7-page dashboard (`streamlit run dashboard/app.py`) · per-day reports in `reports/` · full tables in `results/` · methods & assumptions in `docs/blueprint.md` and `docs/decisions.md` (ADRs).