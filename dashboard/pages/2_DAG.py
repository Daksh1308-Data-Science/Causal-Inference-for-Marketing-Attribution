"""Day-19 dashboard page 2 — interactive causal DAG per channel."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import load_config
from src.dashboard.builders import dag_page

st.set_page_config(page_title="DAG — Causal Structure", layout="wide")
cfg = load_config()
page = dag_page(cfg)

st.title("Causal DAG per channel")
channels = list(page["figures"].keys())
tab = st.tabs(channels)
for t, ch in zip(tab, channels):
    with t:
        st.plotly_chart(page["figures"][ch], use_container_width=True)

st.divider()
st.markdown("#### Honest framing")
for tok in page["tokens"]:
    st.info(tok)
