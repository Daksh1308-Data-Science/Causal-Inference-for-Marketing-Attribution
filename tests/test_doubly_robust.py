"""Day 11 acceptance tests: doubly robust AIPW.

Covers the Day 11 validation hook from docs/roadmap.md:
"Consistent vs OLS/IPW"

Validates:
- AIPW estimated for all 4 channels x 2 outcomes
- Consistency vs OLS/IPW (the validation hook)
- PS truncation bounds the augmentation (no explosion at p -> 1)
- Email weak-overlap units counted and handled (n_ps_truncated >= 13)
- Influence-function SE/CI reported
- **Double robustness property:** small synthetic DGP recovers the true
  treatment effect when only ONE of (PS, outcome model) is correct
- Files written; report explains double robustness; determinism
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy.special import expit

from src.causal.doubly_robust import (
    _aipw_ate,
    dr_estimate,
    dr_estimates_table,
    dr_report,
    write_dr_table,
    write_dr_report,
    OUTCOMES,
)
from src.causal.confounders import CHANNELS
from src.causal.propensity import load_analysis_data
from src.config import load_config, project_path


@pytest.fixture(scope="module")
def dr_table() -> pd.DataFrame:
    return dr_estimates_table()


def test_all_channels_all_outcomes_present(dr_table):
    assert len(dr_table) == len(CHANNELS) * len(OUTCOMES)
    for ch in CHANNELS:
        for o in OUTCOMES:
            assert ((dr_table["channel"] == ch) & (dr_table["outcome"] == o)).any()


def test_consistent_vs_ols_ipw(dr_table):
    """Validation hook: DR consistent with OLS/IPW."""
    for _, r in dr_table.iterrows():
        if r["outcome"] == "sim_converted_14d":
            assert abs(r["dr_ate"] - r["ipw_ate"]) < 0.01, \
                f"{r['channel']}: |DR-IPW| = {abs(r['dr_ate']-r['ipw_ate']):.4f}"
            assert abs(r["dr_ate"] - r["coef"]) < 0.02, \
                f"{r['channel']}: |DR-OLS| = {abs(r['dr_ate']-r['coef']):.4f}"
        else:
            assert abs(r["dr_ate"] - r["ipw_ate"]) < 0.10 * abs(r["ipw_ate"])
            assert abs(r["dr_ate"] - r["coef"]) < 0.10 * abs(r["coef"])


def test_se_ci_reported(dr_table):
    for _, r in dr_table.iterrows():
        assert np.isfinite([r["dr_ate"], r["se"], r["ci_lower"], r["ci_upper"]]).all()
        assert r["se"] > 0
        assert r["ci_lower"] < r["dr_ate"] < r["ci_upper"]


def test_email_ps_truncation_reported(dr_table):
    """Email weak overlap: PS truncation count reported (>= 13 controls near PS=1)."""
    email = dr_table[dr_table["channel"] == "email"].iloc[0]
    assert int(email["n_ps_truncated"]) >= 13
    assert email["ps_clip_hi"] < 1.0  # upper clip strictly below 1


def test_email_no_explosion(dr_table):
    """Truncation bounds the augmentation: email DR ~ IPW/OLS, not absurd."""
    email_conv = dr_table[(dr_table["channel"] == "email")
                          & (dr_table["outcome"] == "sim_converted_14d")].iloc[0]
    assert abs(email_conv["dr_ate"]) < 0.5
    assert email_conv["se"] < 0.02


def test_double_robustness_property():
    """True tau recovered when exactly one model is misspecified.

    `_aipw_ate` fits the outcome model internally on `confounders` while the
    PS is passed in — so we can hand it an externally-fit (mis)specified PS
    and control the outcome-model specification via `confounders`.
    """
    rng = np.random.default_rng(7)
    n = 8000
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    # gentle slopes keep the PS bounded away from 0/1 (finite-sample stability);
    # intercept shifts prevalence so both arms are well populated
    t = (rng.random(n) < expit(-1.0 + 0.4 * x1 + 0.4 * x2)).astype(float)
    tau = 1.0
    y = 0.5 + tau * t + x1 + x2 + rng.normal(scale=0.5, size=n)

    sim = pd.DataFrame({"x1": x1, "x2": x2, "t": t, "y": y})

    def fit_ps(dat, confounders):
        # Logit.predict already returns probabilities (no expit wrapper!)
        X = sm.add_constant(dat[confounders], has_constant="add")
        return np.asarray(sm.Logit(dat["t"], X).fit(disp=False).predict(X))

    # Case A: correct PS (x1,x2) passed in; outcome model misspecified (x1 only)
    ateA = _aipw_ate(sim, fit_ps(sim, ["x1", "x2"]), "t", "y", ["x1"], cap=None)["ate"]

    # Case B: wrong PS (x1 only) passed in; outcome model correct (x1,x2)
    ateB = _aipw_ate(sim, fit_ps(sim, ["x1"]), "t", "y", ["x1", "x2"], cap=None)["ate"]

    assert abs(ateA - tau) < 0.2, f"DR with correct PS failed: {ateA:.3f}"
    assert abs(ateB - tau) < 0.2, f"DR with correct outcome model failed: {ateB:.3f}"


def test_files_written():
    cfg = load_config()
    assert write_dr_table(cfg).exists()
    assert write_dr_report(cfg).exists()
    fig_dir = project_path(cfg["paths"]["results"], cfg["results"]["figures"])
    assert (fig_dir / "dr_conversion.html").exists()
    assert (fig_dir / "dr_revenue.html").exists()


def test_report_explains_double_robustness():
    report = dr_report().lower()
    for token in ("double", "robust", "sim_u", "limitations", "influence"):
        assert token in report


def test_deterministic():
    t1 = dr_estimates_table()
    t2 = dr_estimates_table()
    pd.testing.assert_frame_equal(t1, t2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])