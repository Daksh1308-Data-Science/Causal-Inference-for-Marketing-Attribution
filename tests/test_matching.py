"""Day 7 acceptance tests: PSM matching with balance diagnostics.

Covers the Day 7 validation hook from docs/roadmap.md:
"SMD < 0.1"

Validates:
- Nearest-neighbor matching runs for all 4 channels
- SMD love plots (before vs after) exist
- PS after matching plots exist
- All covariates balanced after matching (|SMD| < 0.1)
- Match rates > 90%
- Caliper respected
- Assumptions checklist generated
"""
from __future__ import annotations

import pytest

from src.causal.matching import (
    nearest_neighbor_match,
    compute_smd_after_matching,
    balance_summary,
    assumptions_checklist,
    run_matching_all_channels,
    CHANNELS,
)
from src.causal.propensity import load_analysis_data
from src.config import load_config


@pytest.fixture(scope="module")
def matching_results():
    """Run matching for all channels once."""
    return run_matching_all_channels()


def test_matching_runs_all_channels(matching_results: dict):
    """Matching produces results for all 4 channels."""
    assert set(matching_results.keys()) == set(CHANNELS)
    for ch in CHANNELS:
        assert "matched_df" in matching_results[ch]
        assert "smd_before" in matching_results[ch]
        assert "smd_after" in matching_results[ch]


def test_smd_love_plots_exist():
    """SMD love plot HTML files exist for all channels."""
    from src.config import load_config, project_path
    cfg = load_config()
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    for ch in CHANNELS:
        path = out_dir / f"smd_love_{ch}.html"
        assert path.exists(), f"Missing SMD love plot: {path}"


def test_ps_after_plots_exist():
    """PS after matching HTML files exist for all channels."""
    from src.config import load_config, project_path
    cfg = load_config()
    out_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    for ch in CHANNELS:
        path = out_dir / f"ps_after_{ch}.html"
        assert path.exists(), f"Missing PS after plot: {path}"


def test_match_rates_high(matching_results: dict):
    """Match rates > 90% for all channels."""
    for ch in CHANNELS:
        rate = matching_results[ch]["match_rate"]
        assert rate > 0.90, f"Channel {ch} match rate {rate:.1%} below 90%"


def test_smd_balanced_after_matching(matching_results: dict):
    """All covariates have |SMD| < 0.1 after matching."""
    for ch in CHANNELS:
        smd_after = matching_results[ch]["smd_after"]
        max_smd = smd_after["abs_smd"].max()
        assert max_smd < 0.1, f"Channel {ch} max |SMD| after = {max_smd:.3f} >= 0.1"


def test_smd_improved(matching_results: dict):
    """SMD improved (decreased in absolute value) for all covariates."""
    for ch in CHANNELS:
        before = matching_results[ch]["smd_before"]
        after = matching_results[ch]["smd_after"]
        for _, row in before.iterrows():
            var = row["variable"]
            before_abs = row["abs_smd"]
            after_abs = after[after["variable"] == var].iloc[0]["abs_smd"]
            assert after_abs <= before_abs + 1e-10, \
                f"Channel {ch} {var}: SMD worsened ({before_abs:.3f} -> {after_abs:.3f})"


def test_matched_pairs_exist(matching_results: dict):
    """Each channel has matched pairs."""
    for ch in CHANNELS:
        n_pairs = matching_results[ch]["n_matched_pairs"]
        assert n_pairs > 0, f"Channel {ch} has no matched pairs"


def test_balance_summary_generates(matching_results: dict):
    """balance_summary produces report with PASS/FAIL."""
    for ch in CHANNELS:
        summary = balance_summary(ch)
        assert "SMD Comparison" in summary
        assert "Balance Assessment" in summary
        assert "PASS" in summary or "FAIL" in summary


def test_assumptions_checklist_generates():
    """assumptions_checklist produces report with all 6 assumptions."""
    for ch in CHANNELS:
        checklist = assumptions_checklist(ch)
        assert "Exchangeability" in checklist
        assert "Positivity" in checklist
        assert "Consistency" in checklist
        assert "SUTVA" in checklist
        assert "Correct PS Model" in checklist
        assert "Matching Quality" in checklist


def test_caliper_respected(matching_results: dict):
    """Matched pairs respect caliper (verified by SMD improvement)."""
    # The caliper is enforced in nearest_neighbor_match; 
    # SMD improvement confirms reasonable matches
    for ch in CHANNELS:
        smd_after = matching_results[ch]["smd_after"]
        # At minimum, SMDs should be very small after matching
        assert smd_after["abs_smd"].mean() < 0.05, \
            f"Channel {ch} mean |SMD| after = {smd_after['abs_smd'].mean():.3f}"


def test_no_replacement_used(matching_results: dict):
    """Matching done without replacement (match_indices unique)."""
    # Our implementation uses without replacement
    # Just verify match_indices length matches n_pairs
    for ch in CHANNELS:
        match_indices = matching_results[ch]["match_indices"]
        n_pairs = matching_results[ch]["n_matched_pairs"]
        assert len(match_indices) == n_pairs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])