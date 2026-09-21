"""Day 10 acceptance tests: IPW with stabilized weights, ESS, truncation.

Covers the Day 10 validation hook from docs/roadmap.md:
"ESS reported; weights bounded"

Validates:
- IPW ATE estimated for all 4 channels x 2 outcomes
- Stabilized weights used; truncated at config cap -> weights bounded
- ESS reported before AND after truncation; truncation improves ESS (>= raw)
- Email weak-overlap case: raw ESS tiny, truncation recovers a usable ESS
- Truncated count reported per channel
- Bootstrap SE/CI reported; SE finite and positive
- Consistency: IPW ~ OLS (same order), matching the Day-9 honest story
- Determinism (fixed seed)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.ipw import (
    ipw_weights,
    ipw_estimate,
    ipw_estimates_table,
    ipw_report,
    write_ipw_table,
    write_ipw_report,
    OUTCOMES,
)
from src.causal.confounders import CHANNELS
from src.causal.propensity import load_analysis_data
from src.config import load_config, project_path


@pytest.fixture(scope="module")
def ipw_table() -> pd.DataFrame:
    return ipw_estimates_table()


def test_all_channels_all_outcomes_present(ipw_table):
    assert len(ipw_table) == len(CHANNELS) * len(OUTCOMES)
    for ch in CHANNELS:
        for o in OUTCOMES:
            assert ((ipw_table["channel"] == ch) & (ipw_table["outcome"] == o)).any()


def test_weights_bounded(ipw_table):
    """Validation hook: weights bounded by the config cap."""
    cfg = load_config()
    cap = float(cfg["ipw"]["weight_cap"])
    for _, r in ipw_table.iterrows():
        assert r["max_weight"] <= cap + 1e-9
        assert r["max_weight"] > 0


def test_ess_reported_and_improves(ipw_table):
    """ESS reported before/after truncation; truncation never worsens it."""
    for _, r in ipw_table.iterrows():
        assert r["ess_raw"] > 0
        assert r["ess_trunc"] > 0
        assert r["ess_trunc"] <= r["n"]
        assert r["ess_trunc"] >= r["ess_raw"] - 1e-6
        assert r["ess_raw"] <= r["n"]


def test_email_weak_overlap_ess_recovered(ipw_table):
    """Email: raw stabilized ESS is tiny (weak overlap) but truncation recovers it."""
    email = ipw_table[ipw_table["channel"] == "email"].iloc[0]
    assert email["ess_raw"] < 100, "email raw ESS should be tiny (PS~1 clumping)"
    assert email["ess_trunc"] > 50_000, "truncation should recover email's ESS"
    assert email["n_truncated"] >= 10


def test_truncated_count_nonnegative(ipw_table):
    for _, r in ipw_table.iterrows():
        assert int(r["n_truncated"]) >= 0
        assert int(r["n_truncated"]) <= int(r["n"])


def test_bootstrap_ci_reported(ipw_table):
    """SE finite/positive; CI ordered; reps from config."""
    cfg = load_config()
    for _, r in ipw_table.iterrows():
        assert np.isfinite([r["ipw_ate"], r["se"], r["ci_lower"], r["ci_upper"]]).all()
        assert r["se"] > 0
        assert r["ci_lower"] < r["ci_upper"]
    assert int(ipw_table["bootstrap_reps"].iloc[0]) == int(cfg["ipw"]["bootstrap_reps"])


def test_ipw_consistent_with_ols(ipw_table):
    """IPW ~ OLS (same order) — the Day-9 honest story persists under IPW."""
    for _, r in ipw_table.iterrows():
        if r["outcome"] == "sim_converted_14d":
            assert abs(r["ipw_ate"] - r["coef"]) < 0.02, \
                f"{r['channel']}: IPW {r['ipw_ate']:.4f} vs OLS {r['coef']:.4f}"
        else:
            assert abs(r["ipw_ate"] - r["coef"]) < 0.10 * abs(r["coef"]), \
                f"{r['channel']}: IPW {r['ipw_ate']:.2f} vs OLS {r['coef']:.2f}"


def test_ground_truth_and_naive_columns_present(ipw_table):
    for col in ("diff", "coef", "ground_truth_log_odds", "ess_raw", "ess_trunc", "n_truncated", "max_weight"):
        assert col in ipw_table.columns


def test_weights_function_stabilized():
    """Stabilized weights: treated weight = P(T=1)/p, control = P(T=0)/(1-p)."""
    cfg = load_config()
    df = load_analysis_data(cfg)
    for ch in CHANNELS:
        w = ipw_weights(df, ch, cfg)
        t = df[f"sim_exposed_{ch}"].values
        p_treat = t.mean()
        ps = w["ps"]
        expected = np.where(t == 1, p_treat / ps, (1 - p_treat) / (1 - ps))
        expected = np.minimum(expected, float(cfg["ipw"]["weight_cap"]))
        assert np.allclose(w["w_trunc"], expected, atol=1e-8), ch


def test_files_written():
    cfg = load_config()
    assert write_ipw_table(cfg).exists()
    assert write_ipw_report(cfg).exists()
    fig_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    assert (fig_dir / "ipw_conversion.html").exists()
    assert (fig_dir / "ipw_revenue.html").exists()


def test_report_has_identification_and_limits():
    report = ipw_report().lower()
    for token in ("identification", "ess", "truncat",
                  "limitations", "sim_u", "bootstrap"):
        assert token in report


def test_deterministic():
    t1 = ipw_estimates_table()
    t2 = ipw_estimates_table()
    pd.testing.assert_frame_equal(t1, t2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])