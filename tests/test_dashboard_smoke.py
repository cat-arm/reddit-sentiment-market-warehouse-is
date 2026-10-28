"""Smoke + consistency tests of the Streamlit dashboard (TASKS Q4).

They need the real database output/reddit.sqlite3 (read-only) and are skipped when it is absent:
  * every page runs without an exception (streamlit.testing AppTest, no browser needed)
  * numbers shown by the data layer equal a direct SQL query on the database
  * the on-demand signal engine reproduces the pre-computed `signal_events` rows exactly
"""

import sqlite3
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "output" / "reddit.sqlite3"
PAGES = ["app.py", "pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", "pages/3_Price_and_Return.py",
         "pages/4_Market_and_Sentiment.py", "pages/5_Ranking_and_Signals.py", "pages/6_Hot_Events.py"]


@unittest.skipUnless(DB.exists(), "real database not available")
class DashboardTests(unittest.TestCase):
    def test_every_page_runs_without_exception(self):
        from streamlit.testing.v1 import AppTest
        for page in PAGES:
            started = time.time()
            at = AppTest.from_file(str(ROOT / "dashboard" / page), default_timeout=90).run()
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (page, [e.value for e in at.exception]))
            self.assertLess(time.time() - started, 60, page)

    def test_half_finished_date_selection_does_not_break_pages(self):
        """While the user clicks the range, the widget holds ONE date: pages must show that single day, not crash."""
        import datetime as dt
        from streamlit.testing.v1 import AppTest
        for page in PAGES:
            at = AppTest.from_file(str(ROOT / "dashboard" / page), default_timeout=90).run()
            at.session_state["f_range"] = (dt.date(2026, 8, 12),)
            at = at.run()
            self.assertEqual(len(at.exception), 0, "%s (one date) raised %s" % (page, [e.value for e in at.exception]))
            at.session_state["f_range"] = (dt.date(2026, 8, 1), dt.date(2026, 8, 12))
            at = at.run()
            self.assertEqual(len(at.exception), 0, "%s (range) raised %s" % (page, [e.value for e in at.exception]))

    def test_data_layer_matches_direct_sql(self):
        from dashboard import data
        db = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
        try:
            # last 10 days of REDDIT data (the price data runs a month longer than Reddit)
            hi = db.execute("SELECT MAX(hour_utc) FROM reddit_hourly WHERE variant='all' AND ticker='ALL'").fetchone()[0]
            start, end = hi - 86400 * 10, hi
            expected = db.execute("SELECT COUNT(*), SUM(reddit_volume) FROM reddit_hourly_features WHERE variant='all' "
                                  "AND ticker='BTC-USD' AND hour_utc BETWEEN ? AND ?", (start, end)).fetchone()
            got = data.volume_series(DB, "BTC-USD", start, end)
            self.assertGreater(expected[0], 0)                      # the check must not pass on an empty window
            self.assertEqual((len(got), int(got.reddit_volume.sum())), expected)
            close = db.execute("SELECT COUNT(*), ROUND(AVG(close), 6) FROM merged_hourly_panel WHERE scope='ticker' "
                               "AND variant='all' AND ticker='BTC-USD' AND hour_utc BETWEEN ? AND ?", (start, end)).fetchone()
            ov = data.overview_series(DB, "BTC-USD", start, end)
            self.assertEqual((len(ov), round(float(ov.close.mean()), 6)), close)
        finally:
            db.close()

    def test_hot_events_match_direct_sql(self):
        from dashboard import data
        db = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
        try:
            expected = db.execute("SELECT COUNT(*) FROM merged_hourly_panel WHERE scope='ticker' AND variant='all' AND has_reddit_data=1 "
                                  "AND reddit_volume >= 3 AND reddit_volume_zscore_24 > 2.0 AND ABS(sentiment_mean) >= 0.5").fetchone()[0]
        finally:
            db.close()
        got = data.hot_events(DB, 0, 2 ** 31, 2.0, 0.5, 3)
        self.assertGreater(expected, 0)
        self.assertEqual(len(got), expected)

    def test_source_filter_matches_direct_sql(self):
        """r/wallstreetbets + r/stocks comments only: totals and the mentions of one ticker equal a direct count on the texts."""
        from dashboard import data
        start, end = 1740787200, 1743379200                         # March 2025
        ids = (2, 4)                                                # DimSource: wallstreetbets Comment, stocks Comment
        db = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
        try:
            where = ("p.created_utc >= ? AND p.created_utc < ? AND p.content_type = 'comment' "
                     "AND p.subreddit IN ('wallstreetbets', 'stocks')")
            texts = db.execute("SELECT COUNT(*) FROM filtered_text p WHERE " + where, (start, end + 3600)).fetchone()[0]
            mentions = db.execute("SELECT COALESCE(SUM(m.mention_count), 0) FROM ticker_mentions m JOIN filtered_text p "
                                  "ON p.src_rowid = m.src_rowid WHERE m.ticker = 'TSLA' AND " + where,
                                  (start, end + 3600)).fetchone()[0]
        finally:
            db.close()
        self.assertGreater(texts, 0)
        self.assertEqual(int(data.total_volume_series(DB, start, end, ids).texts.sum()), texts)
        self.assertEqual(int(data.mention_series(DB, "TSLA", start, end, ids).mentions.sum()), mentions)
        split = data.ticker_volume_series(DB, "TSLA", start, end, ids)
        self.assertEqual(int(split.comments.sum()), mentions)
        self.assertEqual(int(split.posts.sum()), 0)                  # posts were filtered out
        self.assertEqual(int(data.mention_hour_source(DB, "TSLA", start, end, ids).value.sum()), mentions)
        ranking = data.mention_ranking(DB, start, end, ids)
        self.assertEqual(int(ranking[ranking.ticker == "TSLA"].mentions.iloc[0]), mentions)
        self.assertTrue(ranking.texts_about.isna().all())            # texts per source are not stored

    def test_recomputed_zscore_equals_the_stored_one(self):
        """The Z-score rule re-applied to the hourly totals gives the stored value, so the filtered view is consistent."""
        from dashboard import data
        start, end = 1740787200, 1743379200
        stored = data.total_volume_series(DB, start, end)[["hour_utc", "zscore"]]
        back = data._read(DB, "SELECT CAST(strftime('%s', t.ts_utc) AS INTEGER) AS hour_utc, SUM(v.texts) AS n "
                              "FROM reddit_volume_hourly v JOIN DimTime t USING (TimeID) WHERE CAST(strftime('%s', t.ts_utc) "
                              "AS INTEGER) BETWEEN ? AND ? GROUP BY t.ts_utc", (start - 86400, end))
        own = data._prior24_zscore(back.hour_utc, back.n.to_numpy(float), start, end)
        both = stored.merge(own, on="hour_utc", suffixes=("_stored", "_own"))
        self.assertGreater(len(both), 700)
        self.assertLess(float((both.zscore_stored - both.zscore_own).abs().max()), 1e-9)

    def test_drill_down_walks_every_level_on_both_pages(self):
        from streamlit.testing.v1 import AppTest
        for page, key in (("pages/1_Reddit_Volume.py", "v_time"), ("pages/2_Ticker_Mentions.py", "m_time")):
            at = AppTest.from_file(str(ROOT / "dashboard" / page), default_timeout=120).run()
            for level in range(4):
                at.selectbox(key="%s_pick_%d" % (key, level)).select_index(0).run()
                self.assertEqual(len(at.exception), 0, "%s level %d: %s" % (page, level, [e.value for e in at.exception]))
            self.assertEqual(len(at.session_state[key + "_path"]), 4)               # year, month, week, day
            at.button(key=key + "_crumb_1").click().run()                           # back up to the year
            self.assertEqual(len(at.session_state[key + "_path"]), 1)

    def test_on_demand_signals_equal_stored_signals(self):
        from analysis import signals
        from dashboard import data
        db = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
        try:
            stored = db.execute("SELECT signal_type, signal_level, COUNT(*) FROM signal_events WHERE z_threshold=2.0 "
                                "AND s_threshold=0.3 GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        finally:
            db.close()
        started = time.time()
        found = signals.detect(data.signal_panel(DB), 2.0, 0.3)
        computed = [(t, l, int(n)) for (t, l), n in found.groupby(["signal_type", "signal_level"]).size().items()]
        self.assertEqual(sorted(computed), sorted(stored))
        self.assertLess(time.time() - started, 10)


if __name__ == "__main__":
    unittest.main()
