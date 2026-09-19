# Project Status — Live Log

Updated at the end of every day. Mirrors `docs/roadmap.md`.

Last updated: **Day 2 — complete** (2026-09-19)

## Current state

| Phase | Status |
|---|---|
| Governance docs | ✅ Done (Day 0) |
| Week 1 — Data + Causal framework (Days 1–7) | 🟡 Day 2 complete; Days 3–7 next |
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

### Day 2 — Data engineering ✅
- [x] `sql/schema.sql` — 9-table DDL (FK-safe drop/create, utf8mb4, MySQL 8)
- [x] `sql/load.sql` — load contract + FK order + row-count gate documented
- [x] Bulk load via `src/data/load_olist.py` (pandas + pymysql executemany, one transaction per table) — **all 9 tables loaded, every row count matches `data/raw/_manifest.json`**
- [x] Dirty-data handling (reported in `data/processed/_load_report.json`, never hidden):
  - `order_reviews`: 814 duplicate `review_id` values → surrogate UUIDs (0 empty)
  - `order_payments`: 0 empty `payment_type`
  - no-item valid orders: 8 (5 created, 2 invoiced, 1 shipped)
- [x] `sql/analytics/customer_analytical.sql` — `v_customer_analytical` view (real Olist data only; no sim_* columns)
  - Cohort (final definition): customers with ≥1 **purchased order** = non-canceled/unavailable order with ≥1 `order_items` row → **N = 94,983**; 7 customers excluded (only no-item pipeline orders)
  - `customer_unique_id` multi-state quirk: 39 customers → state assigned from earliest purchased order
  - **Performance fix (ADR-008):** replaced the correlated `EXISTS` over `order_items` (which MySQL fused with the same-table equi-join into a plan that never finished — >300 s) with `JOIN order_items … SELECT DISTINCT`. Measured: `SELECT COUNT(*)` 22.8 s (was: never finished). Prerequisite discovered: interrupted/harness-killed client sessions left zombie server queries holding the view metadata lock — these must be `KILL`ed before re-creating the view.
- [x] `src/data/build_analytical.py` – materializes the view → `data/processed/customer_analytical.parquet` (94,983 × 12 cols)
- [x] `tests/test_data_schema.py` — **25 tests pass** covering: raw table rows vs manifest, no duplicate/null PKs, cohort count = 94,983, cohort contains only purchased orders, parquet schema/dtypes, no null keys/revenue, RFM plausibility, revenue tracks order count
- [x] **Full suite: 50/50 tests pass** (25 env gate + 25 data schema). **Day 2 validation hook green.**
- [x] Docker housekeeping requested by user: dropped unrelated databases (`creative_studio`, `text_to_sql`, `sakila`, `world`, `newschema`); MySQL now contains only `olist` + system schemas.
- [x] Operational cleanup: `.env` had a UTF-8 BOM (broke `DB_HOST`); `src/config.py` now reads `.env` as `utf-8-sig`. `olist_app` DB password re-synced to `.env`.

## Blockers

None.

## Next actions

1. **Days 3–7:** EDA + cohorts (Day 3) → confounder audit (Day 4) → causal DAG (Day 5) → propensity scores (Day 6) → PSM + balance (Day 7).
2. **Gate 1** — STOP after Day 7 and get human validation before Week 2.