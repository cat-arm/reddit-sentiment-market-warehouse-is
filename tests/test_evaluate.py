import unittest

import numpy as np
import pandas as pd

from analysis.evaluate import (convergence, factor_importance, md_table, panel_ranking, prior_vs_current)

BASE = dict(run_id="r", ticker="ALL", target="x", p_value_bh=None, status="ok", config_hash="h", created_at="t")


def row(analysis, panel, level, group, horizon, metric, value, p=None, predictor="x", n=1000, status="ok"):
    return dict(BASE, analysis=analysis, panel_name=panel, level=level, big_group=group, horizon=horizon,
                metric_name=metric, metric_value=value, p_value=p, predictor=predictor, n_samples=n, status=status)


def cell(panel, horizon, rho, rate, base, auc, std=0.002, p1=0.001, p2=0.001, level="all", group="ALL"):
    pred = "random_direction" if panel == "panel_baseline" else "sentiment_mean"
    sign = "random_direction" if panel == "panel_baseline" else "sign(sentiment_mean)"
    return [row("correlation", panel, level, group, horizon, "spearman", rho, p1, predictor=pred),
            row("winrate", panel, level, group, horizon, "winrate", rate, p2, predictor=sign),
            row("winrate", panel, level, group, horizon, "baseline_winrate", base, None, predictor=sign),
            row("logistic", panel, level, group, horizon, "auc", auc, None, predictor="Level+Lag"),
            row("logistic", panel, level, group, horizon, "auc_std", std, None, predictor="Level+Lag")]


class EvaluateTests(unittest.TestCase):
    def test_convergence_rules(self):
        rows = (cell("panel_global", "1h", 0.05, 0.52, 0.50, 0.51)                       # all positive, significant
                + cell("panel_global", "2h", 0.05, 0.48, 0.50, 0.51)                     # win rate disagrees
                + cell("panel_global", "3h", -0.04, 0.47, 0.50, 0.49)                    # all negative
                + cell("panel_global", "6h", 0.05, 0.52, 0.50, 0.50004, std=0.01)        # AUC edge below its fold std
                + cell("panel_global", "12h", 0.05, 0.52, 0.50, 0.51, p2=0.4))           # win rate not significant
        c = convergence(pd.DataFrame(rows)).set_index("horizon")
        self.assertTrue(c.loc["1h", "weak_convergence"] and c.loc["1h", "strong_convergence"])
        self.assertEqual(c.loc["1h", "direction"], "positive")
        self.assertFalse(c.loc["2h", "weak_convergence"])
        self.assertEqual(c.loc["2h", "direction"], "none")
        self.assertTrue(c.loc["3h", "weak_convergence"] and c.loc["3h", "direction"] == "negative")
        self.assertTrue(c.loc["6h", "weak_convergence"] and not c.loc["6h", "strong_convergence"])
        self.assertTrue(c.loc["12h", "weak_convergence"] and not c.loc["12h", "strong_convergence"])

    def test_missing_method_means_no_convergence_not_zero(self):
        rows = [r for r in cell("panel_global", "1h", 0.05, 0.52, 0.50, 0.51) if r["analysis"] != "logistic"]
        c = convergence(pd.DataFrame(rows))
        self.assertFalse(c.weak_convergence.iloc[0])
        self.assertTrue(np.isnan(c.a3_edge.iloc[0]))                                     # NaN, not 0

    def test_baseline_uses_its_random_columns_and_ranking(self):
        rows = cell("panel_baseline", "1h", 0.001, 0.501, 0.500, 0.5002) + cell("panel_global", "1h", 0.05, 0.52, 0.50, 0.51)
        c = convergence(pd.DataFrame(rows))
        self.assertEqual(set(c.panel_name), {"panel_baseline", "panel_global"})
        rank = panel_ranking(c)
        self.assertEqual(rank.iloc[0].panel_name, "panel_global")                        # larger |edge| ranks first

    def test_prior_vs_current_and_importance(self):
        rows = []
        for pred, v in (("sentiment_mean", 0.01), ("sentiment_lag_1h", -0.03), ("sentiment_momentum_1h", 0.002),
                        ("reddit_volume_zscore_24", 0.005)):
            rows.append(row("correlation", "panel_global", "all", "ALL", "1h", "spearman", v, predictor=pred))
        p = prior_vs_current(pd.DataFrame(rows)).iloc[0]
        self.assertEqual(p.strongest_predictor, "sentiment_lag_1h")
        self.assertTrue(p.lag_beats_current)
        imp = factor_importance(pd.DataFrame([
            row("logistic", "panel_global", "all", "ALL", "1h", "group_importance:Level", 0.2),
            row("logistic", "panel_global", "all", "ALL", "2h", "group_importance:Level", 0.4),
            row("logistic", "panel_global", "all", "ALL", "1h", "group_importance:Lag", 0.1)]))
        self.assertAlmostEqual(imp.set_index("group_name").loc["Level", "mean_abs_coef"], 0.3)

    def test_md_table(self):
        text = md_table(pd.DataFrame({"a": [1.0, np.nan], "b": ["x", "y"]}))
        self.assertEqual(text.splitlines()[0], "| a | b |")
        self.assertIn("|  | y |", text)


if __name__ == "__main__":
    unittest.main()
