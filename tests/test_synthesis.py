"""Day 12 acceptance tests: ATE/ATT synthesis + DoWhy backdoor cross-check.

Covers the Day 12 validation hook from docs/roadmap.md:
"Estimator convergence story"

Validates:
- Master estimate table: channel x outcome x estimator rows with
  point / SE / 95% CI / N / estimator / assumptions (AGENTS §3)
- Estimator convergence (naive/OLS/IPW/DR all within config tolerances)
- ATT from the Day-7 matched sample (large, balanced sample, close to OLS)
- DoWhy backdoor cross-check reproduces the Day-9 OLS ATE (~1e-13)
- Files written; report contains convergence story + limitations;
  DoWhy compat shim is deterministic
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.synthesis import (
    ESTIMATORS,
    att_matched_estimates,
    convergence_summary,
    dowhy_backdoor_estimates,
    master_estimates_table,
    treatment_effects_report,
    write_master_table,
    write_treatment_effects_report,
    render_convergence_plot,
    ESTIMATOR_INFO,
)
from src.causal.confounders import CHANNELS
from src.causal.naive import OUTCOMES
from src.config import load_config, project_path


@pytest.fixture(scope="module")
def master() -> pd.DataFrame:
    return master_estimates_table()


@pytest.fixture(scope="module")
def conv(master: pd.DataFrame) -> pd.DataFrame:
    return convergence_summary(master)


def test_master_table_shape(master):
    assert len(master) == len(CHANNELS) * len(OUTCOMES) * len(ESTIMATORS)
    expected_cols = {"channel", "outcome", "outcome_label", "estimator",
                     "estimator_label", "point", "se", "ci_lower", "ci_upper",
                     "n", "assumptions", "label"}
    assert expected_cols.issubset(set(master.columns))
    for ch in CHANNELS:
        for o in OUTCOMES:
            rows = master[(master["channel"] == ch) & (master["outcome"] == o)]
            assert set(rows["estimator"]) == set(ESTIMATORS)


def test_rows_complete(master):
    for _, r in master.iterrows():
        assert np.isfinite([r["point"], r["se"], r["ci_lower"], r["ci_upper"]]).all()
        assert r["se"] > 0
        assert r["ci_lower"] < r["point"] < r["ci_upper"]
        assert r["n"] > 0
        assert r["assumptions"] and r["estimator_label"]
        assert r["label"] == "estimated (simulated)"  # AGENTS §2/§3
        assert r["estimator"] in ESTIMATOR_INFO


def test_estimator_labels(master):
    """Every registered estimator appears with its documented label.

    The master table must be ordered by the registry within each
    channel x outcome group; `groupby` (unsorted) sorts names
    alphabetically, so assert on the per-group order instead.
    """
    assert set(master["estimator"]) == set(ESTIMATORS)
    for (ch, o), grp in master.groupby(["channel", "outcome"], sort=False):
        assert grp["estimator"].tolist() == list(ESTIMATORS), f"{ch}/{o} ordering"
    for est in ESTIMATORS:
        assert master[master["estimator"] == est]["estimator_label"].iloc[0] \
            == ESTIMATOR_INFO[est]["label"]


def test_dowhy_matches_ols(master):
    """DoWhy backdoor.linear_regression == OLS up to machine precision."""
    ols = master[master["estimator"] == "ols"].set_index(["channel", "outcome"])
    dw = master[master["estimator"] == "dowhy_backdoor"].set_index(["channel", "outcome"])
    for ch in CHANNELS:
        for o in OUTCOMES:
            delta = abs(dw.loc[(ch, o), "point"] - ols.loc[(ch, o), "point"])
            assert delta < 1e-6 * max(abs(ols.loc[(ch, o), "point"]), 1e-9), \
                f"{ch}/{o}: DoWhy {dw.loc[(ch,o),'point']:.6f} vs OLS {ols.loc[(ch,o),'point']:.6f}"


def test_att_present_and_sane(master):
    att = master[master["estimator"] == "att_matched"]
    assert len(att) == len(CHANNELS) * len(OUTCOMES)
    ols = master[master["estimator"] == "ols"].set_index(["channel", "outcome"])
    for _, r in att.iterrows():
        o = ols.loc[(r["channel"], r["outcome"]), "point"]
        if r["outcome"] == "sim_converted_14d":
            assert abs(r["point"] - o) < 0.05, f"{r['channel']}: ATT {r['point']:.4f} vs OLS {o:.4f}"
        else:
            assert abs(r["point"] - o) < 0.15 * abs(o), \
                f"{r['channel']} revenue: ATT {r['point']:.2f} vs OLS {o:.2f}"


def test_att_match_counts_match_day7(master):
    """Matched ATT sample sizes match the Day-7 headline pair counts."""
    expected = {"email": 28118, "social": 24382, "search": 31349, "display": 35285}
    att = master[master["estimator"] == "att_matched"]
    for ch, n in expected.items():
        rows = att[(att["channel"] == ch) & (att["outcome"] == "sim_converted_14d")]
        assert int(rows.iloc[0]["n"]) == n, f"{ch}: {rows.iloc[0]['n']} pairs vs {n}"


def test_convergence_story(conv):
    """Validation hook: estimator convergence within config tolerances."""
    assert len(conv) == len(CHANNELS) * len(OUTCOMES)
    for _, r in conv.iterrows():
        assert r["status"] == "OK", \
            f"{r['channel']}/{r['outcome_label']}: range {r['range']:.4f} > tol {r['tolerance']:.4f}"


def test_convergence_uses_explicit_tolerances(conv):
    cfg = load_config()
    for _, r in conv.iterrows():
        if r["criterion"] == "absolute":
            assert r["tolerance"] == pytest.approx(cfg["synthesis"]["convergence_tol_conversion_abs"])
        else:
            assert r["criterion"] == "relative"
            assert r["tolerance"] > 0


def test_dowhy_deterministic():
    """DoWhy path (the only new estimator) is deterministic across calls."""
    t1 = dowhy_backdoor_estimates().sort_values(["channel", "outcome"]).reset_index(drop=True)
    t2 = dowhy_backdoor_estimates().sort_values(["channel", "outcome"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(t1[["channel", "outcome", "point"]],
                                  t2[["channel", "outcome", "point"]])


def test_files_written(master):
    cfg = load_config()
    assert write_master_table(master, cfg).exists()
    fig_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    conv_dir = fig_dir
    assert (fig_dir / "estimator_convergence_conversion.html").exists()
    assert (conv_dir / "estimator_convergence_revenue.html").exists()
    assert write_treatment_effects_report(master, convergence_summary(master, cfg), cfg).exists()


def test_render_plots_write_files(master):
    cfg = load_config()
    for outcome in OUTCOMES:
        _, p = render_convergence_plot(master, outcome, cfg)
        assert p.exists()


def test_report_content(master):
    cfg = load_config()
    report = treatment_effects_report(master, convergence_summary(master, cfg), cfg).lower()
    for token in ("convergence", "dowhy", "sim_u", "limitations", "estimated (simulated)",
                  "att", "assumptions"):
        assert token in report, f"missing token: {token}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])