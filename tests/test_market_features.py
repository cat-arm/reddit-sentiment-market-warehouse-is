import contextlib
import math
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from etl import market_features
from etl.market_features import ticker_features

START = datetime(2025, 3, 3, 14, 30, tzinfo=timezone.utc)      # a Monday, stock-style xx:30 bars


def epoch(hours, start=START):
    return int((start + timedelta(hours=hours)).timestamp())


def bar(hours, close, volume=100.0, spread=1.0, start=START):
    return (epoch(hours, start), close + spread / 2, close - spread / 2, close, volume)


class FeatureMathTest(unittest.TestCase):
    def test_future_return_is_percent_and_needs_a_bar_exactly_n_hours_later(self):
        rows = ticker_features([bar(0, 100.0), bar(1, 110.0), bar(3, 121.0)])     # no bar at hour 2
        first = dict(zip(market_features.FEATURE_COLUMNS[1:], rows[0]))
        self.assertAlmostEqual(first["future_return_1h"], 10.0)
        self.assertIsNone(first["future_return_2h"])                              # gap -> not valid
        self.assertAlmostEqual(first["future_return_3h"], 21.0)
        self.assertIsNone(first["future_return_6h"])

    def test_log_return_uses_only_the_previous_hour_and_is_percent(self):
        rows = ticker_features([bar(0, 100.0), bar(1, 110.0), bar(3, 121.0)])
        self.assertIsNone(rows[0][4])
        self.assertAlmostEqual(rows[1][4], math.log(1.1) * 100)
        self.assertIsNone(rows[2][4])                                             # previous bar is 2 h away

    def test_hour_bucket_rounds_a_half_hour_bar_down(self):
        rows = ticker_features([bar(0, 100.0)])
        self.assertEqual(rows[0][0], "2025-03-03T14:30:00+00:00")
        self.assertEqual(rows[0][1], "2025-03-03T14:00:00+00:00")

    def test_volume_zscore_excludes_the_current_hour_and_waits_for_enough_history(self):
        bars = [bar(i, 100.0, volume=v) for i, v in enumerate([10, 20, 10, 20, 10, 20, 100])]
        rows = ticker_features(bars)
        zscores = [row[-1] for row in rows]
        self.assertTrue(all(z is None for z in zscores[:5]))                      # < MIN_WINDOW prior bars
        prior = [10, 20, 10, 20, 10, 20]
        mean = sum(prior) / 6
        std = math.sqrt(sum((x - mean) ** 2 for x in prior) / 6)
        self.assertAlmostEqual(zscores[6], (100 - mean) / std)                    # 100 itself is not in the window

    def test_atr_is_mean_true_range_and_normalized_by_close(self):
        rows = ticker_features([bar(i, 100.0, spread=2.0) for i in range(6)])
        atr, normalized = rows[5][-3], rows[5][-2]
        self.assertAlmostEqual(atr, 2.0)
        self.assertAlmostEqual(normalized, 2.0)
        self.assertIsNone(rows[3][-3])                                            # only 4 bars so far

    def test_rsi_is_100_for_a_steadily_rising_price_and_null_before_14_changes(self):
        rows = ticker_features([bar(i, 100.0 + i) for i in range(16)])
        rsi = [row[-4] for row in rows]
        self.assertTrue(all(value is None for value in rsi[:14]))
        self.assertEqual(rsi[14], 100.0)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = self.tmp / "t.sqlite3"
        db = sqlite3.connect(self.db_path)
        db.execute("""CREATE TABLE market_bars (ticker TEXT NOT NULL, timestamp_utc TEXT NOT NULL, open REAL,
            high REAL, low REAL, close REAL, volume REAL, fetched_at_utc TEXT NOT NULL,
            PRIMARY KEY (ticker, timestamp_utc))""")
        crypto0 = datetime(2025, 3, 3, 0, tzinfo=timezone.utc)
        rows = []
        for i in range(30):                                                       # BTC-USD: 24/7, hour 5 is a NULL placeholder
            ts = (crypto0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            close = None if i == 5 else 100.0 + i
            rows.append(("BTC-USD", ts, None, (close or 0) + 1, (close or 0) - 1, close, 10.0, "x"))
        for i in range(7):                                                        # AAPL: one 7-bar session
            ts = (START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            rows.append(("AAPL", ts, None, 201.0 + i, 199.0 + i, 200.0 + i, 5.0, "x"))
        db.executemany("INSERT INTO market_bars VALUES (?,?,?,?,?,?,?,?)", rows)
        db.commit()
        db.close()
        db = sqlite3.connect(self.db_path)
        self.addCleanup(db.close)
        market_features.build(db)
        self.result = market_features.load_fact(db)
        self.db = db

    def test_null_close_rows_are_dropped_and_fact_matches_features(self):
        self.assertEqual(self.result, {"features": 36, "fact_rows": 36})          # 29 BTC + 7 AAPL

    def test_gap_hour_breaks_future_return_and_stock_has_no_12h(self):
        btc = {r[0]: r for r in self.db.execute(
            "SELECT bar_ts, future_return_1h, future_return_2h, future_return_12h FROM market_hourly_features "
            "WHERE ticker = 'BTC-USD'")}
        self.assertIsNone(btc["2025-03-03T04:00:00+00:00"][1])                    # next bar (05:00) is a placeholder
        self.assertIsNone(btc["2025-03-03T03:00:00+00:00"][2])                    # 05:00 missing
        self.assertIsNotNone(btc["2025-03-03T06:00:00+00:00"][1])
        self.assertIsNotNone(btc["2025-03-03T10:00:00+00:00"][3])                 # 22:00 exists
        aapl = self.db.execute("SELECT future_return_6h, future_return_12h FROM market_hourly_features "
                               "WHERE ticker = 'AAPL' ORDER BY bar_ts").fetchall()
        self.assertIsNotNone(aapl[0][0])                                          # first bar of the day has a 6h bar
        self.assertIsNone(aapl[1][0])
        self.assertTrue(all(row[1] is None for row in aapl))


if __name__ == "__main__":
    unittest.main()
