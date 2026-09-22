"""Day 16 acceptance tests: incremental ROI.

Covers the Day 16 validation hook from docs/roadmap.md:
"ROI complete per channel"

Validates:
- ROI table: 4 channels x 3 methods (observational / causal / counterfactual),
  costs from config, n_treated from the frame, labels correct
- CI propagation through the monotone ROI transform
- The honest pattern: causal ROI positive for every channel (sim_u bias), while
  the counterfactual ROI is positive only for email/search (social/display
  negative — the truth no cost assumption can rescue)
- Overstatement multiple (causal ROI / counterfactual ROI) documented
- Gate logic non-vacuity: flipping signs must trip the gates
- Determinism, artifacts, report content
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.confounders import CHANNELS
from src.causal.roi import (
    roi_gates,
    roi_report,
    roi_summary_from,
    roi_table,
    write_roi_report,
    write_roi_tables_from,
)
from src.config import load_config


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def roi_long(cfg: dict) -> pd.DataFrame:
    return roi_table(cfg)


@pytest.fixture(scope="module")
def summary(cfg: dict, roi_long: pd.DataFrame) -> pd.DataFrame:
    return roi_summary_from(roi_long, cfg)


@pytest.fixture(scope="module")
def gates(cfg: dict, roi_long: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    return roi_gates(cfg, roi_long=roi_long, summary=summary)


def test_schema_labels_and_counts(roi_long: pd.DataFrame, cfg: dict):
    assert len(roi_long) == len(CHANNELS) * 3
    assert set(roi_long["method"]) == {"observational", "causal", "counterfactual"}
    assert set(roi_long["channel"]) == set(CHANNELS)
    assert (roi_long["cost_per_treated"] > 0).all()
    expected = cfg["roi"]["cost_per_treated"]
    for ch in CHANNELS:
        assert np.allclose(roi_long.loc[roi_long["channel"] == ch, "cost_per_treated"].astype(float),
                           float(expected[ch]))
    est = roi_long["method"] != "counterfactual"
    assert (roi_long.loc[est, "label"].str.startswith("estimated (simulated)")).all()
    ctf_rows = roi_long["method"] == "counterfactual"
    assert (roi_long.loc[ctf_rows, "label"].str.startswith("counterfactual (simulated ground truth)")).all()
    assert roi_long["label"].str.contains("Day-12 DR revenue ATE").any()
    assert roi_long["label"].str.contains("DGP oracle").any()
    assert roi_long["label"].str.contains("naive diff-in-means revenue ATE").any()


def test_n_treated_matches_frame(roi_long: pd.DataFrame):
    counts = {"email": 28_380, "search": 31_678, "display": 35_470, "social": 24_707}
    for ch, n in counts.items():
        assert (roi_long.loc[roi_long["channel"] == ch, "n_treated"] == n).all()


def test_ci_propagation_and_uncertainty(roi_long: pd.DataFrame):
    causal = roi_long[roi_long["method"] == "causal"]
    assert (causal["roi_ci_low"] < causal["roi"]).all()
    assert (causal["roi"] < causal["roi_ci_high"]).all()
    assert (causal["roi_ci_low"] > 0).all()
    ctf = roi_long[roi_long["method"] == "counterfactual"]
    assert (ctf["roi_ci_low"] == ctf["roi"]).all()
    assert (ctf["roi_ci_high"] == ctf["roi"]).all()


def test_honest_pattern_causal_vs_counterfactual(roi_long: pd.DataFrame):
    """Causal ROI positive everywhere (bias); counterfactual only email/search."""
    caus = roi_long[roi_long["method"] == "causal"].set_index("channel")["roi"]
    assert (caus > 0).all(), "causal ROI must be positive everywhere (sim_u bias)"
    ctf = roi_long[roi_long["method"] == "counterfactual"].set_index("channel")["roi"]
    assert ctf["email"] > 0 and ctf["search"] > 0
    assert ctf["social"] < 0 and ctf["display"] < 0
    assert ctf["display"] == pytest.approx(-1.0)  # zero true effect: cost fully lost


def test_overstatement_documented(summary: pd.DataFrame):
    ratio = summary.set_index("channel")["causal_over_ctf"]
    assert ratio["email"] > 5 and ratio["search"] > 5
    assert pd.isna(ratio["social"]) and pd.isna(ratio["display"])  # sign-flipped: not quotable


def test_cohort_net_counterfactual(summary: pd.DataFrame):
    s = summary.set_index("channel")
    assert s.loc["email", "cohort_net_ctf"] == pytest.approx(65_672.91, rel=1e-3)
    assert s.loc["display", "cohort_net_ctf"] < 0


def test_gates_all_pass(gates: pd.DataFrame):
    failed = gates[~gates["passed"]]
    assert len(failed) == 0, f"gates fail:\n{failed.to_string(index=False)}"


def test_gate_non_vacuity_display_flip(cfg: dict, roi_long: pd.DataFrame):
    bad = roi_long.copy()
    mask = (bad["method"] == "counterfactual") & (bad["channel"] == "display")
    bad.loc[mask, "inc_rev"] = 1.0
    bad.loc[mask, "net_per_treated"] = 0.8
    bad.loc[mask, "roi"] = 4.0
    bad.loc[mask, "roi_ci_low"] = bad.loc[mask, "roi_ci_high"] = 4.0
    sm = roi_summary_from(bad, cfg)
    g = roi_gates(cfg, roi_long=bad, summary=sm)
    assert not g.loc[g["gate"] == "ctf_social_display_negative", "passed"].iloc[0]


def test_gate_non_vacuity_causal_flip(cfg: dict, roi_long: pd.DataFrame):
    bad = roi_long.copy()
    mask = (bad["method"] == "causal") & (bad["channel"] == "search")
    bad.loc[mask, ["inc_rev", "net_per_treated", "roi", "roi_ci_low", "roi_ci_high"]] = -0.5
    sm = roi_summary_from(bad, cfg)
    g = roi_gates(cfg, roi_long=bad, summary=sm)
    assert not g.loc[g["gate"] == "causal_roi_positive", "passed"].iloc[0]


def test_determinism(roi_long: pd.DataFrame):
    assert len(roi_table()) == len(roi_long)
    pd.testing.assert_frame_equal(roi_table(), roi_long)


def test_artifacts_and_report(cfg: dict, roi_long: pd.DataFrame, summary: pd.DataFrame,
                              gates: pd.DataFrame):
    paths = write_roi_tables_from(roi_long, summary, gates, cfg)
    for p in paths.values():
        assert p.exists(), p
    assert pd.read_csv(paths["summary"])["channel"].tolist() == list(CHANNELS)
    report = write_roi_report(cfg, roi_long=roi_long, summary=summary)
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    for token in ["estimated (simulated)", "counterfactual (simulated ground truth)",
                  "Incremental ROI", "Key finding", "sim_u", "Limitations",
                  "Breakeven reads", "Validation hooks", "R$"]:
        assert token in text, f"missing '{token}'"
    assert all(ch in text for ch in CHANNELS)


def test_report_has_no_literal_escapes(cfg: dict, roi_long: pd.DataFrame, summary: pd.DataFrame):
    text = roi_report(cfg, roi_long=roi_long, summary=summary)
    assert "\\n" not in text
    assert text.count("\n") > 30