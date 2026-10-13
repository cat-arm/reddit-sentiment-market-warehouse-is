import unittest

import numpy as np
import pandas as pd

from analysis import results_store
from analysis.correlation import analyse_panel, correlate, groups


def frame(n=60, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    df = pd.DataFrame({"ticker": "AAA", "big_group": "crypto", "sentiment_mean": x,
                       "sentiment_lag_1h": rng.normal(size=n), "sentiment_momentum_1h": rng.normal(size=n),
                       "reddit_volume_zscore_24": rng.normal(size=n), "random_direction": rng.choice([-1, 1], n),
                       "log_return": 2 * x + rng.normal(scale=0.01, size=n)})
    for h in ("1h", "2h", "3h", "6h", "12h"):
        df["future_return_" + h] = -x + rng.normal(scale=0.01, size=n)
    return df


META = dict(run_id="r", analysis="correlation", created_at="t", config_hash="h")


class CorrelationTests(unittest.TestCase):
    def test_known_relationships(self):
        df = frame()
        pr, pp, sr, sp, n, status = correlate(df, "sentiment_mean", "log_return")
        self.assertEqual((n, status), (60, "ok"))
        self.assertGreater(pr, 0.99)
        self.assertGreater(sr, 0.99)
        self.assertLess(correlate(df, "sentiment_mean", "future_return_1h")[0], -0.99)

    def test_nulls_dropped_not_zero_filled(self):
        df = frame()
        df.loc[:9, "sentiment_mean"] = np.nan
        self.assertEqual(correlate(df, "sentiment_mean", "log_return")[4], 50)

    def test_insufficient_and_constant(self):
        df = frame(n=20)
        res = correlate(df, "sentiment_mean", "log_return")
        self.assertEqual(res[5], "insufficient_data")
        self.assertTrue(np.isnan(res[0]))                          # NULL, never 0
        df = frame()
        df["sentiment_mean"] = 0.1
        self.assertEqual(correlate(df, "sentiment_mean", "log_return")[5], "constant")

    def test_rows_and_baseline_predictor(self):
        df = pd.concat([frame(seed=1), frame(seed=2).assign(ticker="BBB", big_group="futures")])
        rows = analyse_panel("panel_global", df, META)
        # 2 tickers + 2 groups + 1 pooled = 5 groups x 4 predictors x 6 targets x 2 methods
        self.assertEqual(len(rows), 5 * 4 * 6 * 2)
        base = analyse_panel("panel_baseline", df, META)
        self.assertEqual({r["predictor"] for r in base}, {"random_direction"})
        self.assertEqual(len(base), 5 * 1 * 6 * 2)
        self.assertEqual([lvl for lvl, *_ in groups(df)].count("ticker"), 2)

    def test_bh_adjusts_upward_and_skips_missing(self):
        rows = [dict(analysis="a", panel_name="p", level="ticker", predictor="x", target="t", metric_name="m",
                     p_value=p, p_value_bh=None, status=s)
                for p, s in ((0.001, "ok"), (0.02, "ok"), (0.04, "ok"), (float("nan"), "insufficient_data"))]
        results_store.add_bh(rows)
        adjusted = [r["p_value_bh"] for r in rows]
        self.assertTrue(all(a >= r["p_value"] for a, r in zip(adjusted[:3], rows[:3])))
        self.assertIsNone(adjusted[3])


if __name__ == "__main__":
    unittest.main()
