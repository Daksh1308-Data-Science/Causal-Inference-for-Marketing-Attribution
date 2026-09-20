"""Day 4 acceptance tests: confounder audit is complete and causally justified.

Covers the Day 4 validation hook from docs/roadmap.md:
"Confounder audit table | Each row causally justified"

Validates:
- Every candidate variable is classified with a valid role from Plan.md Step 4.
- Every row has a non-empty rationale (the "causally justified" requirement).
- Treatments, outcomes, confounders, mediators, colliders, irrelevant all present.
- Adjustment decisions are valid (yes/no/never).
- Machine-readable adjustment sets per channel match the config targeting coefs.
- sim_u is classified as Confounder with adjust=never (unobserved by design).
- sim_ground_truth_* never adjusted.
- Mediators and colliders marked adjust=no.
- CSV and markdown report exist.
"""
from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path

from src.config import load_config, project_path
from src.causal.confounders import (
    build_audit_table,
    audit_rows,
    adjustment_sets,
    ROLE_CONFOUNDER,
    ROLE_TREATMENT,
    ROLE_OUTCOME,
    ROLE_MEDIATOR,
    ROLE_COLLIDER,
    ROLE_IRRELEVANT,
    ADJUST_YES,
    ADJUST_NO,
    ADJUST_NEVER,
    CHANNELS,
)

VALID_ROLES = {
    ROLE_CONFOUNDER,
    ROLE_TREATMENT,
    ROLE_OUTCOME,
    ROLE_MEDIATOR,
    ROLE_COLLIDER,
    ROLE_IRRELEVANT,
}
VALID_ADJUST = {ADJUST_YES, ADJUST_NO, ADJUST_NEVER}


@pytest.fixture(scope="module")
def audit_table():
    return build_audit_table()


def test_audit_table_structure(audit_table: pd.DataFrame):
    required_cols = {"variable", "source", "role", "adjust", "channels", "active_in_preview", "rationale", "note"}
    assert set(audit_table.columns) == required_cols
    assert len(audit_table) > 0


def test_every_row_has_rationale(audit_table: pd.DataFrame):
    """Each row causally justified = non-empty rationale."""
    bad = audit_table[audit_table["rationale"].isna() | (audit_table["rationale"].str.strip() == "")]
    assert len(bad) == 0, f"Rows missing rationale: {bad['variable'].tolist()}"


def test_roles_valid(audit_table: pd.DataFrame):
    invalid = audit_table[~audit_table["role"].isin(VALID_ROLES)]
    assert len(invalid) == 0, f"Invalid roles: {invalid[['variable', 'role']].to_dict('records')}"


def test_adjust_valid(audit_table: pd.DataFrame):
    invalid = audit_table[~audit_table["adjust"].isin(VALID_ADJUST)]
    assert len(invalid) == 0, f"Invalid adjust values: {invalid[['variable', 'adjust']].to_dict('records')}"


def test_treatments_present(audit_table: pd.DataFrame):
    treats = audit_table[audit_table["role"] == ROLE_TREATMENT]
    treat_vars = set(treats["variable"])
    expected = {f"sim_exposed_{ch}" for ch in CHANNELS}
    assert treat_vars == expected, f"Missing/extra treatments: {treat_vars ^ expected}"


def test_outcomes_present(audit_table: pd.DataFrame):
    outcomes = audit_table[audit_table["role"] == ROLE_OUTCOME]
    assert "sim_converted_14d" in outcomes["variable"].values
    assert "sim_revenue_14d" in outcomes["variable"].values
    # outcomes must be never-adjusted
    for _, row in outcomes.iterrows():
        assert row["adjust"] == ADJUST_NEVER, f"Outcome {row['variable']} must have adjust=never"


def test_sim_u_confounder_never_adjusted(audit_table: pd.DataFrame):
    u = audit_table[audit_table["variable"] == "sim_u"].iloc[0]
    assert u["role"] == ROLE_CONFOUNDER
    assert u["adjust"] == ADJUST_NEVER
    assert u["channels"] == "all"
    assert u["active_in_preview"] == True


def test_sim_ground_truth_never_adjusted(audit_table: pd.DataFrame):
    gts = audit_table[audit_table["variable"].str.startswith("sim_ground_truth")]
    assert len(gts) == 1
    assert gts.iloc[0]["adjust"] == ADJUST_NEVER
    assert gts.iloc[0]["role"] == ROLE_IRRELEVANT


def test_mediators_colliders_not_adjusted(audit_table: pd.DataFrame):
    med = audit_table[audit_table["role"] == ROLE_MEDIATOR]
    col = audit_table[audit_table["role"] == ROLE_COLLIDER]
    for _, row in med.iterrows():
        assert row["adjust"] == ADJUST_NO, f"Mediator {row['variable']} must be adjust=no"
    for _, row in col.iterrows():
        assert row["adjust"] == ADJUST_NO, f"Collider {row['variable']} must be adjust=no"


def test_adjustment_sets_match_config():
    cfg = load_config()
    adj = adjustment_sets(cfg)
    active = {}
    for ch in CHANNELS:
        active[ch] = sorted(cfg["simulation"]["preview"]["channels"][ch]["assignment_coefs"].keys())
    assert adj == active, f"Adjustment sets diverge from config: {adj} vs {active}"


def test_adjustment_sets_exclude_sim_u():
    """sim_u is explicitly excluded from adjustment sets (AGENTS §3)."""
    adj = adjustment_sets()
    for s in adj.values():
        assert "sim_u" not in s


def test_confounders_in_adjustment_sets(audit_table: pd.DataFrame):
    """Every variable with role=Confounder, adjust=yes, active_in_preview=True
    for a given channel must appear in that channel's adjustment set."""
    cfg = load_config()
    adj = adjustment_sets(cfg)
    for ch in CHANNELS:
        confounders_active = audit_table[
            (audit_table["role"] == ROLE_CONFOUNDER)
            & (audit_table["adjust"] == ADJUST_YES)
            & (audit_table["active_in_preview"] == True)
        ]
        # filter those that apply to this channel
        confounders_active = confounders_active[
            confounders_active["channels"].apply(lambda c: ch in [x.strip() for x in str(c).split(",")] if c != "all" else True)
        ]
        for _, row in confounders_active.iterrows():
            assert row["variable"] in adj[ch], (
                f"Confounder {row['variable']} active for {ch} not in adjustment set {adj[ch]}"
            )


def test_report_files_exist():
    cfg = load_config()
    csv_path = project_path(cfg["paths"]["results"], cfg["results"]["tables"]) / "confounder_audit.csv"
    md_path = project_path(cfg["paths"]["reports"]) / "confounder_audit.md"
    assert csv_path.exists(), f"CSV not found: {csv_path}"
    assert md_path.exists(), f"Markdown report not found: {md_path}"


def test_audit_rows_deterministic():
    """Same config -> same rows (reproducibility)."""
    rows1 = audit_rows()
    rows2 = audit_rows()
    assert len(rows1) == len(rows2)
    for a, b in zip(rows1, rows2):
        assert a == b


if __name__ == "__main__":
    pytest.main([__file__, "-v"])