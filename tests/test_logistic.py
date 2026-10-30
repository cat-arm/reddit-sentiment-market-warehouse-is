import unittest

import numpy as np
import pandas as pd

from analysis.logistic import (GAP_HOURS, GROUPS, MIN_ROWS, N_SPLITS, analyse_panel, feature_groups, fit_one,
                               hour_folds, prepare)

META = dict(run_id="r", analysis="logistic", created_at="t", config_hash="h")


def panel(n_hours=400, tickers=("AAA", "BBB"), signal=True, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for t in tickers:
        for h in range(n_hours):
            s = rng.normal()
            row = {"ticker": t, "big_group": "crypto", "hour_utc": 3600 * h, "sentiment_mean": s,
                   "sentiment_abs_mean": abs(s), "pos_ratio": 0.4 + 0.1 * s, "neg_ratio": 0.3 - 0.1 * s,
                   "majority_final_status": "positive" if s > 0 else "negative", "voter_agreement_ratio": 0.5,
                   "reddit_volume_zscore_24": rng.normal(), "random_direction": rng.choice([-1, 1]),
                   "sentiment_momentum_1h": rng.normal()}
            for k in (1, 2, 3, 6, 12):
                row["sentiment_lag_%dh" % k] = rng.normal()
            drive = s if signal else rng.normal()
            row["log_return"] = drive + rng.normal(scale=0.5)                  # the Current Return (same hour)
            for hz in ("1h", "2h", "3h", "6h", "12h"):
                row["future_return_" + hz] = drive + rng.normal(scale=0.5)
            rows.append(row)
    return pd.DataFrame(rows)


class LogisticTests(unittest.TestCase):
    def test_folds_are_time_ordered_with_gap_in_hours(self):
        df = prepare(panel())
        folds = hour_folds(df["hour_utc"].to_numpy())
        self.assertEqual(len(folds), N_SPLITS)
        hours = df["hour_utc"].to_numpy()
        for tr, te in folds:
            self.assertGreaterEqual(hours[te].min() - hours[tr].max(), (GAP_HOURS + 1) * 3600)
            self.assertFalse(set(hours[tr]) & set(hours[te]))      # an hour is never on both sides (2 tickers/hour)

    def test_signal_gets_high_auc_noise_gets_chance(self):
        df = prepare(panel(signal=True))
        metrics, status, n = fit_one(df, "future_return_1h", GROUPS)
        self.assertEqual(status, "ok")
        self.assertGreater(metrics["auc"], 0.8)
        self.assertGreater(metrics["group_importance:Level"], metrics["group_importance:Volume"])
        noise, _, _ = fit_one(prepare(panel(signal=False, seed=3)), "future_return_1h", GROUPS)
        self.assertLess(abs(noise["auc"] - 0.5), 0.06)

    def test_missing_features_drop_rows_and_small_samples_flagged(self):
        df = prepare(panel(n_hours=100, tickers=("AAA",)))             # 100 rows < MIN_ROWS
        self.assertEqual(fit_one(df, "future_return_1h", GROUPS)[1:], ("insufficient_data", 100))
        df = prepare(panel())
        df.loc[df.index % 2 == 0, "sentiment_lag_12h"] = np.nan
        self.assertEqual(fit_one(df, "future_return_1h", GROUPS)[2], 400)   # half of 800 rows kept
        df["future_return_1h"] = 0.0
        self.assertEqual(fit_one(df, "future_return_1h", GROUPS)[1], "insufficient_data")   # zero returns dropped

    def test_baseline_uses_only_random_column_and_rows_layout(self):
        self.assertEqual(feature_groups("panel_baseline"), {"Random": ["random_direction"]})
        rows = analyse_panel("panel_global", panel(), META)
        levels = {r["level"] for r in rows}
        self.assertEqual(levels, {"big_group", "all"})                 # no per-ticker fits
        self.assertEqual(len([r for r in rows if r["metric_name"] == "auc"]), 2 * 6)       # 6 targets: Current Return and 1h..12h
        self.assertEqual({r["horizon"] for r in rows}, {"log_return", "1h", "2h", "3h", "6h", "12h"})
        used = {c for cols in GROUPS.values() for c in cols}
        self.assertFalse(used & {"score", "upvote_ratio", "num_comments"})        # forbidden snapshot features
        self.assertFalse([c for c in used if c.startswith("future_return") or c == "log_return"])      # targets are never inputs


if __name__ == "__main__":
    unittest.main()
