"""EXTENSION of A3 (advisor's remark 2026-11-16: "the model needs an evaluation: train, predict on a test set, L1 / L2 regularisation to select the variables").

Two analyses on top of `analysis/logistic.py` (which keeps the proposal's TimeSeriesSplit(5, gap 12) AUC); nothing is written to the database.

ANALYSIS 1  Is the model of a panel better or worse than a random guess?  (per panel x horizon, the pooled level `all`)
  split      the unique hours in time order: the first 75% are the TRAIN part, the last 25% are the FINAL TEST set, with a gap of 12 hours between them
             (the longest forward-return window); the test set is not looked at until the model is chosen; no shuffling.
  tuning     inside the train part only: TimeSeriesSplit(3, gap 12) over its hours picks the penalty (L2 ridge / L1 lasso) and the strength C
             (1e-4 ... 10) with the best mean AUC.  StandardScaler is fitted on the training rows of every fit.
  test       the chosen model (refitted on the whole train part) predicts the test set: AUC with a 95% interval (block bootstrap over the UTC days of the test set),
             accuracy, balanced accuracy, precision, recall, F1, log-loss, Brier score, confusion matrix; the accuracy of always saying the majority class.
  baselines  the same procedure with the PRICE-ONLY variables (the Market group: trading volume, its Z-score, normalised ATR), with the REDDIT-ONLY variables, and
             the panel `panel_baseline` (one random +1 / -1 column); the AUC gain of the full model over the price-only model with a paired bootstrap interval
             (does the Reddit sentiment add anything to the price?).
ANALYSIS 2  How much does each variable add?  (panel Global `panel_global`, level `all`, every horizon; the Current Return is the horizon 'log_return')
  validation train -> VALIDATION -> test (advisor, 2026-11-17): the last third (in time, gap 12 h) of the train part is the VALIDATION set; the variables are chosen on it, with models fitted
             on the sub-train part; the test set is NOT used to choose anything.
  L1 / L2    L1 (lasso) at its best C: the variables whose coefficient is not zero are "selected"; stability = in how many of the 5 time folds of the sub-train part
             they are selected; the standardised L2 coefficient is kept next to it.
  drop-one   refit without the variable (or the group): the AUC of the full model minus the AUC without it, on the VALIDATION set, with a paired bootstrap interval.
  add-one    the price-only model plus ONE Reddit variable (or group): the gain in VALIDATION AUC over the price-only model, with a paired bootstrap interval; the Reddit variables
             whose interval is above 0 are KEPT (with the price base).
  alone      the validation AUC of the variable by itself.
  cut        `cut_on_test`: the ONE time the test set sees the cut: the full model against the model with the kept variables, both fitted on the whole train part.
  A gain whose interval contains 0 = the variable adds nothing.  The Current Return is the return of the SAME clock hour (co-movement, not prediction) and the Market
  group is the price side of the same hour: report the two sides separately.
All models are fitted on the same complete rows (a row with ANY missing feature is dropped, never filled with 0), so every AUC is on the same test rows.
Usage:  python -m analysis.logistic_eval [--db output/reddit.sqlite3] [--boot 200] [--panels panel_global ...] [--no-features]
Output: output/reports/logistic_evaluation.md, logistic_panels.csv, logistic_features.csv, logistic_cut_test.csv, output/figures/logistic_delta_auc.png
"""
import argparse
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score, log_loss, precision_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from analysis import rank_tests
from analysis.logistic import BASELINE_GROUPS, BASELINE_PANEL, GROUPS, HORIZONS, MIN_ROWS, prepare
from etl.common import DEFAULT_DB, ROOT, connect, file_header

OUT_DIR = ROOT / "output" / "reports"
FIGURES = ROOT / "output" / "figures"
TEST_FRACTION = 0.25
GAP_HOURS = 12
INNER_SPLITS = 3
C_GRID = (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0)
CONFIGS = [(penalty, c) for penalty in ("l2", "l1") for c in C_GRID]
PRICE_FEATURES = GROUPS["Market"]
SEED = 20261116
REDDIT_GROUPS = {name: cols for name, cols in GROUPS.items() if name != "Market"}


# ---------------------------------------------------------------------------------------------------------------- model pieces

def make_model(penalty, c):
    kwargs = {"l1_ratio": 1.0, "solver": "liblinear"} if penalty == "l1" else {}
    return LogisticRegression(C=c, max_iter=2000, **kwargs)


def fit_predict(penalty, c, x_train, y_train, x_test):
    """The scaler is fitted on the training rows only.  -> (probabilities of the test rows, the fitted model, the scaler)."""
    scaler = StandardScaler().fit(x_train)
    model = make_model(penalty, c).fit(scaler.transform(x_train), y_train)
    return model.predict_proba(scaler.transform(x_test))[:, 1], model, scaler


def fast_auc(y, p):
    """AUC from the ranks of the scores (average ranks for ties): the same number as roc_auc_score, a few times faster for the bootstrap."""
    y = np.asarray(y)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return np.nan
    ranks = stats.rankdata(p)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def time_split(hours, test_fraction=TEST_FRACTION, gap=GAP_HOURS):
    """(train row index, test row index): the unique hours in time order, the last `test_fraction` are the test set and the `gap` hours before it are dropped."""
    unique = np.unique(hours)
    cut = int(len(unique) * (1.0 - test_fraction))
    train_hours, test_hours = unique[:max(cut - gap, 0)], unique[cut:]
    return np.flatnonzero(np.isin(hours, train_hours)), np.flatnonzero(np.isin(hours, test_hours))


def inner_folds(hours_train, n_splits=INNER_SPLITS, gap=GAP_HOURS):
    unique = np.unique(hours_train)
    out = []
    for tr, te in TimeSeriesSplit(n_splits=n_splits, gap=gap).split(unique):
        out.append((np.flatnonzero(np.isin(hours_train, unique[tr])), np.flatnonzero(np.isin(hours_train, unique[te]))))
    return out


def tune(x_train, y_train, hours_train):
    """Mean AUC of every (penalty, C) over the time folds of the train part -> (best (penalty, C), best L1 (penalty, C), {config: mean AUC})."""
    folds = [(tr, te) for tr, te in inner_folds(hours_train) if len(np.unique(y_train[tr])) == 2 and len(np.unique(y_train[te])) == 2]
    if not folds:
        return None
    table = {}
    for penalty, c in CONFIGS:
        table[(penalty, c)] = float(np.mean([roc_auc_score(y_train[te], fit_predict(penalty, c, x_train[tr], y_train[tr], x_train[te])[0]) for tr, te in folds]))
    best = max(table, key=table.get)
    best_l1 = max((k for k in table if k[0] == "l1"), key=table.get)
    return best, best_l1, table


def test_metrics(y, p):
    predicted = (p >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {"auc": fast_auc(y, p), "accuracy": accuracy_score(y, predicted), "balanced_accuracy": balanced_accuracy_score(y, predicted),
            "precision": precision_score(y, predicted, zero_division=0), "recall": recall_score(y, predicted, zero_division=0), "f1": f1_score(y, predicted, zero_division=0),
            "log_loss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)), "brier": brier_score_loss(y, p), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "majority_accuracy": float(max(y.mean(), 1 - y.mean()))}


class Bootstrap:
    """The same bootstrap samples (whole UTC days of the test set, drawn with replacement) for every model, so the differences of AUC are paired."""

    def __init__(self, hours_test, boot, seed=SEED):
        first, counts = rank_tests.day_blocks(hours_test)
        rng = np.random.default_rng(seed)
        self.samples = [rank_tests.block_indices(first, counts, rng) for _ in range(boot)]

    def auc(self, y, p):
        return np.array([fast_auc(y[idx], p[idx]) for idx in self.samples])

    @staticmethod
    def interval(values):
        return tuple(float(v) for v in np.nanpercentile(values, [2.5, 97.5]))


# ---------------------------------------------------------------------------------------------------------------- data

def load_panel(db, name, features, targets):
    cols = sorted({"ticker", "big_group", "hour_utc", "majority_final_status", "random_direction", "volume",
                   *[c for g in GROUPS.values() for c in g if c not in ("majority_final_status_num", "log_trading_volume")], *targets})
    return pd.read_sql_query("SELECT %s FROM panels WHERE panel_name = ?" % ", ".join(cols), db, params=(name,))


def design(part, target, features):
    """Complete rows (no feature missing, target not 0), in time order -> hours, X, y, tickers."""
    sub = part[["hour_utc", target, *features]].replace([np.inf, -np.inf], np.nan).dropna()
    sub = sub[sub[target] != 0]
    return sub["hour_utc"].to_numpy(), sub[features].to_numpy(float), (sub[target].to_numpy() > 0).astype(int)


def evaluate_set(hours, x, y, columns, subset, boot, tuned=None):
    """Tune on the train part (or use `tuned`), predict the test set with the variables `subset` (names in `columns`).
    -> dict(p, config, inner_auc, l1) or None."""
    idx = [columns.index(c) for c in subset]
    train, test = SPLIT_CACHE
    xs = x[:, idx]
    if tuned is None:
        tuned = tune(xs[train], y[train], hours[train])
        if tuned is None:
            return None
    best, best_l1, table = tuned
    p, model, scaler = fit_predict(best[0], best[1], xs[train], y[train], xs[test])
    return {"p": p, "config": best, "config_l1": best_l1, "inner_auc": table[best], "tuned": tuned}


SPLIT_CACHE = (None, None)


def analysis_panel(part, panel, horizon_label, target, boot):
    """One row of the panel table: the full model, the price-only and Reddit-only models, the gain of the full model over the price-only one."""
    global SPLIT_CACHE
    groups = BASELINE_GROUPS if panel == BASELINE_PANEL else GROUPS
    features = [c for cols in groups.values() for c in cols]
    hours, x, y = design(part, target, features)
    row = {"panel": panel, "horizon": horizon_label, "n_rows": len(y), "status": "ok"}
    if len(y) < MIN_ROWS:
        return dict(row, status="insufficient_data"), None
    train, test = time_split(hours)
    if len(train) < MIN_ROWS or len(test) < 100 or len(np.unique(y[train])) < 2 or len(np.unique(y[test])) < 2:
        return dict(row, status="insufficient_data"), None
    SPLIT_CACHE = (train, test)
    columns = list(features)
    y_test = y[test]
    full = evaluate_set(hours, x, y, columns, features, boot)
    if full is None:
        return dict(row, status="insufficient_data"), None
    metrics = test_metrics(y_test, full["p"])
    boots = Bootstrap(hours[test], boot)
    auc_full = boots.auc(y_test, full["p"])
    low, high = boots.interval(auc_full)
    row.update(n_train=len(train), n_test=len(test), penalty=full["config"][0], C=full["config"][1], inner_auc=full["inner_auc"], auc=metrics["auc"], auc_low=low, auc_high=high,
               better_than_random=bool(low > 0.5), worse_than_random=bool(high < 0.5), **{k: v for k, v in metrics.items() if k != "auc"})
    if panel != BASELINE_PANEL:
        for label, subset in (("price_only", PRICE_FEATURES), ("reddit_only", [c for c in features if c not in PRICE_FEATURES])):
            other = evaluate_set(hours, x, y, columns, subset, boot)
            if other is None:
                continue
            auc_other = boots.auc(y_test, other["p"])
            row[label + "_auc"] = fast_auc(y_test, other["p"])
            row[label + "_auc_low"], row[label + "_auc_high"] = boots.interval(auc_other)
            if label == "price_only":
                gain = auc_full - auc_other
                row["gain_over_price_only"] = float(fast_auc(y_test, full["p"]) - fast_auc(y_test, other["p"]))
                row["gain_low"], row["gain_high"] = boots.interval(gain)
    context = {"hours": hours, "x": x, "y": y, "columns": columns, "full": full, "boots": boots, "train": train, "test": test, "auc_full": fast_auc(y_test, full["p"])}
    return row, context


VALIDATION_FRACTION = 1.0 / 3.0                    # of the TRAIN part, the last third in time is the validation set that chooses the variables


def validation_split(hours, train):
    """(sub-train rows, validation rows) as indices of the whole design: the train part cut in time order with a gap of 12 hours; the test set is not touched."""
    sub, val = time_split(hours[train], VALIDATION_FRACTION, GAP_HOURS)
    return train[sub], train[val]


def analysis_features(context, features_row, boot):
    """The per-variable analysis of one horizon of panel_global: L1 selection, drop-one, add-one, alone (group level too).
    EVERY number here is computed on the VALIDATION set (the last third of the train part), with models fitted on the sub-train part, so the choice of the variables never
    looks at the test set (advisor's remark 2026-11-17: train -> validation -> test, the test set only scores the final model: see `cut_on_test`)."""
    hours, x, y, columns = context["hours"], context["x"], context["y"], context["columns"]
    sub, val = validation_split(hours, context["train"])
    if len(sub) < MIN_ROWS or len(val) < 100 or len(np.unique(y[sub])) < 2 or len(np.unique(y[val])) < 2:
        return []
    tuned = tune(x[sub], y[sub], hours[sub])                                          # the penalty and C are chosen on the sub-train part only
    if tuned is None:
        return []
    best, best_l1, table = tuned
    c_l2 = max((k for k in table if k[0] == "l2"), key=table.get)[1]                  # the best L2 strength: every ablation uses the same one, so only the variables differ
    boots, y_val = Bootstrap(hours[val], boot), y[val]
    rows = []
    # L1 selection and its stability over the 5 time folds of the sub-train part
    scaler = StandardScaler().fit(x[sub])
    l1_model = make_model("l1", best_l1[1]).fit(scaler.transform(x[sub]), y[sub])
    l2_model = make_model("l2", c_l2).fit(scaler.transform(x[sub]), y[sub])
    stability = np.zeros(len(columns))
    folds = [(tr, te) for tr, te in inner_folds(hours[sub], n_splits=5) if len(np.unique(y[sub][tr])) == 2]
    for tr, _ in folds:
        s = StandardScaler().fit(x[sub][tr])
        stability += (make_model("l1", best_l1[1]).fit(s.transform(x[sub][tr]), y[sub][tr]).coef_[0] != 0)
    base_p, _, _ = fit_predict("l2", c_l2, x[sub], y[sub], x[val])
    auc_base_boot = boots.auc(y_val, base_p)
    auc_full = fast_auc(y_val, base_p)
    price_idx = [columns.index(f) for f in PRICE_FEATURES]
    price_p, _, _ = fit_predict("l2", c_l2, x[sub][:, price_idx], y[sub], x[val][:, price_idx])
    auc_price_boot, auc_price = boots.auc(y_val, price_p), fast_auc(y_val, price_p)
    group_of = {c: g for g, cols in GROUPS.items() for c in cols}

    def drop(names):
        keep = [i for i, c in enumerate(columns) if c not in names]
        p, _, _ = fit_predict("l2", c_l2, x[sub][:, keep], y[sub], x[val][:, keep])
        return fast_auc(y_val, p), boots.auc(y_val, p)

    def add(names):
        idx = sorted(set(price_idx) | {columns.index(n) for n in names})
        p, _, _ = fit_predict("l2", c_l2, x[sub][:, idx], y[sub], x[val][:, idx])
        return fast_auc(y_val, p), boots.auc(y_val, p)

    def alone(names):
        idx = [columns.index(n) for n in names]
        p, _, _ = fit_predict("l2", c_l2, x[sub][:, idx], y[sub], x[val][:, idx])
        return fast_auc(y_val, p)

    for i, name in enumerate(columns):
        auc_drop, boot_drop = drop([name])
        row = {"kind": "variable", "name": name, "group": group_of[name], "side": "price" if name in PRICE_FEATURES else "reddit", "l1_selected": bool(l1_model.coef_[0][i] != 0),
               "l1_stability_of_5": int(stability[i]), "l1_coef": float(l1_model.coef_[0][i]), "l2_coef": float(l2_model.coef_[0][i]), "alone_auc": alone([name]),
               "drop_one_delta": auc_full - auc_drop}
        row["drop_one_low"], row["drop_one_high"] = boots.interval(auc_base_boot - boot_drop)
        if name not in PRICE_FEATURES:
            auc_add, boot_add = add([name])
            row["add_one_delta"] = auc_add - auc_price
            row["add_one_low"], row["add_one_high"] = boots.interval(boot_add - auc_price_boot)
        rows.append(row)
    for g, cols in GROUPS.items():
        auc_drop, boot_drop = drop(cols)
        row = {"kind": "group", "name": g, "group": g, "side": "price" if g == "Market" else "reddit", "l1_selected": any(r["l1_selected"] for r in rows if r["kind"] == "variable" and r["group"] == g),
               "l1_stability_of_5": max(r["l1_stability_of_5"] for r in rows if r["kind"] == "variable" and r["group"] == g), "alone_auc": alone(cols), "drop_one_delta": auc_full - auc_drop}
        row["drop_one_low"], row["drop_one_high"] = boots.interval(auc_base_boot - boot_drop)
        if g != "Market":
            auc_add, boot_add = add(cols)
            row["add_one_delta"] = auc_add - auc_price
            row["add_one_low"], row["add_one_high"] = boots.interval(boot_add - auc_price_boot)
        rows.append(row)
    return [dict(features_row, c_l2=c_l2, c_l1=best_l1[1], auc_full=auc_full, auc_price_val=auc_price, n_sub=len(sub), n_val=len(val), **r) for r in rows]


def kept_variables(rows):
    """The variables kept after the validation: the price base (always) and the Reddit variables whose add-one interval on the VALIDATION set is above 0."""
    return [r["name"] for r in rows if r["kind"] == "variable" and (r["side"] == "price" or r["add_one_low"] > 0)]


def cut_on_test(context, rows, boot):
    """The ONE use of the test set for the cut: the model with every variable against the model with only the kept variables (chosen on the validation set), both fitted on the
    whole train part, scored on the test set with a paired day-block bootstrap.  -> dict, or None when the cut model cannot be fitted."""
    kept = kept_variables(rows)
    hours, x, y, columns = context["hours"], context["x"], context["y"], context["columns"]
    reduced = evaluate_set(hours, x, y, columns, kept, boot) if kept else None
    if reduced is None:
        return None
    y_test, boots = y[context["test"]], context["boots"]
    full_p, red_p = context["full"]["p"], reduced["p"]
    full_boot, red_boot = boots.auc(y_test, full_p), boots.auc(y_test, red_p)
    full_ci, red_ci, delta_ci = boots.interval(full_boot), boots.interval(red_boot), boots.interval(red_boot - full_boot)
    return {"kept": kept, "n_kept": len(kept), "full": test_metrics(y_test, full_p), "reduced": test_metrics(y_test, red_p), "full_auc_low": full_ci[0], "full_auc_high": full_ci[1],
            "reduced_auc_low": red_ci[0], "reduced_auc_high": red_ci[1], "delta_auc": float(fast_auc(y_test, red_p) - fast_auc(y_test, full_p)), "delta_low": delta_ci[0], "delta_high": delta_ci[1]}


# ---------------------------------------------------------------------------------------------------------------- run and report

def fmt(v, digits=3):
    return "-" if v is None or (isinstance(v, float) and np.isnan(v)) else ("%.*f" % (digits, v))


def figure(features):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from analysis import figure_style
    figure_style.use_thai_font()                                                     # the Thai captions need a font with Thai glyphs (the project's list)
    both = features[(features.kind == "variable") & (features.horizon == "log_return")]
    if both.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(15, 0.32 * len(both) + 2.0))
    for ax, column, low, high, title, frame in (
            (axes[0], "drop_one_delta", "drop_one_low", "drop_one_high", "ตัดตัวแปรออก (drop-one): AUC ที่ลดลง", both),
            (axes[1], "add_one_delta", "add_one_low", "add_one_high", "เติมเข้าโมเดลราคาล้วนทีละตัว (add-one): AUC ที่เพิ่มขึ้น", both[both.side == "reddit"])):
        sub = frame.sort_values(column)
        ax.barh(sub.name, sub[column], color=["#d62728" if side == "price" else "#4c78a8" for side in sub.side])
        ax.errorbar(sub[column], np.arange(len(sub)), xerr=[sub[column] - sub[low], sub[high] - sub[column]], fmt="none", ecolor="#222222", capsize=2)
        ax.axvline(0, color="#555555", linewidth=0.8)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("เส้นดำ = ช่วงเชื่อมั่น 95% (ไม่คร่อม 0 = ช่วยจริง) · น้ำเงิน = Reddit, แดง = ราคาชั่วโมงเดียวกัน", fontsize=8)
    fig.suptitle("Current Return, panel Global: ตัวแปรแต่ละตัวช่วยเพิ่ม AUC บนชุด validation เท่าไร (เลือกตัวแปรด้วย validation ไม่ใช้ชุดทดสอบ)", fontsize=11)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "logistic_delta_auc.png", dpi=150)
    plt.close(fig)


def report(panels, features, boot, cuts=None):
    ok = panels[panels.status == "ok"]
    lines = ["# Logistic Regression: ประเมินผลบนชุดทดสอบ, L1 / L2 และการวัดความช่วยเหลือของแต่ละตัวแปร (ส่วนขยายของ A3)", "",
             *file_header("ผลประเมินโมเดล Logistic บนชุดทดสอบสุดท้าย (ท้ายสุดของเวลา 25%) แยกจากชุดฝึกที่ใช้ปรับ L1/L2, AUC พร้อมช่วงเชื่อมั่น, metrics อื่น, เทียบโมเดลฐาน (สุ่ม, ราคาล้วน, Reddit ล้วน) "
                          "และการวัดว่าตัวแปรแต่ละตัวช่วยเพิ่มเท่าไร (L1 คัดตัวแปร, drop-one, add-one บนชุด validation) แล้วเทียบก่อน/หลังตัดบนชุดทดสอบครั้งเดียว ตามข้อสังเกตของอาจารย์",
                          "analysis/logistic_eval.py", "python -m analysis.logistic_eval --boot %d" % boot, "ตาราง panels ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "วิธี: แบ่งหน่วยเวลา (ชั่วโมงที่ไม่ซ้ำ) 75%% แรก = ชุดฝึก, 25%% ท้าย = **ชุดทดสอบสุดท้าย** เว้น 12 ชั่วโมง · ปรับ penalty (L2 / L1) และ C (1e-4 ถึง 10) ด้วย TimeSeriesSplit 3 รอบ **ในชุดฝึกเท่านั้น** (AUC เฉลี่ยสูงสุด) · "
             "**เลือกตัวแปรด้วย validation:** ส่วนท้าย 1 ใน 3 ของชุดฝึก (เว้น 12 ชั่วโมง) เป็นชุด validation โมเดลฝึกบนชุดฝึกย่อย ส่วน add-one / drop-one / L1 วัดบน validation ชุดทดสอบไม่ถูกใช้เลือกอะไรเลย · "
             "StandardScaler ฟิตเฉพาะแถวฝึก · ทุกโมเดลใช้แถวครบถ้วนชุดเดียวกัน (แถวที่ตัวแปรใดว่างถูกตัด ไม่เติม 0) · ช่วงเชื่อมั่น 95%% = block bootstrap รายวัน UTC ของชุดทดสอบ (%d รอบ) แบบจับคู่ระหว่างโมเดล" % boot, "",
             "## 1) โมเดลของแต่ละ panel ดีกว่าหรือแย่กว่าสุ่ม (ระดับ `all` รวมทุกสินทรัพย์, AUC บนชุดทดสอบ)", "",
             "AUC 0.5 = เดาสุ่ม · ✔ = ช่วงเชื่อมั่นทั้งช่วงสูงกว่า 0.5 (ดีกว่าสุ่ม) · ✘ = ต่ำกว่า 0.5 ทั้งช่วง (แย่กว่าสุ่ม) · ไม่มีเครื่องหมาย = แยกไม่ออกจากสุ่ม · "
             "◦ = CV เลือก regularization แรงจนโมเดลทายค่าคงที่ (L1 บีบทุกตัวแปรเป็น 0 หรือ C เล็กมาก) AUC = 0.5 พอดี แปลว่าไม่มีตัวแปรใดรอดการคัดตัวแปร (ไม่พบสัญญาณ)", "",
             "| panel | " + " | ".join(HORIZON_LABELS) + " |", "|---|" + "---|" * len(HORIZON_LABELS)]
    for panel in ok.panel.unique():
        cells = []
        for h in HORIZON_LABELS:
            r = ok[(ok.panel == panel) & (ok.horizon == h)]
            if r.empty:
                cells.append("-")
                continue
            r = r.iloc[0]
            if r.auc_high - r.auc_low < 1e-9:                                          # a constant model: the penalty chosen by the CV zeroed every variable
                cells.append("0.500 ◦")
                continue
            mark = " ✔" if r.better_than_random else " ✘" if r.worse_than_random else ""
            cells.append("%s (%s ถึง %s)%s" % (fmt(r.auc), fmt(r.auc_low), fmt(r.auc_high), mark))
        lines.append("| %s | %s |" % (panel, " | ".join(cells)))
    lines += ["", "## 2) ค่า penalty และ C ที่ CV เลือก, และ metrics อื่นบนชุดทดสอบ (panel Global, ทุกข้อความ)", "",
              "| ช่วงเวลา | penalty | C | n ฝึก | n ทดสอบ | AUC | accuracy | เดาข้างมาก | balanced acc. | precision | recall | F1 | log-loss | Brier | TN / FP / FN / TP |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    g = ok[ok.panel == "panel_global"]
    for h in HORIZON_LABELS:
        r = g[g.horizon == h]
        if r.empty:
            continue
        r = r.iloc[0]
        lines.append("| %s | %s | %g | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %d / %d / %d / %d |" % (
            h, r.penalty.upper(), r.C, "{:,}".format(int(r.n_train)), "{:,}".format(int(r.n_test)), fmt(r.auc), fmt(r.accuracy), fmt(r.majority_accuracy), fmt(r.balanced_accuracy),
            fmt(r.precision), fmt(r.recall), fmt(r.f1), fmt(r.log_loss), fmt(r.brier), r.tn, r.fp, r.fn, r.tp))
    lines += ["", "## 3) Reddit ช่วยเพิ่มจากราคาไหม (panel Global): โมเดลเต็ม เทียบราคาล้วน และ Reddit ล้วน", "",
              "ราคาล้วน = กลุ่ม Market (ปริมาณซื้อขาย, Z-score ของมัน, normalized ATR ของชั่วโมงเดียวกัน) · ส่วนต่างที่ช่วงเชื่อมั่นคร่อม 0 = Reddit ไม่ได้เพิ่มอะไรจากราคา", "",
              "| ช่วงเวลา | AUC เต็ม | AUC ราคาล้วน | AUC Reddit ล้วน | เต็ม − ราคาล้วน | ช่วงเชื่อมั่น 95% | Reddit เพิ่มจริง? |", "|---|---|---|---|---|---|---|"]
    for h in HORIZON_LABELS:
        r = g[g.horizon == h]
        if r.empty or "gain_over_price_only" not in r or pd.isna(r.iloc[0].get("gain_over_price_only")):
            continue
        r = r.iloc[0]
        verdict = "ใช่" if r.gain_low > 0 else "ไม่ (ช่วงคร่อม 0)" if r.gain_high >= 0 else "ต่ำลง"
        lines.append("| %s | %s | %s | %s | %+.4f | %+.4f ถึง %+.4f | %s |" % (h, fmt(r.auc), fmt(r.price_only_auc), fmt(r.reddit_only_auc), r.gain_over_price_only, r.gain_low, r.gain_high, verdict))
    if features is not None and not features.empty:
        for h in HORIZON_LABELS:
            f = features[features.horizon == h]
            if f.empty:
                continue
            lines += ["", "## 4.%s) แต่ละตัวแปรช่วยเพิ่ม AUC เท่าไร บนชุด validation: %s (panel Global)" % (HORIZON_LABELS.index(h) + 1, "Current Return (ชั่วโมงเดียวกัน)" if h == "log_return" else "ทำนายล่วงหน้า " + h), "",
                      "L2 C = %g, L1 C = %g, AUC โมเดลเต็มบน validation = %s (แถว validation %s) · drop-one = AUC เต็ม − AUC เมื่อตัดตัวแปรออก · add-one = AUC (ราคาล้วน + ตัวแปรนี้) − AUC ราคาล้วน · ✔ = ช่วงเชื่อมั่นไม่คร่อม 0" % (
                          f.iloc[0].c_l2, f.iloc[0].c_l1, fmt(f.iloc[0].auc_full), "{:,}".format(int(f.iloc[0].n_val))), "",
                      "| ตัวแปร | กลุ่ม | ฝั่ง | L1 เลือก (รอดกี่รอบจาก 5) | L2 coef | AUC ตัวเดียว | drop-one | ช่วงเชื่อมั่น | add-one | ช่วงเชื่อมั่น |", "|---|---|---|---|---|---|---|---|---|---|"]
            for r in f[f.kind == "variable"].sort_values("drop_one_delta", ascending=False).itertuples():
                sig_drop = "✔" if (r.drop_one_low > 0 or r.drop_one_high < 0) else ""
                add = "-" if pd.isna(getattr(r, "add_one_delta", np.nan)) else "%+.4f" % r.add_one_delta
                add_ci = "-" if pd.isna(getattr(r, "add_one_low", np.nan)) else "%+.4f ถึง %+.4f%s" % (r.add_one_low, r.add_one_high, " ✔" if (r.add_one_low > 0 or r.add_one_high < 0) else "")
                lines.append("| %s | %s | %s | %s (%d/5) | %+.3f | %s | %+.4f | %+.4f ถึง %+.4f %s | %s | %s |" % (
                    r.name, r.group, "ราคา" if r.side == "price" else "Reddit", "เลือก" if r.l1_selected else "ถูกบีบเป็น 0", r.l1_stability_of_5, r.l2_coef, fmt(r.alone_auc), r.drop_one_delta,
                    r.drop_one_low, r.drop_one_high, sig_drop, add, add_ci))
            lines += ["", "รายกลุ่ม:", "", "| กลุ่ม | ฝั่ง | AUC กลุ่มเดียว | drop-one | ช่วงเชื่อมั่น | add-one | ช่วงเชื่อมั่น |", "|---|---|---|---|---|---|---|"]
            for r in f[f.kind == "group"].itertuples():
                add = "-" if pd.isna(getattr(r, "add_one_delta", np.nan)) else "%+.4f" % r.add_one_delta
                add_ci = "-" if pd.isna(getattr(r, "add_one_low", np.nan)) else "%+.4f ถึง %+.4f" % (r.add_one_low, r.add_one_high)
                lines.append("| %s | %s | %s | %+.4f | %+.4f ถึง %+.4f | %s | %s |" % (r.name, "ราคา" if r.side == "price" else "Reddit", fmt(r.alone_auc), r.drop_one_delta, r.drop_one_low, r.drop_one_high, add, add_ci))
    if cuts is not None and not cuts.empty:
        lines += ["", "## 5) ก่อนตัด เทียบ หลังตัดตัวแปร บนชุดทดสอบ (ใช้ชุดทดสอบครั้งเดียว panel Global)", "",
                  "ตัวแปรที่เก็บไว้ = ราคา 3 ตัว + ตัวแปร Reddit ที่ add-one บน validation มีช่วงเชื่อมั่นสูงกว่า 0 · โมเดลทั้งสองฝึกบนชุดฝึกทั้งก้อน ทายชุดทดสอบ · "
                  "ส่วนต่าง = AUC หลังตัด − AUC ก่อนตัด (ช่วงเชื่อมั่นแบบจับคู่ ไม่คร่อม 0 = ต่างกันจริง)", "",
                  "| ช่วงเวลา | ตัวแปรที่เก็บไว้ | AUC ก่อนตัด (19 ตัว) | AUC หลังตัด | ส่วนต่าง | ช่วงเชื่อมั่น 95% | accuracy ก่อน / หลัง | F1 ก่อน / หลัง |", "|---|---|---|---|---|---|---|---|"]
        for r in cuts.itertuples():
            lines.append("| %s | %d ตัว (%s) | %s (%s ถึง %s) | %s (%s ถึง %s) | %+.4f | %+.4f ถึง %+.4f | %s / %s | %s / %s |" % (
                r.horizon, r.n_kept, r.kept, fmt(r.full_auc), fmt(r.full_auc_low), fmt(r.full_auc_high), fmt(r.reduced_auc), fmt(r.reduced_auc_low), fmt(r.reduced_auc_high),
                r.delta_auc, r.delta_low, r.delta_high, fmt(r.full_accuracy), fmt(r.reduced_accuracy), fmt(r.full_f1), fmt(r.reduced_f1)))
    lines += ["", "รูป: `output/figures/logistic_delta_auc.png` (Current Return: drop-one ซ้าย, add-one ขวา · drop-one เล็กเพราะตัวแปรความรู้สึกซ้ำซ้อนกัน ตัดตัวหนึ่งตัวอื่นชดเชยได้ จึงดู add-one ควบคู่)", "",
              "ข้อจำกัด: validation เล็กกว่าชุดทดสอบ (ราว 1 ใน 3 ของชุดฝึก) ช่วงเชื่อมั่นของ add-one / drop-one จึงกว้างกว่า · ชุดทดสอบเป็นช่วงเวลาเดียว (25% ท้าย) ผลอาจต่างในช่วงอื่น · แถวของ panel ระดับ `all` รวมหลายสินทรัพย์ในชั่วโมงเดียวกัน (ความรู้สึกระดับตลาดค่าเดียวใช้ร่วมกัน) · "
              "ช่วงเชื่อมั่นใช้บล็อกรายวัน ซึ่งชดเชยความคล้ายกันของชั่วโมงติดกันบางส่วน · Current Return = ผลตอบแทนชั่วโมงเดียวกัน (ไม่ใช่การทำนาย) และกลุ่ม Market คือราคาของแท่งเดียวกัน · "
              "ขอบเขต: ระดับ `all` เท่านั้น (ไม่แยกกลุ่มสินทรัพย์) · ไม่ใช่คำแนะนำการลงทุน", ""]
    return lines


HORIZON_LABELS = list(HORIZONS.values())


def run(db_path=DEFAULT_DB, boot=200, panels=None, do_features=True):
    db = connect(db_path, readonly=True)
    panel_rows, feature_rows, cut_rows = [], [], []
    try:
        names = [n for (n,) in db.execute("SELECT DISTINCT panel_name FROM panels ORDER BY 1").fetchall()]
        for name in names:
            if panels and name not in panels:
                continue
            groups = BASELINE_GROUPS if name == BASELINE_PANEL else GROUPS
            df = prepare(load_panel(db, name, None, list(HORIZONS)))
            for target, horizon in HORIZONS.items():
                started = time.time()
                row, context = analysis_panel(df, name, horizon, target, boot)
                panel_rows.append(row)
                if do_features and name == "panel_global" and context is not None:
                    rows = analysis_features(context, {"panel": name, "horizon": horizon}, boot)
                    feature_rows += rows
                    cut = cut_on_test(context, rows, boot) if rows else None
                    if cut:
                        cut_rows.append({"panel": name, "horizon": horizon, "n_kept": cut["n_kept"], "kept": ", ".join(cut["kept"]),
                                         "full_auc": cut["full"]["auc"], "full_auc_low": cut["full_auc_low"], "full_auc_high": cut["full_auc_high"],
                                         "reduced_auc": cut["reduced"]["auc"], "reduced_auc_low": cut["reduced_auc_low"], "reduced_auc_high": cut["reduced_auc_high"],
                                         "delta_auc": cut["delta_auc"], "delta_low": cut["delta_low"], "delta_high": cut["delta_high"],
                                         **{"full_" + k: v for k, v in cut["full"].items() if k != "auc"}, **{"reduced_" + k: v for k, v in cut["reduced"].items() if k != "auc"}})
                print("%-22s %-11s %s  AUC=%s  %.0fs" % (name, horizon, row["status"], fmt(row.get("auc")), time.time() - started), flush=True)
    finally:
        db.close()
    panels_df = pd.DataFrame(panel_rows)
    features_df = pd.DataFrame(feature_rows)
    cuts_df = pd.DataFrame(cut_rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for frame, name in ((panels_df, "logistic_panels"), (features_df, "logistic_features"), (cuts_df, "logistic_cut_test")):
        with (OUT_DIR / (name + ".csv")).open("w", newline="", encoding="utf-8") as sink:
            sink.write("\n".join(file_header("ผลประเมินโมเดล Logistic บนชุดทดสอบสุดท้าย (%s) ข้อมูลชุดเดียวกับ logistic_evaluation.md" % name, "analysis/logistic_eval.py",
                                             "python -m analysis.logistic_eval", "ตาราง panels", comment=True)) + "\n")
            frame.to_csv(sink, index=False)
    lines = report(panels_df, features_df if do_features and not features_df.empty else None, boot, cuts_df)
    (OUT_DIR / "logistic_evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not features_df.empty:
        figure(features_df)
    return panels_df, features_df


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--boot", type=int, default=200)
    parser.add_argument("--panels", nargs="*")
    parser.add_argument("--no-features", action="store_true")
    args = parser.parse_args(argv)
    run(args.db, args.boot, args.panels, not args.no_features)
    return 0


if __name__ == "__main__":
    sys.exit(main())
