"""Day 5 acceptance tests: causal DAGs are constructed and match the audit.

Covers the Day 5 validation hook from docs/roadmap.md:
"Adjustment set matches audit"

Validates:
- Per-channel DAG HTML files are generated
- DAG nodes include treatment, outcome(s), confounders, unobserved U, conceptual mediator/collider
- Adjustment sets from DAG match the confounder audit's adjustment_sets()
- DoWhy identification (or fallback) returns correct backdoor variables
- Backdoor paths listed include all observed confounders + sim_u
- No pygraphviz dependency (networkx + plotly only)
"""
from __future__ import annotations

import pytest
from pathlib import Path

from src.config import load_config, project_path
from src.causal.dag import (
    render_dag_plotly,
    render_all_dags,
    dag_summary,
    identify_effect,
    build_dowhy_model,
    CHANNELS,
)
from src.causal.confounders import adjustment_sets


def test_dag_html_files_exist():
    """DAG HTML files generated for all 4 channels."""
    cfg = load_config()
    paths = render_all_dags(cfg)
    assert len(paths) == 4
    for ch in CHANNELS:
        assert paths[ch].exists(), f"Missing DAG HTML: {paths[ch]}"
        assert paths[ch].suffix == ".html"


def test_dag_nodes_include_required():
    """Each DAG has treatment, outcome, confounders, U, mediator, collider."""
    for ch in CHANNELS:
        summary = dag_summary(ch)
        assert f"sim_exposed_{ch}" in summary
        assert "sim_converted_14d" in summary
        assert "sim_revenue_14d" in summary
        assert "sim_u" in summary
        assert "click/session" in summary
        assert "co-exposure" in summary.lower()


def test_adjustment_sets_match_audit():
    """DAG adjustment sets must exactly match confounder audit's adjustment_sets()."""
    cfg = load_config()
    for ch in CHANNELS:
        summary = dag_summary(ch)
        # Extract adjustment set from summary
        import re
        match = re.search(r"Sufficient Adjustment Set \(observed\)\n([^#]+)", summary)
        assert match, f"No adjustment set found in summary for {ch}"
        adj_text = match.group(1).strip()
        adj_vars = [v.strip("` ") for v in adj_text.split(",")]
        expected = adjustment_sets(cfg)[ch]
        assert sorted(adj_vars) == sorted(expected), f"Mismatch for {ch}: {adj_vars} vs {expected}"


def test_backdoor_paths_include_confounders():
    """Each backdoor path listed corresponds to an actual confounder."""
    cfg = load_config()
    for ch in CHANNELS:
        summary = dag_summary(ch)
        confounders = adjustment_sets(cfg)[ch]
        for c in confounders:
            assert f"← `{c}` →" in summary, f"Backdoor path for {c} missing in {ch} summary"


def test_backdoor_paths_include_sim_u():
    """Unobserved confounder sim_u appears as unblocked backdoor path."""
    for ch in CHANNELS:
        summary = dag_summary(ch)
        assert "sim_u" in summary
        assert "UNOBSERVED" in summary


def test_identify_effect_returns_backdoor_vars():
    """identify_effect returns correct backdoor variables per channel."""
    cfg = load_config()
    for ch in CHANNELS:
        estimand = identify_effect(ch, cfg)
        assert hasattr(estimand, "backdoor_variables")
        assert sorted(estimand.backdoor_variables) == sorted(adjustment_sets(cfg)[ch])


def test_build_dowhy_model_creates_model():
    """build_dowhy_model returns a CausalModel instance."""
    for ch in CHANNELS:
        model = build_dowhy_model(ch)
        assert model is not None
        assert hasattr(model, "identify_effect")


def test_no_pygraphviz_import():
    """Module does not import pygraphviz (native-build risk on Windows)."""
    import src.causal.dag as dag_module
    import sys
    # pygraphviz should not be in the module's globals or imported
    assert "pygraphviz" not in dag_module.__dict__
    # Also not in sys.modules from our import
    # (it may be in sys.modules if something else imported it, but not by us)


def test_dag_summary_structure():
    """dag_summary has all required sections."""
    for ch in CHANNELS:
        s = dag_summary(ch)
        assert "## Nodes" in s
        assert "## Edges" in s
        assert "## Backdoor Paths" in s
        assert "## Sufficient Adjustment Set" in s
        assert "## Paths Closed by Adjustment" in s
        assert "## Remaining Open Path" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v"])