"""Bulk-load the 9 Olist CSVs from data/raw/ into MySQL (Day 2).

Pipeline: run schema.sql (drop+create, FK-safe order) -> pandas read -> bulk
executemany (one transaction per table) -> ANALYZE TABLE -> load report at
data/processed/_load_report.json.

Dirty-data handling (reported, not hidden):
  * empty review_id in order_reviews -> surrogate uuid4 (count reported)
  * empty payment_type -> 'unknown' (count reported)
  * empty strings / NaN / NaT -> NULL

Usage:
    python -m src.data.load_olist
"""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

import pandas as pd
import pymysql
from pymysql.constants import CLIENT

from src.config import project_path, load_config
from src.data.mysql import connect

BATCH_SIZE = 25_000

# column -> pandas dtype for cheap, robust reads
FLOAT_COLS = ["price", "freight_value", "payment_value"]
INT_COLS = [
    "customer_zip_code_prefix",
    "seller_zip_code_prefix",
    "geolocation_zip_code_prefix",
    "order_item_id",
    "payment_sequential",
    "payment_installments",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
    "review_score",
]
DATE_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
    "shipping_limit_date",
    "review_creation_date",
    "review_answer_timestamp",
]
# raw file -> table name
TABLES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "product_category_name_translation",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
}


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a raw Olist CSV, discriminating dtypes + empty strings -> NaN."""
    dtypes = {
        col: "float64" for col in FLOAT_COLS
    } | {
        col: "Int64" for col in INT_COLS
    }  # Int64 keeps NA instead of coercing to float
    df = pd.read_csv(
        path,
        dtype=dtypes,
        keep_default_na=False,
        na_values=["", "null"],
    )
    # 'null' na_values changes text; drop na handling for string columns below
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize pandas NA to None and string empties to None (except keys we fix)."""
    for col in df.columns:
        if col in DATE_COLS and col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _native(row: tuple) -> tuple:
    """Convert a pandas row to native Python types pymysql accepts happily."""
    out = []
    for v in row:
        if v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v):
            out.append(None)
        elif isinstance(v, pd.Timestamp):
            out.append(v.to_pydatetime())
        elif hasattr(v, "item"):  # numpy scalars
            out.append(v.item())
        else:
            out.append(v)
    return tuple(out)


def _exec_many(cur: pymysql.cursors.Cursor, sql: str, df: pd.DataFrame) -> int:
    total = 0
    tuples = [tuple(r) for r in df.astype(object).to_numpy()]
    for i in range(0, len(tuples), BATCH_SIZE):
        batch = [_native(r) for r in tuples[i : i + BATCH_SIZE]]
        if batch:
            cur.executemany(sql, batch)
            total += len(batch)
    return total


def _run_ddl(conn: pymysql.Connection) -> None:
    """Execute schema.sql in one multi-statement call (MULTI_STATEMENTS flag)."""
    schema = (project_path("sql") / "schema.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(schema)
    conn.commit()


def _insert_table(conn: pymysql.Connection, raw_name: str, table: str) -> dict:
    cfg = load_config()
    raw_dir = project_path(cfg["paths"]["raw_data"])
    df = _clean(_read_csv(raw_dir / raw_name))
    metrics: dict = {}

    if table == "order_reviews":
        empty_mask = df["review_id"].astype(str).str.strip() == ""
        metrics["review_id_empty_imputed"] = int(empty_mask.sum())
        df.loc[empty_mask, "review_id"] = [
            uuid.uuid4().hex for _ in range(int(empty_mask.sum()))
        ]
        dup_mask = df["review_id"].duplicated(keep="first")
        metrics["review_id_duplicate_imputed"] = int(dup_mask.sum())
        df.loc[dup_mask, "review_id"] = [
            uuid.uuid4().hex for _ in range(int(dup_mask.sum()))
        ]
    if table == "order_payments":
        mask = df["payment_type"].astype(str).str.strip() == ""
        metrics["payment_type_empty_to_unknown"] = int(mask.sum())
        df.loc[mask, "payment_type"] = "unknown"

    cols = [c for c in df.columns]
    ph = ",".join(["%s"] * len(cols))
    sql = f"INSERT INTO `{table}` ({','.join('`'+c+'`' for c in cols)}) VALUES ({ph})"

    with conn.cursor() as cur:
        inserted = _exec_many(cur, sql, df)
        conn.commit()
    metrics["rows"] = inserted
    metrics["source_rows"] = int(len(df))
    return metrics


def main() -> int:
    cfg = load_config()
    conn = connect(autocommit=False, client_flag=CLIENT.MULTI_STATEMENTS)

    try:
        _run_ddl(conn)
        report: dict = {"tables": {}}
        # FK-parents first (same order as sql/load.sql contract)
        load_order = [
            "olist_customers_dataset.csv",
            "olist_geolocation_dataset.csv",
            "olist_products_dataset.csv",
            "olist_sellers_dataset.csv",
            "product_category_name_translation.csv",
            "olist_orders_dataset.csv",
            "olist_order_items_dataset.csv",
            "olist_order_payments_dataset.csv",
            "olist_order_reviews_dataset.csv",
        ]
        for raw_name in load_order:
            table = TABLES[raw_name]
            m = _insert_table(conn, raw_name, table)
            report["tables"][table] = m
            print(f"  {table:34s} {m['rows']:>9,} rows" +
                  (f"  (empty review_id -> surrogate {m['review_id_empty_imputed']})" if "review_id_empty_imputed" in m else "") +
                  (f"  (dup review_id -> surrogate {m['review_id_duplicate_imputed']})" if "review_id_duplicate_imputed" in m else "") +
                  (f"  (empty type -> unknown {m['payment_type_empty_to_unknown']})" if "payment_type_empty_to_unknown" in m else ""))

        with conn.cursor() as cur:
            cur.execute(
                "ANALYZE TABLE customers, geolocation, products, sellers, "
                "product_category_name_translation, orders, order_items, "
                "order_payments, order_reviews"
            )
            conn.commit()

        out = project_path(cfg["paths"]["processed_data"]) / "_load_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nLoad report -> {out}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())