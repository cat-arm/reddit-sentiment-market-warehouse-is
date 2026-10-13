import os
import sqlite3
import tempfile
import unittest

from etl import merge_panel
from etl.merge_panel import MARKET_COLUMNS, REDDIT_COLUMNS

T13 = 1_700_000_000 // 3600 * 3600          # an hour boundary
ISO = lambda e: __import__("datetime").datetime.fromtimestamp(e, __import__("datetime").timezone.utc).isoformat()


def make_db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE DimTicker (TickerSymbol TEXT, AssetClass TEXT)")
    db.execute("INSERT INTO DimTicker VALUES ('AAA','stock_etf'), ('BTC','crypto')")
    cols = ", ".join(c + " REAL" for c in MARKET_COLUMNS)
    db.execute("CREATE TABLE market_hourly_features (ticker TEXT, hour_bucket TEXT, %s, volume_zscore_24 REAL)" % cols)
    for ticker in ("AAA", "BTC"):
        for k in range(2):                   # hours T13 and T13+1h
            db.execute("INSERT INTO market_hourly_features (ticker, hour_bucket, close) VALUES (?,?,?)",
                       (ticker, ISO(T13 + k * 3600), 100.0 + k))
    cols = ", ".join(c + (" TEXT" if c.startswith("majority") else " REAL") for c in REDDIT_COLUMNS)
    db.execute("CREATE TABLE reddit_hourly_features (variant TEXT, ticker TEXT, hour_utc INTEGER, "
               "reddit_volume INTEGER, %s)" % cols)
    # AAA-specific sentiment only at hour 0; market-wide ('ALL') sentiment at both hours
    db.execute("INSERT INTO reddit_hourly_features (variant, ticker, hour_utc, reddit_volume, sentiment_mean) "
               "VALUES ('all','AAA',?,5,0.4), ('all','ALL',?,50,0.1), ('all','ALL',?,60,0.2)",
               (T13, T13, T13 + 3600))
    db.commit()
    db.close()


class MergePanelTests(unittest.TestCase):
    def test_left_join_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.sqlite3")
            make_db(path)
            base, summary = merge_panel.build(path)
            db = sqlite3.connect(path)
            try:
                rows = db.execute("SELECT COUNT(*) FROM merged_hourly_panel").fetchone()[0]
                self.assertEqual(rows, base * 6)                               # 2 scopes x 3 variants, no row lost
                get = lambda scope, ticker, k: db.execute(
                    "SELECT reddit_volume, sentiment_mean, has_reddit_data, big_group FROM merged_hourly_panel "
                    "WHERE scope=? AND variant='all' AND ticker=? AND hour_utc=?",
                    (scope, ticker, T13 + k * 3600)).fetchone()
                self.assertEqual(get("ticker", "AAA", 0), (5, 0.4, 1, "stock_etf"))
                self.assertEqual(get("ticker", "AAA", 1), (0, None, 0, "stock_etf"))   # volume 0, sentiment NULL
                self.assertEqual(get("ticker", "BTC", 0), (0, None, 0, "crypto"))
                self.assertEqual(get("global", "BTC", 1), (60, 0.2, 1, "crypto"))      # global joins every ticker
                strong = db.execute("SELECT SUM(has_reddit_data) FROM merged_hourly_panel WHERE variant='strong'").fetchone()[0]
                self.assertEqual(strong, 0)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
