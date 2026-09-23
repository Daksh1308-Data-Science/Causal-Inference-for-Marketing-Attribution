"""Day 17 acceptance tests: counterfactual budget scenarios.

Covers the Day 17 validation hook from docs/roadmap.md:
"Scenarios consistent with causal ROI"

Validates:
- Scenario table: 4 scenarios x 4 channels + 'all' rows; spends sum to the
  fixed as-run budget; labels are counterfactual everywhere
- Cross-day consistency: as_run per-channel nets reproduce the Day-16
  counterfactual cohort nets (roi table)
- The honest pattern gate set: every reallocation beats the as-run scatter,
  email saturation is documented (flags), no scenario exceeds the
  budget-constrained linear optimum, no silent extrapolation
- Gate non-vacuity: inflating a scenario net beyond the optimum, unflagging
  the email saturation, or deflating a reallocation below as_run must trip
  the corresponding gate
- Determinism, artifacts, report content
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.confounders import CHANNELS
from src.causal.counterfactuals import (
    LABEL,
    budget_optimum,
    cf_gates,
    cf_report,
    counterfactual_scenarios,
    scenario_summary_from,
    write_cf_report,
    write_cf_tables_from,
)
from src.causal.roi import roi_summary_from, roi_table
from src.config import load_config


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def roi_long(cfg: dict) -> pd.DataFrame:
    return roi_table(cfg)


@pytest.fixture(scope="module")
def summary_roi(cfg: dict, roi_long: pd.DataFrame) -> pd.DataFrame:
    return roi_summary_from(roi_long, cfg)


@pytest.fixture(scope="module")
def sc(cfg: dict, roi_long: pd.DataFrame, summary_roi: pd.DataFrame) -> pd.DataFrame:
    return counterfactual_scenarios(cfg, roi_long=roi_long, summary=summary_roi)


@pytest.fixture(scope="module")
def summary(cfg: dict, sc: pd.DataFrame) -> pd.DataFrame:
    return scenario_summary_from(sc)


@pytest.fixture(scope="module")
def gates(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame, roi_long: pd.DataFrame) -> pd.DataFrame:
    return cf_gates(cfg, sc=sc, summary=summary, roi_long=roi_long)


def test_schema_and_labels(cfg: dict, sc: pd.DataFrame):
    scen_names = list(cfg["counterfactuals"]["scenarios"])
    assert len(sc) == len(scen_names) * (len(CHANNELS) + 1)
    assert set(sc["scenario"]) == set(scen_names)
    assert set(sc["channel"]) == set(CHANNELS) | {"all"}
    assert (sc["label"] == LABEL).all()
    assert (sc["spend"] >= 0).all()
    assert (sc.loc[sc["channel"] != "all", "treated_after_cap"] <=
            sc.loc[sc["channel"] != "all", "implied_treated"] + 1e-9).all()
    assert (sc.loc[sc["channel"] != "all", "extrapolated"] ==
            (sc.loc[sc["channel"] != "all", "implied_treated"] >
             sc.loc[sc["channel"] != "all", "observed_n_treated"] + 1e-9)).all()


def test_spends_sum_to_budget(sc: pd.DataFrame):
    budget = float(sc[(sc["scenario"] == "as_run") & (sc["channel"] == "all")]["spend"].iloc[0])
    for scen in sc["scenario"].unique():
        total = float(sc[(sc["scenario"] == scen) & (sc["channel"] != "all")]["spend"].sum())
        assert total == pytest.approx(budget, rel=1e-9, abs=0.01)


def test_as_run_reproduces_day16(roi_long: pd.DataFrame, sc: pd.DataFrame, cfg: dict):
    day16 = roi_long[roi_long["method"] == "counterfactual"].set_index("channel")["net_per_treated"]
    n_t = roi_long[roi_long["method"] == "counterfactual"].set_index("channel")["n_treated"]
    as_run = sc[(sc["scenario"] == "as_run") & (sc["channel"] != "all")].set_index("channel")["net"]
    dev = (as_run - day16 * n_t).abs()
    assert dev.max() <= float(cfg["counterfactuals"]["as_run_net_tol"])
    assert dev.max() == pytest.approx(0.0, abs=0.01)


def test_reallocations_beat_as_run(sc: pd.DataFrame, summary: pd.DataFrame):
    as_run_net = float(summary.loc[summary["scenario"] == "as_run", "net"].iloc[0])
    realloc = summary[summary["scenario"] != "as_run"]
    assert (realloc["net"] > as_run_net).all()
    # as_run ranks last in the counterfactual ranking
    assert summary["scenario"].tolist()[-1] == "as_run"
    # ranking is sorted descending by net
    assert summary["net"].is_monotonic_decreasing


def test_email_saturation_and_zero_scenarios(sc: pd.DataFrame):
    flagged_email = sc[(sc["channel"] == "email") & (sc["scenario"] != "as_run")]
    assert flagged_email["extrapolated"].sum() >= 1
    assert (sc[(sc["scenario"] == "as_run")]["extrapolated"] == False).all()  # noqa: E712
    ctf = sc[sc["scenario"] == "ctf_guided"].set_index("channel")
    assert ctf.loc["social", "spend"] == 0 and ctf.loc["display", "spend"] == 0
    assert ctf.loc["social", "net"] == pytest.approx(0.0, abs=1e-6)
    assert ctf.loc["display", "net"] == pytest.approx(0.0, abs=1e-6)


def test_bounded_by_optimum(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame, roi_long: pd.DataFrame):
    budget = float(sc[(sc["scenario"] == "as_run") & (sc["channel"] == "all")]["spend"].iloc[0])
    optimum = budget_optimum(cfg, roi_long, budget)
    assert summary["net"].max() < optimum
    # optimum funds email first at cohort saturation: email spend == cohort x cost
    assert optimum > 0


def test_ci_columns_and_bias_gap(sc: pd.DataFrame, summary: pd.DataFrame):
    assert {"net_est_ci_low", "net_est_ci_high"} <= set(sc.columns)
    assert {"net_est_ci_low", "net_est_ci_high"} <= set(summary.columns)
    assert (summary["net_est_ci_low"] <= summary["net_est_ci_high"]).all()
    assert summary[["net_est_ci_low", "net_est_ci_high"]].notna().all().all()
    # the estimated-scale CI brackets the sim_u-inflated estimates, NOT the counterfactual point:
    # every scenario's counterfactual net lies far BELOW its estimated CI lower bound (the bias)
    assert (summary["net"] < summary["net_est_ci_low"]).all()
    # gap magnitude: counterfactual net is a single-digit-to-low-teens % of the estimated-scale
    # CI lower bound (2.7%-10.3% on this DGP: 10-38x overstatement)
    assert (100 * summary["net"] / summary["net_est_ci_low"] < 15).all()


def test_gates_all_pass(gates: pd.DataFrame):
    failed = gates[~gates["passed"]]
    assert len(failed) == 0, f"gates fail:\n{failed.to_string(index=False)}"


def test_gate_non_vacuity_optimum(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame,
                                  roi_long: pd.DataFrame):
    bad = summary.copy()
    budget = float(sc[(sc["scenario"] == "as_run") & (sc["channel"] == "all")]["spend"].iloc[0])
    optimum = budget_optimum(cfg, roi_long, budget)
    # inflate the best scenario past the optimum -> bounded_by_optimum must fail
    bad.loc[bad["scenario"] == "naive", "net"] = optimum + 100_000
    g = cf_gates(cfg, sc=sc, summary=bad, roi_long=roi_long)
    row = g[g["gate"] == "bounded_by_optimum"].iloc[0]
    assert not row["passed"]


def test_gate_non_vacuity_email_flag(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame,
                                     roi_long: pd.DataFrame):
    bad = sc.copy()
    mask = bad["channel"] == "email"
    bad.loc[mask, "extrapolated"] = False
    bad.loc[mask, "implied_treated"] = bad.loc[mask, "observed_n_treated"]
    bad.loc[mask, "treated_after_cap"] = bad.loc[mask, "observed_n_treated"]
    g = cf_gates(cfg, sc=bad, summary=summary, roi_long=roi_long)
    assert not g[g["gate"] == "email_saturation_documented"].iloc[0]["passed"]


def test_gate_non_vacuity_realloc(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame,
                                  roi_long: pd.DataFrame):
    bad = summary.copy()
    as_run_net = float(bad.loc[bad["scenario"] == "as_run", "net"].iloc[0])
    bad.loc[bad["scenario"] == "causal", "net"] = as_run_net - 1000
    g = cf_gates(cfg, sc=sc, summary=bad, roi_long=roi_long)
    assert not g[g["gate"] == "reallocations_beat_as_run"].iloc[0]["passed"]


def test_gate_non_vacuity_uncertainty(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame,
                                      roi_long: pd.DataFrame):
    bad = summary.copy()
    bad.loc[bad["scenario"] == "naive", ["net_est_ci_low", "net_est_ci_high"]] = [5_000_000, 1_000_000]
    g = cf_gates(cfg, sc=sc, summary=bad, roi_long=roi_long)
    assert not g[g["gate"] == "uncertainty_reported"].iloc[0]["passed"]


def test_determinism(sc: pd.DataFrame):
    again = counterfactual_scenarios()
    pd.testing.assert_frame_equal(again, sc)


def test_artifacts_and_report(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame, gates: pd.DataFrame):
    paths = write_cf_tables_from(sc, summary, gates, cfg)
    for p in paths.values():
        assert p.exists(), p
    assert pd.read_csv(paths["summary"])["scenario"].tolist() == summary["scenario"].tolist()
    report = write_cf_report(cfg, sc=sc, summary=summary)
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    for token in ["counterfactual (simulated ground truth), model-based",
                  "Day 17", "Method", "Key finding", "Extrapolation limit",
                  "Validation hooks", "Limitations", "R$", "⚠", "CI", "Uncertainty"]:
        assert token in text, f"missing '{token}'"
    assert all(ch in text for ch in CHANNELS)
    assert "naive" in text and "ctf_guided" in text and "as_run" in text and "causal" in text


def test_report_has_no_literal_escapes(cfg: dict, sc: pd.DataFrame, summary: pd.DataFrame):
    text = cf_report(cfg, sc=sc, summary=summary)
    assert "\\n" not in text
    assert text.count("\n") > 40