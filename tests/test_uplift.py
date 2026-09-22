"""Day 14 acceptance tests: uplift modeling (Qini curves, segments).

Covers the Day 14 validation hooks from docs/roadmap.md:
"Qini above chance; segments interpretable"

Validates:
- uplift_frame schema: 4 strategies per channel x outcome, aligned 1:1 with
  the Day-13 CATE frame; sim_u is never a strategy score (only the oracle uses
  it, and the oracle column is explicitly counterfactual)
- Qini observed curve == causalml.metrics.get_qini (manual cross-check)
- Random-score Qini lift ~ 0 (chance), oracle-sorted ~ far above it
- True-lift (counterfactual) gates: mean Uplift-strategy true lift over the
  GT!=0 channels >= config; display == 0 (nothing to rank)
- Oracle true-lift is the max strategy per GT!=0 channel (upper bound)
- Revenue true-lift == conversion true-lift (monotone label transform)
- Segments interpretable: 4 quadrants per channel, shares >= config floor,
  structural conversion-rate ordering holds; sizes sum to the cohort
- Determinism of summary tables; artifacts + report content
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.confounders import CHANNELS
from src.causal.naive import OUTCOMES, load_analysis_data
from src.causal.uplift import (
    STRATEGIES,
    qini_curve,
    qini_curves_tables,
    qini_lift,
    segment_summary,
    uplift_frame,
    uplift_gates,
    write_uplift_report,
    write_uplift_tables_from,
)
from src.config import load_config


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def frame(cfg: dict) -> pd.DataFrame:
    return uplift_frame(cfg)


@pytest.fixture(scope="module")
def qtables(cfg: dict) -> dict:
    return qini_curves_tables(cfg)


@pytest.fixture(scope="module")
def segments(cfg: dict) -> pd.DataFrame:
    return segment_summary(cfg)


@pytest.fixture(scope="module")
def gates(cfg: dict, qtables: dict, segments: pd.DataFrame) -> pd.DataFrame:
    return uplift_gates(cfg, qtables=qtables, segments=segments)


def test_uplift_frame_schema_and_alignment(frame: pd.DataFrame, cfg: dict):
    n = len(load_analysis_data(cfg))
    assert len(frame) == len(CHANNELS) * len(OUTCOMES) * n
    assert set(frame.columns) == {"channel", "outcome", "uplift", "propensity",
                                  "baseline", "oracle", "treatment", "y"}
    assert len(frame["treatment"].unique()) == 2
    assert np.isfinite(frame[["uplift", "propensity", "baseline"]].to_numpy()).all()
    # oracle is the only sim_u-derived strategy -> explicitly counterfactual
    assert frame["oracle"].isna().sum() == 0
    for ch in CHANNELS:
        for o in OUTCOMES:
            block = frame[(frame["channel"] == ch) & (frame["outcome"] == o)]
            assert len(block) == n, f"{ch}/{o} misaligned with analysis data"


def test_qini_observed_curve_matches_causalml(cfg: dict):
    """Manual Radcliffe curve == causalml.metrics.get_qini (observed mode).

    Exact score ties exist here (1,806 tied values); my sort is stable
    (deterministic) while causalml's sort_values default is quicksort, so ties
    are broken differently. Jittering the score with unique noise makes the two
    sort orders identical -> the FORMULA comparison is exact (max diff 0.0).
    """
    from causalml.metrics import get_qini

    fr = uplift_frame(cfg)
    grp = fr[(fr["channel"] == "email") & (fr["outcome"] == "sim_converted_14d")]
    score, t, y = grp["uplift"].values, grp["treatment"].values, grp["y"].values
    rng = np.random.default_rng(1)
    score_j = score + rng.random(len(score)) * 1e-9
    _, y_manual = qini_curve(score_j, t, y)

    d = pd.DataFrame({"score": score_j, "w": t, "y": y})
    causal_y = get_qini(d, outcome_col="y", treatment_col="w",
                        normalize=True)["score"].values
    assert len(causal_y) == len(y_manual)
    assert np.allclose(y_manual, causal_y, atol=1e-9), "observed Qini != causalml"

    # stable (deterministic) tie-breaking on the raw score must be reproducible
    _, y_raw_a = qini_curve(score, t, y)
    _, y_raw_b = qini_curve(score, t, y)
    assert np.array_equal(y_raw_a, y_raw_b)


def test_random_score_is_chance(cfg: dict):
    fr = uplift_frame(cfg)
    grp = fr[(fr["channel"] == "search") & (fr["outcome"] == "sim_converted_14d")]
    rng = np.random.default_rng(0)
    perm = rng.permutation(len(grp))
    lift = qini_lift(grp["uplift"].values, grp["treatment"].values, grp["y"].values)
    lift_shuffled = qini_lift(grp["uplift"].values[perm], grp["treatment"].values,
                              grp["y"].values[perm])
    # a permutation destroys the score-outcome link -> near chance on observed data
    assert abs(lift_shuffled) < 1.0
    # but the true score still separates on the observed metric in this sample
    assert abs(lift) > abs(lift_shuffled)


def test_qini_lift_symmetry_observed_vs_true_axes(qtables: dict):
    sm = qtables["summary"]
    assert set(sm["strategy"]) == set(STRATEGIES)
    assert len(sm) == len(CHANNELS) * len(OUTCOMES) * len(STRATEGIES)
    cols = {"channel", "outcome", "strategy", "qini_lift_observed_pct",
            "qini_lift_true_pct", "n", "assumptions", "label"}
    assert cols.issubset(set(sm.columns))
    # oracle rows labelled counterfactual; the rest estimated (simulated)
    assert (sm.loc[sm["strategy"] == "oracle", "label"] ==
            "counterfactual (simulated ground truth)").all()
    assert (sm.loc[sm["strategy"] != "oracle", "label"] ==
            "estimated (simulated)").all()
    assert (sm["assumptions"].str.contains("sim_u")).all()


def test_display_true_lift_is_zero(qtables: dict):
    """Embedded effect 0.00 -> nothing to rank -> true lift == 0 for every strategy."""
    disp = qtables["summary"][(qtables["summary"]["channel"] == "display")]
    assert (disp["qini_lift_true_pct"] == 0.0).all()


def test_oracle_true_lift_is_upper_bound(qtables: dict):
    """Design property: the counterfactual oracle (perfect ranker) is the max
    true-lift strategy for every GT!=0 channel."""
    sm = qtables["summary"]
    for ch in ("email", "social", "search"):
        block = sm[(sm["channel"] == ch) & (sm["outcome"] == "sim_converted_14d")]
        oracle = float(block[block["strategy"] == "oracle"]["qini_lift_true_pct"].iloc[0])
        others = float(block[block["strategy"] != "oracle"]["qini_lift_true_pct"].max())
        assert oracle > others, f"{ch}: oracle {oracle:.2f} not above others {others:.2f}"
        assert oracle > 10.0, f"{ch}: oracle ceiling implausibly low"


def test_uplift_above_chance_gate(gates: pd.DataFrame, cfg: dict):
    """Day 14 hook 1: 'Qini above chance' on the true (counterfactual) metric."""
    assert (gates["passed"]).all(), gates.to_string(index=False)
    g = gates[gates["gate"] == "qini_above_chance_gt"].iloc[0]
    assert g["value"] >= float(cfg["uplift"]["qini_true_lift_min_gt_pct"])
    gd = gates[gates["gate"] == "qini_display_no_effect"].iloc[0]
    assert gd["value"] <= float(cfg["uplift"]["qini_true_lift_display_max_pct"])
    gu = gates[gates["gate"] == "oracle_is_upper_bound"].iloc[0]
    assert gu["passed"]


def test_uplift_gate_fails_on_zero_mean(cfg: dict, qtables: dict, segments: pd.DataFrame):
    """Gate logic is not vacuous: a zero mean-GT true lift must FAIL."""
    sm = qtables["summary"].copy()
    mask = (sm["strategy"] == "uplift") & (sm["outcome"] == "sim_converted_14d") \
           & (sm["channel"].isin(("email", "social", "search")))
    sm.loc[mask, "qini_lift_true_pct"] = 0.0
    gates = uplift_gates(cfg, qtables={"summary": sm, "curves": qtables["curves"]},
                         segments=segments)
    g = gates[gates["gate"] == "qini_above_chance_gt"].iloc[0]
    assert not g["passed"]


def test_revenue_true_lift_matches_conversion(qtables: dict):
    """True-lift is invariant across outcomes for outcome-invariant scores:
    propensity (same p(X) for both outcomes) and oracle (|revenue effect| =
    rev_mean * |conversion effect| is a monotone transform -> identical
    ranking). Uplift/baseline scores are outcome-specific models, so their
    lifts may (and do) differ."""
    sm = qtables["summary"]
    for strat in ("propensity", "oracle"):
        conv = sm[(sm["outcome"] == "sim_converted_14d") & (sm["strategy"] == strat)]
        rev = sm[(sm["outcome"] == "sim_revenue_14d") & (sm["strategy"] == strat)]
        pd.testing.assert_series_equal(
            conv.set_index("channel")["qini_lift_true_pct"],
            rev.set_index("channel")["qini_lift_true_pct"],
            check_exact=False, atol=1e-6, rtol=1e-4,
        )


def test_segments_interpretable(segments: pd.DataFrame, cfg: dict):
    """Day 14 hook 2: 4 quadrants per channel, non-degenerate, structurally sane."""
    ul = cfg["uplift"]
    assert set(segments["segment"]) == {"persuadable", "sure_thing", "sleeping_dog", "lost_cause"}
    for ch in CHANNELS:
        sg = segments[segments["channel"] == ch]
        assert len(sg) == 4
        assert abs(sg["share"].sum() - 1.0) < 1e-6
        assert (sg["share"] >= float(ul["segment_min_share"])).all()
        assert int(sg["n"].sum()) == 94983
        conv = sg.set_index("segment")["conv_rate"]
        # median-split structure: high-baseline arm converts more within each tau arm
        assert conv["sure_thing"] >= conv["persuadable"]
        assert conv["sleeping_dog"] >= conv["lost_cause"]
        tau = sg.set_index("segment")["mean_tau"]
        # high-tau arm > low-tau arm
        assert tau["persuadable"] > tau["lost_cause"]
        assert tau["sure_thing"] > tau["sleeping_dog"]
        assert (sg["label"] == "estimated (simulated)").all()


def test_segment_sizes_sum_to_cohort(segments: pd.DataFrame, cfg: dict):
    n = len(load_analysis_data(cfg))
    for ch in CHANNELS:
        total = int(segments[segments["channel"] == ch]["n"].sum())
        assert total == n, f"{ch}: segments total {total} != cohort {n}"


def test_determinism(qtables: dict):
    s1 = qtables["summary"]
    s2 = qini_curves_tables()
    # the two calls used the same fixed-seed inputs -> identical tables
    pd.testing.assert_frame_equal(s1, dict(s2)["summary"])


def test_artifacts_written(cfg: dict, qtables: dict, segments: pd.DataFrame):
    paths = write_uplift_tables_from(qtables, segments, cfg)
    assert paths["qini_curves"].exists()
    assert paths["qini_summary"].exists()
    assert paths["segment_summary"].exists()
    assert paths["gates"].exists()
    curves = pd.read_csv(paths["qini_curves"])
    assert set(curves["strategy"]) == set(STRATEGIES)
    assert len(curves) == len(CHANNELS) * len(OUTCOMES) * len(STRATEGIES) * 10
    report = write_uplift_report(cfg)
    assert report.exists()


def test_report_content():
    text = write_uplift_report().read_text(encoding="utf-8")
    for token in ["estimated (simulated)", "counterfactual (simulated ground truth)",
                  "Qini", "persuadable", "sleeping dog", "sim_u", "propensity",
                  "Key finding", "Gate results", "Limitations"]:
        assert token in text, f"missing '{token}' in report"