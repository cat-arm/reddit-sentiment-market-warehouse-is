import os
import sqlite3
import tempfile
import unittest

import numpy as np
import pandas as pd

from analysis import results_store, signals
from etl.seed_dims import seed

RULES = dict(min_texts_for_sentiment=3, z_step=1.0, sentiment_levels=[0.0, 0.5, 0.8])


def hours(rows):
    """rows: (z, sentiment_mean, n_texts) -> DataFrame shaped like the ticker-level panel."""
    return pd.DataFrame([dict(ticker="AAA", big_group="crypto", hour_utc=3600 * (1741096800 // 3600 + i),
                              sentiment_mean=s, reddit_volume=n, reddit_volume_zscore_24=z,
                              majority_final_status="positive") for i, (z, s, n) in enumerate(rows)])


class DetectTests(unittest.TestCase):
    def kinds(self, rows, z=1.5, s=0.30):
        out = signals.detect(hours(rows), z, s, RULES)
        return list(out.signal_type), list(out.signal_level)

    def test_types(self):
        types, _ = self.kinds([(2.0, 0.5, 10),      # volume spike + clear sentiment -> combined
                               (2.0, 0.1, 10),      # volume spike, sentiment not clear -> volume_spike
                               (0.5, 0.6, 10),      # only sentiment, positive
                               (0.5, -0.6, 10),     # only sentiment, negative
                               (0.5, 0.1, 10),      # nothing
                               (1.5, 0.9, 10)])     # z exactly at the threshold is NOT above it -> sentiment only
        self.assertEqual(types, ["combined_signal", "volume_spike", "positive_sentiment_spike",
                                 "negative_sentiment_spike", "positive_sentiment_spike"])

    def test_no_signal_without_data_or_enough_text(self):
        types, _ = self.kinds([(np.nan, np.nan, 0),          # hour without Reddit data
                               (np.nan, 0.9, 2),             # too few texts for a sentiment signal
                               (np.nan, 0.9, 3)])            # enough texts, z unknown -> sentiment signal only
        self.assertEqual(types, ["positive_sentiment_spike"])

    def test_levels(self):
        _, levels = self.kinds([(1.6, 0.0, 10),     # 1 point
                                (2.6, 0.0, 10),     # 2 points
                                (4.0, 0.0, 10),     # 3 points
                                (9.0, 0.0, 10),     # capped at 3
                                (0.0, 0.35, 10),    # sentiment crosses 0.30 only -> low
                                (0.0, 0.55, 10),    # crosses 0.5 -> medium
                                (0.0, 0.85, 10)])   # crosses 0.8 -> high
        self.assertEqual(levels, ["low", "medium", "high", "high", "low", "medium", "high"])

    def test_stricter_threshold_never_gives_more_signals(self):
        rng = np.random.default_rng(0)
        df = hours([(z, s, 10) for z, s in zip(rng.normal(1, 1.5, 500), rng.normal(0, 0.4, 500))])
        n = lambda z, s: len(signals.detect(df, z, s, RULES))
        self.assertGreaterEqual(n(1.5, 0.05), n(2.0, 0.05))
        self.assertGreaterEqual(n(2.0, 0.05), n(2.5, 0.05))
        self.assertGreaterEqual(n(1.5, 0.05), n(1.5, 0.30))


class ViewTests(unittest.TestCase):
    def test_view_attaches_statistics_of_the_matching_horizon(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.sqlite3")
            db = sqlite3.connect(path)
            seed(db)
            db.execute(results_store.SCHEMA)
            db.execute(signals.SCHEMA)
            db.execute("INSERT INTO signal_events VALUES (1.5, 0.3, 1741096800, '2025-03-04T14:00:00+00:00', 'AAA', "
                       "'crypto', 0.5, 10, 2.0, 'positive', 'combined_signal', 'low', 'r', 't')")
            base = ("INSERT INTO analysis_results (run_id, analysis, panel_name, level, ticker, big_group, predictor, "
                    "target, horizon, metric_name, metric_value, p_value, n_samples, status, config_hash, created_at) "
                    "VALUES ('r', ?, 'panel_Ticker', 'ticker', 'AAA', 'crypto', ?, 'x', ?, ?, ?, ?, 100, ?, 'h', 't')")
            db.execute(base, ("winrate", "sign(sentiment_mean)", "1h", "winrate", 0.55, 0.01, "ok"))
            db.execute(base, ("correlation", "sentiment_mean", "1h", "spearman", 0.02, 0.5, "ok"))
            db.execute(base, ("winrate", "sign(sentiment_mean)", "12h", "winrate", None, None, "insufficient_data"))
            db.execute(signals.VIEW)
            rows = db.execute("SELECT horizon, winrate, correlation_value, stat_status FROM v_signal_list "
                              "ORDER BY horizon").fetchall()
            db.close()
        self.assertEqual(len(rows), 5)                                    # one row per horizon of this (z, s)
        by_h = {r[0]: r for r in rows}
        self.assertAlmostEqual(by_h["1h"][1], 55.0)
        self.assertEqual(by_h["1h"][2:], (0.02, "ok"))
        self.assertEqual(by_h["12h"][1:], (None, None, "insufficient_data"))   # missing statistic is NULL, not 0
        self.assertEqual(by_h["3h"][3], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
