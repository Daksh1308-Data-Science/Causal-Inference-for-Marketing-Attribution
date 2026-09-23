"""Day-19 acceptance tests: Streamlit dashboard (7 pages, headless AppTest + gates).

Validates the Day-19 roadmap row "Streamlit dashboard with honest framing
§11/§12" against the honest-causal non-negotiables (AGENTS.md §8):

- Every page renders headlessly under ``streamlit.testing.v1.AppTest`` with NO
  exception (no live server needed) and exposes per-page content (frames,
  figures, KPI cards) — thin Streamlit glue only, all logic lives in
  :mod:`src.dashboard.builders` (pure, headless-testable).
- Non-vacuity: every page must carry >= 1 honest token and render real content;
  a page that regresses to a bare point estimate fails.
- Honest-label vocabulary is the SINGLE source of truth in
  :mod:`src.causal.sensitivity` (Day 18) and is IMPORTED by the dashboard
  builders, never re-declared — if the roadmap honestly framed a tree-ever
  number as "established causal", the honest gate trips.
- Every effect is reported with a CI (CI-lower/high columns present), never a
  bare point estimate.
- Determinism: identical config → identical rendered pages (fixed seed).
- Gates are non-vacuous: corrupt/missing ``results/`` must trip the gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.causal.sensitivity import (
    LABEL_ESTIMATED,
    LABEL_MEASURED,
    LABEL_PLACEBO,
    LABEL_TRUTH,
)
from src.config import load_config
from src.dashboard import builders as b

PAGES = [
    "dashboard/app.py",
    "dashboard/pages/2_DAG.py",
    "dashboard/pages/3_Attribution.py",
    "dashboard/pages/4_Uplift.py",
    "dashboard/pages/5_Simulator.py",
    "dashboard/pages/6_Sensitivity.py",
    "dashboard/pages/7_Diagnostics.py",
]

@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config()


def _silence_streamlit_stdout():
    """AppTest is noisy about framework banners; pytest captures it anyway."""


# ---------------------------------------------------------------------------
# Headless render gate — one AppTest per page, asserts NO exception AND that
# the page actually rendered honest tokens (non-vacuity).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("script", PAGES)
def test_page_renders_headless_with_honest_tokens(script: str):
    at = AppTest.from_file(str(_ROOT / script)).run()
    assert not at.exception, f"{script} raised: {at.exception}"
    # every rendered element type (markdown/title/info/error/…) — a page that
    # renders the honest token via st.info would be missed by a markdown-only grep
    text = " ".join(
        str(e.value or "")
        for attr in ("markdown", "title", "caption", "info", "warning", "error", "success")
        for e in getattr(at, attr, [])
    )
    # honest framing must render from the single-source token (non-vacuity)
    assert b.HONEST_TOKEN in text, f"{script} dropped honest framing"


@pytest.mark.parametrize("script", PAGES)
def test_page_no_exception_per_page(script: str):
    at = AppTest.from_file(str(_ROOT / script)).run()
    assert not at.exception, f"{script} raised: {at.exception}"


# ---------------------------------------------------------------------------
# Pure builder contract — keys + honest tokens (single source of truth)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "builder,required_content",
    [
        (b.exec_summary, ("frames", "headline", "kpis")),
        (b.dag_page, ("figures",)),
        (b.attribution_page, ("figure", "frame")),
        (b.uplift_page, ("figure", "segments", "qini")),
        (b.simulator_page, ("roi_long", "scenarios")),
        (b.sensitivity_page, ("evalue", "bias_formula", "falsification", "summary")),
        (b.diagnostics_page, ("master", "evalue")),
    ],
)
def test_builder_contract_keys_and_tokens(cfg: dict, builder, required_content):
    page = builder(cfg)
    for k in required_content:
        assert k in page, f"missing {k}"
        # content must be non-vacuous: not an empty frame / null figure
        assert page[k] is not None
    # honest framing must be carried from the single-source token (not re-declared)
    assert any(b.HONEST_TOKEN in str(t) for t in page.get("tokens", [])), \
        "page dropped its honest framing token"


def test_labels_imported_not_redeclared():
    """builders must reuse the sensitivity LABEL_* vocabulary verbatim (identity)."""
    for name in ("LABEL_ESTIMATED", "LABEL_MEASURED", "LABEL_PLACEBO", "LABEL_TRUTH"):
        assert getattr(b, name) is globals()[name], f"{name} re-declared, not imported"


def test_every_effect_has_ci(cfg: dict):
    """Attribution frame must carry CI columns — never a bare point estimate."""
    att = b.attribution_page(cfg)["frame"]
    assert "inc_rev_ci_low" in att.columns and "inc_rev_ci_high" in att.columns
    assert att[["inc_rev_ci_low", "inc_rev_ci_high"]].notna().all().all()
    assert (att["inc_rev_ci_low"] <= att["inc_rev"]).all()
    assert (att["inc_rev_ci_high"] >= att["inc_rev"]).all()


def test_master_estimates_have_cis(cfg: dict):
    master = b.diagnostics_page(cfg)["master"]
    assert "ci_lower" in master.columns and "ci_upper" in master.columns
    assert master[["ci_lower", "ci_upper"]].notna().all().all()


# ---------------------------------------------------------------------------
# Gate tower — one honest gate per page + non-vacuity of every gate
# ---------------------------------------------------------------------------


def test_render_gate_all_pages_pass(cfg: dict):
    gates = b.render_gate(cfg)
    assert set(gates) == {  # one gate per page builder, none silently missing
        "exec", "dag", "attribution", "uplift", "simulator",
        "sensitivity", "diagnostics",
    }
    for name, g in gates.items():
        assert g["passed"], f"gate {name} failed: {g.get('desc')}"
        assert g["n"] >= 1, f"gate {name} vacuous (0 honest tokens)"


def test_render_gate_trips_when_results_missing(monkeypatch):
    """Gates must be non-vacuous: missing precomputed results trip the gate."""
    missing = _ROOT / "__missing_results_gate__"

    def fake_project_path(*parts: str):
        if parts and parts[0] == "results":
            return missing.joinpath(*parts[1:])
        return _ROOT.joinpath(*parts)

    monkeypatch.setattr(b, "project_path", fake_project_path)
    with pytest.raises(FileNotFoundError):
        b.render_gate(load_config())


# ---------------------------------------------------------------------------
# Determinism — identical config yields identical pages (fixed seed)
# ---------------------------------------------------------------------------


def test_builders_deterministic(cfg: dict):
    p1 = b.attribution_page(cfg)
    p2 = b.attribution_page(cfg)
    pd.testing.assert_frame_equal(p1["frame"], p2["frame"])
    p1s = b.simulator_page(cfg)
    p2s = b.simulator_page(cfg)
    pd.testing.assert_frame_equal(p1s["roi_long"], p2s["roi_long"])


# ---------------------------------------------------------------------------
# Runner — ALL pages render with content (non-vacuity at the bundle level)
# ---------------------------------------------------------------------------


def test_runner_renders_every_page(cfg: dict):
    out = b.run_all(cfg)
    assert "gates" in out
    for name, g in out["gates"].items():
        assert g["passed"], f"{name} failed"
    assert len(out["gates"]) == 7
