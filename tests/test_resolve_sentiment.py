import unittest

from etl.resolve_sentiment import RuleMatcher, resolve


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


if __name__ == "__main__":
    unittest.main()
