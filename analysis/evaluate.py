"""A4 + A5: result evaluation -> tables `evaluation_*` and a Markdown report (proposal 7.4 step 4 "Result Evaluation").

Reads only the numbers already stored in `analysis_results` by A1 (correlation), A2 (win rate) and A3 (logistic) and
answers the four management questions of proposal 7.4 section 3:

  Q1  Is Reddit sentiment/volume aligned with the future direction of the price?           -> evaluation_convergence
        "Convergence" = the three methods point the same way (proposal: "if all three agree it is more reliable")
  Q2  Does the pattern differ between stock/ETF, crypto and futures?                         -> evaluation_by_group
  Q3  Is the PREVIOUS hour's signal better than the current hour's?                          -> evaluation_prior_vs_current
  Q4  Which factor deserves the most weight for the signal-detection thresholds?             -> evaluation_factor_importance
  (+) Which of the 9 panels shows the clearest relation?                                     -> in the report

Definitions used for "edge" (positive = the Reddit signal points the same way as the future return):
  A1 edge  = Spearman rho between sentiment_mean and future_return_h          (panel_baseline: random_direction)
  A2 edge  = win rate - baseline win rate (what a random direction scores on the same hours)
  A3 edge  = mean AUC - 0.5
  weak convergence    all three edges exist and have the SAME sign
  strong convergence  weak convergence AND A1 p < 0.05 AND A2 p < 0.05 AND A3 edge larger than its fold std
                      (raw p-values; with hundreds of thousands of overlapping hourly rows they are descriptive,
                      so "strong" still does NOT mean tradable - see the caveats in the report)
Only the pooled ('all') and Big_Group levels are used here; per-ticker detail stays in analysis_results.
Everything is recomputed on each run; the report is written to output/reports/a5_evaluation.md.

Usage:  python -m analysis.evaluate [--db output/reddit.sqlite3]
"""

import argparse
import sys

import numpy as np
import pandas as pd

from etl.common import DEFAULT_DB, ROOT, connect, file_header

REPORT = ROOT / "output" / "reports" / "a5_evaluation.md"
HORIZONS = ["1h", "2h", "3h", "6h", "12h"]
BASELINE_PANEL = "panel_baseline"
KEY = ["panel_name", "level", "big_group", "horizon"]
LEVELS = ("all", "big_group")


def _pick(df, analysis, metric, predictor=None, extra=None):
    """Rows of one metric restricted to the pooled / Big_Group levels (one number per KEY)."""
    sel = (df.analysis == analysis) & (df.metric_name == metric) & df.level.isin(LEVELS)
    if predictor is not None:
        sel &= df.predictor.isin(predictor)
    if extra is not None:
        sel &= extra
    return df[sel]


def _core(panel_name_series, core, baseline):
    """Per panel the right predictor name: panel_baseline never uses sentiment, it uses its random column."""
    return panel_name_series.map(lambda p: baseline if p == BASELINE_PANEL else core)


def edges(df):
    """One row per KEY with the three edges and their p-values / fold std (NaN when a method has no number)."""
    horizon = df.horizon.isin(HORIZONS)
    a1 = _pick(df, "correlation", "spearman", ["sentiment_mean", "random_direction"], horizon)
    a1 = a1.rename(columns={"metric_value": "a1_rho", "p_value": "a1_p", "n_samples": "a1_n"})[KEY + ["a1_rho", "a1_p", "a1_n"]]

    a2 = _pick(df, "winrate", "winrate", ["sign(sentiment_mean)", "random_direction"], horizon)
    a2 = a2.rename(columns={"metric_value": "a2_rate", "p_value": "a2_p", "n_samples": "a2_n"})[KEY + ["a2_rate", "a2_p", "a2_n"]]
    base = _pick(df, "winrate", "baseline_winrate", ["sign(sentiment_mean)", "random_direction"], horizon)
    base = base.rename(columns={"metric_value": "a2_base"})[KEY + ["a2_base"]]

    a3 = _pick(df, "logistic", "auc", None, horizon).rename(columns={"metric_value": "a3_auc", "n_samples": "a3_n"})
    a3 = a3[KEY + ["a3_auc", "a3_n"]]
    sd = _pick(df, "logistic", "auc_std", None, horizon).rename(columns={"metric_value": "a3_std"})[KEY + ["a3_std"]]

    out = a1
    for part in (a2, base, a3, sd):
        out = out.merge(part, on=KEY, how="outer")
    out["a1_edge"] = out["a1_rho"]
    out["a2_edge"] = out["a2_rate"] - out["a2_base"]
    out["a3_edge"] = out["a3_auc"] - 0.5
    return out


def convergence(df):
    """A5 core: do Correlation, Win Rate and Logistic agree?  One row per panel x level x group x horizon."""
    e = edges(df)
    sign = np.sign(e[["a1_edge", "a2_edge", "a3_edge"]])
    have_all = e[["a1_edge", "a2_edge", "a3_edge"]].notna().all(axis=1)
    e["weak_convergence"] = have_all & (sign.nunique(axis=1) == 1) & (sign["a1_edge"] != 0)
    e["direction"] = np.where(~e["weak_convergence"], "none", np.where(sign["a1_edge"] > 0, "positive", "negative"))
    e["strong_convergence"] = (e["weak_convergence"] & (e["a1_p"] < 0.05) & (e["a2_p"] < 0.05)
                               & (e["a3_edge"].abs() > e["a3_std"]))
    return e.sort_values(KEY).reset_index(drop=True)


def by_group(conv):
    """Q2: the three edges per asset class for the panels that matter (pooled level is shown as 'ALL')."""
    sub = conv[conv.level.isin(LEVELS)].copy()
    sub["group"] = np.where(sub.level == "all", "ALL", sub.big_group)
    return sub[["panel_name", "group", "horizon", "a1_edge", "a2_edge", "a3_edge", "a1_n", "a2_n", "a3_n",
                "weak_convergence", "strong_convergence"]].sort_values(["panel_name", "group", "horizon"])


def prior_vs_current(df):
    """Q3: |rho| of the current-hour sentiment vs the previous-hour sentiment (lag 1h), momentum and volume z."""
    horizon = df.horizon.isin(HORIZONS)
    sel = (df.analysis == "correlation") & (df.metric_name == "spearman") & (df.level == "all") & horizon
    sel &= df.predictor.isin(["sentiment_mean", "sentiment_lag_1h", "sentiment_momentum_1h", "reddit_volume_zscore_24"])
    part = df[sel]
    wide = part.pivot_table(index=["panel_name", "horizon"], columns="predictor", values="metric_value").reset_index()
    for col in ("sentiment_mean", "sentiment_lag_1h", "sentiment_momentum_1h", "reddit_volume_zscore_24"):
        if col not in wide:
            wide[col] = np.nan
    strength = wide[["sentiment_mean", "sentiment_lag_1h", "sentiment_momentum_1h", "reddit_volume_zscore_24"]].abs()
    wide["strongest_predictor"] = strength.idxmax(axis=1, skipna=True).where(strength.notna().any(axis=1))
    wide["lag_beats_current"] = strength["sentiment_lag_1h"] > strength["sentiment_mean"]
    return wide


def factor_importance(df):
    """Q4: mean |coefficient| per variable group from A3 (higher = the model leans on it more)."""
    sel = (df.analysis == "logistic") & df.metric_name.str.startswith("group_importance:") & df.level.isin(LEVELS)
    part = df[sel & (df.status == "ok")].copy()
    part["group_name"] = part.metric_name.str.split(":", n=1).str[1]
    part["unit"] = np.where(part.level == "all", "ALL", part.big_group)
    out = part.groupby(["panel_name", "unit", "group_name"], as_index=False)["metric_value"].mean()
    return out.rename(columns={"metric_value": "mean_abs_coef"})


def panel_ranking(conv):
    """Which panel shows the clearest relation?  Mean |edge| of the three methods on the pooled level."""
    pooled = conv[conv.level == "all"].copy()
    pooled["clarity"] = pooled[["a1_edge", "a2_edge", "a3_edge"]].abs().mean(axis=1)
    out = pooled.groupby("panel_name", as_index=False).agg(
        mean_abs_edge=("clarity", "mean"), weak=("weak_convergence", "sum"), strong=("strong_convergence", "sum"),
        cells=("horizon", "count"))
    return out.sort_values("mean_abs_edge", ascending=False)


def md_table(frame):
    """DataFrame -> Markdown table (own tiny helper so the project does not need the `tabulate` package)."""
    cols = list(frame.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in row) + " |")
    return "\n".join(lines)


def to_markdown(conv, groups, prior, importance, ranking):
    """Plain Markdown report; every number comes from the tables above, none is typed by hand."""
    lines = ["# A5 - Result evaluation (generated by analysis/evaluate.py)", "",
             *file_header("สรุปผลการวิเคราะห์ความสัมพันธ์ (7.4) จากสามวิธี Spearman / Win Rate / Logistic ว่าเห็นตรงกันหรือไม่ แยกตาม panel และกลุ่มสินทรัพย์",
                          "analysis/evaluate.py", "python steps/19_evaluate.py",
                          "ตาราง analysis_results ใน output/reddit.sqlite3 (ผลของขั้น 16-18)"), "",
             "Edges: A1 = Spearman rho, A2 = win rate - baseline win rate, A3 = AUC - 0.5. "
             "Positive = the Reddit signal points the same way as the future return.", ""]
    panel_cells = conv[(conv.level.isin(LEVELS)) & (conv.panel_name != BASELINE_PANEL)]
    lines += ["## Convergence of the three methods (non-baseline panels, pooled + Big_Group levels)", "",
              "- cells with all three edges available: %d" % panel_cells[["a1_edge", "a2_edge", "a3_edge"]].notna().all(axis=1).sum(),
              "- weak convergence (same sign): %d" % panel_cells.weak_convergence.sum(),
              "- of which positive direction: %d" % (panel_cells.direction == "positive").sum(),
              "- strong convergence (also significant and AUC edge > fold std): %d" % panel_cells.strong_convergence.sum(),
              "- control: panel_baseline weak convergence in %d of %d cells (random signals agree by chance about 1 in 4)"
              % (conv[conv.panel_name == BASELINE_PANEL].weak_convergence.sum(),
                 conv[conv.panel_name == BASELINE_PANEL][["a1_edge", "a2_edge", "a3_edge"]].notna().all(axis=1).sum()), ""]
    lines += ["## Panel clarity (mean |edge|, pooled level)", "", md_table(ranking.round(5)), ""]
    lines += ["## Q2 - asset classes (panel_global and panel_Ticker)", "",
              md_table(groups[groups.panel_name.isin(["panel_global", "panel_Ticker"])].round(4)), ""]
    lines += ["## Q3 - previous hour vs current hour (Spearman rho, pooled)", "", md_table(prior.round(4)), ""]
    lines += ["## Q4 - variable-group importance (A3, mean |coefficient|)", "",
              md_table(importance[importance.panel_name.isin(["panel_global", "panel_Ticker"])].round(4)), "",
              "## Caveats", "",
              "- Hourly data are autocorrelated and forward returns of different horizons overlap, so p-values are descriptive.",
              "- Stock/ETF has no 12h data and little 6h data; those cells are empty, not zero.",
              "- Coefficients are only informative when the AUC is clearly above 0.5.", ""]
    return "\n".join(lines)


def run(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM analysis_results", db)
        conv = convergence(df)
        groups, prior, importance, ranking = by_group(conv), prior_vs_current(df), factor_importance(df), panel_ranking(conv)
        for name, table in (("evaluation_convergence", conv), ("evaluation_by_group", groups),
                            ("evaluation_prior_vs_current", prior), ("evaluation_factor_importance", importance),
                            ("evaluation_panel_ranking", ranking)):
            table.to_sql(name, db, if_exists="replace", index=False)   # small summary tables, rebuilt every run
        db.commit()
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(to_markdown(conv, groups, prior, importance, ranking), encoding="utf-8")
        print("report:", REPORT)
        return conv, groups, prior, importance, ranking
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    run(parser.parse_args(argv).db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
