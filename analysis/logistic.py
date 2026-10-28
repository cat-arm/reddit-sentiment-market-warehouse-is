"""A3: Logistic Regression (up/down) with time-ordered cross validation -> `analysis_results` (+ AUC heatmap).
Proposal 7.4 step 3 "Logistic Regression": 6 variable groups, StandardScaler, TimeSeriesSplit with 5 folds,
AUC-ROC against a random baseline, coefficients as feature importance.  Decisions: docs/METHOD_DECISIONS item 3.

  target     y = 1 if future_return_{h} > 0, 0 if < 0   (a return of exactly 0 is dropped)
  groups     Level     sentiment_mean, sentiment_abs_mean
             Direction pos_ratio, neg_ratio
             Vote      majority_final_status (positive=+1, neutral=0, negative=-1), voter_agreement_ratio
             Volume    reddit_volume_zscore_24
             Lag       sentiment_lag_1h/2h/3h/6h/12h
             Momentum  sentiment_momentum_1h
             panel_baseline uses the single column random_direction instead (a no-information yardstick)
  fits       one model per panel x level ('big_group' x3 and 'all' pooled) x horizon.  Rows with ANY missing feature
             are dropped (complete cases): a missing lag stays missing, it is never filled with 0 (= neutral).
  split      TimeSeriesSplit(n_splits=5, gap=12) applied to the sorted UNIQUE HOURS, then mapped back to rows, so a
             test hour never shares its time with the training set and the 12-hour gap covers the longest
             forward-return window (no shuffling, no StratifiedKFold).  Pooled levels contain many tickers per hour,
             which is why the split is on hours, not on rows.
  scaler     StandardScaler is fitted on the TRAIN part of each fold only.
  metrics    auc (mean over folds), auc_std, coef:<feature> (mean standardized coefficient over folds),
             group_importance:<group> (sum of |coef| of the group, mean over folds).
  "enough data" (the proposal says "if the data are sufficient"): >= MIN_ROWS = 500 complete rows and every fold has
             both classes in train and test, otherwise status 'insufficient_data' and NULL metrics.
Forbidden features (never used): score, upvote_ratio, num_comments, future_return_* as inputs.

Usage:  python -m analysis.logistic [--db output/reddit.sqlite3] [--no-figures]
"""

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from analysis import results_store
from analysis.correlation import FIGURES, groups
from etl.common import DEFAULT_DB, connect
from ingest.pipeline_logs import run_id as new_run_id

N_SPLITS = 5
GAP_HOURS = 12
MIN_ROWS = 500
HORIZONS = {"future_return_%s" % h: h for h in ("1h", "2h", "3h", "6h", "12h")}
BASELINE_PANEL = "panel_baseline"
GROUPS = {
    "Level": ["sentiment_mean", "sentiment_abs_mean"],
    "Direction": ["pos_ratio", "neg_ratio"],
    "Vote": ["majority_final_status_num", "voter_agreement_ratio"],
    "Volume": ["reddit_volume_zscore_24"],
    "Lag": ["sentiment_lag_1h", "sentiment_lag_2h", "sentiment_lag_3h", "sentiment_lag_6h", "sentiment_lag_12h"],
    "Momentum": ["sentiment_momentum_1h"],
}
BASELINE_GROUPS = {"Random": ["random_direction"]}
VOTE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}


def feature_groups(panel_name):
    return BASELINE_GROUPS if panel_name == BASELINE_PANEL else GROUPS


def prepare(df):
    """Add the numeric vote column; returns a copy sorted by time."""
    out = df.copy()
    out["majority_final_status_num"] = out["majority_final_status"].map(VOTE)
    return out.sort_values(["hour_utc", "ticker"], kind="stable").reset_index(drop=True)


def hour_folds(hours, n_splits=N_SPLITS, gap=GAP_HOURS):
    """[(train_row_idx, test_row_idx)] from TimeSeriesSplit over the sorted unique hours (gap in HOURS)."""
    uniq = np.unique(hours)
    out = []
    for tr_h, te_h in TimeSeriesSplit(n_splits=n_splits, gap=gap).split(uniq):
        tr = np.flatnonzero(np.isin(hours, uniq[tr_h]))
        te = np.flatnonzero(np.isin(hours, uniq[te_h]))
        out.append((tr, te))
    return out


def fit_one(part, target, groups_map):
    """(metrics dict, status, n_rows) for one panel/level/horizon.  `part` must be sorted by hour."""
    features = [c for cols in groups_map.values() for c in cols]
    sub = part[["hour_utc", target, *features]].replace([np.inf, -np.inf], np.nan).dropna()
    sub = sub[sub[target] != 0]
    n = len(sub)
    if n < MIN_ROWS:
        return None, "insufficient_data", n
    hours = sub["hour_utc"].to_numpy()
    X = sub[features].to_numpy(float)
    y = (sub[target].to_numpy() > 0).astype(int)
    aucs, coefs = [], []
    for tr, te in hour_folds(hours):
        if len(np.unique(y[tr])) < 2 or len(np.unique(y[te])) < 2:
            return None, "insufficient_data", n
        scaler = StandardScaler().fit(X[tr])                         # train part only
        model = LogisticRegression(max_iter=1000).fit(scaler.transform(X[tr]), y[tr])
        aucs.append(roc_auc_score(y[te], model.predict_proba(scaler.transform(X[te]))[:, 1]))
        coefs.append(model.coef_[0])
    coef = np.mean(coefs, axis=0)
    metrics = {"auc": float(np.mean(aucs)), "auc_std": float(np.std(aucs))}
    pos = 0
    for group, cols in groups_map.items():
        for c in cols:
            metrics["coef:" + c] = float(coef[features.index(c)])
        metrics["group_importance:" + group] = float(np.mean([np.abs(cf[pos:pos + len(cols)]).sum() for cf in coefs]))
        pos += len(cols)
    return metrics, "ok", n


def analyse_panel(panel_name, df, meta):
    rows = []
    data = prepare(df)
    gmap = feature_groups(panel_name)
    for level, ticker, big_group, part in groups(data):
        if level == "ticker":
            continue
        for target, horizon in HORIZONS.items():
            metrics, status, n = fit_one(part, target, gmap)
            common = dict(meta, panel_name=panel_name, level=level, ticker=ticker, big_group=big_group,
                          predictor="+".join(gmap), target=target, horizon=horizon, n_samples=n, status=status,
                          p_value=None, p_value_bh=None)
            if metrics is None:
                rows.append(dict(common, metric_name="auc", metric_value=float("nan")))
                continue
            rows += [dict(common, metric_name=name, metric_value=value) for name, value in metrics.items()]
    return rows


def heatmap(rows, out_dir=FIGURES):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    out_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame = frame[frame.metric_name == "auc"]
    frame = frame.assign(unit=np.where(frame.level == "all", "ALL", frame.big_group))
    units = ["ALL", "crypto", "futures", "stock_etf"]
    cols = list(HORIZONS.values())
    fig, axes = plt.subplots(1, 4, figsize=(15, 4), sharey=True)
    for ax, unit in zip(axes, units):
        part = frame[frame.unit == unit]
        value = part.pivot(index="panel_name", columns="horizon", values="metric_value").reindex(columns=cols)
        sns.heatmap(value, annot=True, fmt=".3f", cmap="RdBu_r", center=0.5, vmin=0.47, vmax=0.53, cbar=unit == "stock_etf",
                    ax=ax, annot_kws={"fontsize": 7})
        ax.set_title("AUC - " + unit, fontsize=9)
        ax.set_xlabel("")
        ax.set_ylabel("")
    fig.suptitle("A3 Logistic regression, TimeSeriesSplit(5, gap=12h) mean AUC (0.5 = no skill)", fontsize=10)
    fig.tight_layout()
    path = out_dir / "a3_auc.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def run(db_path=DEFAULT_DB, figures=True):
    db = connect(db_path)
    try:
        cols = sorted({"ticker", "big_group", "hour_utc", "majority_final_status", "random_direction",
                       *[c for g in GROUPS.values() for c in g if c != "majority_final_status_num"], *HORIZONS})
        meta = dict(run_id=new_run_id(), analysis="logistic", created_at=results_store.now(),
                    config_hash=results_store.config_hash(dict(n_splits=N_SPLITS, gap=GAP_HOURS, min_rows=MIN_ROWS,
                                                               groups=GROUPS)))
        rows = []
        for (name,) in db.execute("SELECT DISTINCT panel_name FROM panels ORDER BY 1").fetchall():
            df = pd.read_sql_query("SELECT %s FROM panels WHERE panel_name = ?" % ", ".join(cols), db, params=(name,))
            rows += analyse_panel(name, df, meta)
            print("%-22s fitted" % name, flush=True)
        results_store.replace(db, "logistic", rows)
        if figures:
            print("figure:", heatmap(rows))
        ok = sum(r["status"] == "ok" and r["metric_name"] == "auc" for r in rows)
        print("stored %d rows (%d models fitted)  run_id=%s" % (len(rows), ok, meta["run_id"]))
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
