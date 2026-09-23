"""Bundle of the Day-19 Streamlit dashboard.

The user-facing app lives in :mod:`dashboard` (``streamlit run dashboard/app.py``)
and renders seven pages headlessly-testable via ``streamlit.testing.v1.AppTest``.
All page content is built by the pure, deterministic, read-only builders in
:mod:`src.dashboard.builders`, which read ONLY the precomputed ``results/`` CSVs
(the dashboard performs no refits, no DGP reruns, no random draws) so every page
is fast, reproducible, and honest (AGENTS.md §8, blueprint §11).
"""
