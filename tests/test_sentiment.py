import contextlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl import clean_text, quality_filter, sentiment_finbert, sentiment_vader
from etl.common import status_of


class StatusTest(unittest.TestCase):
    def test_neutral_band_edges(self):
        self.assertEqual(status_of(0.05), "positive")          # edges are directional (VADER convention)
        self.assertEqual(status_of(0.0499), "neutral")
        self.assertEqual(status_of(-0.0499), "neutral")
        self.assertEqual(status_of(-0.05), "negative")
        self.assertEqual(status_of(0.0), "neutral")


class FakeScorer:
    """Stands in for the GPU model: score = +0.9 when the text says 'moon', -0.9 when 'crash', else 0."""
    calls = 0

    def score(self, texts):
        FakeScorer.calls += 1
        return [0.9 if "moon" in t else -0.9 if "crash" in t else 0.0 for t in texts]


class ScoringTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = self.tmp / "t.sqlite3"
        db = sqlite3.connect(self.db_path)
        db.execute("""CREATE TABLE reddit_content (id TEXT PRIMARY KEY, content_type TEXT, subreddit TEXT,
            created_utc INTEGER, title TEXT, selftext TEXT, body TEXT, text_status TEXT, link_id TEXT)""")
        rows = [
            ("a", "comment", "stocks", 3600, None, None, "This is GREAT, TSLA to the moon", "available"),
            ("b", "comment", "stocks", 3700, None, None, "Terrible, the market will crash and I am sad", "available"),
            ("c", "comment", "stocks", 3800, None, None, "I am a bot, and this action was performed automatically.",
             "available"),
            ("d", "comment", "stocks", 3900, None, None, "SPY closed at 450", "available"),
        ]
        db.executemany("INSERT INTO reddit_content (id, content_type, subreddit, created_utc, title, selftext, body, text_status) VALUES (?,?,?,?,?,?,?,?)", rows)
        db.commit()
        db.close()
        clean_text.process(self.db_path)
        quality_filter.process(self.db_path)

    def query(self, sql):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            return db.execute(sql).fetchall()

    def test_vader_scores_every_passed_text_in_range_and_skips_rejected_bot_text(self):
        self.assertEqual(sentiment_vader.process(self.db_path), {"scored": 3})
        rows = self.query("SELECT p.content_id, v.vader_score, v.vader_status FROM sentiment_vader v "
                          "JOIN processed_text p ON p.src_rowid = v.src_rowid ORDER BY 1")
        self.assertEqual([r[0] for r in rows], ["a", "b", "d"])                   # bot text 'c' is not scored
        self.assertTrue(all(-1 <= r[1] <= 1 for r in rows))
        self.assertEqual([r[2] for r in rows], ["positive", "negative", "neutral"])

    def test_vader_is_resumable_and_does_not_rescore(self):
        sentiment_vader.process(self.db_path)
        self.assertEqual(sentiment_vader.process(self.db_path), {"scored": 0})
        self.assertEqual(self.query("SELECT COUNT(*) FROM sentiment_vader"), [(3,)])

    def test_finbert_wrapper_writes_score_and_status_and_resumes(self):
        FakeScorer.calls = 0
        self.assertEqual(sentiment_finbert.process(self.db_path, scorer=FakeScorer()), {"scored": 3})
        rows = self.query("SELECT p.content_id, f.finbert_score, f.finbert_status FROM sentiment_finbert f "
                          "JOIN processed_text p ON p.src_rowid = f.src_rowid ORDER BY 1")
        self.assertEqual(rows, [("a", 0.9, "positive"), ("b", -0.9, "negative"), ("d", 0.0, "neutral")])
        calls = FakeScorer.calls
        self.assertEqual(sentiment_finbert.process(self.db_path, scorer=FakeScorer()), {"scored": 0})
        self.assertEqual(FakeScorer.calls, calls)                                 # nothing left to score


if __name__ == "__main__":
    unittest.main()
