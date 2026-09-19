# Project Status — Live Log

Updated at the end of every day. Mirrors `docs/roadmap.md`.

Last updated: **Day 0** (2026-09-19)

## Current state

| Phase | Status |
|---|---|
| Governance docs | ✅ Done (Day 0) |
| Week 1 — Data + Causal framework (Days 1–7) | 🟡 Next: Day 1 |
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

## In progress

Nothing currently in progress.

## Blockers

1. **MySQL Credentials (blocks Day 1):** MySQL80 service is running but `root@localhost` requires a password. Needed: root/admin credentials (to create `olist` DB + `olist_app` user) or an existing admin user. Will be stored in `.env` (gitignored) — never committed.

## Next actions

1. Get MySQL credentials from the user → start **Day 1**: venv + pinned requirements, extended env gate, DB setup, Olist download + ingestion, commit `Day 1: env gate + MySQL ingestion`.
2. Stop at the end of Day 7 for **Gate 1** validation.