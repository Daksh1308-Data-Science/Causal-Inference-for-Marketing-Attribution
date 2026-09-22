"""Build + execute notebooks/03_cate.ipynb (Day 13).

Constructs the CATE narrative notebook from markdown + code cells, then
EXECUTES it for real with the registered `causal-marketing` kernel. The heavy
learner fits already ran in `src.causal.cate` (module + tests, pinned seed);
the notebook READS the committed artifacts (`results/tables/cate_estimates.parquet`,
`cate_summary.csv`, `cate_agreement.csv`) and re-renders the figures from them —
fast, deterministic, and every output is a genuine artifact, never fabricated.

Usage:
    python -m scripts.build_notebook_03
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "03_cate.ipynb"

CELLS: list[tuple[str, str]] = [
    (
        "markdown",
        """# 03 — CATE with Meta-Learners (T / S / X) — Day 13

Causal Inference for Marketing Attribution — **Week 2, Stage 2**.

**Labelling convention (AGENTS.md §2):** everything below is **estimated
(simulated)** — CATE estimates computed on the clearly-labelled `sim_*`
marketing layer. None of these numbers is an observed Olist fact. The
unobserved confounder `sim_u` is **never a feature** of any learner.

**What this notebook shows:** do the incremental effects vary with observed
customer features? Three meta-learners (T / S / X from causalml 0.17, all
HistGradientBoosting regressors on the probability/revenue scale) are fitted
per channel × outcome, their CATE curves are compared, and a **learner
agreement map** is rendered as the Day-13 validation hook.
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
import pandas as pd

from src.config import load_config, project_path
cfg = load_config()

TABLES = project_path(cfg["paths"]["results"], cfg["results"]["tables"])
FIGURES = project_path(cfg["paths"]["results"], cfg["results"]["figures"])

cate = pd.read_parquet(TABLES / "cate_estimates.parquet")
summary = pd.read_csv(TABLES / "cate_summary.csv")
agreement_detail = pd.read_csv(TABLES / "cate_agreement.csv")

print(f"unit-level CATE rows: {len(cate):,}")
print("summary rows:", len(summary), "| agreement detail rows:", len(agreement_detail))
""",
    ),
    (
        "markdown",
        """## 1. Method & identification (stated before fitting)

| Learner | How it estimates τ(x) | Known behaviour |
|---|---|---|
| **T** | two separate outcome regressions (treated / control arm) | higher variance in low-support cells |
| **S** | one outcome regression, treatment as a feature | shrinks effects toward a constant |
| **X** | outcome + mirrored effect regressions, uses propensity p(X) | tightest τ structure |

- Features = the Day-4 **adjustment set** per channel (email: order_count,
  recency_days, review_score_avg, total_revenue; social/search: order_count,
  tenure_days, total_revenue; display: recency_days, total_revenue).
- **Why regressors on the 0/1 outcome:** causalml's classifier path calls the
  base learner's hard `predict` (class labels), collapsing the CATE to ~0.
  Regressors on 0/1 yield a valid probability-scale CATE (Day-13 finding).
- Assumptions: exchangeability given X with **sim_u unobserved** (CATE inherits
  the Days 8–12 ATE bias); positivity/overlap per Day 6 (email weak overlap
  handled there); consistency + SUTVA as the whole project; in-sample CATE
  (no cross-fitting — deferred to Day 18).
""",
    ),
    (
        "code",
        """summary[["channel", "outcome_label", "learner_label",
          "mean_cate", "ci_lower", "ci_upper", "sd_cate"]].assign(
    ci=lambda d: d.apply(lambda r: f"[{r.ci_lower:.4f}, {r.ci_upper:.4f}]", axis=1)
).drop(columns=["ci_lower", "ci_upper"]).style.format({"mean_cate": "{:.4f}", "sd_cate": "{:.4f}"})
""",
    ),
    (
        "markdown",
        """## 2. Learner agreement map (validation hook)

Each subplot shows, per channel × outcome, the mean CATE by **baseline-risk
decile** for each learner (T red / S green / X blue). Three overlaid curves
that track each other = the learners agree on the *shape* of heterogeneity.

**Gate (config-calibrated):** every learner's mean CATE within the Day-12 OLS
ATE tolerance, AND max pairwise decile-curve spread ≤ 25% of the effect size.
Per-unit (individual) rank agreement is reported but deliberately **not**
gated — on this DGP the observed-X heterogeneity signal is tiny, so per-unit
CATE ordering is weak by construction.
""",
    ),
    (
        "code",
        """from src.causal.cate import learner_agreement
agreement = learner_agreement(cate, cfg)
agreement["status"][["channel", "outcome_label", "max_abs_mean_align",
                     "max_decile_rel", "decile_tolerance", "status"]]
""",
    ),
    (
        "code",
        """from src.causal.cate import render_agreement_map, render_cate_by_channel

fig, map_path = render_agreement_map(cate, agreement, cfg, FIGURES)
fig.show()
print("saved ->", map_path)
""",
    ),
    (
        "markdown",
        """### 2.1 The honest reading of the map

- **Aggregate level — agreement is real.** Mean CATEs match the Day-12 ATE and
  the decile curves track each other (max spread ≤
  `agreement["status"]["max_decile_rel"].max()` of the effect size). The signal
  that survives is smooth: the effect is nearly flat, mildly tilted by baseline
  risk. That is what a constant-log-odds embedded effect looks like on the
  probability scale.
- **Individual level — agreement is weak by design.** Pairwise rank Spearman
  sits ~0.3–0.8: personalized CATE ordering on observed X is **not reliable**.
  `sim_u` dominates the assignment, so the little heterogeneity these learners
  can see is drowned by their own bias/variance structure.
- **Agreement is not truth.** Display (simulated ground-truth effect 0.00) again
  shows a CATE ≈ +0.11 pp — an apparent effect driven by unobserved selection,
  not by treatment. Learner agreement does not certify the effect LEVEL.
""",
    ),
    (
        "code",
        """import plotly.graph_objects as go

# bar summary with bootstrap CI per learner
fig2, bar_path = render_cate_by_channel(summary, cfg, FIGURES)
fig2.show()
print("saved ->", bar_path)
""",
    ),
    (
        "markdown",
        """## 3. What this means for uplift (Day 14)

The CATE curves being essentially flat on observed X is a *finding*, not a
failure: it says observed features carry little heterogeneity, so uplift
modelling (Day 14) must report persuadable segments and Qini curves honestly at
the aggregate level and be transparent that `sim_u`-driven personalization is
invisible to every model built on this data.
""",
    ),
    (
        "code",
        """# required-token sanity: the report carrying the full agreement story
report = (project_path(cfg["paths"]["reports"]) / "cate_effects.md").read_text(encoding="utf-8")
for token in ["estimated (simulated)", "Learner agreement map", "sim_u", "Limitations"]:
    assert token in report, token
print("report OK, tokens present")
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
    client = NotebookClient(nb, kernel_name="causal-marketing", timeout=600,
                            resources={"metadata": {"path": str(ROOT)}})
    client.execute()
    nbformat.write(nb, OUT)
    print(f"executed notebook -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())