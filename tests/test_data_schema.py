"""Day 2 acceptance tests: data schema, cohort definition, processed dataset.

Covers the Day 2 validation hook from docs/roadmap.md:
"Schema tests pass · no dupes · RFM plausible".

Requires: MySQL olist DB loaded (Day 1/2 pipeline) and the processed parquet.
Skipped gracefully if the DB / parquet is absent (env gate covers connectivity).
"""
from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import text

from src.config import load_config, project_path


def q(conn, sql: str):
    """Execute a read statement against a SQLAlchemy connection."""
    return conn.execute(text(sql))


# --- fixtures ----------------------------------------------------------------

@pytest.fixture(scope="module")
def db():
    """Live MySQL connection for the olist project DB (skips if unavailable)."""
    from src.data.mysql import engine as make_engine

    try:
        eng = make_engine()
        with eng.connect() as c:
            q(c, "SELECT 1")
        return eng
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"MySQL unavailable: {type(exc).__name__}: {str(exc)[:120]}")


@pytest.fixture(scope="module")
def analytical_df():
    """Processed analytical parquet (skips if not built)."""
    cfg = load_config()
    path = project_path(cfg["paths"]["processed_data"]) / "customer_analytical.parquet"
    if not path.exists():
        pytest.skip(f"analytical parquet missing: {path}")
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def manifest():
    """Verified row counts for the raw files (data/raw/_manifest.json)."""
    import json

    p = project_path(load_config()["paths"]["raw_data"]) / "_manifest.json"
    if not p.exists():
        pytest.skip(f"manifest missing: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


# --- 1. raw manifest vs DB table row counts ---------------------------------

RAW_TABLES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
    "geolocation": "olist_geolocation_dataset.csv",
}


@pytest.mark.parametrize("table,file", RAW_TABLES.items())
def test_raw_rows_match_manifest(db, manifest, table, file):
    """Every loaded table matches the verified row count of its source file."""
    expected = manifest[file]["rows"]
    with db.connect() as c:
        got = q(c, f"SELECT COUNT(*) FROM `{table}`").scalar()
    assert got == expected, f"{table}: {got} rows in DB vs {expected} in manifest"


def test_all_9_raw_tables_present(db):
    """All 9 Olist source tables exist in the olist schema."""
    with db.connect() as c:
        tables = {
            r[0]
            for r in q(
                c,
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'",
            )
        }
    assert RAW_TABLES.keys() <= tables, RAW_TABLES.keys() - tables


# --- 2. primary-key integrity (no dupes, no null keys) ----------------------

PK_TABLES = {
    "orders": "order_id",
    "customers": "customer_id",
    "order_items": ("order_id", "order_item_id"),
    "order_payments": ("order_id", "payment_sequential"),
    "order_reviews": "review_id",  # 814 source dupes got surrogate UUIDs (Day 2)
    "products": "product_id",
    "sellers": "seller_id",
    "product_category_name_translation": "product_category_name",
}


@pytest.mark.parametrize("table,pk", PK_TABLES.items())
def test_no_duplicate_primary_keys(db, table, pk):
    """Declared key columns are unique and non-null (no dupes)."""
    cols = pk if isinstance(pk, tuple) else (pk,)
    col_sql = ", ".join(f"`{col}`" for col in cols)
    first_col = f"`{cols[0]}`"
    with db.connect() as c:
        total = q(c, f"SELECT COUNT(*) FROM `{table}`").scalar()
        distinct = q(
            c, f"SELECT COUNT(*) FROM (SELECT DISTINCT {col_sql} FROM `{table}`) t"
        ).scalar()
        nulls = q(c, f"SELECT COUNT(*) FROM `{table}` WHERE {first_col} IS NULL").scalar()
    assert distinct == total, f"{table}: {total} rows but only {distinct} distinct keys"
    assert nulls == 0, f"{table}: {nulls} null keys"


# --- 3. cohort definition ----------------------------------------------------

def test_analytical_cohort_count(db):
    """Cohort = customers with >=1 purchased order (valid status AND >=1 item)."""
    with db.connect() as c:
        n = q(c, "SELECT COUNT(*) FROM v_customer_analytical").scalar()
    assert n == 94_983, f"cohort count {n} != expected 94,983"


def test_cohort_is_purchased_only(db):
    """No cohort member has ONLY non-purchased orders (no-item/status-excluded)."""
    with db.connect() as c:
        bad = q(
            c,
            """
            SELECT COUNT(*) FROM v_customer_analytical c
            WHERE NOT EXISTS (
                SELECT 1 FROM orders o
                JOIN order_items i ON i.order_id = o.order_id
                WHERE o.customer_id IN (
                    SELECT customer_id FROM customers cu
                    WHERE cu.customer_unique_id = c.customer_id
                )
                AND o.order_status NOT IN ('canceled', 'unavailable')
            )
            """,
        ).scalar()
    assert bad == 0, f"{bad} cohort members have no purchased order"


# --- 4. processed parquet: schema, dupes, RFM plausibility ------------------

def test_analytical_parquet_schema(analytical_df):
    """Expected 12 columns with correct dtypes."""
    expected_cols = [
        "customer_id", "first_order_date", "last_order_date", "tenure_days",
        "recency_days", "order_count", "total_revenue", "avg_order_value",
        "category_affinity_top", "state", "review_score_avg", "review_count",
    ]
    assert list(analytical_df.columns) == expected_cols
    assert pd.api.types.is_string_dtype(analytical_df["customer_id"])
    assert analytical_df["tenure_days"].dtype.kind in "iu"
    assert analytical_df["order_count"].dtype.kind in "iu"
    assert analytical_df["total_revenue"].dtype.kind == "f"


def test_parquet_has_all_customers_analytical_df_present(analytical_df):
    assert analytical_df["customer_id"].nunique() == len(analytical_df)  # no dupes


def test_parquet_no_null_keys_or_revenue(analytical_df):
    assert analytical_df["customer_id"].isna().sum() == 0
    assert analytical_df["total_revenue"].isna().sum() == 0
    assert analytical_df["order_count"].isna().sum() == 0


def test_rfm_plausible(analytical_df):
    """RFM sanity: >=1 order, non-negative revenue, sane date/tenure ranges."""
    assert analytical_df["order_count"].min() == 1
    assert (analytical_df["total_revenue"] >= 0).all()
    assert (analytical_df["tenure_days"] >= 0).all()
    assert (analytical_df["recency_days"] >= 0).all()
    # data spans 2016-09 .. 2018-09 (documented Olist window)
    assert analytical_df["first_order_date"].min().year == 2016
    assert analytical_df["last_order_date"].max().year == 2018
    # most customers are one-time buyers (documented Olist reality)
    assert analytical_df["order_count"].value_counts().get(1, 0) / len(analytical_df) > 0.9


def test_revenue_tracks_order_count(analytical_df):
    """Expected economic signal: customers with more orders have more revenue."""
    group = analytical_df.groupby("order_count")["total_revenue"].mean()
    assert group[2] > group[1]  # avg revenue of repeat buyers > single buyers