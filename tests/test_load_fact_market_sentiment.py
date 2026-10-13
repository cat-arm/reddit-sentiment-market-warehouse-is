import contextlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from analysis import results_store
from etl import load_fact_market_sentiment as w3
from etl.merge_panel import MARKET_COLUMNS, REDDIT_COLUMNS

# 2025-03-04 14:00 UTC, an hour that exists in DimTime
T = 1741096800


def make_db(path):
    db = sqlite3.connect(path)
    cols = ", ".join(MARKET_COLUMNS + ("market_volume_zscore_24",))
    reddit = ", ".join(REDDIT_COLUMNS)
    db.execute("CREATE TABLE merged_hourly_panel (scope TEXT, variant TEXT, ticker TEXT, big_group TEXT, hour_utc INTEGER, "
               "%s, reddit_volume INTEGER, %s, has_reddit_data INTEGER)" % (cols, reddit))
    ins = ("INSERT INTO merged_hourly_panel (scope, variant, ticker, big_group, hour_utc, close, volume, "
           "future_return_1h, reddit_volume, sentiment_mean, pos_ratio, neg_ratio, neu_ratio, majority_final_status, "
           "has_reddit_data) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    # AAPL has text at T (positive majority) and none at T+1h; BTC-USD has no row of scope 'ticker' variant 'all' noise
    db.execute(ins, ("ticker", "all", "AAPL", "stock_etf", T, 100.0, 5.0, 0.2, 4, 0.4, 0.6, 0.1, 0.3, "positive", 1))
    db.execute(ins, ("ticker", "all", "AAPL", "stock_etf", T + 3600, 101.0, 6.0, None, 0, None, None, None, None, None, 0))
    db.execute(ins, ("ticker", "all", "BTC-USD", "crypto", T, 9.0, 1.0, 0.1, 9, -0.2, 0.2, 0.5, 0.3, "negative", 1))
    db.execute(ins, ("global", "all", "AAPL", "stock_etf", T, 100.0, 5.0, 0.2, 99, 0.9, 0.9, 0.0, 0.1, "positive", 1))
    db.execute(ins, ("ticker", "strong", "AAPL", "stock_etf", T, 100.0, 5.0, 0.2, 2, 0.8, 1.0, 0.0, 0.0, "positive", 1))
    db.execute(results_store.SCHEMA)
    base = dict(run_id="r", analysis="winrate", panel_name="panel_Ticker", level="ticker", big_group="stock_etf",
                predictor="sign(sentiment_mean)", target="x", metric_name="winrate", config_hash="h", created_at="t")
    rows = [
        # AAPL: 1h win rate 55 % (p 0.01); 12h not enough data
        dict(base, ticker="AAPL", horizon="1h", metric_value=0.55, p_value=0.01, n_samples=500, status="ok"),
        dict(base, ticker="AAPL", horizon="12h", metric_value=None, p_value=None, n_samples=3, status="insufficient_data"),
        # a row that must NOT be picked: other panel / other predictor
        dict(base, ticker="AAPL", horizon="2h", metric_value=0.99, p_value=0.0, n_samples=500, status="ok",
             panel_name="panel_global"),
        dict(base, ticker="AAPL", horizon="3h", metric_value=0.99, p_value=0.0, n_samples=500, status="ok",
             predictor="majority_final_status"),
    ]
    for r in rows:
        db.execute("INSERT INTO analysis_results (%s) VALUES (%s)" % (", ".join(results_store.COLUMNS),
                                                                       ", ".join("?" * len(results_store.COLUMNS))),
                   tuple(r.get(c) for c in results_store.COLUMNS))
    db.commit()
    return db


class FactMarketSentimentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)    # Windows: the db file is closed first
        self.db = make_db(str(self.tmp / "t.sqlite3"))
        self.addCleanup(self.db.close)

    def test_grain_values_and_nulls(self):
        summary = w3.load(self.db)
        self.assertEqual(summary["fact_rows"], 3)                       # only scope=ticker, variant=all rows
        row = self.db.execute("""SELECT f.sentiment_mean, f.reddit_volume, mm.MajorityStatus, f.winrate_1h,
                                        f.winrate_p_value_1h, f.winrate_2h, f.winrate_3h, f.winrate_12h, f.close
                                 FROM FactMarketSentiment f JOIN DimTicker k USING (TickerID)
                                 JOIN DimTime t USING (TimeID) LEFT JOIN DimMajoritySentiment mm USING (MajorityID)
                                 WHERE k.TickerSymbol = 'AAPL' AND t.ts_utc = '2025-03-04T14:00:00+00:00'""").fetchone()
        self.assertEqual(row[:3], (0.4, 4, "positive"))
        self.assertAlmostEqual(row[3], 55.0)                            # fraction -> percent
        self.assertEqual(row[4], 0.01)
        self.assertEqual(row[5:8], (None, None, None))                  # other panel / predictor / insufficient -> NULL
        self.assertEqual(row[8], 100.0)

    def test_no_text_hour_keeps_null_not_zero(self):
        w3.load(self.db)
        row = self.db.execute("""SELECT f.sentiment_mean, f.pos_ratio, f.reddit_volume, f.MajorityID FROM FactMarketSentiment f
                                 JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID)
                                 WHERE k.TickerSymbol = 'AAPL' AND t.ts_utc = '2025-03-04T15:00:00+00:00'""").fetchone()
        self.assertEqual(row, (None, None, 0, None))

    def test_fixed_source_and_config_and_rerun(self):
        w3.load(self.db)
        w3.load(self.db)                                                # rebuild must not duplicate rows
        src, cfg, n = self.db.execute("""SELECT COUNT(DISTINCT SentimentSourceID), COUNT(DISTINCT DetectionConfigID), COUNT(*)
                                         FROM FactMarketSentiment""").fetchone()
        self.assertEqual((src, cfg, n), (1, 1, 3))
        z, s, h = self.db.execute("""SELECT ZscoreThreshold, SentimentThreshold, Horizon FROM DimDetectionConfig
                                     WHERE ConfigID = (SELECT DetectionConfigID FROM FactMarketSentiment LIMIT 1)""").fetchone()
        self.assertEqual((z, s, h), w3.DEFAULT_CONFIG)


if __name__ == "__main__":
    unittest.main()
