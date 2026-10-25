import contextlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl import clean_text, extract_tickers, load_fact_reddit_volume, quality_filter, seed_dims

HOUR = 1727740800          # 2024-10-01T00:00:00Z


class SeedDimsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = self.tmp / "t.sqlite3"

    def counts(self):
        db = sqlite3.connect(self.db_path)
        with contextlib.closing(db):
            return {t: db.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                    for t in ("DimTicker", "DimSource", "DimSentimentSource", "DimMajoritySentiment",
                              "DimDetectionConfig", "DimTime")}

    def test_dimension_sizes_and_idempotence(self):
        seed_dims.main(["--db", str(self.db_path)])
        expected = {"DimTicker": 34, "DimSource": 12, "DimSentimentSource": 7, "DimMajoritySentiment": 3,
                    "DimDetectionConfig": 30, "DimTime": 17544}
        self.assertEqual(self.counts(), expected)
        seed_dims.main(["--db", str(self.db_path)])
        self.assertEqual(self.counts(), expected)

    def test_proposal_example_config_exists(self):
        seed_dims.main(["--db", str(self.db_path)])
        db = sqlite3.connect(self.db_path)
        with contextlib.closing(db):
            row = db.execute("SELECT 1 FROM DimDetectionConfig WHERE ZscoreThreshold=2.0 "
                             "AND SentimentThreshold=0.3 AND Horizon='1h'").fetchone()
        self.assertIsNotNone(row)


class FactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = self.tmp / "t.sqlite3"
        db = sqlite3.connect(self.db_path)
        db.execute("""CREATE TABLE reddit_content (id TEXT PRIMARY KEY, content_type TEXT, subreddit TEXT,
            created_utc INTEGER, title TEXT, selftext TEXT, body TEXT, text_status TEXT, link_id TEXT)""")
        rows = [
            # hour 0, stocks comments: two texts mention TSLA (3 + 1 mentions), one also NVDA
            ("a", "comment", "stocks", HOUR + 10, None, None, "TSLA TSLA and Tesla, $NVDA", "available"),
            ("b", "comment", "stocks", HOUR + 3599, None, None, "I like TSLA", "available"),
            # hour 1, a post in wallstreetbets
            ("c", "submission", "wallstreetbets", HOUR + 3600, "NVDA earnings", "", None, "available"),
            # no mention at all
            ("d", "comment", "stocks", HOUR + 20, None, None, "nothing here", "available"),
        ]
        db.executemany("INSERT INTO reddit_content (id, content_type, subreddit, created_utc, title, selftext, body, text_status) VALUES (?,?,?,?,?,?,?,?)", rows)
        db.commit()
        db.close()
        clean_text.process(self.db_path)
        quality_filter.process(self.db_path)
        extract_tickers.process(self.db_path)
        db = sqlite3.connect(self.db_path)
        self.addCleanup(db.close)
        self.result = load_fact_reddit_volume.load(db)
        self.rows = db.execute(
            "SELECT t.ts_utc, k.TickerSymbol, s.Subreddit, s.ContentType, f.reddit_volume, f.ticker_mention_count "
            "FROM FactRedditVolume f JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID) "
            "JOIN DimSource s USING (SourceID) ORDER BY 1,2,3").fetchall()

    def test_hand_counted_rows(self):
        # reddit_volume = ALL texts of that hour/source, so hour 0 r/stocks Comment is 3 (a, b and the text "d" that
        # mentions no ticker) on BOTH ticker rows; ticker_mention_count = mentions of that ticker.
        self.assertEqual(self.rows, [
            ("2024-10-01T00:00:00+00:00", "NVDA", "r/stocks", "Comment", 3, 1),
            ("2024-10-01T00:00:00+00:00", "TSLA", "r/stocks", "Comment", 3, 4),
            ("2024-10-01T01:00:00+00:00", "NVDA", "r/wallstreetbets", "Post", 1, 1),
        ])

    def test_totals_match_ticker_mentions(self):
        self.assertEqual(self.result["mention_count_total"], self.result["mention_count_expected"])
        self.assertEqual(self.result["rows_without_total_volume"], 0)

    def test_total_volume_table_counts_every_filtered_text(self):
        db = sqlite3.connect(self.db_path)
        with contextlib.closing(db):
            total = db.execute("SELECT SUM(texts) FROM reddit_volume_hourly").fetchone()[0]
            kept = db.execute("SELECT COUNT(*) FROM filtered_text").fetchone()[0]
        self.assertEqual(total, kept)


if __name__ == "__main__":
    unittest.main()
