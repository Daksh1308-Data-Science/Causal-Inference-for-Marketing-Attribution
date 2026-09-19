# Architecture Decision Records (ADRs)

Status: **Accepted** unless noted. When a decision changes, add a new ADR overriding the old one — never rewrite history silently.

---

## ADR-001 — MySQL 8.0 + MySQL Workbench for the SQL layer

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Master prompt specifies PostgreSQL; no local PostgreSQL exists, and Docker Desktop's daemon is not running. MySQL 8.0 is installed and running as service `MySQL80`, with Workbench available.
- **Decision:** Use MySQL 8.0 + MySQL Workbench. Drivers: `pymysql` + `SQLAlchemy`.
- **Consequences:** MySQL 8 supports window functions/CTEs — all analytics (RFM, cohorts, retention, conversion windows) implemented in SQL. Dialect notes: `AUTO_INCREMENT`, backticks. README will document MySQL as the SQL engine.

## ADR-002 — Simulated marketing layer on real Olist data (never fabricate real treatments)

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Olist has no marketing treatment data. The prompt forbids fabricating treatments as real.
- **Decision:** Build the customer backbone from real Olist data; overlay a clearly-labeled simulated marketing layer (`sim_*` variables) with known ground-truth effects, confounding by design, and an unobserved-confounding variable. Pipeline validated by ground-truth recovery.
- **Consequences:** Absolute rule — no simulated variable is ever presented as observed. Feasibility doc (`docs/data-feasibility.md`) explains the real-data mapping.

## ADR-003 — Stage-gated 21-day execution

- **Date:** 2026-09-19 · **Status:** Accepted
- **Decision:** Build Week 1 (Days 1–7) → human validation → Week 2 → validation → Week 3 → validation → `v1.0`. No jumping ahead (prompt §27).

## ADR-004 — Python 3.14 + pinned causal stack: `dowhy==0.8`, causalml, econml, statsmodels

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Python 3.14.6 in use; a prior env gate passed this stack. DoWhy 0.8 uses the classic API.
- **Decision:** Use classic DoWhy 0.8 API (`CausalModel` + `identify_effect` + `estimate_effect`). Do not upgrade DoWhy mid-project without a new env gate.
- **Consequences:** All DoWhy code targets the 0.8 API.

## ADR-005 — DAG rendering without pygraphviz

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** `pygraphviz` has native-build risk on Windows.
- **Decision:** Use `networkx` (layout) + `plotly` (interactive render) for DAGs. DAG construction still via DoWhy's `CausalModel`.

## ADR-006 — Channel costs are config assumptions, not observed data

- **Date:** 2026-09-19 · **Status:** Accepted
- **Context:** Olist has no spend data; ROI needs a cost basis.
- **Decision:** Per-channel costs (CPM/CPC/contact) live in `configs/config.yaml`, explicitly labeled assumptions, documented in ROI reports.

## ADR-007 — Streamlit reads precomputed results

- **Date:** 2026-09-19 · **Status:** Accepted
- **Decision:** The 7-page dashboard loads `results/*.json` + artifacts; only the counterfactual simulator recomputes in memory. Fast, deterministic, reproducible.