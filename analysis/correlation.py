"""A1: Pearson + Spearman correlation of Reddit sentiment with price returns, for the 9 panels -> `analysis_results`
(+ heatmaps in output/figures/).  Proposal 7.4 step 3 "Correlation Execution".

For every panel, at three levels (each of the 34 tickers / each Big_Group / all tickers pooled) it correlates
    predictor  sentiment_mean                                     (the proposal's variable)
               EXTENSIONS (management question "is the past better than the present?"):
               sentiment_lag_1h, sentiment_momentum_1h, reddit_volume_zscore_24
               panel_baseline uses `random_direction` instead - it must not look at sentiment.
    target     log_return (= current_return in the proposal; same thing, the DB name is the old one)
                                         CONTEMPORANEOUS: the return of the same clock hour as the Reddit hour,
                                         so it describes co-movement, NOT prediction
               future_return_1h/2h/3h/6h/12h   the forward returns (the real question)
Rules: pairs with a NULL on either side are dropped (never filled with 0); fewer than MIN_N=30 pairs ->
status 'insufficient_data'; a constant column -> 'constant'.  Benjamini-Hochberg p-values (extension) are added
within each (panel, level, predictor, target, method) family.
Caveats to quote in the report: hourly data are autocorrelated and future returns of different horizons overlap,
so p-values are descriptive, not exact; in the global panels every ticker shares the same market-wide sentiment.

Usage:  python -m analysis.correlation [--db output/reddit.sqlite3] [--no-figures]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from analysis import results_store
from etl.common import DEFAULT_DB, ROOT, connect
from pipeline_logs import run_id as new_run_id

MIN_N = 30
TARGETS = list(results_store.HORIZONS)
CORE_PREDICTOR = "sentiment_mean"
EXTENSION_PREDICTORS = ["sentiment_lag_1h", "sentiment_momentum_1h", "reddit_volume_zscore_24"]
BASELINE_PREDICTOR = "random_direction"
FIGURES = ROOT / "output" / "figures"


def predictors_for(panel_name):
    return [BASELINE_PREDICTOR] if panel_name == "panel_baseline" else [CORE_PREDICTOR] + EXTENSION_PREDICTORS


def correlate(df, predictor, target):
    """(pearson, p, spearman, p, n, status) for one predictor/target pair in one group."""
    pair = df[[predictor, target]].dropna()
    n = len(pair)
    nan = float("nan")
    if n < MIN_N:
        return nan, nan, nan, nan, n, "insufficient_data"
    x, y = pair[predictor].to_numpy(float), pair[target].to_numpy(float)
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return nan, nan, nan, nan, n, "constant"
    pr = stats.pearsonr(x, y)
    sr = stats.spearmanr(x, y)
    return float(pr[0]), float(pr[1]), float(sr[0]), float(sr[1]), n, "ok"


def groups(df):
    """(level, ticker, big_group, subframe) for every ticker, every Big_Group and the pooled panel."""
    for ticker, part in df.groupby("ticker"):
        yield "ticker", ticker, part["big_group"].iloc[0], part
    for group, part in df.groupby("big_group"):
        yield "big_group", "ALL", group, part
    yield "all", "ALL", "ALL", df


def analyse_panel(panel_name, df, meta):
    rows = []
    for level, ticker, big_group, part in groups(df):
        for predictor in predictors_for(panel_name):
            for target in TARGETS:
                pr, pp, sr, sp, n, status = correlate(part, predictor, target)
                for metric, value, p in (("pearson", pr, pp), ("spearman", sr, sp)):
                    rows.append(dict(meta, panel_name=panel_name, level=level, ticker=ticker, big_group=big_group,
                                     predictor=predictor, target=target, horizon=results_store.HORIZONS[target],
                                     metric_name=metric, metric_value=value, p_value=p, p_value_bh=None,
                                     n_samples=n, status=status))
    return rows


def heatmaps(rows, out_dir=FIGURES):
    """One PNG per panel x method: tickers (grouped by Big_Group) x targets, star = BH-adjusted p < 0.05."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    out_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame = frame[(frame.level == "ticker") & (frame.predictor.isin([CORE_PREDICTOR, BASELINE_PREDICTOR]))]
    paths = []
    for (panel, method), part in frame.groupby(["panel_name", "metric_name"]):
        order = part.drop_duplicates("ticker").sort_values(["big_group", "ticker"])["ticker"].tolist()
        cols = list(results_store.HORIZONS.values())
        value = part.pivot(index="ticker", columns="horizon", values="metric_value").reindex(index=order, columns=cols)
        sig = part.pivot(index="ticker", columns="horizon", values="p_value_bh").reindex(index=order, columns=cols)
        labels = np.array([[("n/a" if np.isnan(v) else "%.3f" % v) + ("*" if s < 0.05 else "")
                            for v, s in zip(vrow, srow)]
                           for vrow, srow in zip(value.to_numpy(float), sig.to_numpy(float))], dtype=object)
        fig, ax = plt.subplots(figsize=(8, 0.28 * len(order) + 2))
        sns.heatmap(value, annot=labels, fmt="", cmap="RdBu_r", center=0, vmin=-0.3, vmax=0.3, linewidths=0.3,
                    cbar_kws={"label": method}, ax=ax, annot_kws={"fontsize": 6})
        ax.set_title("%s - %s correlation of %s with returns   (* = BH p < 0.05; Current Return (db column log_return) is same-hour)"
                     % (panel, method, part.predictor.iloc[0]), fontsize=8)
        ax.set_xlabel("")
        ax.set_ylabel("")
        path = out_dir / ("a1_%s_%s.png" % (panel, method))
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)
        paths.append(path)
    return paths


def run(db_path=DEFAULT_DB, figures=True):
    db = connect(db_path)
    try:
        this_run = new_run_id()
        meta = dict(run_id=this_run, analysis="correlation", created_at=results_store.now(),
                    config_hash=results_store.config_hash(dict(min_n=MIN_N, targets=TARGETS, core=CORE_PREDICTOR,
                                                               extensions=EXTENSION_PREDICTORS)))
        rows = []
        for (panel_name,) in db.execute("SELECT DISTINCT panel_name FROM panels ORDER BY 1").fetchall():
            cols = sorted({CORE_PREDICTOR, BASELINE_PREDICTOR, *EXTENSION_PREDICTORS, *TARGETS, "ticker", "big_group"})
            df = pd.read_sql_query("SELECT %s FROM panels WHERE panel_name = ?" % ", ".join(cols), db, params=(panel_name,))
            rows += analyse_panel(panel_name, df, meta)
            print("%-22s rows=%d  analysed" % (panel_name, len(df)), flush=True)
        results_store.add_bh(rows)
        results_store.replace(db, "correlation", rows)
        if figures:
            print("heatmaps:", len(heatmaps(rows)))
        ok = sum(r["status"] == "ok" for r in rows)
        print("stored %d rows (%d ok, %d not computed)  run_id=%s" % (len(rows), ok, len(rows) - ok, this_run))
        return rows
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)
    run(args.db, figures=not args.no_figures)
    return 0


if __name__ == "__main__":
    sys.exit(main())
