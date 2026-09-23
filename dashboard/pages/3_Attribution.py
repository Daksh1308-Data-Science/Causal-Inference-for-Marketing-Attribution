"""Day-19 dashboard page 3 — channel attribution (naive vs causal vs counterfactual)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import load_config
from src.dashboard.builders import attribution_page

st.set_page_config(page_title="Channel Attribution", layout="wide")
cfg = load_config()
page = attribution_page(cfg)

st.title("Channel attribution — observed vs causal vs counterfactual")
st.plotly_chart(page["figure"], use_container_width=True)

st.subheader("Long-format estimates (with CIs)")
st.dataframe(page["frame"])

st.divider()
st.markdown("#### Honest framing")
for tok in page["tokens"]:
    st.info(tok)
