# AGENTS.md — Agent Operating Rules

This file governs every AI agent working in this repository. Read it before making any change. If a rule conflicts with an ad-hoc request, the rule wins unless the human user explicitly overrides it in writing.

## 1. Project

**Causal Inference for Marketing Attribution** — a portfolio-grade analysis estimating the *incremental causal impact* of marketing channels (email, social, search, display) on conversion and revenue. It walks the chain:

**Correlation → Causal Effect → Incremental Revenue → Marketing ROI → Budget Allocation**

- Master prompt: `Plan.md` (source of truth — never modify it).
- Design blueprint: `docs/blueprint.md`
- 21-day execution roadmap: `docs/roadmap.md`
- Live progress log: `docs/status.md`
- Recorded decisions: `docs/decisions.md`
- Data feasibility & simulation design: `docs/data-feasibility.md`

The build is **stage-gated**: a week is not complete until the human user validates it.

## 2. Non-negotiable rules (from Plan.md §27)

1. Never confuse correlation with causation. Never write "causes" for a claim supported only by correlation.
2. Never fabricate causal effects or results. Treat example numbers in the prompt as targets, not truth.
3. Clearly label every result as **observed**, **estimated**, **simulated**, or **counterfactual**.
   - Every simulated marketing variable MUST be prefixed `sim_` and documented in `docs/data-feasibility.md`.
   - Never present simulated-treatment results as observed Olist facts.
4. State causal assumptions explicitly and BEFORE fitting: exchangeability, positivity, consistency, SUTVA/no-interference — each with evidence and limitation.
5. Validate assumptions wherever possible: covariate balance, overlap, placebo tests, alternative estimators, bootstrap.
6. Report uncertainty (CI, SE, bootstrap), never bare point estimates.
7. Explain limitations honestly.
8. Do not force predetermined business conclusions — if the data says something different, say so.
9. Prioritize causal identification over model complexity.
10. Write reproducible code: pinned requirements, config-driven tunables, fixed seeds.
11. Make output understandable to both a CMO and a senior data scientist.
12. Do not claim an assumption is satisfied merely because a library executed successfully.

## 3. Every causal analysis must include

- An **identification strategy** written before fitting: causal question, treatment, outcome, required assumptions, why assignment is confounded, sufficient adjustment set, positivity/overlap evidence, SUTVA and consistency plausibility, remaining unobserved-confounding sources.
- ATE/ATT/CATE reported with: point estimate, CI, standard error, sample size, estimator, key assumptions, interpretation.
- A sensitivity statement: how strong an unmeasured confounder would have to be to eliminate the estimated effect (E-value / bias formula / Rosenbaum-style bounds).

## 4. Data & database

- **MySQL 8.0** (service `MySQL80`, running locally) + **MySQL Workbench**. Do NOT use Docker for the database.
- Credentials live in `.env` (gitignored): `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`.
- Pipeline code uses a dedicated `olist` database and `olist_app` user — never root in code.
- SQL dialect is MySQL 8: `AUTO_INCREMENT`, backticks; window functions and CTEs are supported. No `SERIAL`, no `ILIKE`.
- All SQL lives in `sql/`; analytics implemented as views; use `EXPLAIN ANALYZE` when optimizing.
- **Olist has NO marketing treatment data.** The marketing layer is a clearly-labeled simulation (see rule 2 and `docs/data-feasibility.md`). Do not pretend otherwise.

## 5. Environment (Windows)

- Python 3.14.6 at `C:\Python314`. Project venv `.venv` (gitignored).
- Causal stack pinned and previously validated on this Python: `dowhy==0.8` (classic API), `causalml`, `econml`, `statsmodels`.
- Use the DoWhy 0.8 classic API: `CausalModel` + `identify_effect` + `estimate_effect`.
- DAG rendering: `networkx` + `plotly`. **NEVER install `pygraphviz`** (native-build risk on Windows).
- Tests: `pytest` from repo root. Environment gate: `tests/test_gate_env.py`.
- Dashboard: `streamlit run dashboard/app.py` (reads precomputed `results/`).

## 6. Code conventions

- Modular logic in `src/` (`data/`, `features/`, `causal/`, `uplift/`, `evaluation/`, `visualization/`). Notebooks are for analysis narrative, not for logic that belongs in modules.
- All tunables (paths, DSN, seeds, channel costs, outcome window) in `configs/config.yaml`. No hardcoded magic values.
- Fixed random seed for every simulation/model, sourced from config.
- Type hints and docstrings on public functions.
- Tests cover: env gate, data schema, ground-truth recovery on a small simulation, dashboard data presence.

## 7. Git & progress

- One commit per day: `Day N: <summary>`. Final release tag `v1.0`.
- Update `docs/status.md` and the checkboxes in `docs/roadmap.md` immediately after each completed day.
- `.env`, `data/raw/`, `venv/`, caches are never committed.
- **Stage gates:** Week 1 (Days 1–7) → validate → Week 2 (Days 8–14) → validate → Week 3 (Days 15–21) → validate → `v1.0`.
- After the last day of a week, STOP and ask the human to validate before starting the next week.

## 8. Forbidden

- Installing packages without updating `requirements.txt` and re-running the env gate.
- Installing `pygraphviz`; using `psycopg`/Docker for the database.
- Deleting or rewriting `Plan.md` or any user file without explicit permission.
- Proceeding past a stage gate without human validation.
- Silently changing a prior decision — log ADRs in `docs/decisions.md` first.