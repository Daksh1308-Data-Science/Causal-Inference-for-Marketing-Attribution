# Learning Plan

Concept-by-concept roadmap (per `Plan.md` § "PART 4"). Levels: **Solid** = can implement & debug from scratch · **Deep** = can justify every assumption, explain tradeoffs, and defend in an interview.

| Concept | Why you need it (senior-level) | Level | Practical exercise |
|---|---|---|---|
| Potential outcomes (Rubin Causal Model) | Defines the causal question before any code — Y(0), Y(1), ATE/ATT/CATE | Deep | Write the formal quantities for one channel; explain in prose |
| DAGs / d-separation / backdoor criterion | Justifies the adjustment set; avoids conditioning on mediators/colliders | Deep | Draw the Olist DAG; list backdoor paths by hand; verify in DoWhy |
| Exchangeability / positivity / consistency / SUTVA | The four assumptions to state and stress-test | Deep | Fill the assumptions checklist; measure overlap empirically |
| Propensity scores | Diagnose and repair selection into exposure | Solid | Fit logit PS; plot overlap before matching |
| Matching & balance | ATT with credible common support | Solid | SMD before/after + love plot |
| IPW & stabilized weights | ATE by weighting; ESS; fragile weights | Solid | Compute weights, report ESS, clip extremes |
| Doubly robust estimation | One correct model suffices — the workhorse ATE estimator | Deep | AIPW with GLM + GBM outcome models; compare |
| ATE / ATT / CATE table discipline | Senior reports carry point estimate + CI + SE + N + estimator + assumptions | Deep | Produce full estimate tables per channel |
| HTE & uplift learners (T/S/X/DR) | Targeting decisions need heterogeneity, not average effects | Solid | Rank segments by CATE; Qini vs ranking by P(Y) |
| Uplift quadrants | Persuadables vs sure things vs lost causes vs sleeping dogs | Solid | Classify segments; quantify wasted spend |
| Sensitivity analysis (E-value, bias formula, Rosenbaum) | Defense against unobserved confounding | Deep | "How strong must U be?" section with real numbers |
| Counterfactual budget planning | Turns estimates into CMO decisions with uncertainty | Solid | Scenarios A–D with bootstrap CIs |
| SQL analytics (RFM, cohorts, retention, windows) | Realistic data engineering for causal studies | Solid | Build the analytical table in MySQL SQL, not pandas |
| Marketing attribution context (MMM/MTA) | Positions the project in industry practice | Solid | Write one page: MMM vs MTA vs people-based causal inference |

## Practice loop (used every week)

1. Implement the estimator on simulated data where the truth is known.
2. Record bias vs truth (this is our ground-truth validation).
3. Write the interpretation as if to a CMO; then restate technically for a senior DS.
4. Note which assumption is load-bearing and stress-test it.