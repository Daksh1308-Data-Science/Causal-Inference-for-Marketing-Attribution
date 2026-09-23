"""Day 20 acceptance tests: deliverables manifest + honest-label bundle audit.

Roadmap hook (Day 21): "Install→results reproducible". A fresh checkout that
runs the pipeline must produce every artifact in ``results/`` and ``reports/``;
the dashboard (Day 19) renders only from ``results/``. This module is the
bundle-level gate:

- Every roadmapped artifact exists and is non-empty (AGENTS.md §6
  "dashboard data presence", at the artifact level, resolved from config paths).
- The artifact gates files (roi / counterfactuals / sensitivity / uplift /
  target_segments) all report ``passed == True`` — deterministic records, not
  just in-code assertions (non-vacuity).
- Every ``label`` column across results CSVs uses the honest vocabulary
  (estimated / simulated / placebo / counterfactual / naive / observed /
  measured) and never asserts causation (AGENTS.md §2/§8).
- Reports never claim a channel "causes" conversion/revenue (correlation ≠
  causation survives into prose too).

Run:  pytest tests/test_artifacts.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from src.config import load_config, project_path

# Per-results-section required files. Section names resolve through the
# config ``results:`` block (no paths hardcoded; only artifact names, which are
# the deliverables contract, live here).
MANIFEST: dict[str, list[str]] = {
    "tables": [
        "master_estimates.csv",
        "naive_estimates.csv",
        "ols_estimates.csv",
        "ipw_estimates.csv",
        "dr_estimates.csv",
        "confounder_audit.csv",
        "cate_estimates.parquet",
        "cate_summary.csv",
        "cate_agreement.csv",
    ],
    "roi": ["roi_summary.csv", "roi_long.csv", "roi_gates.csv"],
    "counterfactuals": ["scenario_summary.csv", "scenarios.csv", "gates.csv"],
    "sensitivity": ["evalue.csv", "bias_formula.csv", "falsification.csv", "gates.csv"],
    "uplift": ["qini_curves.csv", "qini_summary.csv", "segment_summary.csv", "gates.csv"],
    "target_segments": ["target_segments.csv", "guidance.csv", "gates.csv"],
    "figures": [
        "dag_email.html", "dag_social.html", "dag_search.html", "dag_display.html",
        "ps_distribution_email.html", "ps_distribution_social.html",
        "ps_distribution_search.html", "ps_distribution_display.html",
        "ps_overlap_email.html", "ps_overlap_social.html",
        "ps_overlap_search.html", "ps_overlap_display.html",
        "ps_after_email.html", "ps_after_social.html",
        "ps_after_search.html", "ps_after_display.html",
        "smd_before_email.html", "smd_before_social.html",
        "smd_before_search.html", "smd_before_display.html",
        "smd_love_email.html", "smd_love_social.html",
        "smd_love_search.html", "smd_love_display.html",
        "naive_conversion.html", "naive_revenue.html",
        "ols_conversion.html", "ols_revenue.html",
        "ipw_conversion.html", "ipw_revenue.html",
        "dr_conversion.html", "dr_revenue.html",
        "estimator_convergence_conversion.html", "estimator_convergence_revenue.html",
        "cate_by_channel.html", "cate_distribution_conversion.html",
        "learner_agreement_map.html",
        "qini_curves_conversion.html", "qini_curves_revenue.html",
        "uplift_segments_conversion.html", "target_bands_conversion.html",
        "roi_comparison.html", "counterfactual_scenarios.html",
        "evalue.html", "bias_decomposition.html",
    ],
}

REPORTS: list[str] = [
    "confounder_audit.md",
    "naive_estimates.md",
    "ols_estimates.md",
    "ipw_estimates.md",
    "dr_estimates.md",
    "treatment_effects.md",
    "cate_effects.md",
    "uplift_modeling.md",
    "cate_segmentation.md",
    "roi.md",
    "counterfactuals.md",
    "sensitivity.md",
]

# Honest-label roots every result label must carry (AGENTS.md §2/§8).
LABEL_ROOTS: tuple[str, ...] = (
    "estimated",
    "simulated",
    "placebo",
    "counterfactual",
    "naive",
    "observed",
    "measured",
)
_BANNED_LABEL = re.compile(r"established causal|caused by|^\s*causes?\b", re.IGNORECASE)
# A channel causatively moving conversion/revenue — the correlation-vs-causation
# line (AGENTS.md §8). "common cause", "effect, not a cause", "lost cause" are fine.
_BANNED_CLAIM = re.compile(
    r"\b(?:email|social|search|display)\s+causes\b"
    r"|caused by\s+(?:email|social|search|display)\b"
    r"|established causal",
    re.IGNORECASE,
)

GATES_FILES: list[tuple[str, str]] = [
    ("roi", "roi_gates.csv"),
    ("counterfactuals", "gates.csv"),
    ("sensitivity", "gates.csv"),
    ("uplift", "gates.csv"),
    ("target_segments", "gates.csv"),
]


def _paths(section: str) -> Path:
    return project_path("results", section)


def _all_result_csv() -> list[Path]:
    out = []
    for section, names in MANIFEST.items():
        for name in names:
            if name.endswith(".csv"):
                out.append(_paths(section) / name)
    return out


# ---------------------------------------------------------------------------
# Manifest presence — resolved through config, non-empty
# ---------------------------------------------------------------------------


def test_results_sections_resolve_from_config():
    """Every manifest section maps to a real results/ directory via config."""
    cfg = load_config()
    for section in MANIFEST:
        assert section in cfg["results"], f"results.{section} missing from config"
        assert _paths(section).is_dir(), f"results/{section} does not exist"


@pytest.mark.parametrize(
    "section,name",
    [(s, n) for s, names in MANIFEST.items() for n in names],
)
def test_artifact_exists_nonempty(section: str, name: str):
    p = _paths(section) / name
    assert p.is_file(), f"missing artifact {p}"
    assert p.stat().st_size > 0, f"empty artifact {p}"


def test_reports_exist_nonempty():
    for name in REPORTS:
        p = project_path("reports", name)
        assert p.is_file(), f"missing report {p}"
        assert p.stat().st_size > 0, f"empty report {p}"


# ---------------------------------------------------------------------------
# Key tables carry the schemas the downstream consumers rely on
# ---------------------------------------------------------------------------


def test_master_estimates_schema():
    df = pd.read_csv(_paths("tables") / "master_estimates.csv")
    assert {"channel", "outcome", "estimator", "point", "se", "ci_lower",
            "ci_upper", "n", "label"}.issubset(df.columns)


def test_dashboard_data_contract_covered_by_manifest():
    """Every CSV the dashboard builders read (static scan) exists on disk AND is
    in the manifest — the Day-19 "dashboard reads results/ only" guarantee."""
    src = (project_path("src", "dashboard") / "builders.py").read_text(encoding="utf-8")
    reads = set(re.findall(r'_(?:read|maybe)\(cfg, "([a-z_]+)", "([a-z_]+)"\)', src))
    assert reads, "no _read/_maybe calls found — dashboard data contract changed?"
    for section, name in sorted(reads):
        fname = f"{name}.csv"
        assert fname in MANIFEST[section], \
            f"dashboard reads results/{section}/{fname} but manifest omits it"
        assert (_paths(section) / fname).is_file(), \
            f"dashboard reads missing results/{section}/{fname}"


def test_roi_summary_has_cis():
    """Every effect carries a CI — never a bare point (AGENTS.md §6)."""
    df = pd.read_csv(_paths("roi") / "roi_summary.csv")
    assert {"causal_roi", "causal_roi_ci_low", "causal_roi_ci_high"}.issubset(df.columns)
    assert (df["causal_roi_ci_low"] <= df["causal_roi"]).all()
    assert (df["causal_roi_ci_high"] >= df["causal_roi"]).all()


def test_scenario_summary_has_cis():
    """Scenario CIs are on the ESTIMATED (Day-12 DR) scale, above the truth-scale
    net — that gap IS the documented sim_u overstatement (ADR-025: truth net is
    2.7–10.3% of the estimated CI lower bound). Asserting it keeps the honest
    reading visible in the artifact, not hidden."""
    df = pd.read_csv(_paths("counterfactuals") / "scenario_summary.csv")
    assert {"scenario", "net", "net_est_ci_low", "net_est_ci_high",
            "any_extrapolation"}.issubset(df.columns)
    assert (df["net_est_ci_low"] <= df["net_est_ci_high"]).all(), "inverted CI"
    # estimated-scale CI lies strictly above the truth-scale net for every scenario
    assert (df["net_est_ci_low"] > df["net"]).all(), \
        "estimated CI should sit above the truth-scale net (overstatement gap)"


def test_evalue_table_has_cis():
    df = pd.read_csv(_paths("sensitivity") / "evalue.csv")
    assert {"channel", "ate_point", "ci_lower", "ci_upper", "evalue_point",
            "evalue_ci_lower"}.issubset(df.columns)


# ---------------------------------------------------------------------------
# Gate records — every artifact gate file must report green (deterministic)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("section,name", GATES_FILES)
def test_gate_files_all_pass(section: str, name: str):
    df = pd.read_csv(_paths(section) / name)
    assert {"gate", "passed", "value", "threshold"}.issubset(df.columns)
    assert len(df) >= 1, f"{section}/{name} has no gate rows (vacuous)"
    failed = df[~df["passed"].astype(bool)]
    assert failed.empty, f"{section}/{name} gates FAILED:\n{failed.to_string()}"
    # every gate must carry a concrete measured value (non-vacuity)
    assert df["value"].notna().all(), f"{section}/{name} has gates without values"


# ---------------------------------------------------------------------------
# Honest vocabulary — label columns everywhere, and no 'causes' in reports
# ---------------------------------------------------------------------------


def test_every_result_label_is_honest_vocabulary():
    """Every label across results CSVs is honest-labelled, never a causal claim."""
    checked = 0
    for p in _all_result_csv():
        df = pd.read_csv(p)
        if df.empty or "label" not in df.columns:
            continue
        checked += 1
        for value in df["label"].dropna().astype(str):
            low = value.lower()
            assert not _BANNED_LABEL.search(low), f"{p}: banned label {value!r}"
            assert any(root in low for root in LABEL_ROOTS), \
                f"{p}: label outside honest vocabulary {value!r}"
    assert checked >= 10, f"label audit did not cover enough files ({checked})"


def test_no_channel_causes_claim_in_reports():
    """Correlation-vs-causation survives into prose: no channel 'causes' claim."""
    for name in REPORTS:
        text = (project_path("reports", name)).read_text(encoding="utf-8")
        hits = [ln for ln in text.splitlines() if _BANNED_CLAIM.search(ln)]
        assert not hits, f"{name} contains causal claims:\n" + "\n".join(hits[:5])


def test_no_channel_causes_claim_in_csv_labels():
    for p in _all_result_csv():
        df = pd.read_csv(p)
        if df.empty or "label" not in df.columns:
            continue
        for value in df["label"].dropna().astype(str):
            assert not _BANNED_CLAIM.search(value), f"{p}: {value!r}"