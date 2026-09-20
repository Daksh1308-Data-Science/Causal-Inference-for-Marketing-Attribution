"""Descriptive EDA for the analytical dataset (Day 3).

Observed real-Olist facts only — this module never fabricates marketing
variables. It computes missingness, IQR-outlier flags, and univariate
distribution summaries from `data/processed/customer_analytical.parquet`.

Every function here returns plain pandas objects (DataFrames/Series);
figure rendering lives in src/visualization/plots.py.
"""
from __future__ import annotations

import pandas as pd

# Cost-based business columns analyzed for outliers (revenue drives everything).
REVENUE_COLS = ("total_revenue", "avg_order_value")


def load_analytical() -> pd.DataFrame:
    """Load the Day-2 cohort parquet (94,983 customers)."""
    from src.config import load_config, project_path

    cfg = load_config()
    path = project_path(cfg["paths"]["processed_data"]) / "customer_analytical.parquet"
    return pd.read_parquet(path)


def missingness_report(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column null counts and percentages.

    Column order follows the input; rows with zero missingness are included
    so the report doubles as a schema overview.
    """
    report = pd.DataFrame(
        {
            "column": df.columns,
            "n_missing": df.isna().sum().values,
            "pct_missing": (df.isna().mean() * 100).round(2).values,
        }
    )
    return report.sort_values("n_missing", ascending=False).reset_index(drop=True)


def iqr_outlier_flags(df: pd.DataFrame, cols: tuple[str, ...] = REVENUE_COLS) -> pd.DataFrame:
    """IQR-based (k=1.5) outlier flags for the given numeric columns.

    Returns a frame with one column per input column containing a boolean
    mask (True = IQR outlier). Uses per-column Q1/Q3 so thresholds are
    distribution-specific. Missing values are never flagged.
    """
    flags = {}
    for col in cols:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        flags[col] = df[col].notna() & ((df[col] < lo) | (df[col] > hi))
    return pd.DataFrame(flags, index=df.index)


def outlier_summary(df: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """Counts + bounds per flagged column (handy table for EDA narrative)."""
    rows = []
    for col in flags.columns:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        rows.append(
            {
                "column": col,
                "q1": round(q1, 2),
                "q3": round(q3, 2),
                "iqr": round(iqr, 2),
                "lower_fence": round(q1 - 1.5 * iqr, 2),
                "upper_fence": round(q3 + 1.5 * iqr, 2),
                "n_outliers": int(flags[col].sum()),
                "pct_outliers": round(100 * flags[col].mean(), 2),
            }
        )
    return pd.DataFrame(rows)


def distribution_summary(df: pd.DataFrame, cols: tuple[str, ...]) -> pd.DataFrame:
    """Univariate summary: n, mean, sd, min, quartiles, max, skew, kurtosis.

    skew/kurtosis use pandas (Fisher skew; excess kurtosis). Rows with
    missing values are dropped per column.
    """
    rows = []
    for col in cols:
        s = df[col].dropna()
        rows.append(
            {
                "column": col,
                "n": len(s),
                "mean": round(s.mean(), 2),
                "std": round(s.std(), 2),
                "min": round(s.min(), 2),
                "q25": round(s.quantile(0.25), 2),
                "median": round(s.median(), 2),
                "q75": round(s.quantile(0.75), 2),
                "max": round(s.max(), 2),
                "skew": round(s.skew(), 2),
                "kurtosis": round(s.kurt(), 2),
            }
        )
    return pd.DataFrame(rows)


NUMERIC_COLS = (
    "tenure_days",
    "recency_days",
    "order_count",
    "total_revenue",
    "avg_order_value",
    "review_score_avg",
    "review_count",
)