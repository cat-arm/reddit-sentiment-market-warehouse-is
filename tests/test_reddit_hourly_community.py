import sqlite3
import unittest

from etl.reddit_hourly_community import MODELS, SCHEMA, SCHEMA_GLOBAL, VARIANTS, aggregate, aggregate_global

H = 3600 * 100


def make_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE processed_text (src_rowid INTEGER PRIMARY KEY, created_utc INTEGER, subreddit TEXT, content_type TEXT)")
    db.execute("CREATE TABLE ticker_mentions (content_id TEXT, ticker TEXT, src_rowid INTEGER)")
    db.execute("CREATE TABLE sentiment_item (src_rowid INTEGER PRIMARY KEY, final_sentiment REAL, final_status TEXT, "
               "vader_score REAL, vader_status TEXT, finbert_score REAL, finbert_status TEXT)")
    texts = [(1, H + 10, "stocks", 0.6, "positive"), (2, H + 20, "stocks", -0.4, "negative"),
             (3, H + 30, "options", 0.02, "neutral"), (4, H + 3600, "options", 0.2, "positive")]
    for rowid, ts, sub, score, status in texts:
        db.execute("INSERT INTO processed_text VALUES (?,?,?,?)", (rowid, ts, sub, "submission" if rowid == 2 else "comment"))
        # VADER reads every text as 0.5 x the final score, FinBERT always says -0.1 (negative)
        db.execute("INSERT INTO sentiment_item VALUES (?,?,?,?,?,?,?)", (rowid, score, status, score / 2, status, -0.1, "negative"))
        db.execute("INSERT INTO ticker_mentions VALUES (?,?,?)", ("c%d" % rowid, "TSLA", rowid))
    db.execute("INSERT INTO ticker_mentions VALUES ('x', 'AAPL', 3)")
    db.execute("INSERT INTO processed_text VALUES (5, ?, 'stocks', 'comment')", (H + 40,))      # a text that mentions no ticker
    db.execute("INSERT INTO sentiment_item VALUES (5, 0.9, 'positive', 0.9, 'positive', 0.9, 'positive')")
    return db


class CommunityHourlyTests(unittest.TestCase):
    def setUp(self):
        self.all = list(aggregate(make_db()))
        self.rows = {(r[0], r[1], r[2], r[11]): r for r in self.all if r[9] == "VADER+FinBERT" and r[10] == "all"}

    def test_one_row_per_ticker_hour_community_and_content_type(self):
        post, comment = self.rows[("TSLA", H, "r/stocks", "Post")], self.rows[("TSLA", H, "r/stocks", "Comment")]
        self.assertEqual((post[3], post[6], post[7], post[8]), (1, 0, 1, 0))             # text 2 is a post: -0.4, negative
        self.assertEqual((comment[3], comment[6], comment[7], comment[8]), (1, 1, 0, 0))   # text 1 is a comment: +0.6
        self.assertAlmostEqual(post[4] + comment[4], 0.6 - 0.4)                          # the two types sum to the hour
        self.assertAlmostEqual(post[5] + comment[5], 0.6 + 0.4)
        self.assertEqual(self.rows[("TSLA", H, "r/options", "Comment")][3], 1)
        self.assertEqual(self.rows[("AAPL", H, "r/options", "Comment")][3], 1)

    def test_hour_without_text_has_no_row(self):
        self.assertNotIn(("AAPL", H + 3600, "r/options", "Comment"), self.rows)

    def test_each_model_reads_its_own_scores(self):
        by_model = {(r[9], r[10], r[0], r[1], r[2], r[11]): r for r in self.all}
        self.assertEqual({r[9] for r in self.all}, {m[0] for m in MODELS})
        vader = by_model[("VADER", "all", "TSLA", H, "r/stocks", "Comment")]
        self.assertAlmostEqual(vader[4], 0.6 / 2)
        self.assertEqual((vader[6], vader[7], vader[8]), (1, 0, 0))
        fin = by_model[("FinBERT", "all", "TSLA", H, "r/stocks", "Comment")]
        self.assertAlmostEqual(fin[4], -0.1)
        self.assertEqual((fin[3], fin[6], fin[7], fin[8]), (1, 0, 1, 0))               # the same text, read as negative
        self.assertEqual(vader[3], fin[3])

    def test_the_strong_and_quality_variants_drop_weak_texts(self):
        by_key = {(r[9], r[10], r[0], r[1], r[2], r[11]): r for r in self.all}
        self.assertNotIn(("VADER+FinBERT", "strong", "TSLA", H, "r/options", "Comment"), by_key)          # its only text scores 0.02
        self.assertEqual(by_key[("VADER+FinBERT", "strong", "TSLA", H, "r/stocks", "Comment")][3], 1)       # 0.6 is strong
        self.assertEqual(by_key[("VADER+FinBERT", "strong", "TSLA", H, "r/stocks", "Post")][3], 1)          # -0.4 is strong
        self.assertEqual(by_key[("VADER+FinBERT", "quality", "TSLA", H, "r/stocks", "Post")][3], 1)         # |0.4| >= 0.30
        self.assertNotIn(("VADER+FinBERT", "quality", "TSLA", H + 3600, "r/options", "Comment"), by_key)    # 0.2 is below 0.30

    def test_the_market_counts_every_text_not_only_those_that_mention_a_ticker(self):
        market = {(r[0], r[1], r[8], r[9], r[10]): r for r in aggregate_global(make_db())}
        comments, posts = market[(H, "r/stocks", "VADER+FinBERT", "all", "Comment")], market[(H, "r/stocks", "VADER+FinBERT", "all", "Post")]
        self.assertEqual((comments[2], posts[2]), (2, 1))                               # texts 1 and 5 are comments (5 mentions nothing), 2 is a post
        self.assertAlmostEqual(comments[3] + posts[3], 0.6 - 0.4 + 0.9)
        self.assertEqual(market[(H, "r/stocks", "VADER+FinBERT", "strong", "Comment")][2], 2)

    def test_schemas_create(self):
        sqlite3.connect(":memory:").execute(SCHEMA)
        sqlite3.connect(":memory:").execute(SCHEMA_GLOBAL)
        self.assertEqual([v[0] for v in VARIANTS], ["all", "strong", "quality"])


if __name__ == "__main__":
    unittest.main()
