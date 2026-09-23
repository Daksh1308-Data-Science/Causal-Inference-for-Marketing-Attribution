"""Day-19 dashboard page 5 — counterfactual budget simulator (Day-17 scenarios)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import load_config
from src.dashboard.builders import simulator_page

st.set_page_config(page_title="Budget Simulator", layout="wide")
cfg = load_config()
page = simulator_page(cfg)

st.title("Counterfactual budget simulator (deterministic Day-17 scenarios)")
st.subheader("Scenario ROI (as-run / naive / causal / ctf-guided)")
st.dataframe(page["scenarios"])

st.subheader("ROI long (per channel × method)")
st.dataframe(page["roi_long"])

st.divider()
st.markdown("#### Honest framing")
for tok in page["tokens"]:
    st.info(tok)
