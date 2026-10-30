import sqlite3
import unittest

from etl.reddit_hourly_community import MODELS, SCHEMA, aggregate

H = 3600 * 100


def make_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE processed_text (src_rowid INTEGER PRIMARY KEY, created_utc INTEGER, subreddit TEXT)")
    db.execute("CREATE TABLE ticker_mentions (content_id TEXT, ticker TEXT, src_rowid INTEGER)")
    db.execute("CREATE TABLE sentiment_item (src_rowid INTEGER PRIMARY KEY, final_sentiment REAL, final_status TEXT, "
               "vader_score REAL, vader_status TEXT, finbert_score REAL, finbert_status TEXT)")
    texts = [(1, H + 10, "stocks", 0.6, "positive"), (2, H + 20, "stocks", -0.4, "negative"),
             (3, H + 30, "options", 0.02, "neutral"), (4, H + 3600, "options", 0.2, "positive")]
    for rowid, ts, sub, score, status in texts:
        db.execute("INSERT INTO processed_text VALUES (?,?,?)", (rowid, ts, sub))
        # VADER reads every text as 0.5 x the final score, FinBERT always says -0.1 (negative)
        db.execute("INSERT INTO sentiment_item VALUES (?,?,?,?,?,?,?)", (rowid, score, status, score / 2, status, -0.1, "negative"))
        db.execute("INSERT INTO ticker_mentions VALUES (?,?,?)", ("c%d" % rowid, "TSLA", rowid))
    db.execute("INSERT INTO ticker_mentions VALUES ('x', 'AAPL', 3)")
    return db


class CommunityHourlyTests(unittest.TestCase):
    def setUp(self):
        self.all = list(aggregate(make_db()))
        self.rows = {(r[0], r[1], r[2]): r for r in self.all if r[9] == "VADER+FinBERT"}

    def test_one_row_per_ticker_hour_and_community(self):
        r = self.rows[("TSLA", H, "r/stocks")]
        self.assertEqual((r[3], r[6], r[7], r[8]), (2, 1, 1, 0))                # texts, pos, neg, neu
        self.assertAlmostEqual(r[4], 0.6 - 0.4)
        self.assertAlmostEqual(r[5], 0.6 + 0.4)
        self.assertEqual(self.rows[("TSLA", H, "r/options")][3], 1)
        self.assertEqual(self.rows[("AAPL", H, "r/options")][3], 1)

    def test_hour_without_text_has_no_row(self):
        self.assertNotIn(("AAPL", H + 3600, "r/options"), self.rows)

    def test_each_model_reads_its_own_scores(self):
        by_model = {(r[9], r[0], r[1], r[2]): r for r in self.all}
        self.assertEqual({r[9] for r in self.all}, {m[0] for m in MODELS})
        vader = by_model[("VADER", "TSLA", H, "r/stocks")]
        self.assertAlmostEqual(vader[4], (0.6 - 0.4) / 2)
        self.assertEqual((vader[6], vader[7], vader[8]), (1, 1, 0))
        fin = by_model[("FinBERT", "TSLA", H, "r/stocks")]
        self.assertAlmostEqual(fin[4], -0.2)
        self.assertEqual((fin[3], fin[6], fin[7], fin[8]), (2, 0, 2, 0))               # same texts, all negative
        self.assertEqual(vader[3], fin[3])

    def test_schema_creates(self):
        sqlite3.connect(":memory:").execute(SCHEMA)


if __name__ == "__main__":
    unittest.main()
