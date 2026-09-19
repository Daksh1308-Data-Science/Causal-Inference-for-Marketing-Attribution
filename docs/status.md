# Project Status — Live Log

Updated at the end of every day. Mirrors `docs/roadmap.md`.

Last updated: **Day 1** (2026-09-19)

## Current state

| Phase | Status |
|---|---|
| Governance docs | ✅ Done (Day 0) |
| Week 1 — Data + Causal framework (Days 1–7) | 🟡 Next: Day 2 |
| Week 2 — Treatment effect estimation (Days 8–14) | ⬜ Not started |
| Week 3 — Business + robustness + product (Days 15–21) | ⬜ Not started |

## Completed

### Day 0 — Governance & project scaffolding
- [x] `AGENTS.md` — operating rules for AI agents
- [x] `docs/blueprint.md` — full project design
- [x] `docs/roadmap.md` — 21-day plan with progress tracking
- [x] `docs/data-feasibility.md` — Olist feasibility + simulation design
- [x] `docs/learning-plan.md` — concept learning roadmap
- [x] `docs/decisions.md` — architecture decision records
- [x] `README.md` stub + `.gitignore` (`.env`, `data/raw/`, venv excluded)
- **Gate 0 passed:** user approved the three key decisions (sim layer on Olist, MySQL, stage-gated).

### Day 1 — Environment + data ingestion
- [x] `requirements.txt` pinned + `requirements.lock.txt` frozen (dowhy==0.8 classic API, causalml, econml, statsmodels, streamlit, pymysql, …)
- [x] `.venv` built on Python 3.14.6; all packages import cleanly
- [x] Extended env gate `tests/test_gate_env.py` — **25 tests pass** (python version, 21 package imports, DoWhy 0.8 classic API, config load, raw-data manifest, live DB connection)
- [x] MySQL 8.0.46 verified; `olist` DB + `olist_app` user created (random 32-char password)
- [x] `.env` written (gitignored) — `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`; `.env.example` committed
- [x] All 9 Olist CSVs downloaded → `data/raw/` from a verified GitHub mirror and checked against documented row counts: orders 99,441 · customers 99,441 · order_items 112,650 · payments 103,886 · reviews 99,224 · products 32,951 · sellers 3,095 · geolocation 1,000,163 · category translation 73 (mirror count; 71 on Kaggle)
- [x] `data/raw/_manifest.json` written (rows + sha256 per file) for Day 2 schema tests
- [x] Skeleton: `src/config.py` (config/.env loader), `src/data/download_olist.py`, `configs/config.yaml` (paths, seed, outcome window, Olist registry)

## In progress

Nothing currently in progress.

## Blockers

None. (MySQL root access resolved on Day 1; `olist_app` is the pipeline user going forward.)

## Next actions

1. **Day 2 — Data engineering:** `sql/schema.sql` + `sql/load.sql`, bulk-load the 9 tables into MySQL `olist`, build `customer_analytical` view (RFM / tenure / category / state / seasonality), export processed parquet to `data/processed/`.
2. Stop at the end of Day 7 for **Gate 1** validation.