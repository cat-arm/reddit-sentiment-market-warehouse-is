"""Pure rules of the Market and Sentiment page (no database): recombining the per-community sums into the KPIs of the
proposal (table 15) and the majority-status filter."""

import unittest

import numpy as np
import pandas as pd

from dashboard import data

H = 3600 * 1000
COLUMNS = ["ticker", "hour_utc", "texts", "sentiment_sum", "pos_n", "neg_n", "neu_n"]


def sums(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


class SentimentFrameTests(unittest.TestCase):
    def setUp(self):
        # TSLA: hour 0: 4 texts (+0.6 pos, -0.4 neg, 0.02 neu, 0.0 neu); hour 2: 1 text (+0.2 pos); hour 1: none
        # AAPL: hour 0: 1 text (-0.5 neg)
        self.sent = sums([("TSLA", H, 4, 0.22, 1, 1, 2), ("TSLA", H + 7200, 1, 0.2, 1, 0, 0), ("AAPL", H, 1, -0.5, 0, 1, 0)])

    def frame(self, combined=False):
        return data.sentiment_frame(self.sent, H, H + 7200, combined=combined).set_index(["series", "hour_utc"])

    def test_kpis_by_hand(self):
        f = self.frame()
        hour0 = f.loc[("TSLA", H)]
        self.assertEqual(hour0.texts, 4)
        self.assertAlmostEqual(hour0.sentiment_mean, 0.22 / 4)
        self.assertAlmostEqual(hour0.pos_ratio + hour0.neg_ratio + hour0.neu_ratio, 1.0)
        self.assertEqual(hour0.majority, "neutral")                      # 2 neutral vs 1 pos vs 1 neg
        self.assertEqual(f.loc[("TSLA", H + 7200)].majority, "positive")

    def test_an_hour_without_text_is_null_not_zero(self):
        gap = self.frame().loc[("TSLA", H + 3600)]
        self.assertEqual(gap.texts, 0)
        self.assertTrue(np.isnan(gap.sentiment_mean) and np.isnan(gap.pos_ratio) and pd.isna(gap.majority))

    def test_momentum_needs_text_in_both_hours(self):
        f = self.frame()
        self.assertTrue(np.isnan(f.loc[("TSLA", H + 7200)].momentum))   # the previous hour has no text
        self.assertTrue(np.isnan(f.loc[("TSLA", H)].momentum))          # the hour before the range has none either

    def test_tie_goes_to_neutral_then_positive(self):
        tie = data.sentiment_frame(sums([("X", H, 2, 0.0, 1, 1, 0), ("Y", H, 2, 0.0, 0, 1, 1)]), H, H).set_index("series")
        self.assertEqual(tie.loc["X"].majority, "positive")             # positive 1, negative 1: positive wins the tie
        self.assertEqual(tie.loc["Y"].majority, "neutral")              # negative 1, neutral 1: neutral wins the tie

    def test_combined_sums_the_tickers(self):
        c = self.frame(combined=True).loc[("รวม", H)]
        self.assertEqual(c.texts, 5)
        self.assertAlmostEqual(c.sentiment_mean, (0.22 - 0.5) / 5)

    def test_empty_input(self):
        self.assertTrue(data.sentiment_frame(sums([]), H, H + 3600).empty)


class MajorityFilterTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({"close": [10.0, 11.0, 12.0], "volume": [5.0, 6.0, 7.0], "reddit_volume": [3, 4, 0],
                             "sentiment_mean": [0.2, -0.1, np.nan], "pos_ratio": [0.5, 0.2, np.nan], "neg_ratio": [0.2, 0.5, np.nan],
                             "neu_ratio": [0.3, 0.3, np.nan], "zscore": [1.0, 2.0, np.nan], "momentum": [0.1, -0.3, np.nan],
                             "majority_final_status": ["positive", "negative", None]})

    def test_unticked_hours_lose_every_reddit_measure_but_not_the_price(self):
        out = data.mask_majority(self.frame(), ("positive",))
        row = out.iloc[1]
        for col in data.REDDIT_MEASURES + ("majority_final_status",):
            self.assertTrue(pd.isna(row[col]), col)
        self.assertEqual((row.close, row.volume), (11.0, 6.0))          # market columns stay
        self.assertEqual(out.iloc[0].sentiment_mean, 0.2)               # ticked status stays
        self.assertEqual(out.iloc[2].reddit_volume, 0)                  # no text: untouched

    def test_all_statuses_ticked_changes_nothing(self):
        pd.testing.assert_frame_equal(data.mask_majority(self.frame(), ("positive", "negative", "neutral")), self.frame())

    def test_the_input_is_not_modified(self):
        frame = self.frame()
        data.mask_majority(frame, ())
        pd.testing.assert_frame_equal(frame, self.frame())


if __name__ == "__main__":
    unittest.main()
