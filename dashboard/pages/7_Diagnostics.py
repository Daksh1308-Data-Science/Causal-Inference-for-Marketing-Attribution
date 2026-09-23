"""Day-19 dashboard page 7 — model diagnostics (CIs, balance, agreement, placebo)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import load_config
from src.dashboard.builders import diagnostics_page

st.set_page_config(page_title="Model Diagnostics", layout="wide")
cfg = load_config()
page = diagnostics_page(cfg)

st.title("Model diagnostics — every effect with a CI")
st.subheader("Master estimates (with CIs)")
st.dataframe(page["master"])
st.subheader("E-values")
st.dataframe(page["evalue"])

st.divider()
st.markdown("#### Honest framing")
for tok in page["tokens"]:
    st.info(tok)
