"""A2: Historical Win Rate + Binomial test for the 9 panels -> `analysis_results` (+ heatmaps in output/figures/).
Proposal 7.4 step 3 "Historical Win Rate" and KPI table 15 (Win Rate = matches / all events x 100).

Definitions (documented decisions, see docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md item 4):
  signal      predictor 'sign(sentiment_mean)'  : + if sentiment_mean > 0, - if < 0 (exactly 0 = no direction)
              predictor 'majority_final_status' : + if positive, - if negative (neutral = no direction)
              panel_baseline: 'random_direction' (+1/-1 drawn with a fixed seed, never looks at sentiment)
  event       an hour with a directional signal AND a computable, non-zero future_return_{h}
              (a return of exactly 0 has no direction, so it is not an event)
  win         sign(signal) == sign(future_return_h)
  win rate    wins / events (stored as a FRACTION 0..1 in analysis_results; the fact table shows it x 100 as %)
  baseline    p0 = win rate of panel_baseline for the SAME group (ticker / Big_Group / all) and horizon, i.e. what a
              random direction scores on the same hours; panel_baseline itself is compared with 0.5.
  test        two-sided exact Binomial test of (wins, events) against p0  (scipy.stats.binomtest).  The sign of
              winrate - baseline_winrate tells whether it is above or below chance.
  guard       fewer than MIN_N = 30 events -> status 'insufficient_data', winrate/p-value stay NULL (never 0)
Each (panel, group, horizon, predictor) stores two rows: metric 'winrate' (with the p-value) and
'baseline_winrate' (the p0 used).  BH adjustment (extension) is added across tickers like in A1.
Same caveats as A1: autocorrelated hours and overlapping horizons make p-values descriptive.

Usage:  python -m analysis.winrate [--db output/reddit.sqlite3] [--no-figures]
"""

import argparse
import sys

import numpy as np
import pandas as pd
from scipy import stats

from analysis import figure_style, results_store
from analysis.correlation import FIGURES, groups
from etl.common import DEFAULT_DB, connect
from pipeline_logs import run_id as new_run_id

MIN_N = 30
HORIZONS = {"future_return_%s" % h: h for h in ("1h", "2h", "3h", "6h", "12h")}
BASELINE_PANEL = "panel_baseline"
PRED_SIGN = "sign(sentiment_mean)"
PRED_MAJORITY = "majority_final_status"
PRED_RANDOM = "random_direction"
MAJORITY_SIGN = {"positive": 1, "negative": -1}


def signals(df, panel_name):
    """{predictor_name: Series of +1/-1/NaN} for one panel."""
    if panel_name == BASELINE_PANEL:
        return {PRED_RANDOM: df["random_direction"].astype(float)}
    sign = np.sign(df["sentiment_mean"]).replace(0, np.nan)
    majority = df["majority_final_status"].map(MAJORITY_SIGN)
    return {PRED_SIGN: sign, PRED_MAJORITY: majority.astype(float)}


def wins_and_events(signal, future_return):
    """(wins, events) for one signal vs one return column; zero returns / missing values are not events."""
    ret = np.sign(future_return).replace(0, np.nan)
    both = pd.concat([signal, ret], axis=1, keys=["s", "r"]).dropna()
    return int((both["s"] == both["r"]).sum()), len(both)


def evaluate(wins, events, p0):
    """(winrate, p_value, status) with the n >= MIN_N guard."""
    if events < MIN_N:
        return float("nan"), float("nan"), "insufficient_data"
    return wins / events, float(stats.binomtest(wins, events, p0).pvalue), "ok"


def baseline_rates(panels):
    """{(level, ticker, big_group, horizon): win rate of the random-direction baseline}."""
    out = {}
    df = panels[BASELINE_PANEL]
    for level, ticker, big_group, part in groups(df):
        sig = signals(part, BASELINE_PANEL)[PRED_RANDOM]
        for target, horizon in HORIZONS.items():
            wins, events = wins_and_events(sig, part[target])
            out[(level, ticker, big_group, horizon)] = wins / events if events >= MIN_N else 0.5
    return out


def analyse_panel(panel_name, df, base, meta):
    rows = []
    for level, ticker, big_group, part in groups(df):
        for predictor, sig in signals(part, panel_name).items():
            for target, horizon in HORIZONS.items():
                wins, events = wins_and_events(sig, part[target])
                p0 = 0.5 if panel_name == BASELINE_PANEL else base[(level, ticker, big_group, horizon)]
                rate, p, status = evaluate(wins, events, p0)
                common = dict(meta, panel_name=panel_name, level=level, ticker=ticker, big_group=big_group,
                              predictor=predictor, target=target, horizon=horizon, n_samples=events, status=status)
                rows.append(dict(common, metric_name="winrate", metric_value=rate, p_value=p, p_value_bh=None))
                rows.append(dict(common, metric_name="baseline_winrate",
                                 metric_value=p0 if status == "ok" else float("nan"), p_value=None, p_value_bh=None))
    return rows


def heatmaps(rows, out_dir=FIGURES):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    figure_style.use_thai_font()
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame = frame[(frame.level == "ticker") & (frame.metric_name == "winrate") & (frame.predictor != PRED_MAJORITY)]
    cols = list(HORIZONS.values())
    paths = []
    for panel, part in frame.groupby("panel_name"):
        order = part.drop_duplicates("ticker").sort_values(["big_group", "ticker"])["ticker"].tolist()
        value = part.pivot(index="ticker", columns="horizon", values="metric_value").reindex(index=order, columns=cols)
        sig = part.pivot(index="ticker", columns="horizon", values="p_value_bh").reindex(index=order, columns=cols)
        size = part.pivot(index="ticker", columns="horizon", values="n_samples").reindex(index=order, columns=cols)
        labels = figure_style.cell_labels(value.to_numpy(float), size.to_numpy(float), sig.to_numpy(float), lambda v: "%.1f" % (100 * v))
        fig, ax = plt.subplots(figsize=(8, 0.42 * len(order) + 2.6))
        sns.heatmap(value, annot=labels, fmt="", cmap=figure_style.colormap(), center=0.5, vmin=0.45, vmax=0.55, linewidths=0.3,
                    cbar_kws={"label": "win rate (แดง < 50%, เขียว > 50%; สีเต็มที่ 45% / 55%)"}, ax=ax, annot_kws={"fontsize": 6})
        ax.set_title("%s - win rate %% (%s)\n%s\n"
                     "(* = BH p < 0.05 เทียบ baseline; n = จำนวนครั้งที่มีสัญญาณและราคาขยับ)"
                     % (panel, part.predictor.iloc[0], figure_style.panel_note(panel)), fontsize=8)
        ax.set_xlabel("")
        ax.set_ylabel("")
        path = out_dir / ("a2_%s_winrate.png" % panel)
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)
        paths.append(path)
    return paths


def run(db_path=DEFAULT_DB, figures=True):
    db = connect(db_path)
    try:
        cols = ["ticker", "big_group", "sentiment_mean", "majority_final_status", "random_direction",
                *HORIZONS]
        panels = {name: pd.read_sql_query("SELECT %s FROM panels WHERE panel_name = ?" % ", ".join(cols), db,
                                          params=(name,))
                  for (name,) in db.execute("SELECT DISTINCT panel_name FROM panels ORDER BY 1").fetchall()}
        meta = dict(run_id=new_run_id(), analysis="winrate", created_at=results_store.now(),
                    config_hash=results_store.config_hash(dict(min_n=MIN_N, horizons=list(HORIZONS.values()),
                                                               baseline=BASELINE_PANEL)))
        base = baseline_rates(panels)
        rows = []
        for name, df in panels.items():
            rows += analyse_panel(name, df, base, meta)
            print("%-22s analysed" % name, flush=True)
        results_store.add_bh([r for r in rows if r["metric_name"] == "winrate"])
        results_store.replace(db, "winrate", rows)
        if figures:
            print("heatmaps:", len(heatmaps(rows)))
        ok = sum(r["status"] == "ok" and r["metric_name"] == "winrate" for r in rows)
        print("stored %d rows (%d win rates computed)  run_id=%s" % (len(rows), ok, meta["run_id"]))
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
