"""Build + execute notebooks/01_eda.ipynb (Day 3).

Constructs the EDA notebook from narrative markdown + code cells that call
the modular analysis in src/ (AGENTS.md §6: notebooks carry the narrative,
logic lives in modules), then EXECUTES it for real with the registered
`causal-marketing` kernel so every figure/table in the committed notebook
is a genuine output — never fabricated.

Usage:
    python -m scripts.build_notebook_01
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "01_eda.ipynb"

# --- cell sources (narrative markdown + code) ---------------------------------

CELLS: list[tuple[str, str]] = [
    (
        "markdown",
        """# 01 — Exploratory Data Analysis (Day 3)

Causal Inference for Marketing Attribution — **Week 1, Stage 1**.

**Dataset:** Brazilian E-Commerce (Olist) — real customer/order observations.
**Cohort:** 94,983 customers with ≥1 *purchased order* (Day 2, `v_customer_analytical`).

**Labelling convention (AGENTS.md §2):** everything below is **observed** real-Olist
data until the final section, which shows a clearly-labelled **simulated** marketing
preview (`sim_*`). Simulated numbers are never presented as Olist facts.
""",
    ),
    (
        "code",
        """# --- setup ---------------------------------------------------------------
import sys
from pathlib import Path
ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
%matplotlib inline
import matplotlib.pyplot as plt
import pandas as pd

from src.features import eda, cohorts, rfm
from src.visualization import plots
from simulation.simulate_marketing import build_sim_preview, load_backbone, channel_descriptive_stats

results = plots.figures_dir()
print(f"figures -> {results}")
""",
    ),
    (
        "markdown",
        """## 1. Analytical cohort overview (observed)

Load the Day-2 customer analytical table and confirm the documented scale:
~96k unique customers, ~100k orders (raw), purchased cohort 94,983 / 98,199 orders.
""",
    ),
    (
        "code",
        """df = eda.load_analytical()
print(f"customers: {len(df):,}")
print(f"total purchased orders: {df['order_count'].sum():,}")
print(f"order span: {df['first_order_date'].min().date()} -> {df['last_order_date'].max().date()}")
df.head()
""",
    ),
    (
        "markdown",
        """## 2. Missingness (observed)

Only two columns carry nulls and both are expected: customers without a
reviewable order (684) and without a known top category (1,299).
""",
    ),
    (
        "code",
        """missing = eda.missingness_report(df)
fig = plots.plot_missingness(missing)
plots.save_fig(fig, "01_missingness.png")
missing[missing["n_missing"] > 0]
""",
    ),
    (
        "markdown",
        """## 3. Outliers (observed)

IQR-fence (k=1.5) flags on the revenue columns. Outliers here are real
high-value customers — flagged for the record, **not removed** (they carry
information about the spend distribution and will be confounders, not noise).
""",
    ),
    (
        "code",
        """flags = eda.iqr_outlier_flags(df)
out_sum = eda.outlier_summary(df, flags)
fig = plots.plot_outlier_box(df, eda.REVENUE_COLS, log=True)
plots.save_fig(fig, "02_outliers_revenue.png")
out_sum
""",
    ),
    (
        "markdown",
        """## 4. Distributions (observed)

Olist reality check: revenue/total spend is right-skewed (median R$108 vs a
long tail to R$13k), ~97% of customers are one-time buyers, tenure and
recency are spread across the full 2016-09 → 2018-09 window.
""",
    ),
    (
        "code",
        """dist = eda.distribution_summary(df, eda.NUMERIC_COLS)
fig = plots.plot_hist(df, "total_revenue", log_x=True, title="Total spend per customer (log scale, observed)")
plots.save_fig(fig, "03_revenue_log_hist.png")
fig = plots.plot_hist(df, "order_count", title="Order count per customer (observed)")
plots.save_fig(fig, "04_order_count_hist.png")
dist
""",
    ),
    (
        "code",
        """fig = plots.plot_hist(df, "tenure_days")
plots.save_fig(fig, "05_tenure_hist.png")
fig = plots.plot_hist(df, "review_score_avg", title="Average review score per customer (observed)")
plots.save_fig(fig, "06_review_score_hist.png")
plt.show()
""",
    ),
    (
        "markdown",
        """### 4.1 Geography & category mix (observed)""",
    ),
    (
        "code",
        """fig = plots.plot_state_bar(df)
plots.save_fig(fig, "07_states.png")
fig = plots.plot_top_categories(df, top_n=15)
plots.save_fig(fig, "08_categories.png")
plt.show()
""",
    ),
    (
        "markdown",
        """## 5. Monthly activity / seasonality (observed)

Orders and revenue by purchase month — used for seasonal controls and the
simulation's campaign grid later.
""",
    ),
    (
        "code",
        """om = cohorts.load_order_monthly()
monthly = cohorts.cohort_summary(om)
fig = plots.plot_monthly_activity(monthly)
plots.save_fig(fig, "09_monthly_activity.png")
monthly.tail(8)
""",
    ),
    (
        "markdown",
        """## 6. Acquisition cohorts & retention (observed)

Cohort = calendar month of the customer's **first** purchased order. Retention
is the share of a cohort placing ≥1 further purchased order in months m+0…m+12.
The steep drop-off confirms the documented reality: Olist is structurally a
**one-transaction marketplace** (~97% single-purchase customers), so retention
is a sparse signal — `order_count` and `recency` will dominate RFM-style
features and must be handled with care in the causal design.
""",
    ),
    (
        "code",
        """acq = cohorts.acquisition_cohorts(om)
print(f"acquisition months: {acq['cohort_month'].min()} .. {acq['cohort_month'].max()} (n={len(acq)})")
ret = cohorts.retention_matrix(om, max_months=12)
fig = plots.plot_retention_heatmap(ret)
plots.save_fig(fig, "10_retention_heatmap.png")
ret.head(6)
""",
    ),
    (
        "code",
        """# overall m+1..m+12 retention (mean across cohorts with full history)
full = ret.set_index("cohort_month")[["m+1", "m+3", "m+6", "m+12"]].mean().round(2)
print("mean retention across cohorts with full history:")
print(full.to_string())
""",
    ),
    (
        "markdown",
        """## 7. RFM segmentation (observed)

Scores: **R** = recency quintiles (5 = most recent), **F** = frequency bands
(1 / 2 / 3-4 / 5-9 / 10+ — quantiles would collapse because P(F=1)≈0.97),
**M** = monetary quintiles. Composite `rfm_score = 100R + 10F + M`.

This is a *descriptive* segmentation of observed data; on Days 4-5 it feeds
the confounder audit and the DAG.
""",
    ),
    (
        "code",
        """df_rfm = rfm.add_rfm(df)
seg = rfm.segment_summary(df_rfm)
fig = plots.plot_rfm_segments(seg)
plots.save_fig(fig, "11_rfm_segments.png")
seg
""",
    ),
    (
        "markdown",
        """## 8. Channel descriptive statistics — ⚠️ **SIMULATED PREVIEW**

Olist has **no marketing data** (no campaigns, impressions, spend — see
`docs/data-feasibility.md`). The row below is NOT observed. It is a clearly
labelled preview of the synthetic marketing layer (`sim_*`) that Days 5+
will use to benchmark estimators against known ground truth.

Preview design (config-driven, seed-fixed): latent purchase intent `sim_u`
drives both exposure and conversion (confounding by design); exposures are
drawn from logistic targeting rules; a 14-day conversion outcome and
follow-on revenue are simulated.
""",
    ),
    (
        "code",
        """# deterministic: RNG seed fixed by config "seed"
sim = build_sim_preview()
print(f"sim preview: {len(sim):,} rows x {sim.shape[1]} cols | sim_* columns:")
print([c for c in sim.columns if c.startswith("sim_")])
""",
    ),
    (
        "code",
        """chan = channel_descriptive_stats(sim)
fig = plots.plot_channel_exposure(chan["exposure_rate"])
plots.save_fig(fig, "12_sim_exposure_rates.png")
chan["exposure_rate"]
""",
    ),
    (
        "code",
        """fig = plots.plot_naive_conversion(chan["naive_conversion"])
plots.save_fig(fig, "13_sim_naive_conversion.png")
chan["naive_conversion"]
""",
    ),
    (
        "markdown",
        """### Interpreting the sim preview (read carefully)

* Exposure rates differ **by channel by design** (targeting rules differ).
* The «conversion among exposed vs unexposed» gap is a **naive descriptive
  difference** — it is NOT a causal effect and will NOT match the embedded
  ground truth, precisely because `sim_u` (latent intent) and the real
  features confound assignment. Day 8 will quantify this raw gap, and
  Days 9-12 will show adjusted estimators recovering the embedded effects.
* Ground-truth log-odds per channel are stored in `sim_ground_truth_*`.

| Channel | Embedded effect (log-odds) | Narrative |
|---|---|---|
| Email | +0.12 | reactivation works |
| Search | +0.15 | captures demand |
| Display | 0.00 | apparent effect is pure confounding |
| Social | -0.08 | sleeping dogs |
""",
    ),
    (
        "code",
        """sim[["sim_ground_truth_email", "sim_ground_truth_search", "sim_ground_truth_display", "sim_ground_truth_social"]].iloc[0].to_frame("effect_log_odds")
""",
    ),
    (
        "markdown",
        """## 9. Summary & next steps

**Observed facts locked in (sane distributions ✅):** 94,983-customer cohort via
98,199 purchased orders for a ~96k-customer / ~100k-order raw dataset; missingness
only in review/category proxies; revenue right-skewed with a long high-value tail;
~97% one-time buyers (sparse frequency, low retention — will shape the confounder
audit and RFM use); SP-dominant geography; monthly order/revenue seasonality;
RFM segments led by `one_time_lapsed`, `new_customer`, `big_spender`.

**Next (Days 4-5):** confounder audit → causal DAG → adjustment set, then
propensity scoring (Day 6) and matching (Day 7) on the simulated preview.

**Gate 1:** after Day 7, STOP for human validation before Week 2.
""",
    ),
]

# --- build + execute ----------------------------------------------------------


def main() -> int:
    nb = nbformat.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3.14 (causal-marketing)", "language": "python", "name": "causal-marketing"},
        "language_info": {"name": "python"},
    }
    for kind, src in CELLS:
        cell = nbformat.v4.new_markdown_cell(src) if kind == "markdown" else nbformat.v4.new_code_cell(src)
        nb.cells.append(cell)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    client = NotebookClient(nb, kernel_name="causal-marketing", timeout=600, resources={"metadata": {"path": str(ROOT)}})
    client.execute()
    nbformat.write(nb, OUT)
    print(f"executed notebook -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())