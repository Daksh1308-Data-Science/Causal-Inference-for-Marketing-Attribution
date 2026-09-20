"""Environment gate (Day 1) — the project does not start if this fails.

Verifies, from the repo root:
  * Python version (project targets 3.14)
  * every pinned package imports
  * DoWhy 0.8 classic API is present (CausalModel + identify_effect + estimate_effect)
  * the raw Olist manifest from configs/config.yaml verifies (skips if data absent)
  * a live MySQL connection works with the credentials in .env (skips if no .env)

Run:  pytest tests/test_gate_env.py -v
"""
from __future__ import annotations

import importlib
import json
import sys

import pymysql
import pytest

from src.config import load_config, load_env, project_path

REQUIRED_PACKAGES = [
    "pandas",
    "numpy",
    "pyarrow",
    "yaml",
    "dotenv",
    "pymysql",
    "sqlalchemy",
    "statsmodels",
    "scipy",
    "sklearn",
    "lightgbm",
    "xgboost",
    "dowhy",
    "causalml",
    "econml",
    "matplotlib",
    "seaborn",
    "plotly",
    "networkx",
    "nbformat",
    "nbclient",
    "ipykernel",
    "tabulate",
    "streamlit",
]


def test_python_version() -> None:
    assert sys.version_info >= (3, 10), "Python >= 3.10 required"


@pytest.mark.parametrize("pkg", REQUIRED_PACKAGES)
def test_package_importable(pkg: str) -> None:
    importlib.import_module(pkg)


def test_dowhy_classic_api() -> None:
    import dowhy

    assert dowhy.__version__ == "0.8", "pitched to the classical DoWhy 0.8 API"
    from dowhy import CausalModel  # classic interface

    assert hasattr(CausalModel, "identify_effect")
    assert hasattr(CausalModel, "estimate_effect")


def test_config_loads() -> None:
    cfg = load_config()
    assert cfg["paths"]["raw_data"] == "data/raw"
    assert cfg["olist"]["files"]["olist_orders_dataset.csv"]["rows"] == 99441


def test_raw_manifest_verifies() -> None:
    """All 9 raw Olist files present with rows matching the documented counts."""
    cfg = load_config()
    manifest_path = project_path(cfg["paths"]["raw_data"], "_manifest.json")
    if not manifest_path.exists():
        pytest.skip("raw data not downloaded yet (run src.data.download_olist)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for fname, spec in cfg["olist"]["files"].items():
        assert fname in manifest, f"{fname} missing from manifest"
        assert manifest[fname]["ok"], (
            f"{fname}: {manifest[fname]['rows']} rows, "
            f"expected {manifest[fname]['expected_rows']}"
        )


def test_db_connection() -> None:
    env = load_env()
    if not env:
        pytest.skip("no .env — MySQL credentials not configured")
    conn = pymysql.connect(
        host=env.get("DB_HOST", "localhost"),
        port=int(env.get("DB_PORT", "3306")),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION()")
            version = cur.fetchone()[0]
        assert version.startswith("8."), f"expected MySQL 8.x, got {version}"
    finally:
        conn.close()