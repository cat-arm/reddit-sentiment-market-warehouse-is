"""analysis/hot_events.py: the score, the level, and the forward check never uses what happened after the hour."""
import sys
import unittest
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import hot_events as he  # noqa: E402

H = 3600


def rows(**cols):
    base = {"reddit_volume_zscore_24": 0.0, "mention_rate": 0.0, "sentiment_mean": 0.0, "momentum": 0.0, "volume_zscore_24": 0.0,
            "normalized_atr": 0.0, "log_return": 0.0}
    n = len(next(iter(cols.values())))
    return pd.DataFrame({**{k: [v] * n for k, v in base.items()}, **cols})


class ScoreTests(unittest.TestCase):
    def test_six_kpis_each_with_a_threshold_and_an_explanation_and_no_weights(self):
        self.assertEqual([m for m, *_ in he.METRICS], ["rz", "mr", "ss", "tz", "na", "cr"])
        self.assertEqual(set(he.ABOUT), set(he.DEFAULT_RULES))
        self.assertTrue(all(isinstance(t, float) for t in he.DEFAULT_RULES.values()))        # kpi -> threshold only
        self.assertEqual(set(he.PRICE_KPIS) | set(he.REDDIT_KPIS), set(he.DEFAULT_RULES))

    def test_the_score_counts_the_kpis_above_their_threshold_and_missing_never_passes(self):
        df = rows(reddit_volume_zscore_24=[1.5, 1.6, np.nan], sentiment_mean=[-0.06, 0.0, 0.2])
        rules = {"rz": 1.5, "ss": 0.05}
        self.assertEqual(list(he.score(df, rules)), [1, 1, 1])  # z 1.5 is not > 1.5; |-0.06| > 0.05; NaN z never passes
        self.assertEqual(list(he.score(df.assign(sentiment_mean=0.5), rules)), [1, 2, 1])

    def test_the_size_of_a_signed_kpi_counts(self):
        df = rows(sentiment_mean=[-0.2, 0.2, 0.0], log_return=[-1.0, 1.0, 0.0])
        self.assertEqual(list(he.score(df, {"ss": 0.1, "cr": 0.5})), [2, 2, 0])

    def test_current_return_is_a_horizon_known_one_hour_later(self):
        self.assertEqual(he.target("now"), ("log_return", 1))
        self.assertEqual(he.target("6h"), ("future_return_6h", 6))

    def test_levels_follow_the_number_of_kpis_passed(self):
        self.assertEqual(list(he.level(pd.Series([0.0, 39.9, 40.0, 59.9, 60.0, 79.9, 80.0, 100.0]))), ["", "", "low", "low", "medium", "medium", "high", "high"])   # the default cuts: 40 / 60 / 80 %
        self.assertEqual(list(he.level(pd.Series([1, 2, 3]), {"low": 1, "medium": 2, "high": 3})), ["low", "medium", "high"])

    def test_the_score_as_a_percent_and_the_levels_of_the_percent(self):
        df = rows(reddit_volume_zscore_24=[0.0, 9.0, 9.0, 9.0], sentiment_mean=[0.0, 0.0, 0.5, 0.5], log_return=[0.0, 0.0, 0.0, 9.0])
        rules = {"rz": 1.5, "ss": 0.05, "cr": 0.7}                                              # three KPIs in use: 0, 1, 2 and 3 passed
        self.assertEqual([round(v) for v in he.score_pct(df, rules)], [0, 33, 67, 100])
        self.assertEqual(he.DEFAULT_CUTS_PCT, {"low": 40.0, "medium": 60.0, "high": 80.0})
        self.assertEqual(list(he.level(he.score_pct(df, rules), he.DEFAULT_CUTS_PCT)), ["", "", "medium", "high"])
        six = he.score_pct(rows(reddit_volume_zscore_24=[9.0] * 7, sentiment_mean=[0.5] * 7))   # 2 of 6 = 33 % is low, a lone KPI is not
        self.assertEqual(list(he.level(pd.Series([100.0 / 6, 200.0 / 6, 300.0 / 6, 400.0 / 6]), he.DEFAULT_CUTS_PCT)), ["", "", "low", "medium"])
        self.assertEqual(len(six), 7)

    def test_the_weights_total_100_and_the_score_is_the_weight_of_the_kpis_passed(self):
        self.assertAlmostEqual(sum(he.DEFAULT_WEIGHTS.values()), 100.0)
        self.assertEqual(set(he.DEFAULT_WEIGHTS), set(he.DEFAULT_RULES))
        df = rows(reddit_volume_zscore_24=[9.0, 0.0, 9.0], sentiment_mean=[0.0, 0.5, 0.5])
        rules, weights = {"rz": 1.5, "ss": 0.05}, {"rz": 70.0, "ss": 30.0}
        self.assertEqual([round(v, 1) for v in he.score_pct(df, rules, weights)], [70.0, 30.0, 100.0])
        self.assertEqual([round(v, 1) for v in he.score_pct(df, {"rz": 1.5}, weights)], [100.0, 0.0, 100.0])   # a KPI that is not used leaves the total: 70 of 70
        worst = {n: min(sum(c) for c in combinations(he.DEFAULT_WEIGHTS.values(), n)) for n in (3, 4, 5)}
        best = {n: max(sum(c) for c in combinations(he.DEFAULT_WEIGHTS.values(), n)) for n in (2, 3, 4)}
        for n, lv, below in ((3, "low", 2), (4, "medium", 3), (5, "high", 4)):
            self.assertGreaterEqual(worst[n], he.DEFAULT_CUTS_PCT[lv])                      # n KPIs always reach the level ...
            self.assertLess(best[below], he.DEFAULT_CUTS_PCT[lv])                            # ... and the next count below never does


class LearnDefaultsTests(unittest.TestCase):
    def test_thresholds_are_learned_on_the_training_period_only(self):
        rng = np.random.default_rng(0)
        n = 2000
        hours = np.arange(n) * H
        z = rng.normal(size=n)
        df = rows(reddit_volume_zscore_24=z, sentiment_mean=rng.normal(scale=0.1, size=n)).assign(
            ticker="X", hour_utc=hours, future_return_1h=np.abs(z) + rng.normal(scale=0.5, size=n))
        split = int(hours[n // 2])
        out = he.learn_defaults(df, split=split).set_index("kpi")
        self.assertEqual(list(out.index), [m for m, *_ in he.METRICS])
        self.assertGreater(out.auc_train["rz"], out.auc_train["ss"])                 # the KPI that warns has the higher AUC
        late = df.assign(reddit_volume_zscore_24=np.where(df.hour_utc >= split, 99.0, df.reddit_volume_zscore_24))
        self.assertAlmostEqual(he.learn_defaults(late, split=split).set_index("kpi").threshold["rz"], out.threshold["rz"])   # later rows never used


class ForwardTests(unittest.TestCase):
    def test_normal_move_uses_only_rows_whose_horizon_had_ended(self):
        n = 400
        df = pd.DataFrame({"ticker": "X", "hour_utc": np.arange(n) * H, "future_return_6h": 1.0, "sentiment_mean": 0.1})
        df.loc[n - 1, "future_return_6h"] = 100.0                      # a huge move at the last row must not raise its own normal
        rel = he.relative_move(df, "6h", min_prior=10)
        self.assertAlmostEqual(rel.iloc[-1], 100.0)                    # normal = mean of rows with hour <= t - 6h = 1.0
        self.assertTrue(np.isnan(rel.iloc[0]))                         # no history yet

    def test_normal_move_is_per_asset(self):
        hours = np.arange(300) * H
        df = pd.concat([pd.DataFrame({"ticker": "A", "hour_utc": hours, "future_return_1h": 1.0}),
                        pd.DataFrame({"ticker": "B", "hour_utc": hours, "future_return_1h": 10.0})], ignore_index=True)
        rel = he.relative_move(df, "1h", min_prior=5).dropna()
        self.assertTrue(np.allclose(rel, 1.0))

    def test_auc(self):
        self.assertEqual(he.auc(pd.Series([1, 2, 3, 4.0]), pd.Series([0, 0, 1, 1.0])), 1.0)
        self.assertEqual(he.auc(pd.Series([1, 1, 1, 1.0]), pd.Series([0, 1, 0, 1.0])), 0.5)
        self.assertTrue(np.isnan(he.auc(pd.Series([1, 2.0]), pd.Series([1, 1.0]))))


if __name__ == "__main__":
    unittest.main()
