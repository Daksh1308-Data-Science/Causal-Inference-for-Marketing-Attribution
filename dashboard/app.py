"""Day-19 dashboard entry point — executive summary (page 1).

Thin Streamlit glue over :mod:`src.dashboard.builders` (pure, headless-testable
builders that read precomputed ``results/`` only). Honest framing is
non-negotiable (AGENTS.md §8): headline + KPI cards are wired to Day-13/16/17
numbers with the honest label vocabulary imported from
:mod:`src.causal.sensitivity` — never re-declared here.
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- Repo-root bootstrap (works under `streamlit run` from repo root AND AppTest) ---
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import load_config
from src.dashboard.builders import exec_summary

st.set_page_config(page_title="Marketing Attribution — Honest Causal Dashboard", layout="wide")

cfg = load_config()
page = exec_summary(cfg)

st.title(page["headline"])
st.caption("Observed-data lift is confounder-compatible and fragile — NOT established causal (Day 18).")

# --- Honest KPI cards ---
cols = st.columns(len(page["kpis"]))
for col, kpi in zip(cols, page["kpis"]):
    col.metric(
        label=kpi["label"],
        value=kpi["value"],
        delta=kpi.get("delta"),
        help=kpi.get("help"),
    )

st.divider()

# --- Frames ---
st.subheader("ROI summary (observed vs causal, per channel)")
st.dataframe(page["frames"]["roi_summary"])

st.subheader("Budget scenarios (as-run / naive / causal / ctf-guided)")
st.dataframe(page["frames"]["scenario_summary"])

# --- Honest tokens ---
st.divider()
st.markdown("#### Honest framing")
for tok in page["tokens"]:
    st.error(tok) if "NOT" in tok.upper() or "not established" in tok.lower() else st.info(tok)
