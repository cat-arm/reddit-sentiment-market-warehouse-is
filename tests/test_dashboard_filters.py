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
MULTI_PAGES = SOURCE_PAGES                                                    # and these take several tickers
TIME_KEYS = ["f_range", "f_gran"]
COMMUNITIES = ["r/wallstreetbets", "r/stocks", "r/investing", "r/StockMarket", "r/options", "r/CryptoCurrency"]
SOURCE_KEYS = ["f_src_" + c for c in COMMUNITIES] + ["f_type_Post", "f_type_Comment"]
GROUP_KEYS = ["f_group_stock_etf", "f_group_futures", "f_group_crypto"]
PAGES = ["app.py", "pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", "pages/3_Price_and_Return.py",
         "pages/4_Market_and_Sentiment.py", "pages/5_Ranking_and_Signals.py", "pages/6_Hot_Events.py"]


def expected_keys(page):
    """Sidebar order: time (DimTime) first, then source (DimSource), then asset (DimTicker)."""
    asset = GROUP_KEYS + (["f_tickers"] if page in MULTI_PAGES else ["f_ticker"])
    return TIME_KEYS + (SOURCE_KEYS if page in SOURCE_PAGES else []) + asset


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
            self.assertFalse(at.sidebar.checkbox(key="f_group_crypto").value, page)
            self.assertTrue(at.sidebar.checkbox(key="f_group_stock_etf").value, page)
            if page not in MULTI_PAGES:
                self.assertEqual(at.sidebar.selectbox(key="f_ticker").value, "QQQ", page)
            self.assertEqual(at.sidebar.selectbox(key="f_gran").value, "รายเดือน", page)
            self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value),
                             (dt.date(2026, 8, 3), dt.date(2026, 8, 9)), page)

    def test_every_source_box_starts_ticked_and_changes_the_numbers(self):
        for page in SOURCE_PAGES:
            at = self.run_page(page)
            for key in SOURCE_KEYS:
                self.assertTrue(at.sidebar.checkbox(key=key).value, "%s %s" % (page, key))
            full = at.metric[0].value
            at.sidebar.checkbox(key="f_src_r/wallstreetbets").set_value(False).run()
            self.assertNotEqual(at.metric[0].value, full, page + " (community off)")
            smaller = at.metric[0].value
            at.sidebar.checkbox(key="f_type_Post").set_value(False).run()
            self.assertNotEqual(at.metric[0].value, smaller, page + " (posts off)")
            self.assertEqual(len(at.exception), 0, page)

    def test_several_tickers_and_classes_change_the_numbers(self):
        """Pages 1-2: nothing chosen = every ticker; choosing tickers or unticking a class narrows the numbers."""
        for page in SOURCE_PAGES:
            at = self.run_page(page)
            full = at.metric[0].value
            at.multiselect(key="f_tickers").set_value(["TSLA", "NVDA"]).run()
            two = at.metric[0].value
            self.assertNotEqual(two, full, page)
            at.multiselect(key="f_tickers").set_value(["TSLA", "NVDA", "BTC-USD"]).run()
            self.assertNotEqual(at.metric[0].value, two, page)
            at.sidebar.checkbox(key="f_group_crypto").set_value(False).run()          # BTC-USD leaves with its class
            self.assertEqual(at.session_state["f_tickers"], ["TSLA", "NVDA"], page)
            self.assertEqual(at.metric[0].value, two, page)
            self.assertEqual(len(at.exception), 0, page)

    def test_total_volume_page_shows_all_texts_unless_tickers_are_chosen(self):
        at = self.run_page("pages/1_Reddit_Volume.py")
        self.assertEqual(at.metric[0].label, "Reddit Volume รวม")
        self.assertEqual(len(at.info), 0)
        at.multiselect(key="f_tickers").set_value(["SPY"]).run()
        self.assertEqual(at.metric[0].label, "Ticker Mention Count รวม")
        self.assertEqual(len(at.info), 1)                            # the page says what it now counts

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

    def test_several_tickers_chart_survives_lines_and_bars(self):
        at = self.run_page("pages/2_Ticker_Mentions.py")
        at.multiselect(key="f_tickers").set_value(["TSLA", "NVDA", "SPY"]).run()
        self.assertEqual(len(at.exception), 0)
        at.radio(key="ck_m_count").set_value("แท่ง").run()             # stacked bars, one colour per ticker
        self.assertEqual(len(at.exception), 0)
        at.multiselect(key="f_tickers").set_value(list(["TSLA", "NVDA", "SPY", "QQQ", "AAPL", "AMD", "AMC", "GME", "MSFT"])).run()
        self.assertEqual(len(at.exception), 0)                       # more than 8 tickers: one summed line

    def test_default_range_is_the_last_year_of_the_data(self):
        at = self.run_page("app.py")
        lo, hi = at.sidebar.date_input(key="f_range").value
        self.assertEqual(hi, dt.date(2026, 8, 31))                 # last day of Reddit data
        self.assertEqual((hi - lo).days, 365)

    def test_source_and_ticker_choices_hold_across_pages_that_do_not_draw_them(self):
        """The source filter and the multi-select are drawn on pages 1-2 only; a choice made there must come back."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "pages/1_Reddit_Volume.py"), default_timeout=90).run()
        at.sidebar.checkbox(key="f_src_r/options").set_value(False)
        at.sidebar.checkbox(key="f_type_Post").set_value(False)
        at.multiselect(key="f_tickers").set_value(["TSLA"])
        at = at.run()
        self.assertEqual(len(at.exception), 0)
        state = {"f_src_r/options": False, "f_type_Post": False, "f_tickers": ["TSLA"]}
        other = AppTest.from_file(str(ROOT / "dashboard" / "pages/3_Price_and_Return.py"), default_timeout=90)
        for key, value in state.items():
            other.session_state[key] = value
        other = other.run()                                         # page without the widgets: the values go to shadow keys
        self.assertFalse(other.session_state["_keep_f_src_r/options"])
        self.assertFalse(other.session_state["_keep_f_type_Post"])
        self.assertEqual(other.session_state["_keep_f_tickers"], ["TSLA"])

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
