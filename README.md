# Causal Inference for Marketing Attribution

**Measuring what actually causes conversion — not just what correlates with it.**

This project estimates the *incremental causal impact* of marketing channels (email, social, search, display) on conversion and revenue, using a transparent simulated marketing layer on top of the real Brazilian E-Commerce (Olist) dataset. It walks the chain:

**Correlation → Causal Effect → Incremental Revenue → Marketing ROI → Budget Allocation**

> ⚠️ **Status: Under construction.** The full portfolio narrative (25-section README, technical report, executive summary) is a Day 21 deliverable. This stub links to the working docs.

## Working documents

| Document | Purpose |
|---|---|
| [`Plan.md`](Plan.md) | Master prompt — the full project specification |
| [`AGENTS.md`](AGENTS.md) | Operating rules for AI agents working in this repo |
| [`docs/blueprint.md`](docs/blueprint.md) | Architecture, DAG, identification & modeling strategy |
| [`docs/roadmap.md`](docs/roadmap.md) | 21-day execution plan with progress tracking |
| [`docs/status.md`](docs/status.md) | Live progress log (what's done / in progress / blocked) |
| [`docs/data-feasibility.md`](docs/data-feasibility.md) | Olist feasibility + simulated treatment-layer design |
| [`docs/learning-plan.md`](docs/learning-plan.md) | Concept-by-concept learning roadmap |
| [`docs/decisions.md`](docs/decisions.md) | Architecture Decision Records (ADRs) |

## Stack

Python 3.14 · Pandas · NumPy · **MySQL 8.0** (Workbench) · DoWhy 0.8 · CausalML · EconML · Statsmodels · Scikit-learn · LightGBM · XGBoost · NetworkX · Plotly · Matplotlib · Streamlit · Pytest