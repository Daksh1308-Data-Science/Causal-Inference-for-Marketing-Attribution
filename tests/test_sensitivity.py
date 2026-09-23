"""Day 18 acceptance tests: sensitivity analysis (E-value / bias formula).

Validates the roadmap Day-18 hook "Each claim stress-tested":
- E-value (VanderWeele-Ding, continuous-outcome approx): finite, ordered
  (CI-lower E-value <= point E-value), inside the fragility band (1, max]
- Linear bias formula: delta_U * gamma_U reproduces >= share_explained_min of
  every observed bias per channel
- Measured actual confounder sim_u: treated/untreated difference above the
  documented minimum for every channel
- Falsification (placebo) tests: placebo outcome sim_u and placebo channel
  display both show large significant "effects" (the bias is detectable)
- Gate non-vacuity: weakening the confounder, inflating an E-value, or
  neutralising a placebo must trip the corresponding gate
- Determinism, artifact/report content, no literal escapes
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.causal.confounders import CHANNELS
from src.causal.sensitivity import (
    LABEL_ESTIMATED,
    LABEL_MEASURED,
    LABEL_PLACEBO,
    LABEL_TRUTH,
    bias_formula_table,
    evalue_table,
    falsification_table,
    master_revenue_ate,
    sensitivity_gates,
    sensitivity_report,
    write_sensitivity_tables,
    _measure,
)
from src.config import load_config


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="module")
def measured(cfg: dict) -> dict:
    return _measure(cfg)


@pytest.fixture(scope="module")
def ev(cfg: dict, measured: dict) -> pd.DataFrame:
    return evalue_table(cfg, measured=measured)


@pytest.fixture(scope="module")
def bf(cfg: dict, measured: dict) -> pd.DataFrame:
    return bias_formula_table(cfg, measured=measured)


@pytest.fixture(scope="module")
def fals(cfg: dict, measured: dict) -> pd.DataFrame:
    return falsification_table(cfg, measured=measured)


@pytest.fixture(scope="module")
def gates(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame, fals: pd.DataFrame,
          measured: dict) -> pd.DataFrame:
    return sensitivity_gates(cfg, ev, bf, fals, measured)


def test_schema_and_labels(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame, fals: pd.DataFrame):
    assert set(ev["channel"]) == set(CHANNELS)
    assert set(bf["channel"]) == set(CHANNELS)
    assert (ev["label"] == LABEL_ESTIMATED).all()
    assert (bf["label"] == f"{LABEL_ESTIMATED} / {LABEL_TRUTH} / {LABEL_MEASURED}").all()
    assert (fals["label"] == LABEL_PLACEBO).all()
    for df in (ev, bf, fals):
        assert df.notna().all().all()


def test_evalue_ordered_and_fragile(ev: pd.DataFrame, cfg: dict):
    assert (ev["evalue_ci_lower"] <= ev["evalue_point"] + 1e-9).all()
    assert (ev["evalue_point"] > 1).all()
    assert (ev["evalue_ci_lower"] > 1).all()
    assert (ev["evalue_point"] <= cfg["sensitivity"]["max_point_evalue"]).all()
    # values are computed from the documented RR approximation
    for _, r in ev.iterrows():
        rr = np.exp(cfg["sensitivity"]["d_to_rr_coef"] * r["d_point"])
        assert r["evalue_point"] == pytest.approx(float(rr + np.sqrt(rr * (rr - 1))))


def test_bias_formula_consistency(bf: pd.DataFrame):
    # share_explained = delta * gamma / bias, in (0, 1]; gamma constant across channels
    gam = bf["gamma"].iloc[0]
    assert (bf["gamma"] == gam).all()
    expected = bf["delta_actual"] * gam / bf["observed_bias"]
    assert np.allclose(bf["share_explained"], expected)
    assert (bf["share_explained"] > 0).all() and (bf["share_explained"] <= 1).all()
    assert (bf["delta_req_truth"] > bf["delta_actual"]).all()


def test_actual_u_magnitude(measured: dict, cfg: dict):
    min_delta = min(float(measured[f"delta_{ch}"]) for ch in CHANNELS)
    assert min_delta >= cfg["sensitivity"]["actual_u_min_delta"]
    assert measured["gamma"] > 0


def test_placebo_falsified(fals: pd.DataFrame, cfg: dict):
    assert (fals["t_stat"].abs() >= cfg["sensitivity"]["min_placebo_t"]).all()
    assert (fals["falsified"]).all()
    # every placebo "effect" is positive (selection inflates, never deflates, here)
    assert (fals["estimate"] > 0).all()


def test_display_placebo_z(cfg: dict, fals: pd.DataFrame):
    ate = master_revenue_ate(cfg)
    disp = ate[ate["channel"] == "display"].iloc[0]
    z = float(disp["point"]) / float(disp["se"])
    row = fals[fals["test"] == "placebo channel display (true effect 0)"].iloc[0]
    assert row["t_stat"] == pytest.approx(z)
    assert row["estimate"] == pytest.approx(float(disp["point"]))


def test_gates_all_pass(gates: pd.DataFrame):
    failed = gates[~gates["passed"]]
    assert len(failed) == 0, f"gates fail:\n{failed.to_string(index=False)}"


def test_gate_non_vacuity_evalue(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame,
                                 fals: pd.DataFrame, measured: dict):
    bad = ev.copy()
    bad.loc[bad["channel"] == "email", "evalue_point"] = 4.0
    g = sensitivity_gates(cfg, bad, bf, fals, measured)
    assert not g[g["gate"] == "evalue_fragility_documented"].iloc[0]["passed"]
    assert g[g["gate"] == "evalue_reported"].iloc[0]["passed"]  # ordering still holds


def test_gate_non_vacuity_actual_u(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame,
                                   fals: pd.DataFrame, measured: dict):
    weak = dict(measured)
    weak["delta_email"] = 0.1
    g = sensitivity_gates(cfg, ev, bf, fals, weak)
    assert not g[g["gate"] == "actual_u_is_real_confounder"].iloc[0]["passed"]
    # unchanged bf -> bias-formula gate unaffected (isolated failure)
    assert g[g["gate"] == "bias_formula_explains_most"].iloc[0]["passed"]


def test_gate_non_vacuity_formula(cfg: dict, ev: pd.DataFrame, fals: pd.DataFrame,
                                  measured: dict):
    weak = dict(measured)
    weak["delta_social"] = 0.05
    bf_bad = bias_formula_table(cfg, measured=weak)
    g = sensitivity_gates(cfg, ev, bf_bad, fals, weak)
    assert not g[g["gate"] == "bias_formula_explains_most"].iloc[0]["passed"]


def test_gate_non_vacuity_placebo(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame,
                                  fals: pd.DataFrame, measured: dict):
    bad = fals.copy()
    bad.loc[0, "t_stat"] = 0.5
    g = sensitivity_gates(cfg, ev, bf, bad, measured)
    assert not g[g["gate"] == "placebo_tests_falsified"].iloc[0]["passed"]


def test_determinism(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame, fals: pd.DataFrame,
                     measured: dict):
    ev2 = evalue_table(cfg, measured=measured)
    pd.testing.assert_frame_equal(ev2, ev)
    bf2 = bias_formula_table(cfg, measured=measured)
    pd.testing.assert_frame_equal(bf2, bf)


def test_artifacts_and_report(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame,
                              fals: pd.DataFrame, gates: pd.DataFrame):
    paths = write_sensitivity_tables(cfg, ev, bf, fals, gates)
    for p in paths.values():
        assert p.exists(), p
    assert pd.read_csv(paths["gates"])["passed"].all()
    text = sensitivity_report(cfg, ev, bf, fals, gates, measured=_measure(cfg))
    report = __import__("src.config", fromlist=["project_path"]).project_path(
        cfg["paths"]["reports"], "sensitivity.md")
    for token in ["Day 18", "E-value", "bias formula", "placebo", "sim_u", "VanderWeele",
                  "Key finding", "Validation hooks", "Limitations", "δ_U", "γ_U", "R$"]:
        assert token in text, f"missing '{token}'"
    assert all(ch in text for ch in CHANNELS)
    assert report.exists()


def test_report_no_literal_escapes(cfg: dict, ev: pd.DataFrame, bf: pd.DataFrame,
                                   fals: pd.DataFrame, gates: pd.DataFrame):
    text = sensitivity_report(cfg, ev, bf, fals, gates, measured=_measure(cfg))
    assert "\\n" not in text
    assert text.count("\n") > 40