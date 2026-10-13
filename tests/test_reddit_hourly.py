import sqlite3
import unittest

from etl.reddit_hourly import VARIANTS, aggregate, majority

H = 3600 * 100


def make_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE processed_text (src_rowid INTEGER PRIMARY KEY, created_utc INTEGER)")
    db.execute("CREATE TABLE ticker_mentions (content_id TEXT, ticker TEXT, src_rowid INTEGER)")
    db.execute("CREATE TABLE sentiment_item (src_rowid INTEGER PRIMARY KEY, vader_status TEXT, finbert_status TEXT, "
               "final_sentiment REAL, final_status TEXT)")
    # hour H: +0.6 pos, -0.4 neg, 0.02 neu, 0.0 neu ; hour H+1: one text +0.2 pos
    texts = [(1, H + 10, 0.6, "positive"), (2, H + 20, -0.4, "negative"), (3, H + 3599, 0.02, "neutral"),
             (4, H + 30, 0.0, "neutral"), (5, H + 3600, 0.2, "positive")]
    for rowid, ts, score, status in texts:
        db.execute("INSERT INTO processed_text VALUES (?,?)", (rowid, ts))
        db.execute("INSERT INTO sentiment_item VALUES (?,?,?,?,?)", (rowid, status, "neutral", score, status))
    db.execute("INSERT INTO ticker_mentions VALUES ('a','TSLA',1)")
    db.execute("INSERT INTO ticker_mentions VALUES ('b','TSLA',3)")
    db.execute("INSERT INTO ticker_mentions VALUES ('c','AAPL',2)")
    return db


class HourlyTests(unittest.TestCase):
    def setUp(self):
        self.db = make_db()

    def rows(self, variant, ticker=None):
        return {(r[1], r[2]): r for r in aggregate(self.db, variant, VARIANTS[variant], ticker)}

    def test_market_hour_by_hand(self):
        r = self.rows("all")[("ALL", H)]
        self.assertEqual(r[3], 4)                                  # volume
        self.assertAlmostEqual(r[4], (0.6 - 0.4 + 0.02 + 0.0) / 4)  # sentiment_mean
        self.assertAlmostEqual(r[5], (0.6 + 0.4 + 0.02) / 4)        # abs mean
        self.assertAlmostEqual(r[6] + r[7] + r[8], 1.0)
        self.assertEqual(r[11], "neutral")                         # 2 neutral vs 1 pos vs 1 neg
        self.assertAlmostEqual(r[12], 0.5)

    def test_strong_filters_texts_before_averaging(self):
        r = self.rows("strong")[("ALL", H)]
        self.assertEqual(r[3], 2)                                  # neutral texts dropped
        self.assertAlmostEqual(r[4], (0.6 - 0.4) / 2)              # differs from the 'all' mean
        self.assertEqual(self.rows("quality")[("ALL", H)][3], 2)
        self.assertNotIn(("ALL", H + 3600 * 5), self.rows("strong"))

    def test_per_ticker_uses_only_its_texts(self):
        r = self.rows("all", "__each__")
        self.assertEqual(r[("TSLA", H)][3], 2)
        self.assertAlmostEqual(r[("TSLA", H)][4], (0.6 + 0.02) / 2)
        self.assertEqual(r[("AAPL", H)][3], 1)
        self.assertNotIn(("AAPL", H + 3600), r)                    # no text -> no row (not 0)

    def test_majority_ties(self):
        self.assertEqual(majority(1, 1, 0), ("neutral", 1))
        self.assertEqual(majority(0, 2, 2), ("positive", 2))


if __name__ == "__main__":
    unittest.main()
