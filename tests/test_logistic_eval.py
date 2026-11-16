"""Tests of analysis/logistic_eval.py on synthetic panels (no database): the split, the tuning, the metrics, the bootstrap and the per-variable analysis."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import logistic_eval as le  # noqa: E402
from analysis.logistic import GROUPS  # noqa: E402


def synthetic(n_hours=2400, tickers=3, seed=0, signal="normalized_atr", weak="sentiment_mean"):
    """Panel rows (hour x ticker) with every feature of the groups; the target `log_return` depends strongly on one price variable and weakly on one Reddit variable."""
    rng = np.random.default_rng(seed)
    rows = []
    for t in range(tickers):
        frame = pd.DataFrame({c: rng.normal(size=n_hours) for cols in GROUPS.values() for c in cols})
        frame["hour_utc"] = np.arange(n_hours) * 3600
        frame["ticker"] = "T%d" % t
        frame["log_return"] = 1.2 * frame[signal] + 0.25 * frame[weak] + rng.normal(size=n_hours)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True).sort_values(["hour_utc", "ticker"], kind="stable").reset_index(drop=True)


class SplitTests(unittest.TestCase):
    def test_the_test_set_is_the_end_of_time_and_a_gap_separates_it(self):
        df = synthetic(n_hours=800, tickers=2)
        hours = df.hour_utc.to_numpy()
        train, test = le.time_split(hours)
        self.assertLess(hours[train].max(), hours[test].min())
        self.assertGreaterEqual((hours[test].min() - hours[train].max()) // 3600, le.GAP_HOURS)            # at least the gap of 12 hours between train and test
        self.assertAlmostEqual(len(np.unique(hours[test])) / len(np.unique(hours)), le.TEST_FRACTION, delta=0.01)
        self.assertEqual(len(np.intersect1d(train, test)), 0)

    def test_inner_folds_stay_inside_the_train_part_and_in_time_order(self):
        hours = np.repeat(np.arange(600) * 3600, 2)
        for tr, te in le.inner_folds(hours):
            self.assertLess(hours[tr].max(), hours[te].min())


class ModelTests(unittest.TestCase):
    def test_fast_auc_equals_sklearn(self):
        from sklearn.metrics import roc_auc_score
        rng = np.random.default_rng(1)
        y = rng.integers(0, 2, 500)
        p = rng.random(500).round(2)                                                  # ties on purpose
        self.assertAlmostEqual(le.fast_auc(y, p), roc_auc_score(y, p), places=10)

    def test_metrics_are_consistent(self):
        y = np.array([1, 1, 0, 0, 1, 0, 1, 0])
        p = np.array([0.9, 0.8, 0.2, 0.4, 0.3, 0.1, 0.7, 0.6])
        m = le.test_metrics(y, p)
        self.assertEqual((m["tn"], m["fp"], m["fn"], m["tp"]), (3, 1, 1, 3))
        self.assertAlmostEqual(m["accuracy"], 6 / 8)
        self.assertAlmostEqual(m["majority_accuracy"], 0.5)

    def test_l1_zeroes_noise_and_keeps_the_signal(self):
        rng = np.random.default_rng(2)
        x = rng.normal(size=(4000, 6))
        y = (1.0 * x[:, 0] + rng.normal(size=4000) > 0).astype(int)
        p, model, scaler = le.fit_predict("l1", 0.01, x, y, x)
        coef = model.coef_[0]
        self.assertNotEqual(coef[0], 0.0)
        self.assertGreaterEqual(int((coef[1:] == 0).sum()), 3)                         # most of the noise columns are exactly zero

    def test_the_scaler_sees_the_train_rows_only(self):
        rng = np.random.default_rng(3)
        x_train, x_test = rng.normal(size=(500, 2)), rng.normal(size=(100, 2)) + 50.0
        _, _, scaler = le.fit_predict("l2", 1.0, x_train, rng.integers(0, 2, 500), x_test)
        np.testing.assert_allclose(scaler.mean_, x_train.mean(axis=0))


class PanelAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = synthetic()
        cls.row, cls.context = le.analysis_panel(cls.df, "panel_global", "log_return", "log_return", boot=60)

    def test_the_panel_row(self):
        row = self.row
        self.assertEqual(row["status"], "ok")
        self.assertGreater(row["auc"], 0.7)                                              # a strong price signal
        self.assertTrue(row["better_than_random"])
        self.assertLess(row["auc_low"], row["auc"])
        self.assertGreater(row["auc_high"], row["auc"])
        self.assertIn(row["penalty"], ("l1", "l2"))
        self.assertGreater(row["n_train"], row["n_test"])
        self.assertGreater(row["price_only_auc"], row["reddit_only_auc"])                # the signal is on the price side

    def test_a_random_target_is_not_better_than_random(self):
        noise = self.df.assign(log_return=np.random.default_rng(4).normal(size=len(self.df)))
        row, _ = le.analysis_panel(noise, "panel_global", "log_return", "log_return", boot=60)
        self.assertFalse(row["better_than_random"])
        self.assertAlmostEqual(row["auc"], 0.5, delta=0.05)

    def test_variable_analysis_finds_the_signal_and_not_the_noise(self):
        rows = pd.DataFrame(le.analysis_features(self.context, {"panel": "panel_global", "horizon": "log_return"}, boot=60))
        variables = rows[rows.kind == "variable"].set_index("name")
        self.assertTrue(variables.loc["normalized_atr", "l1_selected"])
        self.assertGreater(variables.loc["normalized_atr", "drop_one_delta"], 0.05)
        self.assertGreater(variables.loc["normalized_atr", "drop_one_low"], 0.0)          # the interval of the real signal excludes 0
        noise = variables.loc["reddit_mention_rate"]
        self.assertLess(abs(noise.drop_one_delta), 0.02)
        self.assertLessEqual(noise.drop_one_low, 0.0 + 1e-9)                              # the interval of a noise column reaches 0
        groups = rows[rows.kind == "group"].set_index("name")
        self.assertGreater(groups.loc["Market", "drop_one_delta"], groups.loc["Volume", "drop_one_delta"])
        self.assertTrue(pd.isna(groups.loc["Market", "add_one_delta"]))                    # the price group is the base of the add-one gain

    def test_the_variables_are_chosen_on_a_validation_set_that_is_not_the_test_set(self):
        """Advisor 2026-11-17: train -> validation -> test.  The validation set is the end of the train part (a gap of 12 hours between them) and never touches the test set."""
        hours, train, test = self.context["hours"], self.context["train"], self.context["test"]
        sub, val = le.validation_split(hours, train)
        self.assertFalse(set(val) & set(test))
        self.assertFalse(set(sub) & set(val))
        self.assertTrue(set(sub) | set(val) <= set(train))
        self.assertGreaterEqual(hours[val].min() - hours[sub].max(), (le.GAP_HOURS + 1) * 3600)      # a gap between the sub-train and the validation set
        self.assertLess(hours[val].max(), hours[test].min())                                           # time order: sub-train < validation < test
        rows = le.analysis_features(self.context, {"panel": "panel_global", "horizon": "log_return"}, boot=40)
        self.assertEqual({r["n_val"] for r in rows}, {len(val)})                                      # the rows say which set they were measured on

    def test_the_cut_is_scored_on_the_test_set_with_the_variables_of_the_validation(self):
        rows = le.analysis_features(self.context, {"panel": "panel_global", "horizon": "log_return"}, boot=40)
        kept = le.kept_variables(rows)
        self.assertTrue(set(le.PRICE_FEATURES) <= set(kept))                                          # the price base is always kept
        by_name = {r["name"]: r for r in rows if r["kind"] == "variable"}
        for name in kept:
            self.assertTrue(by_name[name]["side"] == "price" or by_name[name]["add_one_low"] > 0)       # a Reddit variable is kept only when its VALIDATION interval is above 0
        cut = le.cut_on_test(self.context, rows, boot=40)
        self.assertEqual(cut["kept"], kept)
        self.assertLessEqual(cut["reduced_auc_low"], cut["reduced"]["auc"] + 1e-9)
        self.assertEqual(len(cut["full"]) , len(cut["reduced"]))                                       # the same metrics for both models


if __name__ == "__main__":
    unittest.main()
