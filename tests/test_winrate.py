import unittest

import numpy as np
import pandas as pd

from analysis import results_store
from analysis.winrate import (BASELINE_PANEL, MIN_N, PRED_MAJORITY, PRED_RANDOM, PRED_SIGN, analyse_panel,
                              baseline_rates, evaluate, signals, wins_and_events)

META = dict(run_id="r", analysis="winrate", created_at="t", config_hash="h")


def frame(sent, ret, majority=None, ticker="AAA", group="crypto"):
    n = len(sent)
    df = pd.DataFrame({"ticker": ticker, "big_group": group, "sentiment_mean": sent,
                       "majority_final_status": majority or ["positive" if s > 0 else "negative" for s in sent],
                       "random_direction": np.where(np.arange(n) % 4 < 2, 1, -1)})     # + + - - (half right vs alternating)
    for h in ("1h", "2h", "3h", "6h", "12h"):
        df["future_return_" + h] = ret
    return df


class WinRateTests(unittest.TestCase):
    def test_hand_computed_wins_and_zero_exclusions(self):
        sig = pd.Series([1.0, -1.0, 1.0, np.nan, 1.0, -1.0])
        ret = pd.Series([0.5, -0.2, -0.1, 0.4, 0.0, np.nan])         # win, win, loss, no signal, zero return, no return
        self.assertEqual(wins_and_events(sig, ret), (2, 3))

    def test_zero_sentiment_has_no_direction(self):
        df = frame([0.0, 0.2, -0.3], [0.1, 0.1, 0.1], majority=["neutral", "positive", "negative"])
        s = signals(df, "panel_global")
        self.assertTrue(np.isnan(s[PRED_SIGN].iloc[0]))
        self.assertTrue(np.isnan(s[PRED_MAJORITY].iloc[0]))
        self.assertEqual(set(signals(df, BASELINE_PANEL)), {PRED_RANDOM})

    def test_guard_and_binomial(self):
        rate, p, status = evaluate(10, MIN_N - 1, 0.5)
        self.assertEqual(status, "insufficient_data")
        self.assertTrue(np.isnan(rate) and np.isnan(p))
        rate, p, status = evaluate(60, 100, 0.5)                     # 60/100 vs 0.5 -> p ~ 0.057
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(rate, 0.6)
        self.assertAlmostEqual(p, 0.0569, places=3)
        self.assertEqual(evaluate(50, 100, 0.5)[1], 1.0)

    def test_panel_uses_baseline_rate_and_perfect_signal(self):
        n = 80
        sent = np.where(np.arange(n) % 2 == 0, 0.4, -0.4)
        df = frame(sent, np.where(sent > 0, 1.0, -1.0))             # signal always right
        panels = {BASELINE_PANEL: df}
        base = baseline_rates(panels)
        rows = analyse_panel("panel_global", df, base, META)
        w = [r for r in rows if r["metric_name"] == "winrate" and r["predictor"] == PRED_SIGN and r["level"] == "all"]
        self.assertEqual(len(w), 5)
        self.assertTrue(all(r["metric_value"] == 1.0 and r["status"] == "ok" for r in w))
        self.assertTrue(all(r["p_value"] < 1e-6 for r in w))
        b = [r for r in rows if r["metric_name"] == "baseline_winrate" and r["level"] == "all"]
        self.assertTrue(all(abs(r["metric_value"] - 0.5) < 1e-9 for r in b))   # alternating random vs alternating returns
        results_store.add_bh([r for r in rows if r["metric_name"] == "winrate"])


if __name__ == "__main__":
    unittest.main()
