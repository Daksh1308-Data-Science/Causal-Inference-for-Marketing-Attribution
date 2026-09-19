"""Export the customer analytical table (Day 2).

Creates the v_customer_analytical view from sql/analytics/customer_analytical.sql,
then materializes it to data/processed/customer_analytical.parquet.

Usage:
    python -m src.data.build_analytical
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from src.config import load_config, project_path
from src.data.mysql import engine

VIEW_SQL = project_path("sql") / "analytics" / "customer_analytical.sql"


def main() -> int:
    cfg = load_config()
    eng = engine()

    with eng.begin() as conn:
        conn.execute(text(VIEW_SQL.read_text(encoding="utf-8")))

    df = pd.read_sql("SELECT * FROM v_customer_analytical", eng)
    # DECIMAL columns come back as Decimal -> float for downstream math
    for col in ("total_revenue", "avg_order_value", "review_score_avg"):
        if col in df:
            df[col] = df[col].astype(float)
    df["review_count"] = df["review_count"].fillna(0).astype("int64")
    df["first_order_date"] = pd.to_datetime(df["first_order_date"])
    df["last_order_date"] = pd.to_datetime(df["last_order_date"])

    out_dir = project_path(cfg["paths"]["processed_data"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "customer_analytical.parquet"
    df.to_parquet(out, index=False)
    print(f"wrote {len(df):,} customers x {len(df.columns)} cols -> {out}")
    print(df.dtypes.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())