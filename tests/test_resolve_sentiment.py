import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl.resolve_sentiment import RuleMatcher, is_ambiguous, migrate, resolve


class RuleSignalTests(unittest.TestCase):
    def setUp(self):
        self.m = RuleMatcher()

    def test_signals(self):
        self.assertEqual(self.m.signal("I am BULLISH on this"), "positive")
        self.assertEqual(self.m.signal("time to buy puts"), "negative")
        self.assertEqual(self.m.signal("bullish today, bearish tomorrow"), "mixed")
        self.assertEqual(self.m.signal("nothing here"), "none")
        self.assertEqual(self.m.signal("Buy  calls now"), "positive")

    def test_negation_is_ignored_not_flipped(self):
        self.assertEqual(self.m.signal("not bullish at all"), "none")
        self.assertEqual(self.m.signal("I don't buy calls"), "none")
        self.assertEqual(self.m.signal("not bullish but bearish"), "negative")

    def test_word_boundary(self):
        self.assertEqual(self.m.signal("unbullish"), "none")


class ResolveTests(unittest.TestCase):
    def check(self, v, f, rule, score, method):
        got = resolve(v, f, rule)
        self.assertAlmostEqual(got[0], score)
        self.assertEqual(got[1], method)

    def test_same_direction_proposal_example(self):
        self.check(0.60, 0.40, "none", 0.50, "same_direction")
        self.check(-0.6, -0.2, "positive", -0.4, "same_direction")

    def test_same_direction_far_uses_score_closer_to_zero(self):
        self.check(0.90, 0.10, "none", 0.10, "same_direction_far")               # proposal p30 example
        self.check(-0.90, -0.10, "positive", -0.10, "same_direction_far")
        self.check(0.90, 0.40, "none", 0.65, "same_direction")                   # gap exactly 0.50 is still averaged
        self.check(0.91, 0.40, "none", 0.40, "same_direction_far")

    def test_ambiguous_flag(self):
        for method in ("hard_conflict_no_rule", "hard_conflict_mixed_zero", "small_conflict_rule_clash"):
            self.assertEqual(is_ambiguous(method), 1, method)
        for method in ("both_neutral", "same_direction", "same_direction_far", "hard_conflict_rule",
                       "small_conflict_rule_agrees", "small_conflict_no_rule", "one_model"):
            self.assertEqual(is_ambiguous(method), 0, method)

    def test_small_conflict(self):
        self.check(0.03, 0.65, "positive", 0.65, "small_conflict_rule_agrees")   # proposal p28 example (VADER 0.05 -> 0.03)
        self.check(0.65, 0.0, "negative", 0.0, "small_conflict_rule_clash")
        self.check(0.65, 0.0, "mixed", 0.0, "small_conflict_rule_clash")
        self.check(0.0, 0.65, "none", 0.65, "small_conflict_no_rule")
        self.check(-0.3, 0.02, "negative", -0.3, "small_conflict_rule_agrees")

    def test_hard_conflict(self):
        self.check(-0.55, 0.65, "negative", -0.55, "hard_conflict_rule")         # proposal p29 example
        self.check(-0.55, 0.65, "positive", 0.65, "hard_conflict_rule")
        self.check(-0.55, 0.65, "none", 0.0, "hard_conflict_no_rule")
        self.check(-0.55, 0.65, "mixed", 0.0, "hard_conflict_mixed_zero")

    def test_extensions(self):
        self.check(0.02, -0.04, "none", -0.01, "both_neutral")
        self.check(0.05, 0.0, "positive", 0.05, "small_conflict_rule_agrees")     # edge 0.05 is directional
        self.check(0.4, None, "none", 0.4, "one_model")
        self.check(None, -0.4, "none", -0.4, "one_model")


class MigrateTests(unittest.TestCase):
    def test_migrate_old_table_in_place_and_idempotent(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            path = Path(folder) / "t.sqlite3"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE sentiment_item (src_rowid INTEGER PRIMARY KEY, vader_score REAL, vader_status TEXT,"
                       " finbert_score REAL, finbert_status TEXT, rule_signal TEXT, final_sentiment REAL,"
                       " final_status TEXT, final_method TEXT)")
            db.executemany("INSERT INTO sentiment_item VALUES (?,?,?,?,?,?,?,?,?)", [
                (1, 0.9, "positive", 0.1, "positive", "none", 0.5, "positive", "same_direction"),
                (2, 0.6, "positive", 0.4, "positive", "none", 0.5, "positive", "same_direction"),
                (3, 0.7, "positive", -0.6, "negative", "none", 0.0, "neutral", "hard_conflict_no_rule"),
                (4, 0.7, "positive", 0.0, "neutral", "mixed", 0.0, "neutral", "small_conflict_rule_clash"),
                (5, 0.0, "neutral", 0.0, "neutral", "none", 0.0, "neutral", "both_neutral")])
            db.commit()
            db.close()
            self.assertEqual(migrate(path), {"same_direction_far": 1, "flagged_ambiguous": 2})
            self.assertEqual(migrate(path), {"same_direction_far": 0, "flagged_ambiguous": 0})
            db = sqlite3.connect(path)
            rows = db.execute("SELECT src_rowid, final_sentiment, final_method, is_ambiguous FROM sentiment_item "
                              "ORDER BY 1").fetchall()
            db.close()
        self.assertEqual(rows, [(1, 0.1, "same_direction_far", 0), (2, 0.5, "same_direction", 0),
                                (3, 0.0, "hard_conflict_no_rule", 1), (4, 0.0, "small_conflict_rule_clash", 1),
                                (5, 0.0, "both_neutral", 0)])


if __name__ == "__main__":
    unittest.main()
