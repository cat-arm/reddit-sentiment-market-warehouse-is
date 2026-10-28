"""The central sidebar filter must be the same on every page and must keep its value between pages (TASKS D0).

Streamlit forgets a widget that a page does not draw, so the rule is: every central widget is drawn on every page.
The test runs each page and compares the sidebar widgets (labels, order, values).  It needs the real database.
"""

import datetime as dt
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "output" / "reddit.sqlite3"
SOURCE_PAGES = {"pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py"}   # only these tables are split by source
SOURCE_KEYS = {"f_comm", "f_type_Post", "f_type_Comment"}
PAGES = ["app.py", "pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", "pages/3_Price_and_Return.py",
         "pages/4_Market_and_Sentiment.py", "pages/5_Ranking_and_Signals.py"]
CENTRAL_KEYS = ["f_group_stock_etf", "f_group_futures", "f_group_crypto", "f_ticker", "f_range", "f_gran", "f_chart"]


def sidebar_signature(at):
    """(kind, label, key) of every widget in the sidebar, in order."""
    out = []
    for kind in ("checkbox", "selectbox", "multiselect", "date_input", "radio"):
        for w in getattr(at.sidebar, kind):
            out.append((w.key, kind, w.label))
    return sorted(out)


@unittest.skipUnless(DB.exists(), "real database not available")
class FilterTests(unittest.TestCase):
    def run_page(self, page, **state):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / page), default_timeout=90)
        for key, value in state.items():
            at.session_state[key] = value
        return at.run()

    def test_sidebar_is_identical_on_every_page(self):
        signatures = {page: sidebar_signature(self.run_page(page)) for page in PAGES}
        reference = signatures["app.py"]
        self.assertEqual({k for k, _, _ in reference}, set(CENTRAL_KEYS))
        for page, signature in signatures.items():
            if page in SOURCE_PAGES:       # the same widgets plus the DimSource filter (communities, Post / Comment)
                self.assertEqual({k for k, _, _ in signature}, set(CENTRAL_KEYS) | SOURCE_KEYS, page)
                self.assertEqual([s for s in signature if s[0] in CENTRAL_KEYS], reference, page)
            else:
                self.assertEqual(signature, reference, "%s has a different sidebar" % page)

    def test_a_choice_holds_on_every_page(self):
        chosen = dict(f_group_crypto=False, f_ticker="QQQ", f_range=(dt.date(2026, 8, 3), dt.date(2026, 8, 9)),
                      f_gran="รายเดือน", f_chart="แท่ง")
        for page in PAGES:
            at = self.run_page(page, **chosen)
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (page, [e.value for e in at.exception]))
            self.assertFalse(at.sidebar.checkbox(key="f_group_crypto").value, page)
            self.assertTrue(at.sidebar.checkbox(key="f_group_stock_etf").value, page)
            self.assertEqual(at.sidebar.selectbox(key="f_ticker").value, "QQQ", page)
            self.assertEqual(at.sidebar.selectbox(key="f_gran").value, "รายเดือน", page)
            self.assertEqual(at.sidebar.radio(key="f_chart").value, "แท่ง", page)
            self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value),
                             (dt.date(2026, 8, 3), dt.date(2026, 8, 9)), page)

    def test_default_range_is_the_last_year_of_the_data(self):
        at = self.run_page("app.py")
        lo, hi = at.sidebar.date_input(key="f_range").value
        self.assertEqual(hi, dt.date(2026, 8, 31))                 # last day of Reddit data
        self.assertEqual((hi - lo).days, 365)

    def test_source_choice_holds_across_pages_that_do_not_draw_it(self):
        """The source filter is drawn on pages 1-2 only; a choice made there must come back when the user returns."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "pages/1_Reddit_Volume.py"), default_timeout=90).run()
        at.multiselect(key="f_comm").set_value(["r/stocks", "r/options"])
        at.checkbox(key="f_type_Post").set_value(False)
        at = at.run()
        self.assertEqual(len(at.exception), 0)
        state = dict(f_comm=["r/stocks", "r/options"], f_type_Post=False, f_type_Comment=True)
        other = AppTest.from_file(str(ROOT / "dashboard" / "pages/3_Price_and_Return.py"), default_timeout=90)
        for key, value in state.items():
            other.session_state[key] = value
        other = other.run()                                         # page without the widgets: the values go to shadow keys
        self.assertEqual(other.session_state["_keep_f_comm"], ["r/stocks", "r/options"])
        self.assertFalse(other.session_state["_keep_f_type_Post"])

    def test_every_time_level_works_on_every_page(self):
        """Hour / day / week / month / year (DimTime levels) on a short, a medium and the full range."""
        from dashboard import common
        for level in common.GRANULARITY:
            for page in PAGES[1:]:
                for kind in common.CHART_KINDS:
                    for rng in [(dt.date(2026, 9, 20), dt.date(2026, 9, 25)), (dt.date(2024, 10, 1), dt.date(2026, 10, 1))]:
                        if level == "รายชั่วโมง" and rng[0].year == 2024:
                            continue                      # 2 years of hourly points: slow, and the user can still ask
                        at = self.run_page(page, f_gran=level, f_chart=kind, f_range=rng)
                        self.assertEqual(len(at.exception), 0, "%s / %s / %s / %s raised %s" % (
                            page, level, kind, rng, [e.value for e in at.exception]))

    def test_ticker_outside_chosen_groups_falls_back_to_a_valid_one(self):
        at = self.run_page("pages/3_Price_and_Return.py", f_group_stock_etf=False, f_group_futures=False, f_ticker="SPY")
        self.assertEqual(len(at.exception), 0)
        self.assertIn(at.sidebar.selectbox(key="f_ticker").value, ["BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD",
                                                                    "SOL-USD", "XRP-USD"])


if __name__ == "__main__":
    unittest.main()
