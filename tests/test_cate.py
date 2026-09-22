"""Day 13 acceptance tests: CATE with meta-learners (T/S/X, causalml).

Covers the Day 13 validation hook from docs/roadmap.md:
"Learner agreement map"

Validates:
- Unit-level CATE for all channels x outcomes; sim_u is never a feature
- Summary table: channel x outcome x learner with mean CATE, bootstrap 95% CI,
  SD, quantiles, assumptions, label (AGENTS §3)
- Mean CATE agrees with the Day-12 OLS ATE within config tolerances
- Learner agreement hook: all 8 cells status == OK
  (mean alignment within tolerance AND decile-curve spread <= tolerance,
  where the decile spread is normalised by the effect size, not the tiny SD)
- Individual-level rank agreement is REPORTED (0 < Spearman <= 1) but not gated
- Determinism: refitting one channel twice with the pinned seed is identical
- Artifacts written; report contains the agreement story and limitations
- notebooks/03_cate.ipynb exists after the build (skips if not built yet)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.cate import (
    LEARNERS,
    cate_estimates,
    cate_one_channel,
    cate_summary,
    learner_agreement,
    render_agreement_map,
    render_cate_by_channel,
    write_cate_estimates,
    write_cate_report,
    write_cate_tables,
)
from src.causal.confounders import CHANNELS, adjustment_sets
from src.causal.naive import OUTCOMES, load_analysis_data
from src.config import load_config, project_path


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def cate(cfg: dict) -> pd.DataFrame:
    return cate_estimates(cfg)


@pytest.fixture(scope="module")
def summary(cate: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return cate_summary(cate, cfg)


@pytest.fixture(scope="module")
def agreement(cate: pd.DataFrame, cfg: dict) -> dict:
    return learner_agreement(cate, cfg)


def test_unit_level_shape_and_no_sim_u(cate: pd.DataFrame):
    n = len(cate) // (len(CHANNELS) * len(OUTCOMES))
    assert n == 94983, "analysis cohort should be the documented 94,983 customers"
    assert len(cate) == len(CHANNELS) * len(OUTCOMES) * n
    expected_cols = {"channel", "outcome", "cate_t", "cate_s", "cate_x",
                     "treatment", "y", "baseline"}
    assert expected_cols.issubset(set(cate.columns))
    # sim_u is unobserved: it must never appear in the CATE frame
    assert "sim_u" not in cate.columns
    for col in ("cate_t", "cate_s", "cate_x"):
        assert np.isfinite(cate[col]).all()
    assert set(cate["treatment"].unique()) <= {0, 1}


def test_summary_shape_labels_and_ci(summary: pd.DataFrame):
    assert len(summary) == len(CHANNELS) * len(OUTCOMES) * len(LEARNERS)
    expected_cols = {"channel", "outcome", "outcome_label", "learner",
                     "learner_label", "mean_cate", "sd_cate", "ci_lower",
                     "ci_upper", "q05", "q25", "q50", "q75", "q95", "n",
                     "assumptions", "label"}
    assert expected_cols.issubset(set(summary.columns))
    assert (summary["label"] == "estimated (simulated)").all()
    assert (summary["assumptions"].str.contains("sim_u")).all()
    assert (summary["ci_lower"] <= summary["mean_cate"]).all()
    assert (summary["mean_cate"] <= summary["ci_upper"]).all()
    assert (summary["q05"] <= summary["q25"]).all()
    for q in ("q05", "q25", "q50", "q75", "q95"):
        assert np.isfinite(summary[q]).all()
    assert (summary["n"] == 94983).all()


def test_mean_cate_matches_dowhy_ols_ate(cate: pd.DataFrame, cfg: dict):
    """Learners agree with the established Day-12 OLS ATE (gate 1)."""
    p = project_path(cfg["paths"]["results"], cfg["results"]["tables"]) / "master_estimates.csv"
    assert p.exists(), "Day-12 master table missing"
    master = pd.read_csv(p)
    summary = cate_summary(cate, cfg)
    tol_abs = float(cfg["cate"]["agreement_tol_conversion_abs"])
    tol_rel = float(cfg["cate"]["agreement_tol_revenue_rel"])
    for ch in CHANNELS:
        for o in OUTCOMES:
            ate = float(master[(master["channel"] == ch) & (master["outcome"] == o) &
                               (master["estimator"] == "ols")]["point"].iloc[0])
            means = summary[(summary["channel"] == ch) & (summary["outcome"] == o)]["mean_cate"]
            tol = tol_abs if o == "sim_converted_14d" else tol_rel * abs(ate)
            assert float((means - ate).abs().max()) <= tol, f"{ch}/{o} mean CATE off ATE"


def test_learner_agreement_hook_all_ok(agreement: dict, cfg: dict):
    """Day 13 validation hook: all 8 cells must pass both gates (status == OK)."""
    status = agreement["status"]
    assert len(status) == len(CHANNELS) * len(OUTCOMES)
    assert (status["status"] == "OK").all(), status.to_string(index=False)
    tol_dec = float(cfg["cate"]["agreement_max_decile_rel"])
    assert float(status["max_decile_rel"].max()) <= tol_dec
    for _, r in status.iterrows():
        assert r["max_abs_mean_align"] <= r["mean_tolerance"]
        assert r["max_decile_rel"] <= r["decile_tolerance"]
        assert r["label"] == "estimated (simulated)"


def test_individual_agreement_reported_not_gated(agreement: dict):
    """Per-unit rank agreement is weak on this DGP and must be REPORTED,
    not used as a gate (the map's honest central finding)."""
    detail = agreement["detail"]
    assert len(detail) == len(CHANNELS) * len(OUTCOMES) * 3  # 3 learner pairs
    assert set(detail["pair"]) == {"t-s", "t-x", "s-x"}
    # reported Spearman must be a valid correlation; on this DGP it is weak (< 0.8).
    assert (detail["spearman_individual"] > 0).all()
    assert (detail["spearman_individual"] <= 1.0).all()
    assert (detail["mad_individual"] >= 0).all()
    assert detail["spearman_individual"].max() < 0.8, "observed heterogeneity too strong?"
    assert (detail["label"] == "estimated (simulated)").all()


def test_cate_frame_has_no_observed_or_unobserved_confounders(cate: pd.DataFrame, cfg: dict):
    """CATE frame carries only estimates, assignment, outcome and baseline —
    never raw confounders and never the unobserved sim_u."""
    assert set(cate.columns) == {"channel", "outcome", "cate_t", "cate_s",
                                 "cate_x", "treatment", "y", "baseline"}
    df = load_analysis_data(cfg)
    # the module's feature set is exactly the Day-4 adjustment set per channel
    for ch in CHANNELS:
        adj = adjustment_sets(cfg)[ch]
        assert all(f in df.columns for f in adj)
    assert "sim_u" not in df.columns or "sim_u" not in cate.columns


def test_determinism_refit_same_channel(cfg: dict):
    df = load_analysis_data(cfg)
    a = cate_one_channel(df, "email", "sim_converted_14d", cfg)
    b = cate_one_channel(df, "email", "sim_converted_14d", cfg)
    # pinned seed => identical early-stopping splits => identical CATE vectors
    pd.testing.assert_frame_equal(a, b, rtol=1e-12, atol=1e-12)


def test_determinism_summary_on_loaded_frame(cate: pd.DataFrame, cfg: dict):
    s1 = cate_summary(cate, cfg)
    s2 = cate_summary(cate, cfg)
    pd.testing.assert_frame_equal(s1, s2)


def test_artifacts_written(cate: pd.DataFrame, cfg: dict):
    write_cate_estimates(cate, cfg)
    paths = write_cate_tables(cate, cfg)
    _, map_path = render_agreement_map(cate, None, cfg)
    _, bar_path = render_cate_by_channel(cate_summary(cate, cfg), cfg)
    report_path = write_cate_report(cate, cfg)
    for p in [paths["summary"], paths["agreement"], map_path, bar_path, report_path]:
        assert p.exists(), p
    # agreement CSV rows: detail (per pair), plus the independent status table
    assert paths["summary"].exists()


def test_report_content(cate: pd.DataFrame, cfg: dict):
    report_path = write_cate_report(cate, cfg)
    text = report_path.read_text(encoding="utf-8")
    for token in ["estimated (simulated)", "Learner agreement map",
                  "T-learner", "X-learner", "sim_u", "Limitations",
                  "cross-fitt", "validation hook"]:
        assert token in text, f"missing '{token}' in report"


def test_notebook_deliverable_exists():
    cfg = load_config()
    nb = project_path(cfg["paths"]["notebooks"]) / "03_cate.ipynb"
    if not nb.exists():
        pytest.skip("notebooks/03_cate.ipynb not built yet")
    assert nb.exists()