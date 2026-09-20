"""Export the order-level monthly activity table (Day 3).

Materializes v_order_monthly (sql/analytics/order_monthly.sql) to
data/processed/order_monthly.parquet — the backbone for acquisition-cohort
and retention analysis in the EDA notebook.

Usage:
    python -m src.data.build_order_monthly
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from src.config import load_config, project_path
from src.data.mysql import engine

VIEW_SQL = project_path("sql") / "analytics" / "order_monthly.sql"


def main() -> int:
    cfg = load_config()
    eng = engine()

    with eng.begin() as conn:
        conn.execute(text(VIEW_SQL.read_text(encoding="utf-8")))

    df = pd.read_sql("SELECT * FROM v_order_monthly", eng)
    df["customer_id"] = df["customer_id"].astype(str)
    df["purchase_month"] = pd.to_datetime(df["purchase_month"]).dt.to_period("M").dt.to_timestamp()
    df["revenue"] = df["revenue"].astype(float)

    out_dir = project_path(cfg["paths"]["processed_data"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "order_monthly.parquet"
    df.to_parquet(out, index=False)
    print(f"wrote {len(df):,} customer-month rows -> {out}")
    print(f"distinct customers: {df['customer_id'].nunique():,} | total orders: {df['order_count'].sum():,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())