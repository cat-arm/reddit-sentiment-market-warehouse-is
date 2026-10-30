"""Pure rules of the Market and Sentiment page (no database): recombining the per-community sums into the KPIs of the
proposal (table 15) and the majority-status filter."""

import unittest

import numpy as np
import pandas as pd

import altair as alt

from dashboard import common, data

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


class MaskThresholdsTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0], "reddit_volume": [5, 6, 7, 0], "sentiment_mean": [0.5, 0.1, -0.6, np.nan],
                             "pos_ratio": [0.6, 0.3, 0.1, np.nan], "neg_ratio": [0.2, 0.3, 0.7, np.nan], "neu_ratio": [0.2, 0.4, 0.2, np.nan],
                             "zscore": [2.5, 0.3, 3.0, -1.0], "momentum": [0.1, -0.2, 0.0, np.nan],
                             "majority_final_status": ["positive", "neutral", "negative", None]})

    def test_zero_zero_changes_nothing(self):
        pd.testing.assert_frame_equal(data.mask_thresholds(self.frame(), 0.0, 0.0), self.frame())

    def test_failing_hours_lose_every_reddit_measure_but_keep_the_price(self):
        out = data.mask_thresholds(self.frame(), 2.0, 0.30)
        self.assertEqual(list(out.sentiment_mean.notna()), [True, False, True, False])      # hour 1 has a low Z, hour 3 no text
        row = out.iloc[1]
        for col in data.REDDIT_MEASURES + ("majority_final_status",):
            self.assertTrue(pd.isna(row[col]), col)
        self.assertEqual(out.close.tolist(), [10.0, 11.0, 12.0, 13.0])

    def test_each_threshold_alone(self):
        self.assertEqual(list(data.threshold_mask(self.frame(), 2.0, 0.0)), [True, False, True, False])
        self.assertEqual(list(data.threshold_mask(self.frame(), 0.0, 0.3)), [True, False, True, False])

    def test_the_input_is_not_modified(self):
        frame = self.frame()
        data.mask_thresholds(frame, 2.0, 0.3)
        pd.testing.assert_frame_equal(frame, self.frame())


class PanelNameTests(unittest.TestCase):
    def test_every_variant_and_family_names_a_stored_panel(self):
        names = {data.panel_name(v, f) for v in data.PANEL_VARIANTS for f in data.PANEL_FAMILIES}
        self.assertEqual(names, set(data.STORED_PANELS))                 # nine panels, the baseline once
        self.assertEqual(data.panel_name("all", "Ticker"), "panel_Ticker")
        self.assertEqual(data.panel_name("spike", "global"), "panel_global_spike")
        self.assertEqual(data.panel_name("baseline", "global"), "panel_baseline")


class VariableLabelTests(unittest.TestCase):
    def test_every_variable_of_the_logistic_regression_has_a_thai_name_and_its_group(self):
        from analysis.logistic import BASELINE_GROUPS, GROUPS
        for groups in (GROUPS, BASELINE_GROUPS):
            for group, columns in groups.items():
                for column in columns:
                    self.assertIn(column, data.VARIABLES, column)
                    self.assertEqual(data.VARIABLES[column][1], group, column)                  # the group is the one of analysis.logistic
                    self.assertIn(group, data.VARIABLE_GROUPS)

    def test_the_label_names_the_column_the_thai_name_and_the_group(self):
        label = data.variable_label("neg_ratio")
        self.assertTrue(label.startswith("neg_ratio (") and "สัดส่วนความคิดเห็นเชิงลบ" in label and label.endswith("กลุ่ม Direction"))
        self.assertEqual(data.variable_label("something_new"), "something_new")                 # an unknown column keeps its name


class StatTableTests(unittest.TestCase):
    def samples(self, n=200, seed=0, slope=0.0):
        rng = np.random.default_rng(seed)
        s = rng.normal(0, 0.3, n)
        frame = {"ticker": ["AAA"] * n, "sentiment_mean": s, "zscore": rng.normal(0, 1, n)}
        for target, col in data.STAT_COLUMN.items():
            frame[col] = slope * s + rng.normal(0, 1, n)
        return pd.DataFrame(frame)

    def test_bh_adjust_by_hand(self):
        p = np.array([0.01, 0.04, 0.03, np.nan, 0.20])
        adj = data.bh_adjust(p)
        self.assertTrue(np.isnan(adj[3]))
        self.assertAlmostEqual(adj[0], 0.04)               # 0.01 * 4 tests / rank 1
        self.assertAlmostEqual(adj[2], 0.16 / 3)           # 0.03 and 0.04 both end at 0.0533 (the minimum from the top)
        self.assertAlmostEqual(adj[1], 0.16 / 3)
        self.assertAlmostEqual(adj[4], 0.20)
        self.assertTrue((adj[~np.isnan(adj)] >= p[~np.isnan(p)]).all())

    def test_a_real_relation_is_found_and_noise_is_not(self):
        real = data.stat_table(self.samples(slope=1.0)).set_index("target")
        self.assertLess(real.loc["1h", "spearman_p"], 1e-3)
        self.assertGreater(real.loc["1h", "spearman_rho"], 0.2)
        self.assertGreater(real.loc["1h", "winrate"], 55)
        self.assertLess(real.loc["1h", "win_p"], 0.1)
        noise = data.stat_table(self.samples(slope=0.0, seed=3)).set_index("target")
        self.assertGreater(noise.loc["1h", "spearman_p"], 0.01)

    def test_one_row_per_ticker_and_target_and_a_win_rate_also_for_the_current_return(self):
        out = data.stat_table(pd.concat([self.samples(), self.samples(seed=1).assign(ticker="BBB")]))
        self.assertEqual(len(out), 2 * len(data.STAT_TARGETS))
        self.assertEqual(list(out.columns), data.STAT_COLUMNS)
        current = out[out.target == "log_return"]
        self.assertTrue(current.winrate.notna().all() and current.spearman_rho.notna().all())      # same-hour co-movement, not a prediction
        same_hour = data.stat_table(self.samples(slope=1.0)).set_index("target").loc["log_return"]
        self.assertGreater(same_hour.winrate, 55)

    def test_too_few_pairs_give_nan_not_zero(self):
        out = data.stat_table(self.samples(n=20))
        self.assertTrue(out.spearman_rho.isna().all() and out.winrate.isna().all())
        self.assertTrue((out.n == 20).all())

    def test_a_null_return_is_dropped_and_zero_is_not_a_direction(self):
        s = self.samples(n=100, slope=1.0)
        s.loc[:49, "future_return_1h"] = np.nan                    # half the returns are missing
        s.loc[50:59, "future_return_1h"] = 0.0                      # ten returns of exactly 0
        row = data.stat_table(s).set_index("target").loc["1h"]
        self.assertEqual(row.n, 50)                                 # the NaN rows are gone (the zeros stay in the correlation)
        self.assertEqual(row.win_n, 40)                             # the zeros are not a direction


class PanelSamplesTests(unittest.TestCase):
    H = 3600

    def frames(self):
        hours = [i * self.H for i in range(6)]
        base = pd.DataFrame({"series": ["AAA"] * 6, "hour_utc": hours, "sentiment_mean": [0.5, -0.4, 0.02, 0.6, np.nan, 0.3],
                             "zscore": [2.0, 0.1, 3.0, 1.0, np.nan, 1.6], "majority": ["positive", "negative", "neutral", "positive", None, "positive"]})
        returns = pd.DataFrame({"ticker": ["AAA"] * 6 + ["BBB"] * 6, "hour_utc": hours * 2, "log_return": np.arange(12.0)})
        return base, returns

    def test_every_filter_removes_hours(self):
        base, returns = self.frames()
        every = data.panel_samples(base, None, returns, "Ticker", "all", ("positive", "negative", "neutral"), 0.0, 0.0)
        self.assertEqual(list(every.hour_utc), [0, 3600, 7200, 10800, 18000])               # the hour without text is gone, never 0
        self.assertEqual(len(data.panel_samples(base, None, returns, "Ticker", "all", ("positive",), 0.0, 0.0)), 3)    # majority status
        self.assertEqual(len(data.panel_samples(base, None, returns, "Ticker", "all", ("positive", "negative", "neutral"), 1.5, 0.0)), 3)  # Z > 1.5
        self.assertEqual(len(data.panel_samples(base, None, returns, "Ticker", "all", ("positive", "negative", "neutral"), 0.0, 0.3)), 4)  # |s| >= 0.3

    def test_the_spike_variant_needs_a_z_score_above_1_5(self):
        base, returns = self.frames()
        spike = data.panel_samples(base, None, returns, "Ticker", "spike", ("positive", "negative", "neutral"), 0.0, 0.0)
        self.assertEqual(list(spike.hour_utc), [0, 7200, 18000])

    def test_strong_uses_the_sentiment_of_the_strong_texts_and_the_z_score_of_all_texts(self):
        base, returns = self.frames()
        own = base.assign(sentiment_mean=[0.7, np.nan, np.nan, 0.8, np.nan, 0.5])           # the clear texts only: hours 1 and 2 have none
        strong = data.panel_samples(base, own, returns, "Ticker", "strong", ("positive", "negative", "neutral"), 0.0, 0.0)
        self.assertEqual(list(strong.hour_utc), [0, 10800, 18000])
        self.assertEqual(list(strong.sentiment_mean), [0.7, 0.8, 0.5])
        self.assertEqual(list(strong.zscore), [2.0, 1.0, 1.6])                              # Z-score of ALL the texts of the hour

    def test_global_gives_the_same_market_hour_to_every_ticker(self):
        base, returns = self.frames()
        market = base.assign(series="ALL")
        out = data.panel_samples(market, None, returns, "global", "all", ("positive", "negative", "neutral"), 0.0, 0.0)
        self.assertEqual(sorted(out.ticker.unique()), ["AAA", "BBB"])
        for _, part in out.groupby("ticker"):
            self.assertEqual(list(part.sentiment_mean), [0.5, -0.4, 0.02, 0.6, 0.3])

    def test_baseline_is_a_fixed_random_direction(self):
        base, returns = self.frames()
        market = base.assign(series="ALL")
        first = data.panel_samples(market, None, returns, "global", "baseline", ("positive", "negative", "neutral"), 0.0, 0.0)
        again = data.panel_samples(market, None, returns, "global", "baseline", ("positive", "negative", "neutral"), 0.0, 0.0)
        self.assertEqual(set(first.sentiment_mean), {-1.0, 1.0})
        self.assertEqual(list(first.sentiment_mean), list(again.sentiment_mean))            # reproducible


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
