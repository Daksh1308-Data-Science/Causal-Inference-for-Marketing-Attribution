"""Day-19 dashboard page 6 — sensitivity analysis (E-values, bias formula, falsification)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import load_config
from src.dashboard.builders import sensitivity_page

st.set_page_config(page_title="Sensitivity Analysis", layout="wide")
cfg = load_config()
page = sensitivity_page(cfg)

st.title("Sensitivity analysis — how strong must an unmeasured confounder be?")
st.subheader("E-values (per channel)")
st.dataframe(page["evalue"])
st.subheader("Bias formula")
st.dataframe(page["bias_formula"])
st.subheader("Falsification / placebo tests")
st.dataframe(page["falsification"])

st.divider()
st.markdown("#### Honest framing")
for tok in page["tokens"]:
    st.error(tok) if "NOT" in tok.upper() or "not established" in tok.lower() else st.info(tok)
