"""Day 9 acceptance tests: OLS regression adjustment.

Covers the Day 9 validation hook from docs/roadmap.md:
"CIs sane vs naive"

Validates:
- OLS estimated for all 4 channels x 2 outcomes
- Treatment coefficient, HC3 SE, 95% CI reported; CI sane (lo < coef < hi)
- CIs sane vs naive (SEs same order of magnitude; CIs not absurdly wide)
- Adjustment set from Day-4 audit used in the model
- OLS estimates remain honestly close to naive (residual sim_u confounding
  dominates; observed confounders are weak) — the simulated design point
- Report/table/plots written; determinism
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.regression import (
    estimate_ols,
    ols_estimates_table,
    ols_report,
    write_ols_table,
    write_ols_report,
    OUTCOMES,
    OUTCOME_LABELS,
)
from src.causal.confounders import CHANNELS, adjustment_sets
from src.causal.propensity import load_analysis_data
from src.config import load_config, project_path


@pytest.fixture(scope="module")
def ols_table() -> pd.DataFrame:
    return ols_estimates_table()


def test_all_channels_all_outcomes_present(ols_table):
    assert len(ols_table) == len(CHANNELS) * len(OUTCOMES)
    for ch in CHANNELS:
        for o in OUTCOMES:
            assert ((ols_table["channel"] == ch) & (ols_table["outcome"] == o)).any()


def test_ci_sane(ols_table):
    """Validation hook: CI sane — lo < coef < hi, SE finite and positive."""
    for _, r in ols_table.iterrows():
        assert r["se"] > 0
        assert np.isfinite([r["coef"], r["se"], r["ci_lower"], r["ci_upper"]]).all()
        assert r["ci_lower"] < r["coef"] < r["ci_upper"]


def test_ci_sane_vs_naive(ols_table):
    """CIs sane vs naive: OLS SEs same order of magnitude as naive SEs."""
    from src.causal.naive import naive_estimates_table
    naive = naive_estimates_table()[["channel", "outcome", "se"]]
    merged = ols_table.merge(naive, on=["channel", "outcome"], suffixes=("", "_naive"))
    for _, r in merged.iterrows():
        ratio = r["se"] / r["se_naive"]
        assert 0.5 < ratio < 2.0, f"{r['channel']}/{r['outcome']} SE ratio {ratio:.2f}"


def test_adjustment_set_used(ols_table):
    """Confounder column matches Day-4 audit adjustment_sets."""
    cfg = load_config()
    adj = adjustment_sets(cfg)
    for ch in CHANNELS:
        rows = ols_table[ols_table["channel"] == ch]
        for _, r in rows.iterrows():
            assert set(r["confounders"]) == set(adj[ch])


def test_coef_matches_fitted_model():
    """Treatment coefficient equals the statsmodels OLS fit."""
    cfg = load_config()
    df = load_analysis_data(cfg)
    for ch in CHANNELS:
        for o in OUTCOMES:
            res = estimate_ols(df, ch, o, cfg)
            model = res["model"]
            assert res["coef"] == pytest.approx(model.params[res["treatment"]])
            assert res["se"] == pytest.approx(model.bse[res["treatment"]])
            assert int(model.nobs) == len(df)


def test_hc3_robust_se():
    """Runs with HC3 covariance (heteroskedasticity-robust)."""
    cfg = load_config()
    df = load_analysis_data(cfg)
    res = estimate_ols(df, "email", "sim_converted_14d", cfg)
    model = res["model"]
    assert model.cov_type == "HC3"


def test_estimate_honest_relative_to_naive(ols_table):
    """Observed-confounder adjustment barely moves the gap (sim_u dominates).

    Social is the one channel where adjustment visibly reduces the estimate
    (moves toward its negative ground truth). Being honest about this small
    movement is the Day-9 design point; Day 18 quantifies unobserved U.
    """
    for _, r in ols_table.iterrows():
        # same order of magnitude as the naive gap (residual confounding);
        # tolerance is scale-aware: pp for conversion, relative for revenue
        if r["outcome"] == "sim_converted_14d":
            assert abs(r["coef"] - r["diff"]) < 0.02, \
                f"{r['channel']}/{r['outcome']} moved implausibly far from naive"
        else:
            assert abs(r["coef"] - r["diff"]) < 0.10 * abs(r["diff"]), \
                f"{r['channel']}/{r['outcome']} moved implausibly far from naive"

    social = ols_table[ols_table["channel"] == "social"]
    s_conv = social[social["outcome"] == "sim_converted_14d"].iloc[0]
    assert s_conv["coef"] < s_conv["diff"], "social OLS should shrink toward GT"


def test_plot_and_table_files_written():
    cfg = load_config()
    tbl = write_ols_table(cfg)
    assert tbl.exists()
    rep = write_ols_report(cfg)
    assert rep.exists()
    fig_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    assert (fig_dir / "ols_conversion.html").exists()
    assert (fig_dir / "ols_revenue.html").exists()


def test_report_labels_simulated():
    report = ols_report()
    assert "simulated" in report.lower()
    assert "estimated" in report.lower()
    assert "sim_u" in report  # limitation names the unobserved confounder


def test_report_has_limitations_section():
    report = ols_report()
    assert "## Limitations" in report
    for token in ["Linearity", "LPM", "unobserved confounding"]:
        assert token in report


def test_deterministic():
    t1 = ols_estimates_table()
    t2 = ols_estimates_table()
    pd.testing.assert_frame_equal(t1, t2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])