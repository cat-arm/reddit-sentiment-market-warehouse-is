import contextlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl import clean_text, extract_tickers, quality_filter
from etl.ticker_dict import TickerMatcher


class FindSplitTest(unittest.TestCase):
    def test_strong_and_weak_are_separated_and_add_up_to_find(self):
        matcher = TickerMatcher()
        text = "gold is up, $TSLA and Tesla too"
        strong, weak = matcher.find_split(text)
        self.assertEqual(dict(strong), {"TSLA": 2})
        self.assertEqual(dict(weak), {"GC=F": 1})
        self.assertEqual(matcher.find(text), strong + weak)
        self.assertEqual(matcher.find(text, include_weak=False), strong)


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = self.tmp / "t.sqlite3"
        db = sqlite3.connect(self.db_path)
        db.execute("""CREATE TABLE reddit_content (id TEXT PRIMARY KEY, content_type TEXT, subreddit TEXT,
            created_utc INTEGER, title TEXT, selftext TEXT, body TEXT, text_status TEXT, link_id TEXT)""")
        rows = [
            ("a", "comment", "stocks", 3600, None, None, "TSLA TSLA and Tesla, also $NVDA", "available"),
            ("b", "comment", "stocks", 3700, None, None, "gold is rising", "available"),
            ("c", "comment", "stocks", 3800, None, None, "nothing about any asset here", "available"),
            ("d", "comment", "stocks", 3900, None, None,
             "I am a bot, and this action was performed automatically. TSLA", "available"),
            ("e", "comment", "CryptoCurrency", 4000, None, None, "doge to the moon", "available"),
        ]
        db.executemany("INSERT INTO reddit_content (id, content_type, subreddit, created_utc, title, selftext, body, text_status) VALUES (?,?,?,?,?,?,?,?)", rows)
        db.commit()
        db.close()
        clean_text.process(self.db_path)
        quality_filter.process(self.db_path)
        self.totals = extract_tickers.process(self.db_path)

    def query(self, sql):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            return db.execute(sql).fetchall()

    def test_counts_and_strong_weak_split(self):
        got = self.query("SELECT content_id, ticker, mention_count, strong_count FROM ticker_mentions ORDER BY 1,2")
        self.assertEqual(got, [("a", "NVDA", 1, 1), ("a", "TSLA", 3, 3), ("b", "GC=F", 1, 0),
                               ("e", "DOGE-USD", 1, 1)])

    def test_bot_text_is_not_scanned_and_rerun_adds_nothing(self):
        self.assertEqual(self.query("SELECT COUNT(*) FROM ticker_mentions WHERE content_id = 'd'"), [(0,)])
        extract_tickers.process(self.db_path)
        self.assertEqual(self.query("SELECT COUNT(*) FROM ticker_mentions"), [(4,)])


if __name__ == "__main__":
    unittest.main()
