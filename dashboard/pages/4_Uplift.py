"""Day-19 dashboard page 4 — uplift segments (persuadables) + Qini curve."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import load_config
from src.dashboard.builders import uplift_page

st.set_page_config(page_title="Uplift Segments", layout="wide")
cfg = load_config()
page = uplift_page(cfg)

st.title("Uplift segments (model-based Day-14 CATE)")
st.plotly_chart(page["figure"], use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Segment summary")
    st.dataframe(page["segments"])
with c2:
    st.subheader("Qini curves")
    st.dataframe(page["qini"])

st.divider()
st.markdown("#### Honest framing")
for tok in page["tokens"]:
    st.info(tok)
