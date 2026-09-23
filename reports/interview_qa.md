# Interview Q&A — Causal Inference for Marketing Attribution

Practice questions a data-science interviewer (or a skeptical CMO) will ask about this project, with ready, honest answers. Each answer cites the artifact that backs it — `reports/`, `results/`, `docs/` — so nothing here is unreferenced.

---

## Q1. "Why is `naive ≈ OLS ≈ IPW ≈ DR ≈ matching` — six estimators agreeing usually *is* evidence."

> Why they agree here: they all condition on the **same observed adjustment set** and all leave the **same `sim_u` unadjusted**. `sim_u` is built into assignment (coefficient 0.8) and outcome (coefficient 1.0, plus R$ 20.5/SD on revenue). Adjusting for observed covariates removes the *observed* component of selection but the latent component is untouched, and since every estimator maps the same X → same residual confounding, they converge to the same biased number. The proof this is bias and not signal is in the **placebos** (`reports/sensitivity.md`, `results/sensitivity/falsification.csv`): a fake channel with true effect zero "measures" R$ 16.17 (t = 27.5), and every channel "measures" a 0.69–0.74-SD effect on a pre-treatment placebo outcome (|t| 95–110). Six confounded estimators agreeing tells you how strong the confounder is, not that the effect is real. Convergence across *independent identification strategies* would be evidence; convergence across re-weighted versions of the same observed X is not.

## Q2. "Why not just run a randomized experiment?"

> A randomized A/B on these channels is the gold standard and, where feasible, we should run one — this observational analysis explicitly does **not** claim to replace that. Answering honestly: (a) real-world marketing spend can't always be randomized post hoc — you have observation logs, and the question "what did this campaign actually add?" needs the best possible answer from them; (b) this project demonstrates *what an honest observational answer looks like*: explicit assumptions, validated positivity, placebo checks, E-value fragility, and every number labelled observed/estimated/simulated/counterfactual; (c) the simulation gives us a **built-in oracle** — the DGP ground truth — which lets us grade the pipeline's identification the way you'd grade a real study only with a well-run experiment. The deliverable for a real team: "here's how to read your observational attribution, here's how fragile it is, and here's the experiment design that would settle it."

## Q3. "How do you handle unmeasured confounding — isn't that the whole ballgame?"

> It is, and it's handled four ways:
> 1. **Stated up front**: exchangeability is *violated by design* in this DGP; every estimate since Day 8 inherits `sim_u`.
> 2. **E-value** (`reports/sensitivity.md`): point E-values 1.68–1.75, CI-lower 1.64–1.71 — an unmeasured confounder associated with treatment and outcome at RR ≈ 1.71 on each axis fully explains the estimates away. That's the single number I quote to audiences.
> 3. **Bias formula with the confounder measured**: the DGP lets me read the *actual* `sim_u` (δ = 0.69–0.74 SD, γ = R$ 20.5/SD), and the formula reproduces 82–97% of the observed bias. In a real study you can't measure U, so you invert the logic: *given* your observed bias and a plausible γ, how big must δ be? The `delta_req` columns in `results/sensitivity/bias_formula.csv` are the required-confounder thresholds.
> 4. **Refutation**: a future analysis on real data should add negative-control outcomes and unexposed-group placebos; this build demonstrates both and shows what "failing loudly" looks like.

## Q4. "Walk me through your positivity/overlap check and how you validated it."

> Day 6–7 (`reports/confounder_audit.md`, `results/figures/ps_*` and `smd_*`): propensity-score distributions plotted per channel × treated/untreated — clear overlap regions with bounded tails; SMD for every covariate before vs. after matching (|SMD| < 0.1 after 1:1 caliper matching on the PS). IPW additionally uses stabilized weights truncated at the Cole–Hernán cap of 10 (`configs/config.yaml → ipw.weight_cap`), and the DR/decomposition gates report how many weights hit the cap (they do — that *is* the positivity strain from `sim_u`). I also flag the honest limit: overlap in **observed** covariates does not guarantee overlap in the **latent** `sim_u` — the estimand remains identified only under the full exchangeability assumption, which this DGP violates on purpose.

## Q5. "Why DoWhy, and what did the classic API add over your own estimators?"

> DoWhy 0.8's classic API (`CausalModel` → `identify_effect` → `estimate_effect`) is an independent implementation of the backdoor adjustment on the same DAG — a cross-check, not a dependency for the headline numbers. It reproduced the Day-9 OLS ATE to ~1e-13 (`reports/treatment_effects.md`), which is the expected result given both are linear backdoor estimators on the same X. Its value here: (a) it forces the identification step to be *explicit* (graph → estimand → estimator) rather than a buried regression; (b) it's the vocabulary a reviewer expects. The mainline estimates remain OLS/IPW/DR/matching, each with its own convergence and placebo gates.

## Q6. "Your observed and 'causal' ROIs are all positive but the oracle says social −297%, display −100%. Is that a contradiction?"

> No — it's the point. The causal ROI inherits the confounded ATE (R$ 16–18 per treated across all channels vs. truth R$ 2.4 email, 3.0 search, 0 display, −1.6 social). Because ROI is a monotone transform of the ATE for fixed cost, the *estimated* ROI is a monotone overstatement: email 7.5× the truth, search 11×, and sign-inverted for the losers. The oracle column is labelled **simulated ground truth** — it is the DGP's *actual* per-treated effect, used to grade the pipeline; it is not an observed result and not a claim about real campaigns. The contradiction is precisely why I report three columns (observed / causal / counterfactual) with CIs on the causal column and labels on every row (`reports/roi.md`, `results/roi/roi_summary.csv`).

## Q7. "Budget takeaway — what would you tell the marketing team to do differently?"

> On this build's counterfactual ground truth: **email to saturation (~R$ 9,498 spend covers the cohort), then search; stop social and display** — every reallocation of the fixed R$ 77,215 nets R$ 148k–164k vs. R$ 48k as-run, and the theoretical optimum (R$ 288k) is *unreachable by any observed-data rule* because all observed rules keep funding inflated losers (`reports/counterfactuals.md`). I'd pair that with the transferable process advice: require an E-value on every attribution number, a negative-control check, and an explicit label of what each number is (observed vs. incremental vs. counterfactual). The recommendation itself is model-based and counterfactual — the *method* is the durable product.

## Q8. "How is this reproducible? Prove it."

> `pytest` from the repo root — 368 tests, all green — including an env gate (Python 3.14 + pinned stack, MySQL 8 reachable), a data schema/cohort gate, ground-truth recovery (synthetic τ = 1.0 DR double-robustness), per-day gate records, a headless dashboard render suite, and a **deliverables manifest** (`tests/test_artifacts.py`) that asserts every artifact exists, every `gates.csv` records `passed=True` with measured values, and every label across all result CSVs uses the honest vocabulary. Everything is config-driven (`configs/config.yaml`: seeds, paths, costs, thresholds), requirements are pinned in `requirements.lock.txt`, the dashboard reads only precomputed `results/`, and a fixed seed makes re-runs byte-stable (the only diffs are plotly HTML UUIDs, which stay out of commits). Install → results path: README §22.

## Q9. "What are this project's biggest limitations?"

> 1. **It's a simulation** — the oracle comparison validates the *pipeline*, not the real world; ground truth was authored, not discovered.
> 2. **Costs are assumptions** (ADR-006), not observed spend; ROI is only as good as those inputs.
> 3. **No interference** (SUTVA) is plausible by construction, not proven.
> 4. **CATE signal is weak**: observed-X rank agreement across meta-learners is 0.32–0.77 (reported in learner-agreement maps) because `sim_u` dominates — so segmentation guidance is model-based and counterfactual-informed, not "this customer causes revenue."
> 5. **The recommendation is a counterfactual priority**, not an observed-data causal conclusion — I never claim the observed lift is a causal effect (the honest-language scanner in `tests/test_artifacts.py` enforces this across every report and result label).
> 6. **Single dataset, single DGP** — external validity is asserted, not demonstrated.

## Q10. "Why should I hire you / what did you actually learn?"

> The project's thesis, earned the hard way: **observed lift is not causal lift, and the gap is big enough to invert a budget.** Concretely I can now: write an identification strategy before a fit and defend each assumption with evidence; choose and validate estimators (IPW, DR, matching) rather than defaulting to one regression; quantify how strong an unmeasured confounder must be (E-value, bias formula) and prove it with placebos; translate ATEs into incremental revenue and ROI with honest CIs; and productize the whole thing — dashboard, manifest-tested artifacts, reproducible pipeline — without ever letting "the library ran" stand in for "the assumption holds." That combination — causal rigor *and* shipping discipline — is what the role needs.