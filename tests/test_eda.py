"""Day 3 acceptance tests: EDA outputs are sane and reproducible.

Covers the Day 3 validation hook from docs/roadmap.md:
"Distributions sane · ~96k customers / ~100k orders".

Also locks in the AGENTS.md §2 contract for the simulated preview: every
simulated marketing column is prefixed `sim_`, the preview is deterministic
under a fixed seed, and exposure rates are proper probabilities.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.config import load_config, project_path
from src.features import cohorts, eda, rfm
from simulation.simulate_marketing import build_sim_preview, channel_descriptive_stats


@pytest.fixture(scope="module")
def df():
    """Analytical cohort parquet (skips if not built)."""
    cfg = load_config()
    path = project_path(cfg["paths"]["processed_data"]) / "customer_analytical.parquet"
    if not path.exists():
        pytest.skip(f"analytical parquet missing: {path}")
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def order_monthly():
    """Order-level monthly parquet (skips if not built)."""
    p = cohorts.load_order_monthly()
    if p.empty:
        pytest.skip("order_monthly parquet missing")
    return p


# --- distributions sane ------------------------------------------------------

def test_cohort_scale(df):
    """Observed scale matches Olist docs: ~96k customers, ~100k orders."""
    assert 94_000 <= len(df) <= 98_000, f"cohort size {len(df):,} out of documented range"
    assert 95_000 <= df["order_count"].sum() <= 102_000, (
        f"total purchased orders {df['order_count'].sum():,} out of range"
    )


def test_revenue_nonnegative_and_sane(df):
    assert (df["total_revenue"] >= 0).all()
    assert (df["avg_order_value"] >= 0).all()
    assert df["total_revenue"].median() > 0
    assert df["total_revenue"].max() < 1e6  # no absurd magnitudes


def test_one_time_buyer_majority(df):
    """Olist reality: P(order_count == 1) overwhelmingly dominant."""
    share = (df["order_count"] == 1).mean()
    assert share > 0.9, f"one-time buyer share {share:.3f} < 0.9"


def test_tenure_recency_window(df):
    """Tenure/recency stay inside the documented 2016-09..2018-09 window."""
    assert df["tenure_days"].min() >= 0
    assert df["recency_days"].min() >= 0
    assert df["tenure_days"].max() <= 800


# --- missingness & outliers --------------------------------------------------

def test_missingness_only_expected(df):
    """Only the two documented proxies may carry nulls."""
    non_null = [c for c in df.columns if df[c].isna().sum() == 0]
    assert "customer_id" in non_null and "total_revenue" in non_null
    null_cols = df.columns[df.isna().any()].tolist()
    assert set(null_cols) <= {"category_affinity_top", "review_score_avg"}, null_cols


def test_distribution_summary_shape(df):
    rep = eda.distribution_summary(df, eda.NUMERIC_COLS)
    assert list(rep.columns) == [
        "column", "n", "mean", "std", "min", "q25", "median", "q75", "max", "skew", "kurtosis",
    ]
    assert len(rep) == len(eda.NUMERIC_COLS)


def test_outlier_report_positive_count(df):
    flags = eda.iqr_outlier_flags(df)
    summ = eda.outlier_summary(df, flags)
    assert set(summ["column"]) == set(eda.REVENUE_COLS)
    assert (summ["n_outliers"] > 0).all()


# --- cohorts & retention -----------------------------------------------------

def test_order_monthly_scale(order_monthly):
    """Monthly table reproduces the cohort totals (94,983 / 98,199)."""
    assert order_monthly["customer_id"].nunique() == 94_983
    assert order_monthly["order_count"].sum() == 98_199


def test_retention_matrix_structure(order_monthly):
    ret = cohorts.retention_matrix(order_monthly, max_months=12)
    assert ret["cohort_month"].nunique() > 20  # full 2016-09..2018-09 span
    # month 0 must be 100% by construction (acquisition month has an order)
    assert (ret["m+0"] == 100.0).all()


def test_retention_declines(order_monthly):
    """Later months must not beat the acquisition month (no fabricated upticks)."""
    ret = cohorts.retention_matrix(order_monthly, max_months=6).set_index("cohort_month")
    # overall mean retention must decrease from m+0
    means = ret[["m+0", "m+1", "m+3", "m+6"]].mean()
    assert means["m+0"] >= means["m+1"] >= means["m+6"]


def test_acquisition_cohorts_cover_cohort(order_monthly):
    acq = cohorts.acquisition_cohorts(order_monthly)
    assert acq["n_customers"].sum() == 94_983


# --- RFM segmentation --------------------------------------------------------

def test_rfm_segments_partition(df):
    out = rfm.add_rfm(df)
    assert len(out) == len(df)
    assert out["rfm_segment"].notna().all()
    assert out["rfm_segment"].nunique() >= 5
    assert out["rfm_R"].between(1, 5).all()
    assert out["rfm_M"].between(1, 5).all()
    assert out["rfm_F"].between(1, 5).all()


def test_rfm_large_segments_match_reality(df):
    """The biggest segments reflect one-time buyers (observed reality)."""
    out = rfm.add_rfm(df)
    top = out["rfm_segment"].value_counts()
    assert set(top.head(3).index) <= {"one_time_lapsed", "new_customer", "lapsed", "big_spender"}


# --- simulated preview (sim_* contract) --------------------------------------

def test_sim_preview_all_simulated_columns_prefixed(df):
    sim = build_sim_preview(df)
    sim_only = [c for c in sim.columns if "sim_" in c]
    for c in sim_only:
        assert c.startswith("sim_"), f"simulated column without sim_ prefix: {c}"
    for ch in ("email", "social", "search", "display"):
        assert f"sim_exposed_{ch}" in sim.columns
        assert f"sim_ground_truth_{ch}" in sim.columns


def test_sim_preview_deterministic(df):
    a = build_sim_preview(df, seed=42)
    b = build_sim_preview(df, seed=42)
    assert a["sim_u"].equals(b["sim_u"])
    for ch in ("email", "social", "search", "display"):
        assert a[f"sim_exposed_{ch}"].equals(b[f"sim_exposed_{ch}"])


def test_sim_exposure_rates_are_probabilities(df):
    sim = build_sim_preview(df)
    stats = channel_descriptive_stats(sim)["exposure_rate"]
    assert (stats["pct_exposed"].between(0, 100)).all()
    assert stats["channel"].tolist() == ["email", "social", "search", "display"]


def test_sim_ground_truth_matches_config(df):
    cfg = load_config()
    sim = build_sim_preview(df)
    for ch in ("email", "social", "search", "display"):
        expected = cfg["simulation"]["preview"]["channels"][ch]["effect_log_odds"]
        assert sim[f"sim_ground_truth_{ch}"].iloc[0] == expected


def test_figures_are_written():
    """Deliverable: notebooks/01_eda + figures exist after the build."""
    fig_dir = project_path(load_config()["paths"]["results"], load_config()["results"]["figures"])
    nb = project_path(load_config()["paths"]["notebooks"]) / "01_eda.ipynb"
    if not fig_dir.exists() or not nb.exists():
        pytest.skip("figures/notebook not built yet")
    pngs = list(fig_dir.glob("*.png"))
    assert len(pngs) >= 10, f"only {len(pngs)} figures present"
    assert nb.exists()