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
NO_ASSET_PAGES = {"pages/1_Reddit_Volume.py"}                                # total volume has nothing to do with an asset
TIME_KEYS = ["f_year", "f_range", "f_gran"]
SOURCE_KEYS = ["f_comm", "f_type_Post", "f_type_Comment"]
ASSET_KEYS = ["f_group_stock_etf", "f_group_futures", "f_group_crypto", "f_ticker"]
PAGES = ["app.py", "pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", "pages/3_Price_and_Return.py",
         "pages/4_Market_and_Sentiment.py", "pages/5_Ranking_and_Signals.py", "pages/6_Hot_Events.py"]


def expected_keys(page):
    """Sidebar order: time (DimTime) first, then source (DimSource), then asset (DimTicker)."""
    return TIME_KEYS + (SOURCE_KEYS if page in SOURCE_PAGES else []) + ([] if page in NO_ASSET_PAGES else ASSET_KEYS)


def sidebar_order(at):
    """Keys of the sidebar widgets in the order they are drawn."""
    return [b.key for b in at.sidebar.children.values() if getattr(b, "key", None)]


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

    def test_sidebar_has_the_dimensions_in_order_on_every_page(self):
        for page in PAGES:
            order = sidebar_order(self.run_page(page))
            self.assertEqual(order, expected_keys(page), "%s sidebar order" % page)

    def test_a_choice_holds_on_every_page(self):
        chosen = dict(f_group_crypto=False, f_ticker="QQQ", f_range=(dt.date(2026, 8, 3), dt.date(2026, 8, 9)),
                      f_gran="รายเดือน")
        for page in PAGES:
            at = self.run_page(page, **chosen)
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (page, [e.value for e in at.exception]))
            if page not in NO_ASSET_PAGES:
                self.assertFalse(at.sidebar.checkbox(key="f_group_crypto").value, page)
                self.assertTrue(at.sidebar.checkbox(key="f_group_stock_etf").value, page)
                self.assertEqual(at.sidebar.selectbox(key="f_ticker").value, "QQQ", page)
            self.assertEqual(at.sidebar.selectbox(key="f_gran").value, "รายเดือน", page)
            self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value),
                             (dt.date(2026, 8, 3), dt.date(2026, 8, 9)), page)

    def test_time_hierarchy_sets_the_range_and_clears_below(self):
        """Year > Month > Week > Day: each choice narrows the date range of the page and picks a suitable chart level."""
        at = self.run_page("pages/1_Reddit_Volume.py")
        at.sidebar.selectbox(key="f_year").select(2026).run()
        self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value), (dt.date(2026, 1, 1), dt.date(2026, 8, 31)))
        self.assertEqual(at.sidebar.selectbox(key="f_gran").value, "รายเดือน")
        at.sidebar.selectbox(key="f_month").select(3).run()
        self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value), (dt.date(2026, 3, 1), dt.date(2026, 3, 31)))
        at.sidebar.selectbox(key="f_week").select(10).run()                         # ISO week 10: 2-8 March
        self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value), (dt.date(2026, 3, 2), dt.date(2026, 3, 8)))
        at.sidebar.selectbox(key="f_day").select_index(2).run()
        self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value), (dt.date(2026, 3, 3), dt.date(2026, 3, 3)))
        self.assertEqual(at.sidebar.selectbox(key="f_gran").value, "รายชั่วโมง")
        at.sidebar.selectbox(key="f_month").select(4).run()                         # changing a level clears the ones below
        self.assertIsNone(at.session_state["f_week"])
        self.assertEqual(len(at.exception), 0)
        at.sidebar.date_input(key="f_range").set_value((dt.date(2026, 1, 5), dt.date(2026, 1, 9))).run()
        self.assertIsNone(at.sidebar.selectbox(key="f_year").value)                 # a hand-made range clears the hierarchy
        at.sidebar.selectbox(key="f_year").select(2025).run()
        at.sidebar.selectbox(key="f_year").select_index(0).run()                    # "all" goes back to the default year
        self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value), (dt.date(2025, 8, 31), dt.date(2026, 8, 31)))

    def test_hierarchy_days_agree_with_dimtime(self):
        """The weeks and days offered by the sidebar are the DimTime weeks and days (Year / Month / Week / Day)."""
        import sqlite3
        from dashboard import common
        lo, hi = dt.date(2024, 9, 30), dt.date(2026, 8, 31)
        db = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
        try:
            for year, month in ((2024, 12), (2025, 1), (2025, 3), (2026, 8)):
                rows = db.execute("SELECT Week, Day FROM DimTime WHERE Year = ? AND Month = ? GROUP BY Week, Day ORDER BY Day",
                                  (year, month)).fetchall()
                rows = [(w, d) for w, d in rows if lo <= dt.date(year, month, d) <= hi]
                for week in sorted({w for w, _ in rows}):
                    expected = [dt.date(year, month, d) for w, d in rows if w == week]
                    self.assertEqual(common.week_days(year, month, week, lo, hi), expected, (year, month, week))
        finally:
            db.close()

    def test_every_chart_can_switch_to_bars(self):
        """The line / bar switch sits on each chart (not in the sidebar) and every chart survives being a bar chart."""
        for page in PAGES[1:5]:
            at = self.run_page(page)
            switches = [r for r in at.radio if r.key and r.key.startswith("ck_")]
            self.assertGreaterEqual(len(switches), 1, page)
            for switch in switches:
                at.radio(key=switch.key).set_value("แท่ง")
            at = at.run()
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (page, [e.value for e in at.exception]))
        self.assertEqual(len(list(self.run_page("pages/1_Reddit_Volume.py").sidebar.radio)), 0)

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
                for rng in [(dt.date(2026, 9, 20), dt.date(2026, 9, 25)), (dt.date(2024, 10, 1), dt.date(2026, 10, 1))]:
                    if level == "รายชั่วโมง" and rng[0].year == 2024:
                        continue                          # 2 years of hourly points: slow, and the user can still ask
                    at = self.run_page(page, f_gran=level, f_range=rng)
                    self.assertEqual(len(at.exception), 0, "%s / %s / %s raised %s" % (
                        page, level, rng, [e.value for e in at.exception]))

    def test_ticker_outside_chosen_groups_falls_back_to_a_valid_one(self):
        at = self.run_page("pages/3_Price_and_Return.py", f_group_stock_etf=False, f_group_futures=False, f_ticker="SPY")
        self.assertEqual(len(at.exception), 0)
        self.assertIn(at.sidebar.selectbox(key="f_ticker").value, ["BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD",
                                                                    "SOL-USD", "XRP-USD"])


if __name__ == "__main__":
    unittest.main()
