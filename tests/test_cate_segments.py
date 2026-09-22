"""Day 15 acceptance tests: CATE segmentation & targeting guidance.

Covers the Day 15 validation hook from docs/roadmap.md:
"Segments explain pattern"

Validates:
- Target-segment table: channel x outcome x band (+ all) rows; shares sum to 1;
  n sums to the cohort; labels (estimated vs counterfactual oracle) correct
- The handcrafted honest pattern IS the gate:
  - estimated CATE is positive in every band of every channel (the shared
    sim_u bias: observed data cannot recover the true sign structure)
  - counterfactual oracle signs match the DGP: email/search positive
    throughout, social negative throughout, display exactly zero
  - email/search rank gradient (top-band oracle > bottom-band) is real but tiny
- Targeting guidance: one row per channel; recommendations follow the
  counterfactual sign (Run / Skip / No budget); display's Spearman is NaN
  (constant zero oracle) handled gracefully
- Uncertainty: every band row has finite positive SE and a sane 95% CI
- Gate logic is non-vacuous: a flipped oracle sign makes the gate fail
- Determinism, artifacts, report content
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.confounders import CHANNELS
from src.causal.naive import OUTCOMES, load_analysis_data
from src.causal.segments import (
    BANDS,
    cate_segmentation_report,
    segment_gates,
    target_segments,
    targeting_guidance,
    write_cate_segmentation_report,
    write_segment_tables_from,
)
from src.config import load_config


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def ts(cfg: dict) -> pd.DataFrame:
    return target_segments(cfg)


@pytest.fixture(scope="module")
def guide(cfg: dict, ts: pd.DataFrame) -> pd.DataFrame:
    return targeting_guidance(cfg, ts=ts)


@pytest.fixture(scope="module")
def gates(cfg: dict, ts: pd.DataFrame) -> pd.DataFrame:
    return segment_gates(cfg, ts=ts)


def test_target_segments_schema_and_coverage(ts: pd.DataFrame, cfg: dict):
    n = len(load_analysis_data(cfg))
    n_bands = int(cfg["segments"]["n_bands"])
    assert set(BANDS[:n_bands]) <= set(ts["band"])
    assert len(ts) == len(CHANNELS) * len(OUTCOMES) * (n_bands + 1)
    for (ch, o), grp in ts.groupby(["channel", "outcome"]):
        bands = grp[grp["band"] != "all"]
        assert bands["share"].sum() == pytest.approx(1.0)
        assert int(bands["n"].sum()) == n, f"{ch}/{o} band sizes != cohort"
    assert (ts["label"] == "estimated (simulated)").all()
    assert (ts["oracle_label"] == "counterfactual (simulated ground truth)").all()


def test_band_order_is_canonical(ts: pd.DataFrame):
    for (ch, o), grp in ts[ts["band"] != "all"].groupby(["channel", "outcome"]):
        assert list(grp["band"]) == list(BANDS), f"{ch}/{o} bands out of order"


def test_uncertainty_reported(ts: pd.DataFrame):
    bands = ts[ts["band"] != "all"]
    assert (bands["tau_se"] > 0).all()
    assert (bands["tau_ci_low"] < bands["tau_mean"]).all()
    assert (bands["tau_mean"] < bands["tau_ci_high"]).all()


def test_estimated_signal_all_positive(ts: pd.DataFrame, cfg: dict):
    """Bias demonstration: every band, every channel — estimated CATE positive."""
    t = float(cfg["segments"]["est_all_positive_min"])
    conv = ts[(ts["outcome"] == "sim_converted_14d") & (ts["band"] != "all")]
    assert (conv["tau_mean"] > t).all(), "a band's estimated CATE is not positive"

def test_oracle_sign_structure_matches_dgp(ts: pd.DataFrame, cfg: dict):
    """Counterfactual truth: + / - / 0 per channel (the pattern that explains)."""
    seg = cfg["segments"]
    conv = ts[(ts["outcome"] == "sim_converted_14d") & (ts["band"] != "all")].copy()
    for ch in ("email", "search"):
        assert (conv.loc[conv["channel"] == ch, "oracle_mean"]
                > float(seg["gt_positive_min_oracle"])).all(), f"{ch} not positive throughout"
    assert (conv.loc[conv["channel"] == "social", "oracle_mean"]
            < float(seg["social_negative_max_oracle"])).all(), \
        "social not negative throughout"
    assert (conv.loc[conv["channel"] == "display", "oracle_mean"].abs()
            <= float(seg["display_oracle_zero_tol"])).all(), "display oracle not zero"
    # negative-share columns agree with the sign structure
    assert (conv.loc[conv["channel"] == "social", "oracle_neg_share"] == 1.0).all()
    assert (conv.loc[conv["channel"] != "social", "oracle_neg_share"] == 0.0).all()


def test_rank_gradient_real_but_tiny(ts: pd.DataFrame, cfg: dict):
    conv = ts[(ts["outcome"] == "sim_converted_14d") & (ts["band"] != "all")]
    for ch in ("email", "search"):
        b = conv[conv["channel"] == ch]
        gap = float(b.loc[b["band"] == "top", "oracle_mean"].iloc[0]) - \
              float(b.loc[b["band"] == "bottom", "oracle_mean"].iloc[0])
        assert gap > float(cfg["segments"]["rank_gap_min"]), f"{ch} gradient not positive"


def test_gates_all_pass(gates: pd.DataFrame):
    failed = gates[~gates["passed"]]
    assert len(failed) == 0, f"gates fail:\n{failed.to_string(index=False)}"


def test_gate_non_vacuous_social_flip(cfg: dict, ts: pd.DataFrame):
    """A flipped oracle sign must trip the social gate (machinery is real)."""
    bad = ts.copy()
    conv = (bad["outcome"] == "sim_converted_14d") & (bad["channel"] == "social")
    bad.loc[conv, "oracle_mean"] = 0.0
    g = segment_gates(cfg, ts=bad)
    assert not g.loc[g["gate"] == "social_negative_oracle", "passed"].iloc[0]


def test_gate_non_vacuous_estimated(cfg: dict, ts: pd.DataFrame):
    """If the estimated CATE were negative anywhere, the bias demo gate fails."""
    bad = ts.copy()
    conv = (bad["outcome"] == "sim_converted_14d") & (bad["channel"] == "display")
    bad.loc[conv, "tau_mean"] = -0.01
    g = segment_gates(cfg, ts=bad)
    assert not g.loc[g["gate"] == "estimated_signal_all_positive", "passed"].iloc[0]


def test_guidance_shape_and_recommendations(guide: pd.DataFrame):
    assert len(guide) == len(CHANNELS)
    assert set(guide["channel"]) == set(CHANNELS)
    rec = guide.set_index("channel")["recommendation"]
    assert "Run" in rec["email"] and "Run" in rec["search"]
    assert "Skip" in rec["social"]
    assert "No budget" in rec["display"]
    signs = guide.set_index("channel")["true_sign"]
    assert signs["email"] == "+" and signs["search"] == "+"
    assert signs["social"] == "\u2212" and signs["display"] == "0"
    assert pd.isna(guide.set_index("channel").loc["display", "spearman_tau_oracle"])


def test_determinism(ts: pd.DataFrame):
    ts2 = target_segments()
    pd.testing.assert_frame_equal(ts, ts2)


def test_artifacts_and_report(cfg: dict, ts: pd.DataFrame, guide: pd.DataFrame,
                              gates: pd.DataFrame):
    paths = write_segment_tables_from(ts, guide, gates, cfg)
    for p in paths.values():
        assert p.exists(), p
    seg_csv = pd.read_csv(paths["target_segments"])
    assert len(seg_csv) == len(ts)
    report = write_cate_segmentation_report(cfg, ts=ts, guide=guide)
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    for token in ["estimated (simulated)", "counterfactual (simulated ground truth)",
                  "Target-segment table", "Targeting guidance", "Key finding",
                  "sim_u", "Skip", "No budget", "Gate results", "Limitations"]:
        assert token in text, f"missing '{token}' in report"


def test_report_content_has_critical_numbers(cfg: dict, ts: pd.DataFrame):
    text = cate_segmentation_report(cfg, ts=ts)
    # guidance table rendered for all channels
    assert all(ch in text for ch in CHANNELS)
    assert "oracle_neg_share" not in text  # internal column name not leaked