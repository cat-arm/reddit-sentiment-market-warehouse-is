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


class SentimentBucketsTests(unittest.TestCase):
    def frame(self, slope):
        rng = np.random.default_rng(0)
        s = np.linspace(-1, 1, 500)
        return pd.DataFrame({"sentiment_mean": s, "ret": slope * s + rng.normal(0, 0.01, 500)})

    def test_levels_follow_the_fixed_cuts(self):
        edge = [-0.31, -0.30, -0.06, -0.05, -0.049, 0.0, 0.049, 0.05, 0.30, 0.31, np.nan]
        lvl = data.sentiment_level(edge)
        self.assertEqual(list(lvl.iloc[:10]), [0, 1, 1, 1, 2, 2, 2, 3, 3, 4])    # -0.05 / +0.05 are not neutral (VADER edges)
        self.assertTrue(np.isnan(lvl.iloc[10]))

    def test_a_rising_relation_gives_rising_bars(self):
        g = data.sentiment_buckets(self.frame(1.0), "ret")
        self.assertEqual(list(g.bucket), [0, 1, 2, 3, 4])
        self.assertEqual(int(g.n.sum()), 500)
        self.assertTrue((g["mean"].diff().dropna() > 0).all())
        self.assertTrue((g.sent_mean.diff().dropna() > 0).all())
        self.assertTrue(((g.ci_lo < g["mean"]) & (g["mean"] < g.ci_hi)).all())

    def test_no_relation_gives_intervals_over_zero(self):
        g = data.sentiment_buckets(self.frame(0.0), "ret")
        self.assertTrue(((g.ci_lo < 0) & (g.ci_hi > 0)).all())

    def test_an_empty_level_stays_in_with_zero_samples(self):
        df = self.frame(1.0)
        df = df[df.sentiment_mean.abs() <= 0.30]                        # no very-negative / very-positive hours
        g = data.sentiment_buckets(df, "ret").set_index("bucket")
        self.assertEqual((g.loc[0, "n"], g.loc[4, "n"]), (0, 0))
        self.assertTrue(np.isnan(g.loc[0, "mean"]))

    def test_too_few_samples(self):
        self.assertTrue(data.sentiment_buckets(self.frame(1.0).head(30), "ret").empty)

    def test_missing_values_are_dropped(self):
        df = self.frame(1.0)
        df.loc[:99, "ret"] = np.nan
        self.assertEqual(int(data.sentiment_buckets(df, "ret").n.sum()), 400)


class TimingTests(unittest.TestCase):
    def prices(self, n=400, seed=0):
        rng = np.random.default_rng(seed)
        hours = np.arange(n) * 3600
        return pd.DataFrame({"ticker": "AAA", "hour_utc": hours, "log_return": rng.normal(0, 1, n)})

    def test_shifted_return_looks_back_and_forward(self):
        p = pd.DataFrame({"ticker": "A", "hour_utc": [0, 3600, 7200], "log_return": [1.0, 2.0, 3.0]})
        self.assertEqual(list(data.shifted_return(p, -1).fillna(-9)), [-9, 1.0, 2.0])
        self.assertEqual(list(data.shifted_return(p, 1).fillna(-9)), [2.0, 3.0, -9])
        self.assertEqual(list(data.shifted_return(p, 0)), [1.0, 2.0, 3.0])

    def test_past_return_sums_the_previous_hours_and_needs_all_of_them(self):
        p = pd.DataFrame({"ticker": "A", "hour_utc": [0, 3600, 7200, 14400], "log_return": [1.0, 2.0, 3.0, 4.0]})
        self.assertEqual(list(data.past_return(p, 2).fillna(-9)), [-9, -9, 3.0, -9])    # hour 14400: hour 10800 is missing

    def test_the_same_ticker_name_does_not_mix_tickers(self):
        p = pd.DataFrame({"ticker": ["A", "B"], "hour_utc": [0, 3600], "log_return": [1.0, 2.0]})
        self.assertTrue(data.shifted_return(p, 1).isna().all())

    def test_lag_correlation_finds_the_lag_that_was_built_in(self):
        p = self.prices()
        # the sentiment follows the return of the hour before: price first, text after -> the peak is at lag -1
        p["sentiment_mean"] = data.shifted_return(p, -1) + np.random.default_rng(1).normal(0, 0.3, len(p))
        lc = data.lag_correlation(p).set_index("lag")
        self.assertEqual(lc.rho.idxmax(), -1)
        self.assertGreater(lc.loc[-1, "ci_lo"], 0.5)
        self.assertLess(abs(lc.loc[3, "rho"]), 0.2)
        self.assertTrue(((lc.ci_lo <= lc.rho) & (lc.rho <= lc.ci_hi)).all())

    def test_lag_correlation_with_nothing(self):
        p = self.prices(10)
        p["sentiment_mean"] = np.nan
        self.assertTrue(data.lag_correlation(p).rho.isna().all())

    def test_return_buckets_show_sentiment_following_the_price(self):
        p = self.prices(600)
        p["past"] = data.past_return(p, 1)
        p["sentiment_mean"] = p.past * 0.1
        g = data.return_buckets(p, "past")
        self.assertEqual(list(g.bucket), [0, 1, 2, 3, 4])
        self.assertTrue((g["mean"].diff().dropna() > 0).all())
        self.assertTrue((g.lo.iloc[1:].values >= g.hi.iloc[:-1].values).all())

    def test_return_buckets_too_few(self):
        p = self.prices(20)
        p["past"] = data.past_return(p, 1)
        p["sentiment_mean"] = 0.1
        self.assertTrue(data.return_buckets(p, "past").empty)


class SignalTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({"zscore": [2.0, 2.0, 1.0, 3.0, np.nan, 2.0], "sentiment_mean": [0.4, -0.5, 0.9, 0.1, 0.9, np.nan],
                             "ret": [1.0, -1.0, 5.0, 7.0, 9.0, 9.0]})

    def test_both_thresholds_must_be_met(self):
        hit = data.signal_hours(self.frame(), 1.5, 0.30)
        self.assertEqual(list(hit.index), [0, 1])                       # row 2: Z too low, 3: |s| too small, 4/5: NULL never qualifies
        self.assertEqual(list(hit.direction), ["positive", "negative"])

    def test_thresholds_change_the_hours(self):
        self.assertEqual(len(data.signal_hours(self.frame(), 0.5, 0.05)), 4)
        self.assertEqual(len(data.signal_hours(self.frame(), 5.0, 0.30)), 0)

    def test_the_threshold_edge_counts_for_sentiment_but_not_for_z(self):
        edge = pd.DataFrame({"zscore": [1.5, 1.6], "sentiment_mean": [0.30, 0.30]})
        self.assertEqual(list(data.signal_hours(edge, 1.5, 0.30).index), [1])    # Z must be above, |s| at least

    def test_return_by_signal_compares_with_all_hours(self):
        r = data.return_by_signal(self.frame(), "ret", 1.5, 0.30).set_index("group")
        self.assertEqual((r.loc["signal_positive", "n"], r.loc["signal_negative", "n"]), (1, 1))
        self.assertEqual(r.loc["signal_positive", "mean"], 1.0)
        self.assertEqual(r.loc["signal_negative", "mean"], -1.0)
        self.assertEqual(r.loc["all_hours", "n"], 5)                    # the 5 rows that have a Sentiment Score
        self.assertAlmostEqual(r.loc["all_hours", "mean"], (1 - 1 + 5 + 7 + 9) / 5)

    def test_an_empty_group_has_zero_samples(self):
        r = data.return_by_signal(self.frame(), "ret", 9.0, 0.30).set_index("group")
        self.assertEqual(r.loc["signal_positive", "n"], 0)
        self.assertTrue(np.isnan(r.loc["signal_positive", "mean"]))


class SignificantShareTests(unittest.TestCase):
    def test_rows_without_a_p_value_are_not_tests(self):
        df = pd.DataFrame({"p_value": [0.01, 0.2, np.nan, 0.05, 0.049]})
        self.assertEqual(data.significant_share(df), (2, 4))            # 0.05 itself is not below alpha; NaN is no test

    def test_another_column_and_alpha(self):
        df = pd.DataFrame({"p_bh": [0.01, 0.2], "p_value": [0.5, 0.5]})
        self.assertEqual(data.significant_share(df, "p_bh", 0.25), (2, 2))


class VoteSharesTests(unittest.TestCase):
    def frame(self):
        times = pd.date_range("2026-03-01", periods=6, freq="h", tz="UTC")
        return pd.DataFrame({"time": times, "majority_final_status": ["positive", "positive", "negative", None, "neutral", "positive"]})

    def test_every_hour_is_one_vote(self):
        v = data.vote_shares(self.frame())
        self.assertEqual(len(v), 5)                                    # the hour without text casts no vote
        self.assertTrue((v.share == 1.0).all())                        # one vote per hour: 100% for its status

    def test_a_day_counts_the_hours_by_status(self):
        v = data.vote_shares(self.frame(), {"rule": "1D"}).set_index("status")
        self.assertEqual(dict(v.hours), {"positive": 3, "negative": 1, "neutral": 1})
        self.assertAlmostEqual(v.loc["positive", "share"], 3 / 5)
        self.assertAlmostEqual(v.share.sum(), 1.0)

    def test_a_status_ticked_out_has_no_hours(self):
        masked = data.mask_majority(self.frame().assign(sentiment_mean=1.0), ("negative", "neutral"))
        v = data.vote_shares(masked, {"rule": "1D"})
        self.assertNotIn("positive", set(v.status))                    # its share is 0
        self.assertAlmostEqual(v.share.sum(), 1.0)                     # the rest is re-normalised

    def test_no_votes(self):
        self.assertTrue(data.vote_shares(self.frame().assign(majority_final_status=None)).empty)


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
