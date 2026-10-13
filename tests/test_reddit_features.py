import unittest

import numpy as np
import pandas as pd

from etl.reddit_features import build_features

H = 3600 * 1000


def rows(variant, ticker, spec):
    """spec: {hour_index: (volume, sentiment_mean)}"""
    return [dict(variant=variant, ticker=ticker, hour_utc=H + i * 3600, reddit_volume=v, sentiment_mean=s)
            for i, (v, s) in spec.items()]


def get(out, variant, ticker, i):
    r = out[(out.variant == variant) & (out.ticker == ticker) & (out.hour_utc == H + i * 3600)]
    assert len(r) == 1, (variant, ticker, i, len(r))
    return r.iloc[0]


class FeatureTests(unittest.TestCase):
    def test_zscore_excludes_current_hour_and_zero_fills_gaps(self):
        # hours 0..9 volume = 10 except hour 3 missing (=0 texts); hour 10 spikes to 40
        spec = {i: (10, 0.1) for i in range(10) if i != 3}
        spec[10] = (40, 0.3)
        out = build_features(pd.DataFrame(rows("all", "AAA", spec)))
        prior = [10, 10, 10, 0, 10, 10, 10, 10, 10, 10]               # hours 0..9, hour 3 = 0
        expected = (40 - np.mean(prior)) / np.std(prior)               # population std, current hour not in window
        self.assertAlmostEqual(get(out, "all", "AAA", 10).reddit_volume_zscore_24, expected)

    def test_early_hours_are_null_not_zero(self):
        spec = {i: (5 + i, 0.0) for i in range(12)}
        out = build_features(pd.DataFrame(rows("all", "AAA", spec)))
        self.assertTrue(np.isnan(get(out, "all", "AAA", 3).reddit_volume_zscore_24))   # < 6 prior hours
        self.assertFalse(np.isnan(get(out, "all", "AAA", 8).reddit_volume_zscore_24))

    def test_flat_window_gives_null(self):
        spec = {i: (7, 0.0) for i in range(10)}
        out = build_features(pd.DataFrame(rows("all", "AAA", spec)))
        self.assertTrue(np.isnan(get(out, "all", "AAA", 9).reddit_volume_zscore_24))   # std == 0

    def test_sentiment_lag_is_by_clock_hour_and_null_when_missing(self):
        spec = {0: (1, 0.5), 1: (1, 0.2), 3: (1, -0.1)}               # hour 2 has no texts
        out = build_features(pd.DataFrame(rows("all", "AAA", spec)))
        r3 = get(out, "all", "AAA", 3)
        self.assertTrue(np.isnan(r3.sentiment_lag_1h))                # hour 2 missing -> NULL, not hour 1's value
        self.assertAlmostEqual(r3.sentiment_lag_2h, 0.2)
        self.assertAlmostEqual(r3.sentiment_lag_3h, 0.5)
        self.assertTrue(np.isnan(r3.sentiment_momentum_1h))
        r1 = get(out, "all", "AAA", 1)
        self.assertAlmostEqual(r1.sentiment_momentum_1h, 0.2 - 0.5)

    def test_no_leak_across_tickers_and_volume_copied_to_other_variants(self):
        a = rows("all", "AAA", {i: (10, 0.1) for i in range(8)})
        b = rows("all", "BBB", {7: (99, 0.9)})
        s = rows("strong", "AAA", {7: (3, 0.4)})
        out = build_features(pd.DataFrame(a + b + s))
        self.assertTrue(np.isnan(get(out, "all", "BBB", 7).sentiment_lag_1h))
        self.assertEqual(get(out, "all", "BBB", 7).reddit_volume_lag_1h, 0)
        strong = get(out, "strong", "AAA", 7)
        self.assertEqual(strong.reddit_volume_lag_1h, 10)              # volume features come from variant 'all'
        self.assertTrue(np.isnan(strong.sentiment_lag_1h))             # strong has no row at hour 6


if __name__ == "__main__":
    unittest.main()
