import contextlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl import clean_text, quality_filter
from etl.quality_filter import classify


class ClassifyTest(unittest.TestCase):
    def test_bot_and_moderation_notices_are_rejected(self):
        for text in (
            "Bagholder spotted. I am a bot, and this action was performed automatically. Please contact the moderators.",
            "Your submission was removed because it is a short post.",
            "Your submission in was automatically removed because your account has insufficient Karma.",
            "!banbet",
            "[ Removed by moderator ]",
            "User Report| | | | :--|:--|:--|:-- Total Submissions | 10 | First Seen In WSB | 3 years ago",
            "Hello, Direct links to images are require an r/ CryptoCurrency membership",
        ):
            self.assertEqual(classify(text), "bot_or_moderation_text", text)

    def test_ordinary_opinions_that_mention_moderators_or_removal_pass(self):
        for text in (
            "The moderator here is clueless but TSLA to the moon",
            "My post got removed lol, anyway NVDA earnings tomorrow",
            "I am a bull on AMD",
        ):
            self.assertIsNone(classify(text), text)

    def test_short_real_words_pass_but_symbol_only_text_is_too_short(self):
        for text in ("Yes", "lol", "No", "Same", "face with tears of joy"):
            self.assertIsNone(classify(text), text)
        for text in ("!!!", "420", "+10%", "?", "K"):
            self.assertEqual(classify(text), "too_short", text)

    def test_non_latin_scripts_are_not_english(self):
        self.assertEqual(classify("这个股票明天会涨吗"), "non_english")
        self.assertEqual(classify("Привет всем, что думаете про биткоин сегодня"), "non_english")

    def test_foreign_latin_text_is_not_english(self):
        self.assertEqual(classify("Mañana el mercado va a subir porque los bancos tienen muy buenas noticias"),
                         "non_english")
        self.assertEqual(classify("Das ist nicht gut und die Aktie ist auch schon wieder mit dem Markt gefallen"),
                         "non_english")

    def test_english_with_jargon_or_a_foreign_word_passes(self):
        for text in (
            "TSLA 450c 3/21 calls printing hard today",
            "I love the el chapo documentary but this stock is a scam",
            "Die tesler die smiling face with horns",
            "Short text no",
        ):
            self.assertIsNone(classify(text), text)


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db_path = self.tmp / "t.sqlite3"
        db = sqlite3.connect(self.db_path)
        db.execute("""CREATE TABLE reddit_content (id TEXT PRIMARY KEY, content_type TEXT, subreddit TEXT,
            created_utc INTEGER, title TEXT, selftext TEXT, body TEXT, text_status TEXT, link_id TEXT)""")
        rows = [
            ("a", "comment", "stocks", 3600, None, None, "TSLA looks strong today", "available"),
            ("b", "comment", "stocks", 3700, None, None, "I am a bot, and this action was performed automatically.",
             "available"),
            ("c", "comment", "stocks", 3800, None, None, "[removed]", "removed"),
            ("d", "comment", "stocks", 3900, None, None, "![img](emote|t5_2th52|1)", "available"),
            ("e", "comment", "stocks", 7300, None, None, "420", "available"),
            ("f", "comment", "Bitcoin", 3600, None, None, "not in scope", "available"),
        ]
        db.executemany("INSERT INTO reddit_content (id, content_type, subreddit, created_utc, title, selftext, body, text_status) VALUES (?,?,?,?,?,?,?,?)", rows)
        db.commit()
        db.close()
        clean_text.process(self.db_path)
        self.totals = quality_filter.process(self.db_path)

    def query(self, sql):
        with contextlib.closing(sqlite3.connect(self.db_path)) as db:
            return db.execute(sql).fetchall()

    def test_every_in_scope_raw_row_is_counted_exactly_once(self):
        total = self.query("SELECT SUM(row_count) FROM data_quality_audit")[0][0]
        self.assertEqual(total, 5)             # a..e; the Bitcoin row is out of scope

    def test_reasons(self):
        got = dict(self.query("SELECT remove_reason, SUM(row_count) FROM data_quality_audit GROUP BY 1"))
        self.assertEqual(got, {"passed": 1, "bot_or_moderation_text": 1, "removed": 1,
                               "empty_after_cleaning": 1, "too_short": 1})

    def test_view_keeps_only_passed_rows(self):
        self.assertEqual(self.query("SELECT content_id FROM filtered_text"), [("a",)])


if __name__ == "__main__":
    unittest.main()
