"""Acquisition-cohort and retention analysis (Day 3).

Consumes the order-level monthly activity table
(`data/processed/order_monthly.parquet`, built by src.data.build_order_monthly)
and produces:

* acquisition cohorts: distinct customers whose first purchase fell in month M
* cohort retention: share of a cohort placing >=1 order in each subsequent
  month (classic "months since first order" retention matrix)

All inputs are observed real Olist order facts; nothing here is simulated.
"""
from __future__ import annotations

import pandas as pd


def load_order_monthly() -> pd.DataFrame:
    """Load the order-monthly activity parquet."""
    from src.config import load_config, project_path

    cfg = load_config()
    path = project_path(cfg["paths"]["processed_data"]) / "order_monthly.parquet"
    return pd.read_parquet(path)


def acquisition_cohorts(order_monthly: pd.DataFrame) -> pd.DataFrame:
    """One row per acquisition month: cohort month + number of new customers.

    A customer's cohort is the first calendar month in which they placed a
    purchased order. Rows are sorted ascending by cohort month.
    """
    first = (
        order_monthly.groupby("customer_id")["purchase_month"].min().rename("cohort_month")
    )
    cohort_sizes = (
        first.groupby(first.dt.strftime("%Y-%m")).size().rename("n_customers")
    )
    return cohort_sizes.reset_index().rename(columns={"index": "cohort_month"})


def retention_matrix(order_monthly: pd.DataFrame, max_months: int = 12) -> pd.DataFrame:
    """Retention matrix: rows = acquisition month, cols = months since first order.

    Values are percentages (0-100): of customers acquired in the cohort
    month, what share placed at least one purchased order in that month
    offset (0 = acquisition month itself). Month offset is capped at
    ``max_months``.

    NOTE (observed-data truth): Olist retention is structurally low (the
    dataset is ~94% one-time buyers, per docs/data-feasibility.md §2), so
    columns beyond offset 0 drop steeply.
    """
    first = (
        order_monthly.groupby("customer_id")["purchase_month"].min().rename("cohort_month")
    )
    df = order_monthly.join(first, on="customer_id").copy()
    # months since first order = 12*(y2-y1) + (m2-m1)
    y = df["purchase_month"].dt.year - df["cohort_month"].dt.year
    m = df["purchase_month"].dt.month - df["cohort_month"].dt.month
    df["months_since"] = 12 * y + m
    df = df[df["months_since"] <= max_months]

    # customers active in each (cohort, offset) cell
    active = (
        df.groupby(["cohort_month", "months_since"])["customer_id"].nunique().unstack("months_since")
    )
    cohort_size = (
        df.groupby("cohort_month")["customer_id"].nunique().rename("cohort_size")
    )
    # convert to percentage of the cohort, fill structurally-missing offsets
    retention = active.div(cohort_size, axis=0) * 100
    retention = retention.reindex(
        columns=range(0, max_months + 1)
    ).fillna(0.0).round(2)

    retention.index = retention.index.strftime("%Y-%m")
    retention.index.name = "cohort_month"
    retention.columns = [f"m+{c}" for c in retention.columns]
    return retention.reset_index()


def cohort_summary(order_monthly: pd.DataFrame) -> pd.DataFrame:
    """Monthly aggregates: rows, distinct customers, orders, revenue per month."""
    key = order_monthly["purchase_month"].dt.strftime("%Y-%m")
    g = (
        order_monthly.assign(_month=key)
        .groupby("_month")
        .agg(
            n_customer_months=("customer_id", "size"),
            n_customers=("customer_id", "nunique"),
            n_orders=("order_count", "sum"),
            revenue=("revenue", "sum"),
        )
        .reset_index()
        .rename(columns={"_month": "month"})
    )
    g["revenue"] = g["revenue"].round(2)
    return g