import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl import clean_text as ct


class CleanTextTest(unittest.TestCase):
    def test_reddit_emote_markup_removed_but_signal_text_kept(self):
        self.assertEqual(ct.clean_text("pltr to 30 ![img](emote|t5_2th52|4258)"), "pltr to 30")

    def test_text_that_is_only_emote_becomes_empty(self):
        self.assertEqual(ct.clean_text("![img](emote|t5_2th52|27421)![img](emote|t5_2th52|27421)"), "")

    def test_cashtag_survives(self):
        self.assertEqual(ct.clean_text("$GME to the moon!!!"), "$GME to the moon!!!")

    def test_escaped_cashtag_is_unescaped(self):
        self.assertEqual(ct.clean_text(r"loading up on \$TSLA"), "loading up on $TSLA")

    def test_percent_prices_and_symbols_survive(self):
        text = "NVDA +12.5% to $450.25 today?!"
        self.assertEqual(ct.clean_text(text), text)

    def test_case_and_apostrophes_are_preserved(self):
        self.assertEqual(ct.clean_text("This is GREAT but don't buy"), "This is GREAT but don't buy")

    def test_curly_apostrophe_is_normalised(self):
        self.assertEqual(ct.clean_text("don’t sell"), "don't sell")

    def test_url_removed_and_markdown_link_keeps_its_text(self):
        self.assertEqual(ct.clean_text("see https://example.com/a?b=1 now"), "see now")
        self.assertEqual(ct.clean_text("[earnings](https://example.com/e) beat"), "earnings beat")
        self.assertEqual(ct.clean_text("www.example.com is down"), "is down")

    def test_html_entities_are_decoded(self):
        self.assertEqual(ct.clean_text("AT&amp;T"), "AT&T")
        self.assertEqual(ct.clean_text("&gt; quoted line\nreply"), "quoted line reply")   # quote marker at line start
        self.assertEqual(ct.clean_text("AT&amp;T &gt; Verizon"), "AT&T > Verizon")       # comparison mid-sentence stays

    def test_user_and_subreddit_mentions_removed(self):
        self.assertEqual(ct.clean_text("thanks u/some_user from r/wallstreetbets"), "thanks from")

    def test_markdown_syntax_removed(self):
        text = "# Title\n> quoted line\n**bold** and *italic* and `code`\n---\nend"
        self.assertEqual(ct.clean_text(text), "Title quoted line bold and italic and code end")

    def test_zero_width_nbsp_and_newlines_collapse(self):
        self.assertEqual(ct.clean_text("a​b\xa0c\n\n d"), "ab c d")

    def test_emoji_become_words(self):
        self.assertEqual(ct.clean_text("my portfolio is down \U0001F62D"), "my portfolio is down loudly crying face")
        self.assertEqual(ct.clean_text("to the moon \U0001F680\U0001F680"), "to the moon rocket rocket")

    def test_emoji_skin_tone_words_are_dropped(self):
        self.assertEqual(ct.clean_text("thumbs up \U0001F44D\U0001F3FD"), "thumbs up thumbs up")

    def test_thai_text_is_not_dropped_by_the_cleaner(self):
        self.assertEqual(ct.clean_text("ซื้อ $GME"), "ซื้อ $GME")

    def test_non_string_and_empty_inputs(self):
        for value in (None, "", 42):
            self.assertEqual(ct.clean_text(value), "")

    def test_cleaning_is_idempotent(self):
        for text in ("$GME to the moon!!! \U0001F680", "[a](http://x.y) **b** u/z", "don’t &amp; won't"):
            once = ct.clean_text(text)
            self.assertEqual(ct.clean_text(once), once)

    def test_submission_uses_title_plus_selftext(self):
        self.assertEqual(ct.build_final_text("submission", "NVDA earnings", "huge beat", None),
                         "NVDA earnings huge beat")

    def test_link_post_uses_title_only_and_removed_body_is_ignored(self):
        self.assertEqual(ct.build_final_text("submission", "Link post", "", None), "Link post")
        self.assertEqual(ct.build_final_text("submission", "Title stays", "[removed]", None), "Title stays")

    def test_comment_without_known_post_uses_body_only(self):
        self.assertEqual(ct.build_final_text("comment", "ignored", "ignored", "Buy $AAPL!"), "Buy $AAPL!")

    def test_comment_gets_the_title_of_its_post_as_context(self):
        self.assertEqual(ct.build_texts("comment", None, None, "hold", "This stock is amazing"),
                         ("This stock is amazing hold", "hold"))

    def test_comment_with_empty_body_is_empty_even_if_the_post_has_a_title(self):
        self.assertEqual(ct.build_texts("comment", None, None, "![img](emote|t5_1|2)", "This stock is amazing"),
                         ("", ""))

    def test_submission_own_text_equals_final_text(self):
        self.assertEqual(ct.build_texts("submission", "NVDA beat", "great", None, "ignored"),
                         ("NVDA beat great", "NVDA beat great"))


class ProcessTest(unittest.TestCase):
    def make_db(self, root):
        path = Path(root) / "test.sqlite3"
        db = sqlite3.connect(str(path))
        db.execute("""CREATE TABLE reddit_content (id TEXT PRIMARY KEY, content_type TEXT, subreddit TEXT,
            created_utc INTEGER, title TEXT, selftext TEXT, body TEXT, text_status TEXT, link_id TEXT)""")
        db.executemany("INSERT INTO reddit_content VALUES (?,?,?,?,?,?,?,?,?)", [
            ("c1", "comment", "wallstreetbets", 100, None, None, "$GME to the moon", "available", "s1"),
            ("c2", "comment", "Bitcoin", 101, None, None, "out of scope subreddit", "available", "s1"),
            ("c3", "comment", "stocks", 102, None, None, "![img](emote|t5_1|2)", "available", "s1"),
            ("c4", "comment", "stocks", 103, None, None, "[removed]", "removed", "s1"),
            ("s1", "submission", "investing", 104, "NVDA beat", "great quarter", None, "available", None),
            ("c5", "comment", "stocks", 105, None, None, "hold", "available", "missing_post"),
        ])
        db.commit()
        db.close()
        return path

    def test_process_filters_scope_status_and_empty_and_resumes(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.make_db(root)
            totals = ct.process(path, window=2)
            self.assertEqual(totals, {"read": 4, "written": 3, "empty": 1, "comments_with_post_title": 1})
            db = sqlite3.connect(str(path))
            rows = db.execute("SELECT content_id, final_text, own_text, token_len, cleaner_version FROM processed_text "
                              "ORDER BY src_rowid").fetchall()
            self.assertEqual(rows, [("c1", "NVDA beat $GME to the moon", "$GME to the moon", 6, ct.CLEANER_VERSION),
                                    ("s1", "NVDA beat great quarter", "NVDA beat great quarter", 4, ct.CLEANER_VERSION),
                                    ("c5", "hold", "hold", 1, ct.CLEANER_VERSION)])
            db.close()
            again = ct.process(path, window=2)           # nothing left to do: no duplicates
            self.assertEqual(again, {"read": 0, "written": 0, "empty": 0, "comments_with_post_title": 0})
            db = sqlite3.connect(str(path))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM processed_text").fetchone()[0], 3)
            db.close()


if __name__ == "__main__":
    unittest.main()
