"""Day 8 acceptance tests: naive estimates + why-not-causal write-up.

Covers the Day 8 validation hook from docs/roadmap.md:
"Direction documented"

Validates:
- Naive diff-in-means computed for all 4 channels x 2 outcomes
- Differences match treated mean - control mean exactly
- SE/CI reported (positive, finite)
- Direction documented per channel (values match raw means)
- Simulated ground-truth column present and labeled
- Display shows confounding signature (naive > 0 while ground truth = 0)
- Report + tables + plots written to results/
- Deterministic on repeat runs
"""

from __future__ import annotations

import pytest

from src.causal.naive import (
    naive_estimates_table,
    naive_estimates_one_channel,
    naive_report,
    why_not_causal_narrative,
    write_naive_tables,
    write_naive_report,
    OUTCOMES,
    OUTCOME_LABELS,
)
from src.causal.confounders import CHANNELS
from src.causal.propensity import load_analysis_data
from src.config import load_config, project_path


@pytest.fixture(scope="module")
def naive_table() -> "pd.DataFrame":
    """Compute the naive estimates once for all tests."""
    return naive_estimates_table()


def test_all_channels_all_outcomes_present(naive_table):
    """4 channels x 2 outcomes = 8 rows."""
    assert len(naive_table) == len(CHANNELS) * len(OUTCOMES)
    for ch in CHANNELS:
        for o in OUTCOMES:
            assert ((naive_table["channel"] == ch) & (naive_table["outcome"] == o)).any()


def test_diff_matches_means(naive_table):
    """Diff = mean(treated) - mean(control) exactly."""
    df = load_analysis_data()
    for ch in CHANNELS:
        tcol = f"sim_exposed_{ch}"
        treated = df[df[tcol] == 1]
        control = df[df[tcol] == 0]
        for o in OUTCOMES:
            row = naive_table[
                (naive_table["channel"] == ch) & (naive_table["outcome"] == o)
            ].iloc[0]
            assert row["diff"] == pytest.approx(treated[o].mean() - control[o].mean())
            assert row["n_treated"] == len(treated)
            assert row["n_control"] == len(control)


def test_se_and_ci_reported(naive_table):
    """SE > 0, finite; CI ordered lo < hi and contains the diff."""
    for _, r in naive_table.iterrows():
        assert r["se"] > 0
        assert r["se"] == pytest.approx(r["se"])  # not NaN
        assert r["ci_lower"] < r["diff"] < r["ci_upper"]


def test_direction_documented_positive(naive_table):
    """Validation hook: all naive gaps are positive (selection-dominated)."""
    for _, r in naive_table.iterrows():
        assert r["diff"] > 0, f"{r['channel']}/{r['outcome']} naive diff not positive"


def test_ground_truth_labeled_present(naive_table):
    """Simulated ground-truth column exists per row."""
    assert "ground_truth_log_odds" in naive_table.columns
    for _, r in naive_table.iterrows():
        assert isinstance(r["ground_truth_log_odds"], float)


def test_display_confounding_signature(naive_table):
    """Display: naive gap strongly positive while ground truth is 0 (pure confounding)."""
    display = naive_table[naive_table["channel"] == "display"]
    for _, r in display.iterrows():
        assert r["ground_truth_log_odds"] == 0.0
        assert r["diff"] > 0.05  # apparent effect is selection, not a causal effect


def test_social_confounding_signature(naive_table):
    """Social: negative ground truth (-0.08) but positive naive gap -> selection wins."""
    social = naive_table[naive_table["channel"] == "social"]
    for _, r in social.iterrows():
        assert r["ground_truth_log_odds"] < 0
        assert r["diff"] > 0.05  # naive gap opposite sign of ground truth


def test_conversion_diff_in_pp_range(naive_table):
    """Conversion diffs are risk differences, bounded by [-1, 1] and ~0.1."""
    conv = naive_table[naive_table["outcome"] == "sim_converted_14d"]
    assert (conv["diff"] > 0.05).all() and (conv["diff"] < 0.5).all()


def test_why_not_causal_narrative_covers_confounding():
    """Narrative names selection / confounded assignment for every channel."""
    for ch in CHANNELS:
        text = why_not_causal_narrative(ch).lower()
        assert "sim_u" in text or "latent" in text
        assert "selection" in text or "targeted" in text
        assert "not causal" in text or "≠" in text or "adjustment" in text


def test_report_has_simulated_label():
    """Report explicitly labels results as observed (simulated), per AGENTS.md §2."""
    report = naive_report()
    assert "simulated" in report.lower()
    assert "observed (simulated)" in report.lower() or "sim_" in report.lower()


def test_tables_and_plots_written():
    """CSV table + 2 plots + report exist on disk."""
    cfg = load_config()
    tbl_path = write_naive_tables(cfg)
    assert tbl_path.exists()
    rep_path = write_naive_report(cfg)
    assert rep_path.exists()
    fig_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    assert (fig_dir / "naive_conversion.html").exists()
    assert (fig_dir / "naive_revenue.html").exists()


def test_deterministic():
    """Repeated computation is identical (no RNG in Day-8 path)."""
    t1 = naive_estimates_table()
    t2 = naive_estimates_table()
    assert t1.equals(t2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])